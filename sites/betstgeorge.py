from typing import Optional
from playwright.sync_api import Page
from sites.base import BaseSiteAdapter, extract_clean_error_message, is_already_registered_error
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot, capture_login_proof_screenshot


class BetStGeorgeAdapter(BaseSiteAdapter):
    """Adapter for Bet St George (https://betstgeorge.com/)."""

    def __init__(self, promo_url: str = "https://betstgeorge.com/?promo=B20G20afs&btag=6a8954687602ed96cd480d2c_699f0c4baa77fde72d25e55f&affiliateId=69c6b31e35700061a8907364"):
        super().__init__(
            site_id="betstgeorge",
            site_name="Bet St George",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info(f"Starting Bet St George registration for {client.full_name}")

        try:
            # 1. Cookiebot Consent Handling
            cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, #CybotCookiebotDialogBodyButtonAccept, button:has-text("Allow all"), button:has-text("Accept")').first
            if cookie_btn.is_visible(timeout=3000):
                log.info("Accepting Cookiebot consent on Bet St George")
                cookie_btn.click(force=True)
                page.wait_for_timeout(1000)

            # Check if sign up modal or landing form is open
            email_inp = page.locator('input[data-test="landing-page-email-input"], input[data-test="email-input"], input[placeholder*="Email"]').first
            if not email_inp.is_visible(timeout=3000):
                reg_btn = page.locator('a[data-test="account-navigation-signup-link"], a:has-text("Sign Up"), button:has-text("Sign Up")').first
                if reg_btn.is_visible(timeout=3000):
                    log.info("Clicking Sign Up CTA on Bet St George")
                    reg_btn.click(force=True)
                    page.wait_for_timeout(2000)

            # 2. Step 1: Credentials
            email_inp = page.locator('input[data-test="landing-page-email-input"], input[data-test="email-input"], input[placeholder*="Email"]').first
            pwd_inp = page.locator('input[data-test="landing-page-password-input"], input[data-test="create-password-input"], input[placeholder*="password"]').first

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

            create_acc_btn = page.locator('button:has-text("Create Account"), button:has-text("Sign Up"), button:has-text("Join Here"), button[data-test="create-account-button"], button[type="submit"]:has-text("Sign Up"), button[type="submit"]').first
            if create_acc_btn.is_visible(timeout=2000):
                create_acc_btn.click(force=True)
                page.wait_for_timeout(3000)

            # Check for Step 1 validation errors
            step1_err = page.locator('div[class*="error"]:visible, span[class*="error"]:visible, p[class*="error"]:visible, [data-test*="error"]:visible, [class*="errorMessage"]:visible, :has-text("already exists"):visible').first
            if step1_err.is_visible(timeout=1500):
                err_txt = step1_err.inner_text().strip()
                if is_already_registered_error(err_txt) or any(kw in err_txt.lower() for kw in ["already exists", "in use", "already registered", "taken"]):
                    log.warning(f"Bet St George: Client {client.full_name} is ALREADY REGISTERED ({err_txt})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        account_reference="BetStGeorge-Existing",
                        error_summary=f"Already registered: {err_txt}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                elif any(kw in err_txt.lower() for kw in ["invalid", "error", "required"]):
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
                dup_err = page.locator('div[class*="error"]:visible, span[class*="error"]:visible, p[class*="error"]:visible, [data-test*="error"]:visible, :has-text("already exists"):visible, :has-text("in use"):visible').first
                if dup_err.is_visible(timeout=1000):
                    raw_txt = dup_err.inner_text().strip().replace("\n", " - ")
                    clean_err = extract_clean_error_message(raw_txt) or raw_txt
                    if is_already_registered_error(raw_txt) or "already exists" in raw_txt.lower():
                        log.warning(f"Bet St George: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.ALREADY_REGISTERED,
                            email=client.email,
                            password=password,
                            account_reference="BetStGeorge-Existing",
                            error_summary=f"Already registered: {clean_err}",
                            screenshot_path=bundle.screenshot_path,
                            dom_snapshot_path=bundle.dom_snapshot_path
                        )

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

            # Select Title (Mr / Ms)
            title_el = page.locator('[data-test="mr-title-choose-box"], [data-test="title-choose-box"] div:first-child, label:has-text("Mr")').first
            if title_el.is_visible(timeout=2000):
                title_el.click(force=True)
                page.wait_for_timeout(300)

            log.info("Filling Step 2 Personal Details (Name, DOB, Phone, Postcode)")
            fn_inp.fill(client.first_name)
            ln_inp.fill(client.last_name)
            day_inp.fill(str(int(client.dob_day)).zfill(2))
            month_inp.fill(str(int(client.dob_month)).zfill(2))
            year_inp.fill(str(client.dob_year))

            # Phone number (strip leading 0 as UK prefix +44 is pre-selected)
            cleaned_phone = client.phone
            if cleaned_phone.startswith("+44"):
                cleaned_phone = cleaned_phone[3:]
            cleaned_phone = cleaned_phone.lstrip("0")
            num_inp.fill(cleaned_phone)

            # Postcode & Address Lookup
            postcode_inp.fill(client.postcode)
            page.wait_for_timeout(500)

            search_addr_btn = page.locator('button[data-test="sign-up-search-address-button"], button:has-text("Search")').first
            if search_addr_btn.is_visible(timeout=2000):
                log.info(f"Searching address for postcode: {client.postcode}")
                search_addr_btn.click(force=True)
                page.wait_for_timeout(2500)

                # Select matching address or traverse nested dropdown
                addr_list = page.locator('li[data-component="AddressesListItemWrapper"], ul[class*="AddressesList"] li')
                if addr_list.count() > 0:
                    log.info(f"Selecting address: {addr_list.first.inner_text().strip()}")
                    addr_list.first.click(force=True)
                    page.wait_for_timeout(1500)
                    if addr_list.count() > 0:
                        log.info(f"Selecting specific street address: {addr_list.first.inner_text().strip()}")
                        addr_list.first.click(force=True)
                        page.wait_for_timeout(1000)

                # Fallback to manual entry if address input is not yet populated
                addr1 = page.locator('input[data-test="first-line-address-input"], input[name="address-1"]').first
                if not addr1.is_visible(timeout=1000):
                    manual_btn = page.locator('a:has-text("Enter Manually"), button:has-text("Enter Manually"), span:has-text("Enter Manually")').first
                    if manual_btn.is_visible(timeout=1000):
                        manual_btn.click(force=True)
                        page.wait_for_timeout(1000)
                        if addr1.is_visible(timeout=1000):
                            addr1.fill(client.address_line1)
                            city_inp = page.locator('input[data-test="town-city-input"], input[name="town-city"]').first
                            if city_inp.is_visible(timeout=1000):
                                city_inp.fill(client.town_city)

            # 4. Step 2 Submission: Agree & Join
            agree_btn = page.locator('button[data-test="agree-and-join-button"]').first
            if agree_btn.is_visible(timeout=3000):
                log.info("Submitting registration via 'Agree & Join'")
                agree_btn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                agree_btn.click(force=True)
                page.wait_for_timeout(6000)

            # 5. Confirm Registration Success
            # Check for error message under Agree & Join or in SignUpStepsContainer
            error_el = page.locator('[data-test="error-message-content"]:visible, aside[data-test="SignUpStepsContainer"] [class*="MessageWrapper"]:visible, [data-test*="error"]:visible').first
            if error_el.is_visible(timeout=3000):
                raw_err_text = error_el.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text) or "operating license" in raw_err_text.lower() or "regret to inform" in raw_err_text.lower()
                final_err_msg = clean_err or raw_err_text

                if is_duplicate:
                    log.warning(f"[DUPLICATE] Bet St George: Client {client.full_name} is ALREADY REGISTERED ({final_err_msg})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        error_summary=f"Already registered: {final_err_msg}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                else:
                    log.warning(f"Bet St George registration rejected: {final_err_msg}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "server_error", Exception(final_err_msg))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        password=password,
                        error_summary=final_err_msg,
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )

            # Handle Safer Gambling modal if present
            safer_modal = page.locator('legend:has-text("SAFER GAMBLING"), h2:has-text("SAFER GAMBLING"), [data-test*="safer-gambling"]').first
            if safer_modal.is_visible(timeout=3000):
                log.info("Safer Gambling modal detected, progressing...")
                ack_toggle = page.locator('span[class*="switch"], [role="switch"], label:has-text("deposit limit"), [class*="Switch"]').last
                if ack_toggle.is_visible(timeout=1500):
                    ack_toggle.click(force=True)
                    page.wait_for_timeout(500)
                next_btn = page.locator('button:has-text("Next"), button:has-text("NEXT"), button[data-test*="next"]').first
                if next_btn.is_visible(timeout=2000):
                    next_btn.click(force=True)
                    page.wait_for_timeout(4000)

            # Authenticated indicators / Deposit modal / KYC prompt
            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-component="AccountNavigation"] [data-test*="account"]',
                '.user-balance', '[class*="deposit-modal"]', 'h1:has-text("SAFER GAMBLING")'
            ]
            has_auth = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1500):
                        has_auth = True
                        break
                except Exception:
                    continue

            # Check if signup form is still open
            agree_still_open = page.locator('button[data-test="agree-and-join-button"]:visible').first.is_visible(timeout=1000)

            if (has_auth or not agree_still_open):
                log.info("Bet St George registration confirmed successfully!")
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
                    account_reference="BetStGeorge-Direct",
                    screenshot_path=success_shot
                )
            else:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "verify_submission")
                log.warning("Bet St George submission could not be confirmed")
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
            log.error(f"Registration error on Bet St George: {e}")
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
        """Specialized login verification handler for Bet St George."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Navigating to Bet St George clean login URL: https://betstgeorge.com/?account=login")

        try:
            page.goto("https://betstgeorge.com/?account=login", wait_until="domcontentloaded", timeout=25000)
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
                return False, bundle.screenshot_path, "Bet St George login inputs not visible"

            log.info(f"Filling credentials for {username_or_email}")
            email_inp.fill(username_or_email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            modal = page.locator('div[data-component="Modal"], div[class*="login"], form').first
            submit_btn = modal.locator('button[type="submit"]:has-text("Login"), button:has-text("Login")').first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            page.wait_for_timeout(5000)

            # Check for error message
            err_el = page.locator('div[data-test="error-message-content"]:visible, div[class*="error"]:visible, .error-message:visible, div[role="alert"]:visible, :has-text("not verified"):visible, :has-text("Invalid"):visible').first
            err_text = None
            if err_el.is_visible(timeout=1000):
                err_text = err_el.inner_text().strip().replace("\n", " - ")

            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

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

            is_login_open = page.locator('input[name="password"]:visible, input[type="password"]:visible').first.is_visible(timeout=1000)

            if is_authenticated and not is_login_open and not err_text:
                log.info(f"Bet St George login successfully verified! Proof: {proof_path}")
                return True, proof_path, None
            else:
                summary = err_text or "Login failed: Credentials rejected or session indicators not found"
                log.warning(f"Bet St George login failed: {summary}")
                return False, proof_path, summary

        except Exception as e:
            log.error(f"Bet St George login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)
