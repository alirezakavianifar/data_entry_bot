import os
from typing import Optional, Dict, Any
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
from config.settings import (
    BROWSER_HEADLESS,
    BROWSER_SLOW_MO_MS,
    BROWSER_TIMEOUT_MS,
    ENABLE_PLAYWRIGHT_TRACE,
    ARTIFACTS_DIR,
    ENABLE_BROWSER_STEALTH,
    BROWSER_PROFILES_DIR,
    PROXY_SERVER,
    PROXY_USERNAME,
    PROXY_PASSWORD,
    PROXY_BYPASS
)
from core.logger import get_logger

logger = get_logger(step="BrowserManager")

STEALTH_EVASION_SCRIPT = """
(() => {
    // 1. Mask navigator.webdriver safely
    try {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        delete navigator.__proto__.webdriver;
    } catch (e) {}

    // 2. Mock authentic window.chrome runtime object
    try {
        if (!window.chrome) {
            window.chrome = {};
        }
        if (!window.chrome.runtime) {
            window.chrome.runtime = {
                OnInstalledReason: {
                    CHROME_UPDATE: "chrome_update",
                    INSTALL: "install",
                    SHARED_MODULE_UPDATE: "shared_module_update",
                    UPDATE: "update"
                },
                OnRestartRequiredReason: {
                    APP_UPDATE: "app_update",
                    OS_UPDATE: "os_update",
                    PERIODIC: "periodic"
                },
                PlatformArch: {
                    ARM: "arm",
                    ARM64: "arm64",
                    MIPS: "mips",
                    MIPS64: "mips64",
                    X86_32: "x86-32",
                    X86_64: "x86-64"
                },
                PlatformNaclArch: {
                    ARM: "arm",
                    MIPS: "mips",
                    MIPS64: "mips64",
                    X86_32: "x86-32",
                    X86_64: "x86-64"
                },
                PlatformOs: {
                    ANDROID: "android",
                    CROS: "cros",
                    LINUX: "linux",
                    MAC: "mac",
                    OPENBSD: "openbsd",
                    WIN: "win"
                },
                RequestUpdateCheckStatus: {
                    NO_UPDATE: "no_update",
                    THROTTLED: "throttled",
                    UPDATE_AVAILABLE: "update_available"
                }
            };
        }
        if (!window.chrome.app) {
            window.chrome.app = {
                isInstalled: false,
                InstallState: { DISABLED: "disabled", INSTALLED: "installed", NOT_INSTALLED: "not_installed" },
                RunningState: { CANNOT_RUN: "cannot_run", READY_TO_RUN: "ready_to_run", RUNNING: "running" }
            };
        }
    } catch (e) {}

    // 3. Mock authentic Navigator Hardware, Memory and Languages
    try {
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-GB', 'en-US', 'en'],
            configurable: true
        });
        Object.defineProperty(navigator, 'language', {
            get: () => 'en-GB',
            configurable: true
        });
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8,
            configurable: true
        });
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8,
            configurable: true
        });
        Object.defineProperty(navigator, 'maxTouchPoints', {
            get: () => 0,
            configurable: true
        });
    } catch (e) {}

    // 4. Safe Permissions query mocking (prevents Illegal Invocation error)
    try {
        if (window.navigator && window.navigator.permissions && window.navigator.permissions.query) {
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = function(parameters) {
                if (parameters && parameters.name === 'notifications') {
                    const permState = (typeof Notification !== 'undefined' && Notification.permission === 'denied') ? 'denied' : 'prompt';
                    return Promise.resolve({ state: permState, onchange: null });
                }
                return originalQuery.apply(window.navigator.permissions, arguments);
            };
        }
    } catch (e) {}

    // 5. Discrete GPU Profile WebGL spoofing (safe)
    try {
        const getParameterProto = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) {
                return 'Google Inc. (NVIDIA)';
            }
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) {
                return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            }
            return getParameterProto.apply(this, arguments);
        };
        if (window.WebGL2RenderingContext) {
            const getParameterProto2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Google Inc. (NVIDIA)';
                }
                if (parameter === 37446) {
                    return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                }
                return getParameterProto2.apply(this, arguments);
            };
        }
    } catch (e) {}
})();
"""


class BrowserManager:
    """Manages Playwright browser and context lifecycles with advanced anti-detection stealth."""

    def __init__(
        self,
        headless: Optional[bool] = None,
        slow_mo_ms: Optional[int] = None,
        trace: Optional[bool] = None,
        stealth: Optional[bool] = None,
        proxy_server: Optional[str] = None
    ):
        self.headless = BROWSER_HEADLESS if headless is None else headless
        self.slow_mo_ms = BROWSER_SLOW_MO_MS if slow_mo_ms is None else slow_mo_ms
        self.enable_trace = ENABLE_PLAYWRIGHT_TRACE if trace is None else trace
        self.stealth = ENABLE_BROWSER_STEALTH if stealth is None else stealth
        self.proxy_server = proxy_server or PROXY_SERVER
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    def _get_proxy_dict(self) -> Optional[Dict[str, str]]:
        if not self.proxy_server:
            return None
        proxy_cfg: Dict[str, str] = {"server": self.proxy_server}
        if PROXY_USERNAME:
            proxy_cfg["username"] = PROXY_USERNAME
        if PROXY_PASSWORD:
            proxy_cfg["password"] = PROXY_PASSWORD
        if PROXY_BYPASS:
            proxy_cfg["bypass"] = PROXY_BYPASS
        return proxy_cfg

    def start(self):
        if not self._playwright:
            self._playwright = sync_playwright().start()
            
            # Anti-detection launch arguments
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--lang=en-GB,en",
                "--no-first-run"
            ]
            if not self.headless:
                launch_args.append("--start-maximized")

            proxy_dict = self._get_proxy_dict()

            # Multi-tier launch strategy:
            # 1. System Chrome
            # 2. Default Chromium
            # 3. System Microsoft Edge
            launch_strategies = [
                ("system_chrome", lambda: self._playwright.chromium.launch(
                    channel="chrome",
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args,
                    proxy=proxy_dict
                )),
                ("default_chromium", lambda: self._playwright.chromium.launch(
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args,
                    proxy=proxy_dict
                )),
                ("system_msedge", lambda: self._playwright.chromium.launch(
                    channel="msedge",
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                    args=launch_args,
                    proxy=proxy_dict
                )),
            ]

            last_error = None
            for strategy_name, launcher in launch_strategies:
                try:
                    self._browser = launcher()
                    proxy_info = f", Proxy: {self.proxy_server}" if self.proxy_server else ""
                    logger.info(f"Launched browser via strategy '{strategy_name}' (Headless: {self.headless}, Stealth: {self.stealth}{proxy_info})")
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
                        args=launch_args,
                        proxy=proxy_dict
                    )
                    logger.info("Launched newly installed Playwright Chromium browser")
                    return
                else:
                    logger.warning(f"Playwright auto-install returned code {res.returncode}: {res.stderr}")
            except Exception as install_err:
                logger.error(f"Automated browser installation failed: {install_err}")

            if not self._browser:
                raise RuntimeError(f"Unable to launch any browser engine (Chrome/Chromium/Edge). Error: {last_error}")

    def new_context(self, trace_name: Optional[str] = None) -> BrowserContext:
        if not self._browser:
            self.start()

        context_kwargs: Dict[str, Any] = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "locale": "en-GB",
            "timezone_id": "Europe/London",
            "color_scheme": "dark",
            "permissions": ["geolocation", "notifications"],
            "extra_http_headers": {
                "Accept-Language": "en-GB,en;q=0.9"
            }
        }
        if not self.headless:
            context_kwargs["no_viewport"] = True
        else:
            context_kwargs["viewport"] = {"width": 1920, "height": 1080}

        proxy_dict = self._get_proxy_dict()
        if proxy_dict:
            context_kwargs["proxy"] = proxy_dict

        context = self._browser.new_context(**context_kwargs)

        # Inject comprehensive stealth evasion script on every frame / navigation
        if self.stealth:
            context.add_init_script(STEALTH_EVASION_SCRIPT)

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

