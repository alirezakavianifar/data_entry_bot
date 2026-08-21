import time
from abc import ABC, abstractmethod
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle

COMMON_COOKIE_SELECTORS = [
    'button:has-text("Accept")',
    'button:has-text("Accept All")',
    'button:has-text("I Accept")',
    'button:has-text("Allow all")',
    '#onetrust-accept-btn-handler',
    'button[id*="cookie-accept"]',
    'a:has-text("Accept")',
    'button:has-text("Agree")'
]

GEOBLOCK_KEYWORDS = [
    "unavailable in your location",
    "geographical restrictions",
    "access from certain territories",
    "outside uk or ireland",
    "offer not available for your country",
    "attention required! | cloudflare",
    "sorry, you have been blocked"
]


class BaseSiteAdapter(ABC):
    """Abstract base adapter for bookmaker registration platforms."""

    def __init__(self, site_id: str, site_name: str, default_promo_url: str, requires_uk_ip: bool = True):
        self.site_id = site_id
        self.site_name = site_name
        self.default_promo_url = default_promo_url
        self.requires_uk_ip = requires_uk_ip

    def navigate(self, page: Page, promo_url: Optional[str] = None) -> bool:
        """Navigates to the promo/registration URL and checks for immediate errors."""
        url = promo_url or self.default_promo_url
        log = get_logger(site_id=self.site_id, step="navigate")
        log.info(f"Navigating to {url}")
        
        resp = page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2000)
        
        status = resp.status if resp else 200
        if status == 403 or self.check_geoblock(page):
            log.warning(f"Geoblock / 403 detected on {self.site_name}")
            return False
        return True

    def accept_cookies(self, page: Page) -> bool:
        """Attempts to detect and click common cookie consent banners."""
        log = get_logger(site_id=self.site_id, step="accept_cookies")
        for selector in COMMON_COOKIE_SELECTORS:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=1500):
                    log.info(f"Clicking cookie banner with selector: {selector}")
                    locator.click(force=True, timeout=2000)
                    page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue
        log.debug("No cookie banner detected or already accepted")
        return False

    def check_geoblock(self, page: Page) -> bool:
        """Returns True if the page contains explicit geographic restriction copy."""
        try:
            body_text = page.inner_text("body").lower()
            for kw in GEOBLOCK_KEYWORDS:
                if kw in body_text:
                    return True
        except Exception:
            pass
        return False

    @abstractmethod
    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        """Executes the specific form interactions for account signup."""
        pass

    def execute(self, page: Page, client: Client, password: str, promo_url: Optional[str] = None) -> RegistrationResult:
        """Main lifecycle template method with complete diagnostic bundle logging."""
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="execute")
        log.info(f"Starting registration workflow for {client.full_name} ({client.email})")

        try:
            # 1. Navigate
            if not self.navigate(page, promo_url):
                bundle = capture_failure_bundle(
                    page, client.client_id, self.site_id, "navigate",
                    Exception("Geographical IP restriction or 403 forbidden detected")
                )
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    error_summary=bundle.error_summary,
                    screenshot_path=bundle.screenshot_path,
                    dom_snapshot_path=bundle.dom_snapshot_path
                )

            # 2. Accept Cookies
            self.accept_cookies(page)

            # 3. Fill and Submit Registration
            result = self.fill_registration(page, client, password)
            log.info(f"Registration finished with status: {result.status.value}")
            return result

        except Exception as e:
            log.error(f"Unhandled exception during registration execution: {e}")
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "fill_registration", e)
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                password=password,
                error_summary=bundle.error_summary,
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )
