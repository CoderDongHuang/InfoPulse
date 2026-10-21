"""Rate limiting and official-feed failover without external network calls."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import unittest
from unittest.mock import patch

import httpx

from app.services.collectors.arxiv import ArxivCollector, _states
from app.services.collectors.http import UpstreamRateLimited, get_response, retry_after_seconds


ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>https://arxiv.org/abs/2610.12345v1</id><title>AI paper</title>
<summary>Research</summary><published>2026-10-20T01:00:00Z</published>
<author><name>Ada</name></author></entry></feed>'''
RSS = b'''<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>arXiv</title><item><title>AI paper</title>
<link>https://arxiv.org/abs/2610.12345v1</link><dc:creator>Ada, Lin</dc:creator>
<description>&lt;p&gt;Research &amp;amp; results&lt;/p&gt;</description>
<pubDate>Tue, 20 Oct 2026 01:00:00 GMT</pubDate><category>cs.AI</category>
</item><item><title>AI paper</title><link>https://arxiv.org/abs/2610.12345v1</link>
</item></channel></rss>'''


class UpstreamRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_429_does_not_rapidly_retry(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, headers={"Retry-After": "120"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(UpstreamRateLimited) as raised:
                await get_response(client, "https://export.arxiv.org/api/query")
        self.assertEqual(raised.exception.retry_after, 120)
        self.assertEqual(len(calls), 1)
        self.assertIn("限流", str(raised.exception))

    def test_retry_after_supports_dates_and_invalid_values(self):
        date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=120), usegmt=True)
        self.assertTrue(118 <= retry_after_seconds(date) <= 120)
        for value in (None, "invalid", "-1", "NaN", "inf"):
            self.assertEqual(retry_after_seconds(value), 60)
        self.assertEqual(retry_after_seconds("0"), 0)

    async def test_transient_5xx_still_retries(self):
        count = 0
        def handler(request):
            nonlocal count
            count += 1
            return httpx.Response(502 if count < 3 else 200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch('app.services.collectors.http.asyncio.sleep'):
                response = await get_response(client, "https://example.com/feed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(count, 3)


class ArxivResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = 1000.0
        self.delays = []
        async def sleep(seconds):
            self.delays.append(seconds)
            self.clock += seconds
        self.time_patch = patch('app.services.collectors.arxiv.monotonic', side_effect=lambda: self.clock)
        self.sleep_patch = patch('app.services.collectors.arxiv.asyncio.sleep', side_effect=sleep)
        self.time_patch.start()
        self.sleep_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.addCleanup(self.sleep_patch.stop)

    async def test_429_falls_back_to_official_rss_and_deduplicates(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, headers={"Retry-After": "600"}) if request.url.host == "export.arxiv.org" else httpx.Response(200, content=RSS)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            items = await ArxivCollector(client).collect(30)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].external_id, "2610.12345v1")
            self.assertEqual(items[0].content_type, "paper")
            self.assertEqual(items[0].author_name, "Ada, Lin")
            self.assertEqual(items[0].body, "Research & results")
            self.assertEqual(items[0].published_at.tzinfo, timezone.utc)
            self.assertEqual(calls[1].url, ArxivCollector.feed_url)
            self.assertGreaterEqual(sum(self.delays), 3)
            # A different batch size bypasses the cache, but not API cooldown.
            await ArxivCollector(client).collect(10)
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[-1].url.host, "rss.arxiv.org")
            self.clock += 601
            await ArxivCollector(client).collect(10)
            self.assertEqual(calls[-2].url.host, "export.arxiv.org")

    async def test_concurrent_collectors_share_fresh_cache_and_copy_items(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, content=ATOM)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            batches = await asyncio.gather(*(ArxivCollector(client).collect(30) for _ in range(5)))
            self.assertEqual(len(calls), 1)
            batches[0][0].title = "modified"
            self.assertEqual((await ArxivCollector(client).collect(30))[0].title, "AI paper")
            self.clock += 301
            await ArxivCollector(client).collect(30)
            self.assertEqual(len(calls), 2)

    async def test_expired_cache_is_not_returned_as_success(self):
        failing = False
        def handler(request):
            return httpx.Response(429) if failing else httpx.Response(200, content=ATOM)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await ArxivCollector(client).collect(30)
            failing = True
            self.clock += 301
            with self.assertRaisesRegex(RuntimeError, "官方 RSS.*限流"):
                await ArxivCollector(client).collect(30)
            self.assertGreater(_states[client].cooldowns[ArxivCollector.feed_url], self.clock)

    async def test_transport_failure_can_use_rss(self):
        def handler(request):
            if request.url.host == "export.arxiv.org":
                raise httpx.ConnectError("offline", request=request)
            return httpx.Response(200, content=RSS)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(len(await ArxivCollector(client).collect(1)), 1)

    async def test_invalid_upstream_payloads_do_not_report_success(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html/>"))) as client:
            with self.assertRaisesRegex(RuntimeError, "未返回有效订阅数据"):
                await ArxivCollector(client).collect(30)

    async def test_requests_with_different_limits_are_spaced(self):
        times = []
        def handler(request):
            times.append(self.clock)
            return httpx.Response(200, content=ATOM)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await ArxivCollector(client).collect(1)
            await ArxivCollector(client).collect(30)
        self.assertGreaterEqual(times[1] - times[0], 3)

    def test_rss_oai_guid_preserves_api_versioned_identity(self):
        rss = RSS.replace(b'<link>https://arxiv.org/abs/2610.12345v1</link>', b'<link>https://arxiv.org/abs/2610.12345</link><guid>oai:arXiv.org:2610.12345v1</guid>')
        self.assertEqual(ArxivCollector._parse_rss(rss, 30)[0].external_id, "2610.12345v1")
