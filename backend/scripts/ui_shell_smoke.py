"""Top navigation/profile checks shared by the isolated product acceptance runner."""
import asyncio
from urllib.parse import urlparse, parse_qs

from playwright.async_api import expect


async def assert_layout(page, description):
    # Route/drawer/popper transitions may still be finishing when input values
    # already match. Wait for the visible layout, not an arbitrary sleep.
    try:
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth + 1", timeout=5000)
    except Exception as error:
        overflow = await page.evaluate("""() => [...document.querySelectorAll('body *')]
            .filter(el => el.getBoundingClientRect().right > innerWidth + 1)
            .map(el => `${el.tagName}.${el.className}`).slice(0, 12)""")
        raise AssertionError(f"{description}: horizontal overflow: {overflow}") from error


async def check_shell(page, api, base_url, output, username, password):
    await page.goto(base_url + "/")
    await expect(page.get_by_role("heading", name="今天，从重要信号开始")).to_be_visible()
    await expect(page.locator(".workspace-grid")).to_be_visible()
    bar = await page.locator(".topbar").bounding_box()
    avatar = await page.locator(".profile-button").bounding_box()
    assert bar["y"] == 0 and bar["width"] == 1440 and avatar["x"] > 1300
    assert await page.locator(".main-content").evaluate("el => getComputedStyle(el).paddingLeft === '0px'")
    # Finish finite CSS transitions for documentation captures, not during the
    # interaction checks. Otherwise a correct menu can be captured half-faded.
    await page.screenshot(path=str(output / "workspace-top-navigation.png"), full_page=True, animations="disabled")

    research = page.get_by_role("button", name="研究分析", exact=True)
    await research.focus()
    await page.keyboard.press("Enter")
    await expect(page.get_by_role("menuitem", name="知识库", exact=True)).to_be_visible()
    # The categories must be adjacent columns, not another long vertical list.
    await page.wait_for_function("""() => {
        const menu = [...document.querySelectorAll('.mega-menu')].find(el => el.getBoundingClientRect().height > 0);
        if (!menu) return false;
        const boxes = [...menu.querySelectorAll('.nav-category')].map(el => el.getBoundingClientRect());
        return boxes.length === 3 && Math.max(...boxes.map(b => b.y)) - Math.min(...boxes.map(b => b.y)) < 2
            && boxes[0].x < boxes[1].x && boxes[1].x < boxes[2].x;
    }""")
    await page.screenshot(path=str(output / "navigation-categories.png"), full_page=True, animations="disabled")
    await page.keyboard.press("Escape")
    await expect(page.get_by_role("menuitem", name="知识库", exact=True)).not_to_be_visible()
    await expect(research).to_be_focused()
    await page.get_by_role("button", name="平台与工具", exact=True).click()
    await expect(page.get_by_role("menuitem", name="运行管理", exact=True)).to_have_count(0)
    await expect(page.get_by_role("menuitem", name="认知公地", exact=True)).to_be_visible()
    await assert_layout(page, "four-column platform menu")
    await page.keyboard.press("Escape")
    footer = page.locator(".app-footer")
    await expect(footer.get_by_role("link", name="CoderDongHuang 的 GitHub 主页")).to_have_attribute("href", "https://github.com/CoderDongHuang")
    await expect(footer).to_contain_text("汇聚公开信号，让信息成为洞察。")
    assert "在线" not in await footer.inner_text() and "离线" not in await footer.inner_text()

    search_requests = []
    def record_search(request):
        if urlparse(request.url).path == "/api/v1/search":
            search_requests.append(parse_qs(urlparse(request.url).query).get("q"))
    page.on("request", record_search)
    try:
        await page.get_by_label("全局搜索", exact=True).fill("acceptance-keyword")
        await page.get_by_label("全局搜索", exact=True).press("Enter")
        await expect(page.get_by_placeholder("搜索标题、正文、实体或自然语言问题")).to_have_value("acceptance-keyword")
        await expect(page.locator(".results")).to_contain_text("没有匹配内容")
        assert ["acceptance-keyword"] in search_requests
        await page.get_by_label("全局搜索", exact=True).fill("acceptance-second")
        await page.get_by_label("全局搜索", exact=True).press("Enter")
        await expect(page.get_by_placeholder("搜索标题、正文、实体或自然语言问题")).to_have_value("acceptance-second")
        await expect(page.locator(".results")).to_contain_text("没有匹配内容")
        assert ["acceptance-second"] in search_requests
    finally:
        page.remove_listener("request", record_search)

    await page.get_by_role("button", name="账户菜单").focus()
    await page.keyboard.press("Enter")
    await page.get_by_role("menuitem", name="个人中心", exact=True).click()
    await expect(page).to_have_url(base_url + "/profile")
    name_input = page.get_by_label("用户名", exact=True)
    email_input = page.get_by_label("邮箱", exact=True)
    await expect(name_input).to_have_value(username)
    writes = []
    def record_write(request):
        if urlparse(request.url).path == "/api/v1/auth/me" and request.method == "PUT":
            writes.append(request.post_data_json)
    page.on("request", record_write)
    try:
        await name_input.fill("not-saved")
        await page.get_by_role("button", name="撤销修改", exact=True).click()
        await expect(name_input).to_have_value(username)
        assert not writes

        # Real conflict with another isolated account, not a mocked success or 409.
        other = username + "-other"
        await api("POST", "/auth/register", {"username": other, "email": other + "@example.com", "password": password}, expected=201, auth=False)
        await email_input.fill(other + "@example.com")
        await page.get_by_role("button", name="保存修改", exact=True).click()
        await expect(page.locator(".profile-page").get_by_role("alert")).to_contain_text("已被使用")
        await expect(email_input).to_have_value(other + "@example.com")
        assert (await api("GET", "/auth/me"))["email"] == username + "@example.com"
        await page.get_by_role("button", name="撤销修改", exact=True).click()

        renamed = username + "-edit"
        await name_input.fill(renamed)
        async def offline_save(route):
            if route.request.method == "PUT": await route.abort("connectionfailed")
            else: await route.continue_()
        await page.route("**/api/v1/auth/me", offline_save)
        try:
            await page.get_by_role("button", name="保存修改", exact=True).click()
            await expect(page.locator(".profile-page").get_by_role("alert")).to_contain_text("输入已保留")
            await expect(name_input).to_have_value(renamed)
        finally:
            await page.unroute("**/api/v1/auth/me", offline_save)

        release = asyncio.Event()
        async def hold_save(route):
            if route.request.method == "PUT": await release.wait()
            await route.continue_()
        await page.route("**/api/v1/auth/me", hold_save)
        before = len(writes)
        try:
            await page.get_by_role("button", name="保存修改", exact=True).click()
            await expect(page.get_by_role("button", name="保存中…", exact=True)).to_be_disabled()
            await expect(name_input).to_be_disabled()
            release.set()
            await expect(page.locator(".profile-page").get_by_role("status")).to_have_text("个人资料已保存。")
            assert len(writes) == before + 1
        finally:
            release.set()
            await page.unroute("**/api/v1/auth/me", hold_save)
        assert (await api("GET", "/auth/me"))["username"] == renamed
        await page.reload()
        await expect(name_input).to_have_value(renamed)
        await expect(page.get_by_role("button", name="保存修改", exact=True)).to_be_disabled()
        await page.screenshot(path=str(output / "profile-desktop.png"), full_page=True, animations="disabled")
        await page.get_by_role("button", name="账户菜单").click()
        await expect(page.get_by_role("menuitem", name="退出登录")).to_be_visible()
        await page.screenshot(path=str(output / "avatar-menu.png"), full_page=True, animations="disabled")
        await page.keyboard.press("Escape")
        await expect(page.get_by_role("menuitem", name="退出登录")).not_to_be_visible()
        await expect(page.get_by_role("button", name="账户菜单")).to_be_focused()

        for width in [1024, 768, 390, 320]:
            await page.set_viewport_size({"width": width, "height": 844})
            await assert_layout(page, f"profile at {width}")
            await expect(page.get_by_role("button", name="账户菜单")).to_be_visible()
            await page.get_by_role("button", name="打开导航").click()
            mobile = page.get_by_role("navigation", name="移动导航")
            await expect(mobile.get_by_role("link", name="行动闭环", exact=True)).to_have_count(1)
            await expect(mobile.get_by_role("link", name="运行管理", exact=True)).to_have_count(0)
            await mobile.get_by_role("link", name="工作台", exact=True).click()
            await expect(page).to_have_url(base_url + "/")
            await expect(page.locator(".workspace-grid")).to_be_visible()
            await assert_layout(page, f"workspace at {width}")
            if width == 390:
                await page.screenshot(path=str(output / "workspace-mobile.png"), full_page=True, animations="disabled")
            await page.get_by_role("button", name="账户菜单").click()
            await page.get_by_role("menuitem", name="个人中心", exact=True).click()
            await expect(name_input).to_have_value(renamed)
        await page.screenshot(path=str(output / "profile-mobile.png"), full_page=True, animations="disabled")
        await page.set_viewport_size({"width": 1440, "height": 1000})
        return renamed
    finally:
        page.remove_listener("request", record_write)
