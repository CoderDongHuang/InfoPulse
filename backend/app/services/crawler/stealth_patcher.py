"""
InfoPulse — Stealth Patcher
=============================
Integrates playwright-stealth to hide automation fingerprints.
Used by the browser-rendered Tieba adapter.

Usage:
    from app.services.crawler.stealth_patcher import apply_stealth
    page = await browser.new_page()
    await apply_stealth(page)
"""

import logging

logger = logging.getLogger(__name__)


async def apply_stealth(page):
    """
    Apply playwright-stealth evasion to a Playwright page.
    Masks navigator.webdriver, chrome.runtime, and other bot signals.

    Requires: pip install playwright-stealth
    """
    try:
        from playwright_stealth import Stealth
        await Stealth().apply_stealth_async(page)
        logger.info("[Stealth] Anti-detection applied to page")
    except ImportError:
        logger.warning(
            "[Stealth] playwright-stealth not installed. "
            "Browser fingerprint will be detectable. "
            "Install: pip install playwright-stealth"
        )
