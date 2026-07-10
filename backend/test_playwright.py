"""
InfoPulse — Playwright Smoke Test
==================================
Run this script to verify that Playwright + Chromium work correctly
in the current environment (local or Docker container).

Usage:
    # Local (after pip install -r requirements.txt + playwright install chromium)
    python test_playwright.py

    # Docker
    docker build -t infopulse-test -f Dockerfile .
    docker run --rm infopulse-test python test_playwright.py

If successful, you'll see:
    [OK] Chromium launched successfully
    [OK] Page loaded: https://www.baidu.com
    [OK] Screenshot saved to /tmp/baidu_test.png
    [OK] All checks passed!
"""

import asyncio
import sys
import os


async def main():
    errors = []

    # --- Check 1: Import playwright ---
    try:
        from playwright.async_api import async_playwright
        print("[OK] playwright.async_api imported successfully")
    except ImportError as e:
        print(f"[FAIL] Cannot import playwright: {e}")
        print("       Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    # --- Check 2: Launch browser ---
    browser = None
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        print("[OK] Chromium launched successfully")
    except Exception as e:
        print(f"[FAIL] Cannot launch Chromium: {e}")
        print("       Check: playwright install chromium && playwright install-deps chromium")
        sys.exit(1)

    # --- Check 3: Load a page and screenshot ---
    try:
        page = await browser.new_page()
        await page.goto("https://www.baidu.com", timeout=30000)
        title = await page.title()
        print(f"[OK] Page loaded: {title}")

        screenshot_path = "/tmp/baidu_test.png"
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"[OK] Screenshot saved to {screenshot_path}")
    except Exception as e:
        print(f"[FAIL] Page load / screenshot failed: {e}")
        errors.append(str(e))

    # --- Cleanup ---
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

    # --- Report ---
    if errors:
        print(f"\n[FAIL] {len(errors)} check(s) failed. See details above.")
        sys.exit(1)
    else:
        print("\n[OK] All checks passed! Playwright is ready for InfoPulse.")


if __name__ == "__main__":
    asyncio.run(main())
