import time
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from sites.base import BaseSiteAdapter
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot


class FairplayBetAdapter(BaseSiteAdapter):
    """Adapter for Fairplay Bet (https://fairplaybet.co.uk/)."""

    def __init__(self, promo_url: str = "https://fairplaybet.co.uk/"):
        super().__init__(
            site_id="fairplaybet",
            site_name="Fairplay Bet",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")

        # 1. Click Register button to open the modal
        log.info("Locating and clicking Register button")
        register_btn = page.locator('button:has-text("Register"), a:has-text("Register")').first
        if not register_btn.is_visible(timeout=5000):
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "click_register")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                error_summary="Register button not found on page",
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

        register_btn.click(force=True)
        page.wait_for_timeout(2000)

        # 2. Step 1: Email & Confirm Email
        log.info("Filling Step 1: Email fields")
        email_inp = page.locator('input[name="email"], input[id*="email"], input[placeholder*="email" i]').first
        confirm_email_inp = page.locator('input[name="confirmEmail"], input[name="confirm_email"], input[id*="confirmEmail"]').first

        if email_inp.is_visible(timeout=5000):
            email_inp.fill(client.email)
            if confirm_email_inp.is_visible(timeout=2000):
                confirm_email_inp.fill(client.email)

        # Click Continue / Next if multi-step
        next_btn = page.locator('button:has-text("Next"), button:has-text("Continue"), button[type="submit"]').first
        if next_btn.is_visible(timeout=2000):
            next_btn.click(force=True)
            page.wait_for_timeout(1500)

        # 3. Step 2: Personal Details (First Name, Last Name, DOB, Phone, Password)
        log.info("Filling Step 2: Personal Details")
        fn_inp = page.locator('input[name="firstName"], input[name="first_name"], input[placeholder*="First Name" i]').first
        ln_inp = page.locator('input[name="lastName"], input[name="last_name"], input[placeholder*="Last Name" i]').first
        phone_inp = page.locator('input[name="phone"], input[name="mobile"], input[type="tel"], input[placeholder*="Mobile" i]').first
        pwd_inp = page.locator('input[name="password"], input[type="password"]').first

        if fn_inp.is_visible(timeout=3000):
            fn_inp.fill(client.first_name)
        if ln_inp.is_visible(timeout=3000):
            ln_inp.fill(client.last_name)
        if phone_inp.is_visible(timeout=3000):
            phone_inp.fill(client.phone)
        if pwd_inp.is_visible(timeout=3000):
            pwd_inp.fill(password)
        
        # Confirm password if separate field
        confirm_pwd = page.locator('input[placeholder*="Repeat password" i], input[placeholder*="Confirm password" i], input[name*="confirmPassword" i], input[name*="confirm_password" i]').first
        if confirm_pwd.is_visible(timeout=2000):
            confirm_pwd.fill(password)

        # DOB Selectors or Inputs
        dob_day_inp = page.locator('select[name*="day" i], input[name*="day" i]').first
        dob_month_inp = page.locator('select[name*="month" i], input[name*="month" i]').first
        dob_year_inp = page.locator('select[name*="year" i], input[name*="year" i]').first

        if dob_day_inp.is_visible(timeout=2000):
            if dob_day_inp.evaluate("el => el.tagName.toLowerCase()") == "select":
                dob_day_inp.select_option(value=client.dob_day)
            else:
                dob_day_inp.fill(client.dob_day)

        if dob_month_inp.is_visible(timeout=2000):
            if dob_month_inp.evaluate("el => el.tagName.toLowerCase()") == "select":
                dob_month_inp.select_option(value=client.dob_month)
            else:
                dob_month_inp.fill(client.dob_month)

        if dob_year_inp.is_visible(timeout=2000):
            if dob_year_inp.evaluate("el => el.tagName.toLowerCase()") == "select":
                dob_year_inp.select_option(value=client.dob_year)
            else:
                dob_year_inp.fill(client.dob_year)

        # Next Step if needed
        next_btn = page.locator('button:has-text("Next"), button:has-text("Continue"), button[type="submit"]').first
        if next_btn.is_visible(timeout=2000):
            next_btn.click(force=True)
            page.wait_for_timeout(1500)

        # 4. Step 3: Address & Postcode
        log.info("Filling Step 3: Address details")
        postcode_inp = page.locator('input[name*="postcode" i], input[name*="postalCode" i], input[placeholder*="Postcode" i]').first
        addr1_inp = page.locator('input[name*="address" i], input[placeholder*="Address Line 1" i]').first
        town_inp = page.locator('input[name*="town" i], input[name*="city" i], input[placeholder*="Town" i]').first

        if postcode_inp.is_visible(timeout=3000):
            postcode_inp.fill(client.postcode)
        if addr1_inp.is_visible(timeout=2000):
            addr1_inp.fill(client.address_line1)
        if town_inp.is_visible(timeout=2000):
            town_inp.fill(client.town_city)

        # 5. Terms Checkboxes
        terms_chk = page.locator('input[type="checkbox"][name*="terms" i], input[type="checkbox"][id*="terms" i]').first
        if terms_chk.is_visible(timeout=2000) and not terms_chk.is_checked():
            terms_chk.check(force=True)

        # 6. Check for KYC / CAPTCHA modal
        if page.locator('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], div[class*="captcha"]').is_visible(timeout=1500):
            log.warning("CAPTCHA detected on page")
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "captcha_detected")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.MANUAL_REVIEW,
                email=client.email,
                password=password,
                error_summary="CAPTCHA encountered requiring manual verification",
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

        # 7. Final Submit
        submit_btn = page.locator('button:has-text("Create Account"), button:has-text("Register"), button:has-text("Sign Up"), button[type="submit"]').first
        log.info("Submitting registration form")
        if submit_btn.is_visible(timeout=3000):
            submit_btn.click(force=True)
            page.wait_for_timeout(4000)

        # 8. Verify Result
        auth_indicators = [
            'a:has-text("Deposit")', 'button:has-text("Deposit")',
            'a:has-text("My Account")', 'button:has-text("My Account")',
            '.user-balance', '.account-balance', '[class*="deposit-modal"]'
        ]
        join_btn = page.locator('button:has-text("Register"), a:has-text("Register")').first
        is_join_visible = join_btn.is_visible(timeout=1500)

        has_auth = False
        for selector in auth_indicators:
            try:
                if page.locator(selector).first.is_visible(timeout=1500):
                    has_auth = True
                    break
            except Exception:
                continue

        if has_auth or not is_join_visible:
            log.info("Registration confirmed successfully!")
            success_shot = capture_success_screenshot(page, client.client_id, self.site_id)
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=client.email,
                password=password,
                account_reference="FairplayBet-Direct",
                screenshot_path=success_shot
            )

        # Default fallback capture
        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "verify_submission")
        return RegistrationResult(
            client_id=client.client_id,
            client_name=client.full_name,
            site_id=self.site_id,
            site_name=self.site_name,
            status=RegistrationStatus.FAILED,
            email=client.email,
            password=password,
            error_summary="Registration was not confirmed by Fairplay Bet",
            screenshot_path=bundle.screenshot_path
        )


    def login(
        self,
        page: Page,
        username_or_email: str,
        password: str,
        client_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Specialized login verification handler for Fairplay Bet."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Executing Fairplay Bet login verification for {username_or_email}")

        try:
            if not self.navigate(page):
                return False, None, "Failed to navigate to Fairplay Bet"

            self.accept_cookies(page)

            # Check if login modal button exists
            log_btn = page.locator('button:has-text("Log In"), a:has-text("Log In"), button:has-text("Sign In")').first
            if log_btn.is_visible(timeout=4000):
                log_btn.click(force=True)
                page.wait_for_timeout(1500)

            # Target Fairplay login inputs
            em_inp = page.locator('input[name="email"], input[name="username"], input[type="email"], input[placeholder*="email" i]').first
            pw_inp = page.locator('input[name="password"], input[type="password"]').first

            if not em_inp.is_visible(timeout=4000) or not pw_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "fairplay_login_missing")
                return False, bundle.screenshot_path, "Fairplay Bet login inputs not found"

            em_inp.fill(username_or_email)
            pw_inp.fill(password)
            page.wait_for_timeout(500)

            # Click Log In submit
            submit_btn = page.locator('button:has-text("Log In"), button:has-text("Login"), button[type="submit"]').first
            if submit_btn.is_visible(timeout=3000):
                submit_btn.click(force=True)
            else:
                pw_inp.press("Enter")

            page.wait_for_timeout(5000)

            # Dismiss any welcome / deposit dialogs
            close_btn = page.locator('button[aria-label="Close"], button:has-text("Close"), button:has-text("Maybe Later"), .modal-close').first
            if close_btn.is_visible(timeout=2000):
                try:
                    close_btn.click(force=True)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            # Capture proof
            from core.logger import capture_login_proof_screenshot
            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)
            log.info(f"Fairplay Bet login proof captured: {proof_path}")
            return True, proof_path, None

        except Exception as e:
            log.error(f"Fairplay Bet login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "fairplay_login_error", e)
            return False, bundle.screenshot_path, str(e)

