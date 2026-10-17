"""Real key-free chat round trip plus explicitly isolated transport fault fixtures."""
import asyncio

from playwright.async_api import expect


async def check_agent(page, api, base_url, output):
    before = await api("GET", "/conversations")
    await page.goto(base_url + "/agent")
    await expect(page.get_by_role("heading", name="我是 InfoPulse，很高兴见到你！")).to_be_visible()
    await expect(page.locator(".composer")).to_be_visible()
    assert await page.locator(".composer").evaluate("e => parseFloat(getComputedStyle(e).borderRadius) >= 28")
    assert len(await api("GET", "/conversations")) == len(before), "opening chat must not create empty conversations"
    await page.screenshot(path=str(output / "agent-welcome-desktop.png"), full_page=True)
    prompt = page.get_by_role("textbox", name="输入问题", exact=True)
    send = page.get_by_role("button", name="发送消息", exact=True)
    await expect(send).to_be_disabled()
    await prompt.fill("first line")
    await prompt.press("Shift+Enter")
    await expect(prompt).to_have_value("first line\n")
    await prompt.dispatch_event("keydown", {"key": "Enter", "code": "Enter", "isComposing": True})
    assert len(await api("GET", "/conversations")) == len(before), "IME must not send"

    await page.locator(".knowledge-picker summary").click()
    await page.get_by_role("checkbox", name="Acceptance Knowledge").check()
    await page.locator(".knowledge-picker summary").click()
    await prompt.fill("durable knowledge")
    await prompt.press("Enter")
    answer = page.locator(".message.assistant:not(.streaming-message)").first
    await expect(answer).to_contain_text("acceptance.md", timeout=30000)
    await expect(page.get_by_role("button", name="停止生成", exact=True)).to_have_count(0)
    conversation_url = page.url
    cid = conversation_url.split("conversation=")[1].split("&")[0]
    persisted = await api("GET", "/conversations/" + cid)
    assert len(persisted["messages"]) == 2 and persisted["messages"][1]["citations"]
    await answer.locator(".citations button").first.click()
    await expect(page.get_by_role("dialog", name="回答引用")).to_contain_text("InfoPulse durable knowledge")
    await page.keyboard.press("Escape")
    await expect(page.get_by_role("dialog", name="回答引用")).not_to_be_visible()
    await answer.get_by_role("button", name="有帮助", exact=True).click()
    await expect(answer.get_by_role("button", name="有帮助", exact=True)).to_have_class("selected")
    await page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    await answer.get_by_role("button", name="复制回答", exact=True).click()
    await expect(page.get_by_text("已复制回答", exact=True)).to_be_visible()
    assert "acceptance.md" in await page.evaluate("navigator.clipboard.readText()")
    await expect(page.locator(".el-message")).to_have_count(0, timeout=10000)
    await page.screenshot(path=str(output / "agent-answer-desktop.png"), full_page=True)
    await page.reload()
    await expect(answer).to_contain_text("acceptance.md")

    # An aborted browser transport is intentionally injected, not a claimed server success.
    async def offline(route):
        await route.abort("connectionfailed")

    pattern = "**/api/v1/conversations/*/messages"
    await page.route(pattern, offline)
    try:
        await prompt.fill("offline test question")
        await send.click()
        await expect(page.locator(".message-list [role=alert]")).to_be_visible()
        await expect(prompt).to_have_value("offline test question")
        await expect(send).to_be_enabled()
    finally:
        await page.unroute(pattern, offline)
    await page.reload()
    await expect(answer).to_contain_text("acceptance.md")
    release, intercepted = asyncio.Event(), asyncio.Event()

    async def hold(route):
        intercepted.set()
        await release.wait()
        await route.abort("aborted")

    await page.route(pattern, hold)
    try:
        await prompt.fill("stop test question")
        await send.click()
        await asyncio.wait_for(intercepted.wait(), timeout=10)
        await page.get_by_role("button", name="停止生成", exact=True).click()
        await expect(page.get_by_text("已停止生成。可以继续发送新问题。")).to_be_visible()
        release.set()
        await expect(send).to_be_visible()
    finally:
        release.set()
        await page.unroute(pattern, hold)

    await page.get_by_role("button", name="新建会话", exact=True).click()
    await expect(page.get_by_role("heading", name="我是 InfoPulse，很高兴见到你！")).to_be_visible()
    new_id = page.url.split("conversation=")[1].split("&")[0]
    assert new_id != cid
    # Delete cancellation must leave the real persisted conversation intact.
    current_history = page.locator(".history-item.active")
    await current_history.get_by_role("button", name="删除会话：新会话", exact=True).click()
    await page.get_by_role("button", name="取消", exact=True).click()
    assert (await api("GET", "/conversations/" + new_id))["id"] == new_id
    await current_history.get_by_role("button", name="删除会话：新会话", exact=True).click()
    await page.locator(".el-message-box").get_by_role("button", name="删除", exact=True).click()
    await expect(page).to_have_url(base_url + "/agent")
    assert all(c["id"] != new_id for c in await api("GET", "/conversations"))
    history_search = page.get_by_role("textbox", name="搜索历史会话", exact=True)
    await history_search.fill("no-matching-conversation")
    await expect(page.get_by_text("没有匹配的会话", exact=True)).to_be_visible()
    await history_search.fill("durable")
    await expect(page.locator(".history-link")).to_have_count(1)
    await page.locator(".history-link").filter(has_text="durable knowledge").click()
    await history_search.fill("")
    await expect(answer).to_contain_text("acceptance.md")

    for width in [1024, 768, 390, 320]:
        await page.set_viewport_size({"width": width, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"chat overflow at {width}"
        await expect(prompt).to_be_in_viewport()
        if width < 760:
            await expect(page.locator(".history")).not_to_be_visible()
            toggle = page.get_by_role("button", name="打开历史会话", exact=True)
            await toggle.click()
            await expect(page.locator(".history")).to_be_visible()
            await page.keyboard.press("Escape")
            await expect(page.locator(".history")).not_to_be_visible()
            await expect(toggle).to_be_focused()
        if width == 390:
            await page.screenshot(path=str(output / "agent-answer-mobile.png"), full_page=True)
    await page.goto(base_url + "/agent")
    await expect(page.get_by_role("heading", name="我是 InfoPulse，很高兴见到你！")).to_be_visible()
    await page.screenshot(path=str(output / "agent-welcome-mobile.png"), full_page=True)
    await page.set_viewport_size({"width": 1440, "height": 1000})
