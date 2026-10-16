"""Exercise real public ingestion and a reader journey on a localhost server.

Does not insert articles, alter source configuration, or load fixture data.
Creates one reader account, a favorite and an in-app daily report task.
"""
import argparse
import asyncio
import json
from pathlib import Path
import secrets
from urllib.parse import quote, urlparse

from playwright.async_api import async_playwright, expect


async def run(base_url: str, output: Path):
    if urlparse(base_url).hostname not in {'localhost', '127.0.0.1'}:
        raise ValueError('Real-data smoke is restricted to localhost')
    output.mkdir(parents=True, exist_ok=True)
    checks, sources = [], []
    result = {'completed': False, 'checks': checks, 'sources': sources}
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel='msedge')
            context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
            page = await context.new_page()
            username = 'reader-' + secrets.token_hex(5)
            password = secrets.token_urlsafe(24)
            await page.goto(base_url + '/discover')
            await page.get_by_role('button', name='创建账号', exact=True).click()
            await page.get_by_placeholder('用户名或邮箱').fill(username)
            await page.get_by_placeholder('name@example.com').fill(username + '@example.com')
            await page.get_by_placeholder('至少 6 位').fill(password)
            await page.get_by_placeholder('再次输入密码').fill(password)
            await page.get_by_role('button', name='创建并进入').click()
            await expect(page).to_have_url(base_url + '/discover', timeout=15000)
            token = await page.evaluate("sessionStorage.getItem('infopulse_access_token')")

            async def api(method, path, data=None, expected=200):
                response = await context.request.fetch(base_url + '/api/v1' + path, method=method,
                    headers={'Authorization': 'Bearer ' + token}, data=data)
                if response.status != expected:
                    raise AssertionError(f'{method} {path}: {response.status} {await response.text()}')
                return await response.json() if expected != 204 else None

            checks.append('UI registration and authenticated real-data API')
            # Wait for the actual background worker, never seed articles or fake health.
            for _ in range(90):
                listing = await api('GET', '/sources')
                if all(s['last_sync_at'] is not None for s in listing) and all(s['health_status'] != 'unknown' for s in listing):
                    break
                await asyncio.sleep(2)
            scheduled_success = False
            for source in listing:
                runs = await api('GET', f"/sources/{source['id']}/sync-runs")
                scheduled_success |= any(r['trigger_type'] == 'scheduled' and r['status'] == 'succeeded' for r in runs)
                sources.append({'key': source['key'], 'health': source['health_status'],
                    'error': source['last_error'], 'runs': [{k: r[k] for k in ('status', 'trigger_type', 'fetched_count', 'created_count', 'updated_count', 'skipped_count', 'error_summary')} for r in runs[:2]]})
            succeeded = [s for s in sources if s['health'] == 'healthy' and s['runs'] and s['runs'][0]['fetched_count'] > 0]
            assert succeeded, 'No public source returned real articles; inspect source errors'
            assert scheduled_success, 'No successful scheduled run observed; automatic worker must run first'
            result['scheduled_success_observed'] = True
            checks.append('scheduled public ingestion persisted real upstream content')
            found = await api('GET', '/search?page_size=100')
            assert found['total'] > 0
            item = found['items'][0]
            assert item['canonical_url'].startswith('http') and item['title']
            result['sample'] = {'title': item['title'], 'url': item['canonical_url'], 'source': item['source']['name']}
            result['content_total'] = found['total']
            detail = await api('GET', '/contents/' + item['id'])
            assert detail['title'] == item['title']
            searched = await api('GET', '/search?q=' + quote(item['title']))
            assert any(x['id'] == item['id'] for x in searched['items'])
            checks.append('real content list, keyword search and detail agree')
            await page.reload()
            await expect(page.locator('.discover-list article').first).to_be_visible(timeout=15000)
            await page.locator('.discover-list article').first.get_by_role('button', name='收藏', exact=True).click()
            await expect(page.get_by_text('已收藏', exact=True)).to_be_visible()
            await page.screenshot(path=str(output / 'discover-real.png'), full_page=False)
            checks.append('UI shows public articles and favorite succeeds')
            workspace = await api('GET', '/workspace')
            assert workspace['recommendations'] and workspace['favorites']
            checks.append('workspace recommendations and favorites read persisted data')
            task = await api('POST', '/tasks', {'name': '公开来源验收日报', 'task_type': 'daily_report', 'config': {'channels': ['in_app']}, 'schedule': {'kind': 'interval', 'minutes': 1440}}, 201)
            run = await api('POST', f"/tasks/{task['id']}/run", expected=202)
            completed = None
            for _ in range(40):
                runs = await api('GET', f"/tasks/{task['id']}/runs")
                completed = next((r for r in runs if r['id'] == run['id'] and r['status'] == 'succeeded'), None)
                if completed: break
                await asyncio.sleep(2)
            assert completed and completed['output']['matched'] > 0, 'Daily report did not complete with public citations'
            notifications = await api('GET', '/notifications')
            assert any(n['payload'].get('report_id') == completed['output']['report_id'] for n in notifications)
            await api('POST', f"/tasks/{task['id']}/pause")
            checks.append('daily report task and in-app notification complete without a model key; smoke task paused')
            await page.goto(base_url + '/sources')
            await expect(page.get_by_role('heading', name='数据源中心', exact=True)).to_be_visible()
            await expect(page.get_by_role('button', name='立即同步', exact=True)).to_have_count(0)
            await expect(page.get_by_role('button', name='添加 RSS', exact=True)).to_have_count(0)
            await page.screenshot(path=str(output / 'sources-real.png'), full_page=True)
            checks.append('ordinary reader can inspect source status without admin controls')
            result['completed'] = True
            await browser.close()
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:15174')
    parser.add_argument('--output', type=Path, default=Path('../acceptance-artifacts/public-data'))
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.output))
