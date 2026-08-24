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
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
            if not self.headless:
                launch_args.append("--start-maximized")

            # Multi-tier launch strategy:
            # 1. Default Chromium (Playwright bundled or local ms-playwright)
            # 2. System Chrome
            # 3. System Microsoft Edge
            launch_strategies = [
                ("default_chromium", lambda: self._playwright.chromium.launch(
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args
                )),
                ("system_chrome", lambda: self._playwright.chromium.launch(
                    channel="chrome",
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args
                )),
                ("system_msedge", lambda: self._playwright.chromium.launch(
                    channel="msedge",
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args
                )),
            ]

            last_error = None
            for strategy_name, launcher in launch_strategies:
                try:
                    self._browser = launcher()
                    logger.info(f"Launched browser via strategy '{strategy_name}' (Headless: {self.headless}, Maximized: {not self.headless})")
                    return
                except Exception as e:
                    last_error = e
                    logger.warning(f"Browser launch strategy '{strategy_name}' failed: {e}")

            # Auto-install fallback if no browser was found
            logger.info("Attempting automated Playwright Chromium installation...")
            try:
                import subprocess
                from playwright._impl._driver import compute_driver_executable
                node_exec, cli_path = compute_driver_executable()
                res = subprocess.run([node_exec, cli_path, "install", "chromium"], capture_output=True, text=True, timeout=180)
                if res.returncode == 0:
                    logger.info("Playwright Chromium installed successfully. Retrying browser launch...")
                    self._browser = self._playwright.chromium.launch(
                        headless=self.headless,
                        slow_mo=self.slow_mo_ms,
                        args=launch_args
                    )
                    logger.info("Launched newly installed Playwright Chromium browser")
                    return
                else:
                    logger.warning(f"Playwright auto-install returned code {res.returncode}: {res.stderr}")
            except Exception as install_err:
                logger.error(f"Automated browser installation failed: {install_err}")

            if not self._browser:
                raise RuntimeError(f"Unable to launch any browser engine (Chromium/Chrome/Edge). Error: {last_error}")

    def new_context(self, trace_name: Optional[str] = None) -> BrowserContext:
        if not self._browser:
            self.start()

        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "locale": "en-GB",
            "timezone_id": "Europe/London",
            "extra_http_headers": {
                "Accept-Language": "en-GB,en;q=0.9",
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            }
        }
        if not self.headless:
            context_kwargs["no_viewport"] = True
        else:
            context_kwargs["viewport"] = {"width": 1920, "height": 1080}

        context = self._browser.new_context(**context_kwargs)
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
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
