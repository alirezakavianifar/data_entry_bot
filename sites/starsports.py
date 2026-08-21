from playwright.sync_api import Page
from sites.base import BaseSiteAdapter, extract_clean_error_message, is_already_registered_error
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot


class StarSportsAdapter(BaseSiteAdapter):
    """Adapter for Star Sports (https://www.starsports.bet/)."""

    def __init__(self, promo_url: str = "https://www.starsports.bet/"):
        super().__init__(
            site_id="starsports",
            site_name="Star Sports",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )


    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info(f"Starting Star Sports registration for {client.full_name}")

        try:
            # 1. Direct navigation to clean signup URL or trigger modal
            if not page.url.endswith("?account=signup"):
                page.goto("https://www.starsports.bet/?account=signup", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2000)

            # Cookiebot Consent Handling
            cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, #CybotCookiebotDialogBodyButtonAccept, button:has-text("Allow all"), button:has-text("Accept")').first
            if cookie_btn.is_visible(timeout=3000):
                log.info("Accepting Cookiebot consent on Star Sports")
                cookie_btn.click(force=True)
                page.wait_for_timeout(1000)

            # Check if sign up modal is open
            email_inp = page.locator('input[data-test="email-input"]').first
            if not email_inp.is_visible(timeout=3000):
                reg_btn = page.locator('a[data-test="account-navigation-signup-link"], a:has-text("Sign Up"), button:has-text("Sign Up")').first
                if reg_btn.is_visible(timeout=3000):
                    log.info("Clicking Sign Up CTA on Star Sports")
                    reg_btn.click(force=True)
                    page.wait_for_timeout(2000)

            # 2. Step 1: Credentials
            email_inp = page.locator('input[data-test="email-input"]').first
            pwd_inp = page.locator('input[data-test="create-password-input"]').first

            if not email_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step1_inputs_missing")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Step 1 registration inputs not found",
                    screenshot_path=bundle.screenshot_path
                )

            log.info(f"Filling Step 1 credentials for {client.email}")
            email_inp.fill(client.email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            create_acc_btn = page.locator('button[data-test="create-account-button"]').first
            if create_acc_btn.is_visible(timeout=2000):
                create_acc_btn.click(force=True)
                page.wait_for_timeout(3000)

            # Check for Step 1 validation errors
            step1_err = page.locator('div[class*="error"], span[class*="error"], p[class*="error"]').first
            if step1_err.is_visible(timeout=1000):
                err_txt = step1_err.inner_text().strip()
                if any(kw in err_txt.lower() for kw in ["already exists", "invalid", "in use", "taken"]):
                    log.warning(f"Step 1 validation error: {err_txt}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step1_error", Exception(err_txt))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        password=password,
                        error_summary=f"Step 1 error: {err_txt}",
                        screenshot_path=bundle.screenshot_path
                    )

            # 3. Step 2: Personal Details
            fn_inp = page.locator('input[data-test="first-name-input"]').first
            ln_inp = page.locator('input[data-test="last-name-input"]').first
            day_inp = page.locator('input[data-test="day-input"]').first
            month_inp = page.locator('input[data-test="month-input"]').first
            year_inp = page.locator('input[data-test="year-input"]').first
            num_inp = page.locator('input[data-test="number-input"]').first
            postcode_inp = page.locator('input[data-test="postcode-input"]').first

            if not fn_inp.is_visible(timeout=5000):
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step2_inputs_missing")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Step 2 personal details inputs not visible",
                    screenshot_path=bundle.screenshot_path
                )

            log.info("Filling Step 2 Personal Details (Name, DOB, Phone, Postcode)")
            fn_inp.fill(client.first_name)
            ln_inp.fill(client.last_name)
            day_inp.fill(f"{client.dob_day:02d}")
            month_inp.fill(f"{client.dob_month:02d}")
            year_inp.fill(str(client.dob_year))

            # Phone number (strip leading 0 as UK prefix +44 is pre-selected)
            cleaned_phone = client.phone.lstrip("0")
            num_inp.fill(cleaned_phone)

            # Postcode & Address Lookup
            postcode_inp.fill(client.postcode)
            page.wait_for_timeout(500)

            search_addr_btn = page.locator('button[data-test="sign-up-search-address-button"]').first
            if search_addr_btn.is_visible(timeout=2000):
                log.info(f"Searching address for postcode: {client.postcode}")
                search_addr_btn.click(force=True)
                page.wait_for_timeout(2500)

                # Select first matching address
                addr_item = page.locator('li[data-component="AddressesListItemWrapper"], ul[class*="AddressesList"] li').first
                if addr_item.is_visible(timeout=3000):
                    log.info(f"Selected address: {addr_item.inner_text().strip()}")
                    addr_item.click(force=True)
                    page.wait_for_timeout(1000)

            # 4. Step 2 Submission: Agree & Join
            agree_btn = page.locator('button[data-test="agree-and-join-button"]').first
            if agree_btn.is_visible(timeout=3000):
                log.info("Submitting registration via 'Agree & Join'")
                agree_btn.click(force=True)
                page.wait_for_timeout(6000)

            # 5. Confirm Registration Success
            # Check for error banners first
            error_modal = page.locator('div[class*="error"]:visible, div[role="alert"]:visible, .error-message:visible').first
            if error_modal.is_visible(timeout=1500):
                raw_err_text = error_modal.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text)

                if is_duplicate:
                    log.warning(f"⚠️ Star Sports: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        error_summary=f"Already registered: {clean_err}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                else:
                    log.warning(f"Star Sports registration rejected: {clean_err}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "server_error", Exception(clean_err))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        password=password,
                        error_summary=clean_err,
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )


            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-component="AccountNavigation"] [data-test*="account"]',
                '.user-balance', '[class*="balance"]', '[class*="deposit-modal"]'
            ]
            has_auth = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1500):
                        has_auth = True
                        break
                except Exception:
                    continue

            # Check if registration form is still open
            is_reg_open = page.locator('input[name="email"]:visible, input[name="password"]:visible, input#email:visible').first.is_visible(timeout=1000)

            if has_auth and not is_reg_open:
                log.info("Star Sports registration confirmed successfully!")
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
                    account_reference="StarSports-Direct",
                    screenshot_path=success_shot
                )
            else:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "verify_submission")
                log.warning("Star Sports submission could not be confirmed")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Registration submission was not confirmed by site",
                    screenshot_path=bundle.screenshot_path
                )

        except Exception as e:
            log.error(f"Registration error on Star Sports: {e}")
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "registration_exception", e)
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                password=password,
                error_summary=str(e),
                screenshot_path=bundle.screenshot_path
            )


    def login(
        self,
        page: Page,
        username_or_email: str,
        password: str,
        client_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Specialized login verification handler for Star Sports."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Navigating to Star Sports clean login URL: https://www.starsports.bet/?account=login")

        try:
            page.goto("https://www.starsports.bet/?account=login", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            self.accept_cookies(page)

            # Locate email & password inputs
            email_inp = page.locator('input[name="email"], input[type="email"]').first
            pwd_inp = page.locator('input[name="password"], input[type="password"]').first

            if not email_inp.is_visible(timeout=3000) or not pwd_inp.is_visible(timeout=3000):
                login_btn = page.locator('a[data-test="account-navigation-login-link"], a:has-text("Login")').first
                if login_btn.is_visible(timeout=3000):
                    login_btn.click(force=True)
                    page.wait_for_timeout(1500)

            email_inp = page.locator('input[name="email"], input[type="email"]').first
            pwd_inp = page.locator('input[name="password"], input[type="password"]').first

            if not email_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "login_inputs_missing")
                return False, bundle.screenshot_path, "Star Sports login inputs not visible"

            log.info(f"Filling credentials for {username_or_email}")
            email_inp.fill(username_or_email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            # Scope submit button to the login container
            modal = page.locator('div[data-component="Modal"], div[class*="login"], form').first
            submit_btn = modal.locator('button[type="submit"]:has-text("Login"), button:has-text("Login")').first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            page.wait_for_timeout(5000)

            # Check for error message
            err_el = page.locator('div[class*="error"]:visible, .error-message:visible, div[role="alert"]:visible, :has-text("not verified"):visible, :has-text("Invalid"):visible').first
            err_text = None
            if err_el.is_visible(timeout=1000):
                err_text = err_el.inner_text().strip().replace("\n", " - ")

            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-component="AccountNavigation"] [data-test*="account"]',
                '.user-balance', '[class*="balance"]'
            ]
            is_authenticated = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1000):
                        is_authenticated = True
                        break
                except Exception:
                    continue

            # Check if login modal/form is still visible
            is_login_open = page.locator('input[name="password"]:visible, input[type="password"]:visible').first.is_visible(timeout=1000)

            from core.logger import capture_login_proof_screenshot
            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

            if is_authenticated and not is_login_open and not err_text:
                log.info(f"Star Sports login successfully verified! Proof: {proof_path}")
                return True, proof_path, None
            else:
                summary = err_text or "Login failed: Credentials rejected or session indicators not found"
                log.warning(f"Star Sports login failed: {summary}")
                return False, proof_path, summary

        except Exception as e:
            log.error(f"Star Sports login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)


