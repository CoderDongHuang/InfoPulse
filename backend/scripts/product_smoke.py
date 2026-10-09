"""Exercise an isolated InfoPulse UI/API; writes fixtures, never use on real data."""
import argparse
import asyncio
import json
import uuid
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect


async def run(base_url, output, browser_channel=None):
    if urlparse(base_url).hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Acceptance writes are restricted to localhost")
    output.mkdir(parents=True, exist_ok=True)
    checks, errors, server_errors = [], [], []
    completed = False
    username = "smoke-" + uuid.uuid4().hex[:10]
    password = "Acceptance-test-123!"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000})
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("response", lambda response: server_errors.append(f"{response.status} {urlparse(response.url).path}") if response.status >= 500 else None)
        try:
            await page.goto(base_url + "/knowledge")
            await expect(page).to_have_url(__import__("re").compile(r"/auth"))
            await page.get_by_role("button", name="创建账号", exact=True).click()
            await page.get_by_placeholder("用户名或邮箱").fill(username)
            await page.get_by_placeholder("name@example.com").fill(username + "@example.com")
            await page.get_by_placeholder("至少 6 位").fill(password)
            await page.get_by_placeholder("再次输入密码").fill(password)
            await page.get_by_role("button", name="创建并进入").click()
            await expect(page).to_have_url(base_url + "/knowledge", timeout=15000)
            checks.append("guest redirect and UI registration")
            token = await page.evaluate("sessionStorage.getItem('infopulse_access_token')")
            headers = {"Authorization": "Bearer " + token}

            async def api(method, path, data=None, expected=200, auth=True):
                response = await context.request.fetch(base_url + "/api/v1" + path, method=method, headers=headers if auth else {}, data=data)
                if response.status != expected:
                    raise AssertionError(f"{method} {path}: {response.status} {await response.text()}")
                return await response.json() if expected != 204 else None

            me = await api("GET", "/auth/me")
            assert me["is_admin"] is False
            await api("POST", "/hot-search/explain", {"keyword": "fixture"}, expected=401, auth=False)
            checks.append("registration privilege and anonymous generation denial")
            await page.get_by_role("button", name="新建知识库").click()
            await page.locator(".el-message-box input").fill("Acceptance Knowledge")
            await page.locator(".el-message-box__btns .el-button--primary").click()
            await expect(page.get_by_role("heading", name="Acceptance Knowledge")).to_be_visible()
            # Exceed Nginx's default 1 MiB body limit without making indexing huge.
            fixture = b"# Acceptance\n\nInfoPulse durable knowledge acceptance evidence.\n" + b"\n" * (1024 * 1024 + 1024)
            await page.locator("input[type=file]").set_input_files({"name": "acceptance.md", "mimeType": "text/markdown", "buffer": fixture})
            await expect(page.locator(".doc .ready")).to_be_visible(timeout=30000)
            await page.get_by_placeholder("输入检索问题").fill("durable knowledge")
            await page.get_by_placeholder("输入检索问题").press("Enter")
            await expect(page.locator(".result")).to_contain_text("acceptance.md")
            await expect(page.locator(".el-message")).to_have_count(0, timeout=10000)
            await page.screenshot(path=str(output / "knowledge-desktop.png"), full_page=True)
            checks.append("UI create, upload, automatic index refresh and cited search")

            graph = {"nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}], "edges": [{"source": "start", "target": "end"}]}
            workflow = await api("POST", "/orchestration/workflows", {"name": "Acceptance workflow", "graph": graph}, expected=201)
            document = await api("POST", "/multimodal/collaboration/documents", {"resource_type": "workflow", "resource_id": workflow["id"]}, expected=201)
            ticket = await api("POST", "/multimodal/collaboration/documents/" + document["id"] + "/ticket")
            result = await page.evaluate("""async ({id, ticket}) => new Promise((resolve, reject) => {
              const socket = new WebSocket(`${location.origin.replace('http', 'ws')}/api/v1/multimodal/ws/collaboration/${id}?ticket=${ticket}`);
              const timer = setTimeout(() => { socket.close(); reject(new Error('WebSocket timeout')); }, 10000);
              socket.onmessage = event => {
                const value = JSON.parse(event.data);
                if (value.type === 'connected') socket.send(JSON.stringify({type: 'ping'}));
                if (value.type === 'pong') { clearTimeout(timer); socket.close(); resolve(value.type); }
              };
              socket.onerror = () => { clearTimeout(timer); reject(new Error('WebSocket error')); };
            })""", {"id": document["id"], "ticket": ticket["ticket"]})
            assert result == "pong"
            change = await api("POST", "/multimodal/collaboration/documents/" + document["id"] + "/changes", {"base_version": 1, "client_id": "smoke-client", "client_sequence": 1, "operations": [{"op": "set", "path": "/graph", "value": graph}]})
            assert change["version"] == 2
            detail = await api("GET", "/orchestration/workflows/" + workflow["id"])
            assert len(detail["versions"]) == 2 and detail["active_version_id"] == workflow["active_version_id"]
            checks.append("same-origin WebSocket ping and collaborative workflow draft persistence")

            for route in ["/", "/dashboard", "/discover", "/search", "/events", "/analysis", "/agent", "/reports", "/subscriptions", "/tasks", "/notifications", "/history", "/sources", "/orchestration", "/multimodal", "/global-intelligence", "/action-loop", "/commercial-operations", "/enterprise", "/developers", "/autonomy", "/trust-network", "/global-coordination", "/adaptive-os", "/provable-autonomy", "/planetary-resilience", "/cognitive-infrastructure", "/cognitive-commons", "/insight", "/mouthpiece", "/timeline", "/hot-search", "/watchlist", "/alerts", "/bi", "/help"]:
                await page.goto(base_url + route)
                await page.wait_for_load_state("networkidle", timeout=15000)
                assert await page.locator("#app").inner_text(), route
            checks.append("36 route shells loaded (errors asserted at end)")
            await page.goto(base_url + "/knowledge")
            await page.set_viewport_size({"width": 390, "height": 844})
            await expect(page.get_by_role("heading", name="知识库", exact=True)).to_be_visible()
            await expect(page.locator(".doc .ready")).to_be_visible()
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "mobile horizontal overflow"
            await page.screenshot(path=str(output / "knowledge-mobile.png"), full_page=True)
            await page.reload()
            await expect(page.get_by_role("heading", name="知识库", exact=True)).to_be_visible()
            checks.append("mobile knowledge layout and session restoration")
            await page.locator(".profile-button").click()
            await page.get_by_role("menuitem", name="退出登录").click()
            await expect(page).to_have_url(__import__("re").compile(r"/auth"))
            await api("GET", "/auth/me", expected=401)
            await page.get_by_placeholder("用户名或邮箱").fill(username)
            await page.get_by_placeholder("至少 6 位").fill(password)
            await page.get_by_role("button", name="进入工作台", exact=True).click()
            await expect(page).to_have_url(base_url + "/", timeout=15000)
            checks.append("UI logout revokes server session and UI login works")
            assert not errors, errors
            assert not server_errors, server_errors
            completed = True
        finally:
            if not completed:
                await page.screenshot(path=str(output / "failure.png"), full_page=True)
            (output / "result.json").write_text(json.dumps({"completed": completed, "checks": checks, "page_errors": errors, "server_errors": server_errors}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            await browser.close()
    print(json.dumps({"passed": len(checks), "checks": checks}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:15173")
    parser.add_argument("--output", type=Path, default=Path("../docs/audits/images/2026-10-09"))
    parser.add_argument("--browser-channel", help="Installed Chromium channel, e.g. msedge; defaults to bundled Chromium")
    args = parser.parse_args()
    asyncio.run(run(args.base_url.rstrip("/"), args.output, args.browser_channel))
