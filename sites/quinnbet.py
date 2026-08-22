from playwright.sync_api import Page
from sites.base import BaseSiteAdapter, extract_clean_error_message, is_already_registered_error
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot, capture_login_proof_screenshot


class QuinnbetAdapter(BaseSiteAdapter):
    """Adapter for QuinnBet (https://www.quinnbet.com/)."""

    def __init__(self, promo_url: str = "https://www.quinnbet.com/uk/offers/sports-welcome-offer-ukcb50lo"):
        super().__init__(
            site_id="quinnbet",
            site_name="QuinnBet",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )


    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info(f"Starting QuinnBet multi-step registration for {client.full_name}")

        def _dismiss_cookies():
            for sel in [
                '#onetrust-accept-btn-handler',
                'button:has-text("Accept All Cookies")',
                '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
                '#CybotCookiebotDialogBodyButtonAccept',
                'button:has-text("Allow all")',
                'button:has-text("Accept")'
            ]:
                try:
                    b = page.locator(sel).first
                    if b.is_visible(timeout=1000):
                        log.info(f"Accepting cookie consent ({sel}) on QuinnBet")
                        b.click(force=True)
                        page.wait_for_timeout(800)
                        return True
                except Exception:
                    pass
            return False

        try:
            # 1. Dismiss cookies on landing page
            _dismiss_cookies()

            # 2. Locate and click Register / Join CTA
            if not page.url.endswith("/register"):
                reg_btn = page.locator('button[data-testid="register-button"], a[href*="/register"], a:has-text("JOIN"), button:has-text("JOIN"), a:has-text("Register")').first
                if reg_btn.is_visible(timeout=4000):
                    log.info("Clicking Register CTA on QuinnBet")
                    reg_btn.click(force=True)
                    page.wait_for_timeout(2500)

            _dismiss_cookies()

            # 3. Step 1: Credentials (Email & Password)
            page.locator("form app-reg-step-one input, form input.mat-input-element, form input.form-field__input").first.wait_for(timeout=8000)
            step1_inputs = page.locator("form app-reg-step-one input, form input.mat-input-element, form input.form-field__input").all()
            if len(step1_inputs) < 2:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step1_inputs_missing")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="QuinnBet Step 1 inputs missing",
                    screenshot_path=bundle.screenshot_path
                )

            log.info(f"Filling Step 1 credentials for {client.email}")
            step1_inputs[0].fill(client.email)
            step1_inputs[1].fill(password)
            page.wait_for_timeout(500)

            create_acc_btn = page.locator('button:has-text("CREATE ACCOUNT"), button:has-text("CONTINUE"), form button[type="button"]:has-text("CREATE")').first
            if create_acc_btn.is_visible(timeout=2000):
                create_acc_btn.click(force=True)
                page.wait_for_timeout(3500)

            _dismiss_cookies()

            # Check for Step 1 validation error
            step1_err = page.locator('div.alert-danger, span.error-message, mat-error, p.error').first
            if step1_err.is_visible(timeout=1000):
                err_text = step1_err.inner_text().strip()
                if any(kw in err_text.lower() for kw in ["already exists", "in use", "invalid", "taken"]):
                    log.warning(f"QuinnBet Step 1 validation error: {err_text}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step1_error", Exception(err_text))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        password=password,
                        error_summary=f"Step 1 error: {err_text}",
                        screenshot_path=bundle.screenshot_path
                    )

            # 4. Step 2: Personal Details
            page.locator("app-reg-step-two input").first.wait_for(timeout=8000)
            step2_inputs = page.locator("app-reg-step-two input:visible").all()
            if len(step2_inputs) >= 3:
                log.info("Filling Step 2 Personal Details (Name, Phone)")
                step2_inputs[0].fill(client.first_name)
                step2_inputs[1].fill(client.last_name)

                # Format UK phone number (10 digits without leading 0 / +44)
                phone_clean = client.phone
                if phone_clean.startswith("+44"):
                    phone_clean = phone_clean[3:]
                phone_clean = phone_clean.lstrip("0")
                log.info(f"Filling normalized UK phone: {phone_clean}")

                phone_inp = page.locator("app-reg-step-two input.digit-only, app-reg-step-two input[type='tel']").first
                phone_inp.click()
                phone_inp.fill(phone_clean)
                phone_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
                page.wait_for_timeout(300)

            # DOB Dropdowns
            dob_days = page.locator('select-dropdown[formcontrolname="date"], select[formcontrolname="date"]').first
            dob_months = page.locator('select-dropdown[formcontrolname="month"], select[formcontrolname="month"]').first
            dob_years = page.locator('select-dropdown[formcontrolname="year"], select[formcontrolname="year"]').first

            if dob_days.is_visible(timeout=1500):
                try:
                    dob_days.click(force=True)
                    page.wait_for_timeout(200)
                    day_str = str(int(client.dob_day)).zfill(2)
                    dob_days.locator('li', has_text=day_str).first.click(force=True)
                except Exception as e:
                    log.warning(f"Error selecting DOB Day: {e}")

            if dob_months.is_visible(timeout=1500):
                try:
                    dob_months.click(force=True)
                    page.wait_for_timeout(200)
                    month_str = str(int(client.dob_month)).zfill(2)
                    dob_months.locator('li', has_text=month_str).first.click(force=True)
                except Exception as e:
                    log.warning(f"Error selecting DOB Month: {e}")

            if dob_years.is_visible(timeout=1500):
                try:
                    dob_years.click(force=True)
                    page.wait_for_timeout(200)
                    year_str = str(client.dob_year)
                    dob_years.locator('li', has_text=year_str).first.click(force=True)
                except Exception as e:
                    log.warning(f"Error selecting DOB Year: {e}")

            page.wait_for_timeout(500)

            # Address: Use Manual Address Entry
            manual_btn = page.locator('span:has-text("Enter Manually"), a:has-text("Enter Manually"), div:has-text("Enter Manually")').last
            if manual_btn.is_visible(timeout=2000):
                log.info("Clicking 'Enter Manually' for Address entry")
                manual_btn.click(force=True)
                page.wait_for_timeout(500)

            inputs_after_manual = page.locator("app-reg-step-two input:visible").all()
            if len(inputs_after_manual) >= 7:
                log.info(f"Filling manual address: {client.address_line1}, {client.town_city}, {client.postcode}")
                inputs_after_manual[4].fill(client.address_line1)
                inputs_after_manual[5].fill(client.town_city)
                inputs_after_manual[6].fill(client.postcode)
                page.wait_for_timeout(500)
            elif len(inputs_after_manual) >= 4:
                # Fallback to search input
                inputs_after_manual[3].fill(client.postcode)
                page.wait_for_timeout(500)

            # Check for any Step 2 inline error messages before submit
            step2_err = page.locator('app-reg-step-two mat-error:visible, app-reg-step-two .error:visible, app-reg-step-two .alert:visible').first
            if step2_err.is_visible(timeout=1000):
                err_text = step2_err.inner_text().strip()
                if "already exists" in err_text.lower():
                    log.warning(f"⚠️ QuinnBet Step 2 duplicate error: {err_text}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered", Exception(err_text))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        error_summary=f"Already registered: {err_text}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )

            # Step 2 Submit: Continue button
            continue_btn = page.locator('#registerModalSubmitBtn, button:has-text("CONTINUE"), button[type="submit"]:has-text("CONTINUE")').first
            if continue_btn.is_visible(timeout=3000):
                log.info("Submitting Step 2 via CONTINUE button")
                continue_btn.click(force=True)
                page.wait_for_timeout(5000)

            # 5. Step 3: Marketing Preferences & 18+ Terms Acceptance
            step3_modal = page.locator("app-reg-step-three").first
            if step3_modal.is_visible(timeout=4000):
                log.info("Step 3 Marketing & Terms modal detected on QuinnBet")

                # Select 'None' or 'Select All' for preferences
                page.evaluate("""() => {
                    const labels = Array.from(document.querySelectorAll('app-reg-step-three label.checkbox-label'));
                    const noneLabel = labels.find(l => l.innerText.includes('None')) || labels.find(l => l.innerText.includes('Select All'));
                    if (noneLabel) {
                        noneLabel.click();
                    }
                    const termsLabel = labels.find(l => l.innerText.includes('18'));
                    if (termsLabel) {
                        termsLabel.click();
                    }
                }""")
                page.wait_for_timeout(500)

                finish_btn = page.locator("app-reg-step-three #registerModalSubmitBtn, app-reg-step-three button:has-text('FINISH'), button:has-text('FINISH')").first
                if finish_btn.is_visible(timeout=2000):
                    log.info("Clicking FINISH button on Step 3")
                    finish_btn.click(force=True)
                    page.wait_for_timeout(5000)

            # Check for error message in registration
            error_modal = page.locator('app-register .alert:visible, app-register .error:visible, mat-error:visible, div[role="alert"]:visible').first
            if error_modal.is_visible(timeout=1500):
                raw_err_text = error_modal.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text)

                if is_duplicate:
                    log.warning(f"⚠️ QuinnBet: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
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
                    log.warning(f"QuinnBet registration rejected: {clean_err}")
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
                '[data-testid*="user-menu"]', '[data-testid*="balance"]',
                '.user-balance', '.account-balance', '[class*="deposit-modal"]'
            ]
            has_auth = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1500):
                        has_auth = True
                        break
                except Exception:
                    continue

            is_reg_open = page.locator('app-register:visible, input[name="email"]:visible').first.is_visible(timeout=1000)

            if has_auth and not is_reg_open:
                log.info("QuinnBet registration confirmed successfully!")
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
                    account_reference="QuinnBet-Direct",
                    screenshot_path=success_shot
                )
            else:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "verify_submission")
                log.warning("QuinnBet registration submission could not be confirmed")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Registration was not confirmed by QuinnBet",
                    screenshot_path=bundle.screenshot_path
                )

        except Exception as e:
            log.error(f"Registration error on QuinnBet: {e}")
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
        """Specialized login verification handler for QuinnBet."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Navigating to QuinnBet sports page for login: https://www.quinnbet.com/uk/sports")

        try:
            page.goto("https://www.quinnbet.com/uk/sports", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2500)

            # Accept OneTrust cookies if present
            ot_btn = page.locator('#onetrust-accept-btn-handler, button:has-text("Accept All Cookies")').first
            if ot_btn.is_visible(timeout=2500):
                log.info("Accepting OneTrust cookie consent on QuinnBet")
                ot_btn.click(force=True)
                page.wait_for_timeout(1000)

            # Click LOG IN button
            login_btn = page.locator('button[data-testid="login-button"], a[data-testid="login-button"], button:has-text("LOG IN")').first
            if login_btn.is_visible(timeout=4000):
                log.info("Clicking LOG IN button on QuinnBet")
                login_btn.click(force=True)
                page.wait_for_timeout(2500)

            # Locate username / email & password inputs inside app-login
            email_inp = page.locator("app-login input[type='email'], app-login #txtEmail input, app-login input.mat-input-element").first
            pwd_inp = page.locator("app-login input[type='password'], app-login #txtPassword input").first

            if not email_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "login_inputs_missing")
                return False, bundle.screenshot_path, "QuinnBet login inputs not visible"

            log.info(f"Filling credentials for {username_or_email}")
            email_inp.fill(username_or_email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            submit_btn = page.locator("app-login button:has-text('LOG IN'), app-login button[type='submit']").first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            page.wait_for_timeout(5000)

            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

            # Check if login modal is still present
            login_modal = page.locator("app-login, .login-modal, .loginModal").first
            is_modal_open = False
            try:
                if login_modal.is_visible(timeout=1500):
                    is_modal_open = True
            except Exception:
                pass

            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-testid*="user-menu"]', '[data-testid*="balance"]',
                '.user-balance', '.account-balance', '.wallet-balance'
            ]
            is_authenticated = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1000):
                        is_authenticated = True
                        break
                except Exception:
                    continue

            # Check for error message
            err_el = page.locator('app-login .alert:visible, app-login .error:visible, app-login mat-error:visible, div.alert-danger:visible').first
            err_msg = None
            if err_el.is_visible(timeout=1000):
                err_msg = err_el.inner_text().strip().replace("\n", " - ")

            if is_authenticated and not is_modal_open and not err_msg:
                log.info(f"QuinnBet login successfully verified! Proof: {proof_path}")
                return True, proof_path, None
            else:
                summary = err_msg or "Login failed: Credentials rejected (login modal remained open or session not active)"
                log.warning(f"QuinnBet login failed: {summary}")
                return False, proof_path, summary


        except Exception as e:
            log.error(f"QuinnBet login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)
