"""Private settings UI acceptance; fixture keys only, isolated product server only."""
from playwright.async_api import expect
from scripts.ui_shell_smoke import assert_layout


async def assert_field_alignment(page):
    for width in (1440, 1024, 768, 390, 320):
        await page.set_viewport_size({"width": width, "height": 1000})
        await assert_layout(page, f"private settings at {width}")
        for left, right in (("llm-model", "llm-key"), ("vision-model", "audio-model"),
                            ("smtp-host", "smtp-port"), ("smtp-user", "smtp-password")):
            # Read both rects in one frame: route transitions translate the whole
            # form, so sequential browser calls can compare different positions.
            a, b = await page.evaluate("""ids => ids.map(id => {
                const rect = document.getElementById(id).getBoundingClientRect();
                return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
            })""", [left, right])
            assert abs(a["height"] - b["height"]) < 1, (width, left, right, a, b)
            assert abs(a["width"] - b["width"]) < 1, (width, left, right, a, b)
            if width > 600:
                assert abs(a["y"] - b["y"]) < 1, (width, left, right, a, b)
            else:
                assert abs(a["x"] - b["x"]) < 1 and b["y"] > a["y"]
        boxes = await page.locator("form .settings-card").evaluate_all("""cards => cards.map(card => {
            const rect = card.getBoundingClientRect();
            return {x: rect.x, width: rect.width};
        })""")
        assert abs(boxes[0]["x"] - boxes[1]["x"]) < 1
        assert abs(boxes[0]["width"] - boxes[1]["width"]) < 1
    await page.set_viewport_size({"width": 1440, "height": 1000})


async def check_settings(page, api, base_url, output):
    await page.set_viewport_size({"width": 1440, "height": 1000})
    await page.goto(base_url + "/profile")
    await page.get_by_role("link", name="私人配置：模型与邮件 →").click()
    await expect(page).to_have_url(base_url + "/settings")
    await expect(page.get_by_role("heading", name="连接你的服务")).to_be_visible()
    await page.get_by_role("button", name="账户菜单").click()
    await expect(page.get_by_role("menuitem", name="私人配置", exact=True).locator(".el-icon > svg")).to_have_count(1)
    await page.keyboard.press("Escape")
    await expect(page.get_by_role("button", name="测试已保存的文本模型")).to_be_disabled()
    await assert_field_alignment(page)
    await page.get_by_role("button", name="千问 · 北京", exact=True).click()
    await expect(page.locator("#llm-base")).to_have_value("https://dashscope.aliyuncs.com/compatible-mode/v1")
    await expect(page.locator("#llm-model")).to_have_value("qwen-plus")
    await expect(page.locator("#vision-model")).to_have_value("qwen3-vl-plus")
    await expect(page.locator("#audio-model")).to_have_value("qwen3-asr-flash")
    await expect(page.locator("#audio-protocol")).to_have_value("qwen_asr")
    await assert_field_alignment(page)
    await page.get_by_role("button", name="DeepSeek · 文本", exact=True).click()
    await expect(page.locator("#vision-model")).to_have_value("")
    await expect(page.locator("#audio-model")).to_have_value("")
    await expect(page.locator("#audio-protocol")).to_have_value("openai")
    await expect(page.locator("#llm-base")).to_have_value("https://api.deepseek.com/v1")
    await expect(page.locator("#llm-model")).to_have_value("deepseek-chat")
    fixture_key = "ui-acceptance-fixture-not-a-real-key"
    await page.locator("#llm-key").fill(fixture_key)
    await page.locator("#vision-model").fill("fixture-vision")
    await page.locator("#smtp-host").fill("smtp.example.com")
    await page.locator("#smtp-password").fill("ui-acceptance-mail-fixture")
    await page.locator("#smtp-from").fill("reports@example.com")
    await page.get_by_role("button", name="保存私人配置", exact=True).click()
    await expect(page.locator(".form-notice")).to_contain_text("加密保存")
    await expect(page.locator("#llm-key")).to_have_value("")
    await expect(page.locator("#smtp-password")).to_have_value("")
    await expect(page.get_by_role("button", name="测试已保存的文本模型")).to_be_enabled()
    saved = await api("GET", "/settings/services")
    assert saved["llm_api_key_configured"] and saved["smtp_password_configured"]
    assert "llm_api_key" not in saved and "smtp_password" not in saved
    storage = await page.evaluate("JSON.stringify({local: {...localStorage}, session: {...sessionStorage}})")
    assert fixture_key not in storage and "ui-acceptance-mail-fixture" not in storage
    await page.reload()
    await expect(page.locator("#llm-key")).to_have_value("")
    await expect(page.locator("#llm-model")).to_have_value("deepseek-chat")

    async def offline(route):
        if route.request.method == "PUT":
            await route.abort("connectionfailed")
        else:
            await route.continue_()
    await page.route("**/api/v1/settings/services", offline)
    try:
        await page.locator("#llm-key").fill("replacement-fixture-key")
        await page.get_by_role("button", name="保存私人配置", exact=True).click()
        await expect(page.locator(".form-error")).to_contain_text("输入已保留")
        await expect(page.locator(".el-message--error")).to_have_count(0)
        await expect(page.locator("#llm-key")).to_have_value("replacement-fixture-key")
        await expect(page.get_by_role("button", name="保存私人配置", exact=True)).to_be_enabled()
    finally:
        await page.unroute("**/api/v1/settings/services", offline)
    await page.get_by_role("button", name="保存私人配置", exact=True).click()
    await expect(page.locator(".form-notice")).to_contain_text("加密保存")

    # Deliberate browser fault injection; never contact a provider with fixture keys.
    async def failed_test(route):
        await route.fulfill(status=400, json={"detail": "Connection test failed"})
    await page.route("**/api/v1/settings/services/test/llm", failed_test)
    try:
        await page.get_by_role("button", name="测试已保存的文本模型").click()
        await expect(page.locator(".form-error")).to_contain_text("连接测试未通过")
    finally:
        await page.unroute("**/api/v1/settings/services/test/llm", failed_test)

    # A second tab/write must not be silently overwritten by a stale page.
    saved = await api("GET", "/settings/services")
    await api("PUT", "/settings/services", {**{k: v for k, v in saved.items() if k in {"revision", "llm_api_base", "llm_model", "media_vision_model", "media_transcription_model", "smtp_host", "smtp_port", "smtp_username", "smtp_from"}}, "llm_model": "second-tab-model"})
    await page.locator("#llm-model").fill("stale-model")
    await page.get_by_role("button", name="保存私人配置", exact=True).click()
    await expect(page.locator(".form-error")).to_contain_text("其他标签页")
    await page.get_by_role("button", name="重新加载已保存配置").click()
    await expect(page.locator("#llm-model")).to_have_value("second-tab-model")
    await assert_field_alignment(page)
    await expect(page.locator(".el-message")).to_have_count(0, timeout=10000)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.screenshot(path=str(output / "private-settings-desktop.png"), full_page=True, animations="disabled")
    for width in (320, 390, 768, 1024):
        await page.set_viewport_size({"width": width, "height": 844})
        await assert_layout(page, f"private settings at {width}")
    await page.set_viewport_size({"width": 390, "height": 844})
    await page.evaluate("window.scrollTo(0, 0)")
    await page.screenshot(path=str(output / "private-settings-mobile.png"), full_page=True, animations="disabled")
    # Remove fixture credentials before the rest of the no-model product checks.
    await page.get_by_label("清除已保存的模型密钥（关闭模型调用）", exact=True).check()
    await page.get_by_label("清除已保存的 SMTP 密码", exact=True).check()
    await page.get_by_role("button", name="保存私人配置", exact=True).click()
    await expect(page.locator(".form-notice")).to_contain_text("加密保存")
    cleared = await api("GET", "/settings/services")
    assert not cleared["llm_api_key_configured"] and not cleared["smtp_password_configured"]
    await page.set_viewport_size({"width": 1440, "height": 1000})
