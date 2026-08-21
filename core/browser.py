import os
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
from config.settings import BROWSER_HEADLESS, BROWSER_SLOW_MO_MS, BROWSER_TIMEOUT_MS, ENABLE_PLAYWRIGHT_TRACE, ARTIFACTS_DIR
from core.logger import get_logger

logger = get_logger(step="BrowserManager")


class BrowserManager:
    """Manages Playwright browser and context lifecycles with diagnostic tracing."""

    def __init__(self, headless: Optional[bool] = None, slow_mo_ms: Optional[int] = None, trace: Optional[bool] = None):
        self.headless = BROWSER_HEADLESS if headless is None else headless
        self.slow_mo_ms = BROWSER_SLOW_MO_MS if slow_mo_ms is None else slow_mo_ms
        self.enable_trace = ENABLE_PLAYWRIGHT_TRACE if trace is None else trace
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    def start(self):
        if not self._playwright:
            self._playwright = sync_playwright().start()
            launch_args = ["--start-maximized"] if not self.headless else []
            try:
                # Try system Chrome first on Windows
                self._browser = self._playwright.chromium.launch(
                    channel="chrome",
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args
                )
                logger.info(f"Launched Chromium (Channel: Chrome, Headless: {self.headless}, Maximized: {not self.headless})")
            except Exception as e:
                logger.warning(f"System Chrome launch failed ({e}); falling back to default Chromium executable")
                self._browser = self._playwright.chromium.launch(
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args
                )

    def new_context(self, trace_name: Optional[str] = None) -> BrowserContext:
        if not self._browser:
            self.start()

        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "locale": "en-GB",
            "timezone_id": "Europe/London"
        }
        if not self.headless:
            context_kwargs["no_viewport"] = True
        else:
            context_kwargs["viewport"] = {"width": 1920, "height": 1080}

        context = self._browser.new_context(**context_kwargs)
        context.set_default_timeout(BROWSER_TIMEOUT_MS)

        if self.enable_trace:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        return context

    def new_page(self, context: Optional[BrowserContext] = None) -> tuple[BrowserContext, Page]:
        ctx = context or self.new_context()
        page = ctx.new_page()
        return ctx, page

    def stop_trace(self, context: BrowserContext, export_name: str) -> Optional[str]:
        if not self.enable_trace or not context:
            return None
        try:
            clean_name = "".join(c for c in export_name if c.isalnum() or c in ("-", "_"))
            trace_path = ARTIFACTS_DIR / f"{clean_name}_trace.zip"
            context.tracing.stop(path=str(trace_path))
            logger.info(f"Playwright trace saved to {trace_path.name}")
            return str(trace_path)
        except Exception as e:
            logger.warning(f"Failed to export Playwright trace: {e}")
            return None

    def close(self):
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            logger.info("Browser stopped")
        except Exception as e:
            logger.warning(f"Error during browser teardown: {e}")
