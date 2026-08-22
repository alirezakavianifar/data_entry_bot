import re
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_login_proof_screenshot

ALREADY_REGISTERED_PATTERNS = [
    r"looks like you['’]re already registered",
    r"already registered",
    r"account with this email (?:already )?exists",
    r"account (?:already )?exists",
    r"email (?:address )?is already (?:registered|in use)",
    r"user(?:name)? already exists",
    r"duplicate account",
    r"already have an account"
]

def extract_clean_error_message(text: str) -> str:
    """Extracts a succinct, human-readable error message from raw modal/page text."""
    if not text:
        return ""
    # Check for known explicit error sentences
    for pat in [
        r"(looks like you['’]re already registered[^\.\n]*[\.\n]?)",
        r"(an? account with this [^\.\n]+ already exists)",
        r"(email (?:address )?is already (?:registered|in use)[^\.\n]*)",
        r"(user(?:name)? already exists[^\.\n]*)",
        r"(already registered[^\.\n]*)",
        r"(invalid credentials[^\.\n]*)",
        r"(unable to (?:register|process)[^\.\n]*)",
        r"(please (?:check|correct) the following errors?:?[^\.\n]*)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # Look for line after "Error" label
    lines = [l.strip() for l in text.replace(" - ", "\n").splitlines() if l.strip()]
    for idx, line in enumerate(lines):
        if line.lower() in ("error", "error:", "×", "x", "alert", "warning") and idx + 1 < len(lines):
            candidate = lines[idx + 1]
            if len(candidate) > 5 and not any(k in candidate.lower() for k in ("contact us", "cookie policy", "terms")):
                return f"{candidate}"
        elif "error" in line.lower() and len(line) > 10 and not any(k in line.lower() for k in ("racing", "greyhound", "cookie")):
            return line

    for l in lines:
        if any(k in l.lower() for k in ("already", "exists", "invalid", "failed", "error", "unable", "sorry", "cannot")):
            return l

    return text[:160].strip()

def is_already_registered_error(text: str) -> bool:
    """Returns True if the error message indicates the client account already exists."""
    if not text:
        return False
    for pat in ALREADY_REGISTERED_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

PENDING_VERIFICATION_PATTERNS = [
    r"verify your email",
    r"verification (?:email|link)",
    r"activation (?:email|link)",
    r"check your (?:inbox|email)",
    r"activate your account",
    r"account (?:is )?not (?:yet )?(?:activated|verified)",
    r"email (?:has not been|is not|not) verified",
    r"more info needed",
    r"proof of id",
    r"proof of address",
    r"electoral roll",
    r"document upload",
    r"upload (?:your )?documents",
    r"kyc",
    r"verify your details",
    r"account pending verification",
    r"require email verification",
    r"email verification"
]

def is_pending_verification_error(text: str) -> bool:
    """Returns True if the message indicates the account exists but requires user email or KYC verification."""
    if not text:
        return False
    for pat in PENDING_VERIFICATION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

COMMON_COOKIE_SELECTORS = [

    '#onetrust-accept-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    'button:has-text("Accept All Cookies")',
    'button:has-text("Accept all cookies")',
    'button:has-text("Accept All")',
    'button:has-text("Allow all")',
    'button:has-text("Accept")',
    'button:has-text("I Accept")',
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

    def login(
        self,
        page: Page,
        username_or_email: str,
        password: str,
        client_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Attempts to authenticate into the site using provided credentials and capture proof.
        Returns: (success: bool, screenshot_path: Optional[str], error_message: Optional[str])
        """
        cid = client_id or "client"

        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Initiating login verification for {username_or_email} on {self.site_name}")

        try:
            # 1. Determine clean login URL (strip promo / modal params if needed)
            from urllib.parse import urlparse
            parsed = urlparse(self.default_promo_url)
            clean_base_url = f"{parsed.scheme}://{parsed.netloc}/"
            
            # If site is an FSB technology platform (e.g. planetsportbet, bresbet, starsports)
            if self.site_id in ("planetsportbet", "bresbet", "starsports"):
                target_url = f"{clean_base_url}?account=login"
            else:
                target_url = clean_base_url

            log.info(f"Navigating to login target URL: {target_url}")
            resp = page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)

            if self.check_geoblock(page):
                return False, None, "Geoblock detected during login navigation"

            self.accept_cookies(page)

            # 2. If login inputs not yet visible, locate and click Login / Sign In CTA
            user_inp = page.locator('input[name="email"], input[name="username"], input[type="email"], input[id*="username" i], input[id*="email" i], input[placeholder*="email" i], input[placeholder*="user" i]').first
            if not user_inp.is_visible(timeout=2500):
                # Dismiss any overlay modal first
                close_btn = page.locator('button[aria-label="Close"], button:has-text("Close"), .modal-close, button:has-text("✕"), button:has-text("X")').first
                if close_btn.is_visible(timeout=1000):
                    try:
                        close_btn.click(force=True)
                        page.wait_for_timeout(1000)
                    except Exception:
                        pass

                login_btn = page.locator('a[data-test*="login"], button[data-test*="login"], a:has-text("Login"), button:has-text("Login"), button:has-text("Log In"), a:has-text("Log In"), button:has-text("Sign In"), a:has-text("Sign In")').first
                if login_btn.is_visible(timeout=4000):
                    log.info(f"Clicking Login CTA on {self.site_name}")
                    login_btn.click(force=True)
                    page.wait_for_timeout(2000)

            # 3. Locate credentials fields
            user_inp = page.locator('input[name="email"], input[name="username"], input[type="email"], input[id*="username" i], input[id*="email" i], input[placeholder*="email" i], input[placeholder*="user" i]').first
            pwd_inp = page.locator('input[name="password"], input[type="password"], input[id*="password" i]').first

            if not user_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "login_inputs_missing")
                return False, bundle.screenshot_path, f"Login inputs not visible on {self.site_name}"

            log.info(f"Filling credentials for {username_or_email}")
            user_inp.fill(username_or_email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            # 4. Submit login form
            submit_btn = page.locator('button[type="submit"]:has-text("Login"), button[type="submit"]:has-text("Log In"), button[type="submit"]:has-text("Sign In"), button:has-text("Login"), button:has-text("Log In"), button[type="submit"]').first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            # 5. Wait for authentication response & state transition
            page.wait_for_timeout(5000)

            # 6. Check for dismissible welcome / KYC dialogs post-login
            dismiss_btn = page.locator('button:has-text("Dismiss"), button:has-text("Later"), button:has-text("Maybe Later"), button:has-text("Close"), button[aria-label="Close"], [class*="modal"] button[class*="close"]').first
            if dismiss_btn.is_visible(timeout=2000):
                try:
                    dismiss_btn.click(force=True)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            # 7. Check if Login CTA is STILL visible
            login_cta = page.locator('a[data-test="account-navigation-login-link"], a:has-text("Login"), button:has-text("Login"), a:has-text("Log In"), button:has-text("Log In")').first
            is_login_cta_visible = False
            try:
                if login_cta.is_visible(timeout=1500):
                    is_login_cta_visible = True
            except Exception:
                pass

            # 8. Check for authentic post-login user widgets
            logged_in_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'button:has-text("Log Out")', 'a:has-text("Log Out")',
                'button:has-text("Logout")', 'a:has-text("Logout")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-testid*="user-menu"]', '[data-component="AccountNavigation"] [data-test*="account"]',
                '.user-balance', '.account-balance', '.wallet-balance'
            ]

            has_auth_widget = False
            for selector in logged_in_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1000):
                        has_auth_widget = True
                        log.info(f"Authenticated session element confirmed: {selector}")
                        break
                except Exception:
                    continue

            # Check for invalid credentials / lock error banner
            error_el = page.locator('div[class*="error"]:visible, span[class*="error"]:visible, p[class*="error"]:visible, div[role="alert"]:visible, [class*="alert"]:visible, :has-text("not verified"):visible, :has-text("Invalid"):visible, :has-text("incorrect"):visible').first
            err_msg_found = None
            if error_el.is_visible(timeout=1000):
                err_text = error_el.inner_text().strip()
                if any(err_kw in err_text.lower() for err_kw in ["invalid", "incorrect", "locked", "disabled", "failed", "unrecognized", "error", "not verified"]):
                    err_msg_found = err_text

            # Check if login modal/drawer is still open
            is_login_form_open = page.locator('input[type="password"]:visible, form input#password:visible').first.is_visible(timeout=1000)

            # Strict Evaluation: Login is ONLY verified if genuine auth indicators exist, login form is closed, and no errors
            is_authenticated = has_auth_widget and not is_login_form_open and not err_msg_found

            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

            if is_authenticated:
                log.info(f"Login verified successfully for {username_or_email}! Proof saved: {proof_path}")
                return True, proof_path, None
            else:
                err_summary = err_msg_found or "Login failed: account indicators not found or credentials rejected"
                log.warning(f"Login unconfirmed: {err_summary}")
                return False, proof_path, err_summary


        except Exception as e:
            log.error(f"Exception during login verification: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)


