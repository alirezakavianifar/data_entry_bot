from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from sites.base import BaseSiteAdapter, extract_clean_error_message, is_already_registered_error
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

        # 1. Dismiss cookies
        self.accept_cookies(page)

        # 2. Click Register button to open drawer
        log.info("Locating and opening Fairplay Bet registration drawer")
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
                error_summary="Register button not found on Fairplay Bet",
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

        register_btn.click(force=True)
        page.wait_for_timeout(2000)

        # 3. Step 1: Email & Confirm Email
        log.info("Filling Step 1: Email & Confirm Email")
        email_inp = page.locator('input#email, input[name="email"]').first
        confirm_email_inp = page.locator('input#confirmEmail, input[name="confirmEmail"]').first

        if not email_inp.is_visible(timeout=5000):
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "fairplay_step1_missing")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                error_summary="Fairplay Bet Step 1 email fields not visible",
                screenshot_path=bundle.screenshot_path
            )

        email_inp.fill(client.email)
        page.wait_for_timeout(300)
        confirm_email_inp.fill(client.email)
        page.wait_for_timeout(500)

        # Click Continue on Step 1
        step1_cont = page.locator('form button:has-text("Continue"), form button[type="submit"]').first
        if step1_cont.is_visible(timeout=2000):
            step1_cont.click(force=True)
        else:
            page.locator('button:has-text("Continue"):visible').first.click(force=True)
        page.wait_for_timeout(2000)

        # 4. Step 2: Password & Confirm Password
        log.info("Filling Step 2: Password & Confirm Password")
        pwd_inp = page.locator('input#password, input[name="password"]').first
        confirm_pwd_inp = page.locator('input#confirmPassword, input[name="confirmPassword"]').first

        if not pwd_inp.is_visible(timeout=4000):
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "fairplay_step2_missing")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                password=password,
                error_summary="Fairplay Bet Step 2 password fields not visible",
                screenshot_path=bundle.screenshot_path
            )

        pwd_inp.fill(password)
        page.wait_for_timeout(300)
        confirm_pwd_inp.fill(password)
        page.wait_for_timeout(500)

        # Click Continue on Step 2
        step2_cont = page.locator('form button:has-text("Continue"), form button[type="submit"]').first
        if step2_cont.is_visible(timeout=2000):
            step2_cont.click(force=True)
        else:
            page.locator('button:has-text("Continue"):visible').first.click(force=True)
        page.wait_for_timeout(2500)

        # 5. Step 3: Personal Details, DOB, Phone, Address & Terms
        log.info("Filling Step 3: Personal Details, DOB, Phone & Address")
        fn_inp = page.locator('input#firstName, input[name="firstName"]').first
        ln_inp = page.locator('input#lastName, input[name="lastName"]').first

        if not fn_inp.is_visible(timeout=4000):
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "fairplay_step3_missing")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                password=password,
                error_summary="Fairplay Bet Step 3 personal details fields not visible",
                screenshot_path=bundle.screenshot_path
            )

        fn_inp.fill(client.first_name)
        page.wait_for_timeout(200)
        ln_inp.fill(client.last_name)
        page.wait_for_timeout(200)

        # DOB Fields
        page.locator('input[name="dateOfBirth.day"], input[placeholder="DD"]').first.fill(client.dob_day.zfill(2))
        page.locator('input[name="dateOfBirth.month"], input[placeholder="MM"]').first.fill(client.dob_month.zfill(2))
        page.locator('input[name="dateOfBirth.year"], input[placeholder="YYYY"]').first.fill(client.dob_year)
        page.wait_for_timeout(200)

        # Phone (strip leading 0 and +44 prefix)
        phone_digits = client.phone.lstrip("+44").lstrip("0")
        phone_inp = page.locator('input[name="phoneNumber"], input[placeholder*="phone" i]').first
        if phone_inp.is_visible():
            phone_inp.fill(phone_digits)
        page.wait_for_timeout(200)

        # Postcode & Address Lookup
        postcode_inp = page.locator('input#postcode, input[name="postcode"]').first
        if postcode_inp.is_visible():
            postcode_inp.fill(client.postcode)
            page.wait_for_timeout(500)

            # Click Find Address
            find_addr_btn = page.locator('button:has-text("Find Address")').first
            if find_addr_btn.is_visible(timeout=2000):
                find_addr_btn.click(force=True)
                page.wait_for_timeout(2000)

                # Check for dropdown results
                first_addr_opt = page.locator('ul li:not(:has-text("Enter Manually"))').first
                if first_addr_opt.is_visible(timeout=2000):
                    first_addr_opt.click(force=True)
                    page.wait_for_timeout(1000)
                else:
                    # Click Enter Manually
                    enter_manual = page.locator('span:has-text("Enter Manually"), li:has-text("Enter Manually")').first
                    if enter_manual.is_visible(timeout=1500):
                        enter_manual.click(force=True)
                        page.wait_for_timeout(1000)

                    # Fill manual address fields
                    b_num = client.address_line1.split()[0] if client.address_line1 else "1"
                    b_street = " ".join(client.address_line1.split()[1:]) if " " in client.address_line1 else client.address_line1

                    b_num_inp = page.locator('input[name="buildingNumber"]').first
                    if b_num_inp.is_visible():
                        b_num_inp.fill(b_num)
                    
                    street_inp = page.locator('input[name="street"]').first
                    if street_inp.is_visible():
                        street_inp.fill(b_street)

                    city_inp = page.locator('input[name="townOrCity"]').first
                    if city_inp.is_visible():
                        city_inp.fill(client.town_city)

        # Set Marketing Preferences (No to all)
        for offer_field in ["offers.email", "offers.phone", "offers.sms"]:
            no_label = page.locator(f'label:has(input[name="{offer_field}"][value="no"])').first
            if no_label.is_visible(timeout=1000):
                no_label.click(force=True)
            else:
                try:
                    page.locator(f'input[name="{offer_field}"][value="no"]').first.check(force=True)
                except Exception:
                    pass

        # Agree to Terms & Conditions
        terms_label = page.locator('label[for="termsAccepted"], label:has(input[name="termsAccepted"])').first
        if terms_label.is_visible(timeout=2000):
            terms_label.click(force=True)
        else:
            page.evaluate("() => { const el = document.querySelector('input[name=\"termsAccepted\"]'); if (el) el.click(); }")
        page.wait_for_timeout(500)

        # 6. Check for CAPTCHA
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
        submit_btn = page.locator('form button[type="submit"], button:has-text("Next"):visible, button:has-text("Create Account"):visible').first
        log.info("Submitting Step 3 registration form")
        if submit_btn.is_visible(timeout=3000):
            submit_btn.click(force=True)
            page.wait_for_timeout(3000)

        # 8. Polling Loop (up to 30s) to wait for "Please wait while we verify your details" spinner & confirmation
        log.info("Waiting for Fairplay Bet in-platform verification & confirmation (up to 30s)...")
        max_poll_sec = 30
        is_confirmed = False
        email_verif_needed = False
        kyc_needed = False
        kyc_bundle = None

        for sec in range(1, max_poll_sec + 1):
            # A. Check for duplicate / server error modal
            error_modal = page.locator(
                'div[role="dialog"]:visible, '
                'div[class*="modal"]:visible, '
                'div[class*="Modal"]:visible, '
                'div[class*="Dialog"]:visible, '
                'div[role="alert"]:visible, '
                'div:has-text("already registered"):visible, '
                'p:has-text("already registered"):visible, '
                'h2:has-text("Error"):visible, '
                'h3:has-text("Error"):visible, '
                '.error-message:visible'
            ).first

            if error_modal.is_visible(timeout=300):
                raw_err_text = error_modal.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text) or "already registered" in raw_err_text.lower() or "looks like you" in raw_err_text.lower()

                if is_duplicate:
                    log.warning(f"⚠️ Fairplay Bet: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        account_reference="FairplayBet-Existing",
                        error_summary=f"Already registered: {clean_err or 'Looks like you are already registered'}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                elif any(k in raw_err_text.lower() for k in ("invalid", "rejected", "error", "failed")):
                    log.warning(f"Fairplay Bet registration error returned by server: {clean_err}")
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

            # B. Check for KYC Document Upload Modal ("More info needed")
            kyc_modal = page.locator(
                'div:has-text("More info needed"):visible, '
                'h1:has-text("More info needed"):visible, '
                'h2:has-text("More info needed"):visible, '
                'h3:has-text("More info needed"):visible, '
                'div:has-text("electoral roll"):visible, '
                'div:has-text("Proof of ID"):visible'
            ).first
            if kyc_modal.is_visible(timeout=300):
                log.warning(f"⚠️ Fairplay Bet: Account created for {client.full_name} ({client.email}), but manual KYC document upload is required.")
                kyc_needed = True
                kyc_bundle = capture_failure_bundle(page, client.client_id, self.site_id, "kyc_required")
                break

            # C. Check for Email Verification prompt (Client confirmed Fairplay requires email verification)
            email_prompt = page.locator(
                ':has-text("Verify your email"):visible, '
                ':has-text("check your email"):visible, '
                ':has-text("activation link"):visible, '
                ':has-text("verification email"):visible, '
                ':has-text("Please verify your email"):visible, '
                'h1:has-text("Verify"):visible, '
                'h2:has-text("Verify"):visible'
            ).first
            if email_prompt.is_visible(timeout=300):
                log.info(f"Fairplay Bet email verification prompt confirmed at {sec}s!")
                email_verif_needed = True
                is_confirmed = True
                break

            # D. Check if verification spinner is still active ("Please wait while we verify your details")
            spinner = page.locator(':has-text("Please wait while we verify your details"), :has-text("verify your details")').first
            if spinner.is_visible(timeout=300):
                if sec % 5 == 0:
                    log.info(f"Fairplay Bet verification spinner still processing ({sec}/{max_poll_sec}s)...")
                page.wait_for_timeout(1000)
                continue

            # E. Check for authenticated state indicators
            auth_indicators = [
                'button:has-text("Deposit")', 'a:has-text("Deposit")',
                'button:has-text("DEPOSIT")', 'a:has-text("DEPOSIT")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                'button:has-text("Logout")', 'a:has-text("Logout")',
                '.user-balance', '.account-balance', '[class*="deposit-modal"]'
            ]
            has_auth = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=300):
                        has_auth = True
                        break
                except Exception:
                    continue

            is_drawer_inputs_open = page.locator('form input#firstName, form input#email, input#confirmPassword').first.is_visible(timeout=300)

            if has_auth and not is_drawer_inputs_open:
                log.info(f"Fairplay Bet session confirmed at {sec}s!")
                is_confirmed = True
                break

            page.wait_for_timeout(1000)

        if kyc_needed:
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.MANUAL_REVIEW,
                email=client.email,
                username=client.email,
                password=password,
                account_reference="FairplayBet-KYC-Review",
                error_summary="Account created; KYC document upload required (Proof of ID & Address)",
                screenshot_path=kyc_bundle.screenshot_path if kyc_bundle else None,
                dom_snapshot_path=kyc_bundle.dom_snapshot_path if kyc_bundle else None
            )

        if is_confirmed or email_verif_needed:
            log.info("Fairplay Bet registration confirmed successfully!")
            success_shot = capture_success_screenshot(page, client.client_id, self.site_id)
            ref_label = "FairplayBet (Email Verification Required)" if email_verif_needed else "FairplayBet-Direct"
            summary_label = "✉️ Email activation link sent - client must verify email" if email_verif_needed else None
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=client.email,
                password=password,
                account_reference=ref_label,
                error_summary=summary_label,
                screenshot_path=success_shot
            )

        # 9. Fallback Safety Scan: Check if "already registered" modal/message is present anywhere on page
        body_text = ""
        try:
            body_text = page.locator("body").inner_text()
        except Exception:
            pass

        if is_already_registered_error(body_text) or "looks like you're already registered" in body_text.lower():
            clean_err = extract_clean_error_message(body_text)
            log.warning(f"⚠️ Fairplay Bet: Client {client.full_name} is ALREADY REGISTERED (detected via page scan)")
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.ALREADY_REGISTERED,
                email=client.email,
                password=password,
                account_reference="FairplayBet-Existing",
                error_summary=f"Already registered: {clean_err or 'Looks like you are already registered'}",
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

        # Fallback failure capture
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
            page.wait_for_timeout(1000)

            # Check for a full-page error BEFORE clicking Login
            # (e.g. if navigation landed on an "already registered" error page)
            full_page_err = page.locator(
                'div:has-text("already registered"):visible, '
                'p:has-text("already registered"):visible, '
                'div[class*="error"]:visible, div[role="alert"]:visible'
            ).first
            if full_page_err.is_visible(timeout=1500):
                raw = full_page_err.inner_text().strip().replace("\n", " - ")
                from sites.base import is_already_registered_error, extract_clean_error_message
                if is_already_registered_error(raw):
                    log.warning(f"Full-page 'already registered' error before login attempt: {raw[:120]}")
                    bundle = capture_failure_bundle(page, cid, self.site_id, "fairplay_login_already_registered")
                    return False, bundle.screenshot_path, f"Already registered error page shown (email may be unverified or account locked): {extract_clean_error_message(raw)}"

            # Click the Login button in the header to open the login drawer
            # Use a specific header-scoped selector to avoid accidentally clicking Register
            log_btn = page.locator(
                'header button:has-text("Login"), '
                'header a:has-text("Login"), '
                'nav button:has-text("Login"), '
                'nav a:has-text("Login")'
            ).first
            if log_btn.is_visible(timeout=5000):
                log_btn.click(force=True)
                page.wait_for_timeout(2000)
            else:
                log.warning("Login button not found in header/nav; attempting page-wide fallback")
                # Fallback: any visible Login button that is NOT inside a registration form
                fallback_btn = page.locator('button:has-text("Login"):visible').first
                if fallback_btn.is_visible(timeout=3000):
                    fallback_btn.click(force=True)
                    page.wait_for_timeout(2000)

            # Scope to the Login Drawer — use specific class fragments to avoid matching registration forms
            # The login drawer typically has class names like "right-0", "auth", "login", or "max-w-md"
            drawer = page.locator(
                'div[class*="login"], '
                'div[class*="auth"], '
                'div[class*="fixed right-0"], '
                'div[class*="max-w-md"]'
            ).first

            # Target login email & password inputs inside the drawer
            em_inp = drawer.locator('input[name="email"], input[type="email"], input#email').first
            pw_inp = drawer.locator('input[name="password"], input[type="password"], input#password').first

            if not em_inp.is_visible(timeout=5000):
                # Drawer selector may not have matched — fall back to page-level inputs
                log.warning("Login drawer not matched by class selector; falling back to page-level inputs")
                em_inp = page.locator('input[name="email"], input[type="email"]').first
                pw_inp = page.locator('input[name="password"], input[type="password"]').first

            if not em_inp.is_visible(timeout=4000) or not pw_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "fairplay_login_missing")
                return False, bundle.screenshot_path, "Fairplay Bet login inputs not found after opening login drawer"

            em_inp.fill(username_or_email)
            page.wait_for_timeout(300)
            pw_inp.fill(password)
            page.wait_for_timeout(500)

            # Click the Login submit button inside the drawer
            submit_btn = page.locator(
                'button[type="submit"]:has-text("Login"):visible, '
                'button:has-text("Log in"):visible, '
                'button:has-text("Sign in"):visible'
            ).first
            if submit_btn.is_visible(timeout=3000):
                log.info("Clicking Fairplay Bet login submit button")
                submit_btn.click(force=True)
            else:
                log.info("Submit button not found — pressing Enter on password input")
                pw_inp.press("Enter")

            page.wait_for_timeout(5000)

            # Capture diagnostic proof screenshot
            from core.logger import capture_login_proof_screenshot
            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)
            log.info(f"Fairplay Bet login proof captured: {proof_path}")

            # --- Check 1: Full-page error (e.g. "already registered" banner outside drawer) ---
            full_page_err_after = page.locator(
                'div:has-text("already registered"):visible, '
                'p:has-text("already registered"):visible, '
                '[class*="error-page"]:visible'
            ).first
            if full_page_err_after.is_visible(timeout=1500):
                raw = full_page_err_after.inner_text().strip().replace("\n", " - ")
                from sites.base import extract_clean_error_message
                msg = extract_clean_error_message(raw)
                log.warning(f"Full-page error after login attempt: {msg}")
                return False, proof_path, f"Login error (full-page): {msg}"

            # --- Check 2: Inline drawer errors (Invalid credentials, unverified, etc.) ---
            err_el = page.locator(
                'div[role="alert"]:visible, '
                '.error-message:visible, '
                'p:has-text("Invalid"):visible, '
                'p:has-text("incorrect"):visible, '
                'div:has-text("not verified"):visible'
            ).first
            if err_el.is_visible(timeout=2000):
                err_text = err_el.inner_text().strip().replace("\n", " - ")
                log.warning(f"Fairplay Bet login rejected (inline error): {err_text}")
            # --- Check 2.5: KYC Upload Prompt (Valid authentication, pending document upload) ---
            kyc_on_login = page.locator(
                'div:has-text("More info needed"):visible, '
                'h1:has-text("More info needed"):visible, '
                'div:has-text("Proof of ID"):visible'
            ).first
            if kyc_on_login.is_visible(timeout=1500):
                log.info("Fairplay Bet login authenticated (Account presented with KYC document upload prompt)")
                return True, proof_path, None

            # --- Check 3: Authenticated state indicators ---
            has_deposit = page.locator('button:has-text("Deposit"), a:has-text("Deposit")').first.is_visible(timeout=3000)
            has_account = page.locator('a:has-text("My Account"), button:has-text("My Account"), .user-balance').first.is_visible(timeout=2000)
            pw_still_visible = page.locator('input[type="password"]:visible').first.is_visible(timeout=1000)

            if (has_deposit or has_account) and not pw_still_visible:
                log.info("Fairplay Bet login successfully verified")
                return True, proof_path, None
            else:
                log.warning("Fairplay Bet login failed: authenticated account indicators not found")
                return False, proof_path, "Login failed: account dashboard not reached — account may require email verification"

        except Exception as e:
            log.error(f"Fairplay Bet login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "fairplay_login_error", e)
            return False, bundle.screenshot_path, str(e)



