"""
InfoPulse — Playwright Browser Manager (Singleton + Circuit Breaker)
=====================================================================
Global single-instance Chromium browser with:
- Memory monitoring (restart if > BROWSER_RESTART_MB)
- Task-count-based restart (every N tasks)
- Zombie process cleanup
- Safe Chrome launch args for Docker

Used by the Tieba adapter, which requires a rendered browser page.
"""

import os
import asyncio
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BrowserManager:
    """
    Singleton browser manager.
    Exists so heavy crawlers don't each spin up their own Chromium.
    Includes circuit breaker: auto-restart on memory/usage thresholds.
    """

    _instance = None
    _browser = None
    _playwright = None
    _task_count = 0

    # Thresholds (configurable via env)
    _MEMORY_LIMIT_MB: int = 800
    _TASK_COUNT_RESET: int = 20

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._MEMORY_LIMIT_MB = settings.BROWSER_RESTART_MB
        if not hasattr(self, "_launch_lock"):
            self._launch_lock = asyncio.Lock()
            self._task_lock = asyncio.Lock()

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------
    async def get_browser(self):
        """Return a running Chromium browser instance (lazy init)."""
        async with self._launch_lock:
            if self._browser is None or not self._browser.is_connected():
                await self._launch_browser()
        return self._browser

    async def get_page(self):
        """Acquire the heavy-task slot and return a new browser page."""
        await self._task_lock.acquire()
        try:
            browser = await self.get_browser()
            return await browser.new_page()
        except Exception:
            self._task_lock.release()
            raise

    async def mark_task_done(self):
        """Call after each crawling task. May trigger a restart."""
        try:
            self._task_count += 1
            await self._check_health()
        finally:
            if self._task_lock.locked():
                self._task_lock.release()

    async def close(self):
        """Gracefully shutdown browser and playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._task_count = 0

    # ----------------------------------------------------------------
    # Internal
    # ----------------------------------------------------------------
    async def _launch_browser(self):
        """Launch Chromium with safe args for Docker/headless environments."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright not installed. "
                "Install: pip install playwright && playwright install chromium"
            )

        # Clean up any previous instance
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.CRAWLER_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self._task_count = 0
        logger.info("[BrowserManager] Chromium launched successfully")

    async def _check_health(self):
        """Circuit breaker: restart browser if memory/task thresholds exceeded."""
        # Task-count reset
        if self._task_count >= self._TASK_COUNT_RESET:
            logger.info(f"[BrowserManager] Task count {self._task_count} >= {self._TASK_COUNT_RESET}, restarting...")
            await self._restart_browser()
            return

        # Memory check
        try:
            import psutil
            process = psutil.Process(os.getpid())
            total_rss = process.memory_info().rss
            for child in process.children(recursive=True):
                try:
                    total_rss += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            mem_mb = total_rss / 1024 / 1024
            if mem_mb > self._MEMORY_LIMIT_MB:
                logger.warning(
                    f"[BrowserManager] Memory {mem_mb:.0f}MB > {self._MEMORY_LIMIT_MB}MB, restarting..."
                )
                await self._restart_browser()
        except ImportError:
            pass  # psutil not installed (e.g., Render demo)

    async def _restart_browser(self):
        """Force restart: close browser, kill zombie processes, launch fresh."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

        # Kill only Chromium processes spawned by this backend process.
        try:
            import psutil
            parent = psutil.Process(os.getpid())
            for proc in parent.children(recursive=True):
                name = (proc.name() or "").lower()
                if "chrom" in name:
                    try:
                        proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except ImportError:
            pass

        await asyncio.sleep(1)
        await self._launch_browser()
