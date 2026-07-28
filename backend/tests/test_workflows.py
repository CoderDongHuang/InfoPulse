"""Focused tests for deterministic workflow behavior."""

import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.schemas.workflows import (
    HotItemRequest,
    InsightRequest,
    MouthpieceRequest,
    TimelineRequest,
)
from app.services.crawler.base import RawPost
from app.services.crawler import get_crawler
from app.services.workflows import fallback_insight


class WorkflowTests(unittest.TestCase):
    def test_crawler_registry_honors_global_switch(self):
        with patch("app.services.crawler.settings.CRAWLER_ENABLED", False):
            self.assertIsNone(get_crawler("bilibili"))

    def test_insight_request_deduplicates_platforms(self):
        payload = InsightRequest(keyword="测试话题", platforms=["weibo", "weibo", "bilibili"])
        self.assertEqual(payload.platforms, ["weibo", "bilibili"])

    def test_insight_request_requires_a_platform(self):
        with self.assertRaises(ValidationError):
            InsightRequest(keyword="测试话题", platforms=[])

    def test_mouthpiece_validates_intensity(self):
        payload = MouthpieceRequest(source_text="这是一个足够长的输入内容", intensity=88)
        self.assertEqual(payload.intensity, 88)

    def test_timeline_request_deduplicates_platforms(self):
        payload = TimelineRequest(topic="测试事件", platforms=["tieba", "tieba", "weibo"])
        self.assertEqual(payload.platforms, ["tieba", "weibo"])

    def test_hot_item_rejects_negative_heat(self):
        with self.assertRaises(ValidationError):
            HotItemRequest(title="测试热榜", heat=-1)

    def test_fallback_insight_keeps_source_links(self):
        post = RawPost(
            post_id="1",
            title="事件出现新进展",
            content="网友支持继续公开信息，并期待后续回应。",
            author="tester",
            publish_time="2026-07-20",
            url="https://example.com/source",
            platform="weibo",
        )
        result = fallback_insight("测试事件", [post], [{"platform": "weibo", "count": 1, "status": "ok"}])
        self.assertEqual(result["volume"], 1)
        self.assertEqual(result["representative_opinions"][0]["url"], post.url)
        self.assertEqual(sum(result["sentiment"].values()), 100)


if __name__ == "__main__":
    unittest.main()
