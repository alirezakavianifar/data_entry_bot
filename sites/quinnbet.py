from playwright.sync_api import Page
from sites.base import (
    BaseSiteAdapter,
    extract_clean_error_message,
    is_already_registered_error,
    human_mouse_move,
    human_pause,
    human_click
)
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
                # Inject visual cursor so the user can visibly track the mouse movement down across the screen
                try:
                    page.evaluate("""() => {
                        if (document.getElementById('playwright-visual-cursor')) return;
                        const cursor = document.createElement('div');
                        cursor.id = 'playwright-visual-cursor';
                        cursor.style.position = 'fixed';
                        cursor.style.zIndex = '999999999';
                        cursor.style.width = '20px';
                        cursor.style.height = '20px';
                        cursor.style.borderRadius = '50%';
                        cursor.style.background = 'rgba(255, 0, 0, 0.85)';
                        cursor.style.border = '2px solid white';
                        cursor.style.boxShadow = '0 0 10px rgba(0,0,0,0.6)';
                        cursor.style.pointerEvents = 'none';
                        cursor.style.transform = 'translate(-50%, -50%)';
                        cursor.style.top = '120px';
                        cursor.style.left = '960px';
                        cursor.style.transition = 'width 0.1s, height 0.1s';
                        document.body.appendChild(cursor);

                        window.addEventListener('mousemove', (e) => {
                            cursor.style.left = e.clientX + 'px';
                            cursor.style.top = e.clientY + 'px';
                        });
                        window.addEventListener('mousedown', () => {
                            cursor.style.background = 'rgba(0, 255, 0, 0.9)';
                            cursor.style.width = '28px';
                            cursor.style.height = '28px';
                        });
                        window.addEventListener('mouseup', () => {
                            cursor.style.background = 'rgba(255, 0, 0, 0.85)';
                            cursor.style.width = '20px';
                            cursor.style.height = '20px';
                        });
                    }""")
                except Exception:
                    pass

                # Prioritize promotional offer bottom CTA (e.g. green 'Join' button at the bottom of the offer description)
                # to ensure qualifying for the higher welcome offer rather than the generic top-right header button
                promo_btn = page.locator('a.btn-green:has-text("Join"), a.btn-green:has-text("JOIN"), .qs-intro a.btn-green, a.btn-green, main a:has-text("JOIN"), div.qs-intro a').first
                if promo_btn.is_visible(timeout=3000):
                    log.info("Visibly moving mouse down to QuinnBet promotional offer JOIN button at bottom of page (a.btn-green)...")
                    promo_btn.scroll_into_view_if_needed()
                    page.wait_for_timeout(400)

                    # Start mouse from top center and move down visibly to the bottom button
                    try:
                        page.mouse.move(960, 140)
                        page.wait_for_timeout(300)
                        box = promo_btn.bounding_box()
                        if box:
                            target_x = box["x"] + box["width"] / 2
                            target_y = box["y"] + box["height"] / 2
                            human_mouse_move(page, target_x, target_y, steps=30)
                            promo_btn.evaluate("el => { el.style.outline = '3px solid #00ff00'; el.style.boxShadow = '0 0 20px #00ff00'; }")
                            promo_btn.hover()
                            human_pause(page, 1.2, 2.0)
                    except Exception:
                        pass

                    human_click(promo_btn, page)
                    page.wait_for_timeout(2500)
                else:
                    reg_btn = page.locator('button[data-testid="register-button"], a[href*="/register"], a:has-text("JOIN"), button:has-text("JOIN"), a:has-text("Register")').first
                    if reg_btn.is_visible(timeout=4000):
                        log.info("Clicking fallback Register CTA on QuinnBet")
                        human_click(reg_btn, page)
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
            step1_inputs[0].evaluate("el => el.dispatchEvent(new Event('blur', {bubbles: true}))")
            page.wait_for_timeout(1000)

            # Check for Step 1 validation error (e.g. Email already registered)
            is_email_invalid = False
            try:
                is_email_invalid = step1_inputs[0].evaluate("el => el.classList.contains('ng-invalid')")
            except Exception:
                pass

            step1_err_loc = page.locator('app-reg-step-one .mat-error, app-reg-step-one .field--error-msg, app-reg-step-one .error, app-reg-step-one div.alert-danger, .mat-error, mat-error')
            err_text = ""
            if step1_err_loc.count() > 0:
                for idx in range(step1_err_loc.count()):
                    txt = step1_err_loc.nth(idx).inner_text().strip()
                    if txt:
                        err_text = txt
                        break

            if is_email_invalid or err_text:
                if any(kw in err_text.lower() for kw in ["already exists", "already registered", "in use", "invalid", "taken"]) or "already" in err_text.lower():
                    log.warning(f"[DUPLICATE] QuinnBet Step 1 duplicate error: {err_text or 'Email already registered'}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered", Exception(err_text or "Email already registered"))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        error_summary=f"Already registered: {err_text or 'Email already registered'}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                elif err_text:
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

            create_acc_btn = page.locator('button:has-text("CREATE ACCOUNT"), button:has-text("CONTINUE"), form button[type="button"]:has-text("CREATE")').first
            if create_acc_btn.is_visible(timeout=2000):
                create_acc_btn.click(force=True)
                page.wait_for_timeout(3500)

            _dismiss_cookies()

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
                    log.warning(f"[DUPLICATE] QuinnBet Step 2 duplicate error: {err_text}")
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
                    page.wait_for_timeout(2000)

            # Dynamic Adaptive Polling & Settle Loop (up to 90s) for in-platform auto-verification
            log.info("Monitoring QuinnBet auto-verification (30s initial settle, up to 90s if KYC is in progress)...")
            max_poll_sec = 90
            min_settle_sec = 30
            is_confirmed = False
            auto_verified_banner = False
            kyc_manual_required = False

            for sec in range(1, max_poll_sec + 1):
                # 1. Check for duplicate / already registered error message
                error_modal = page.locator('app-register .alert:visible, app-register .error:visible, mat-error:visible, div[role="alert"]:visible').first
                if error_modal.is_visible(timeout=300):
                    raw_err_text = error_modal.inner_text().strip().replace("\n", " - ")
                    clean_err = extract_clean_error_message(raw_err_text)
                    is_duplicate = is_already_registered_error(raw_err_text)

                    if is_duplicate:
                        log.warning(f"[DUPLICATE] QuinnBet: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.ALREADY_REGISTERED,
                            email=client.email,
                            password=password,
                            account_reference="QuinnBet-Existing",
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

                # 2. Check and auto-dismiss Net Deposit Limit popup
                deposit_limit_dismiss = page.locator('button:has-text("NO, MAYBE LATER"), button:has-text("No, Maybe Later"), button:has-text("NO, THANKS"), button:has-text("No thanks"), button:has-text("MAYBE LATER")').first
                if deposit_limit_dismiss.is_visible(timeout=300):
                    try:
                        log.info("Dismissing 'Set your Net Deposit limit' modal on QuinnBet")
                        deposit_limit_dismiss.click(force=True)
                        page.wait_for_timeout(800)
                    except Exception:
                        pass

                # 3. Check for auto-verification completion status (Fast Success Exit after min settle)
                verif_toast = page.locator(':has-text("auto-verification was successfully completed"), :has-text("auto-verification completed"), :has-text("Great news! Your auto-verification")').first
                if verif_toast.is_visible(timeout=300):
                    log.info(f"QuinnBet in-platform auto-verification successfully completed at {sec}s!")
                    auto_verified_banner = True
                    is_confirmed = True
                    if sec >= min_settle_sec:
                        break

                # 4. Check for manual KYC document upload request
                doc_req = page.locator(':has-text("upload your documents"), :has-text("unable to verify your details automatically"), :has-text("verify your identity manually"), :has-text("Proof of ID")').first
                if doc_req.is_visible(timeout=200):
                    log.warning(f"QuinnBet: Manual KYC document upload requested at {sec}s")
                    kyc_manual_required = True
                    is_confirmed = True
                    if sec >= min_settle_sec:
                        break

                # 5. Check for active in-progress spinner
                verif_in_prog = page.locator(':has-text("auto-verification is currently in progress"), :has-text("Hang tight"), :has-text("auto-verification in progress")').first
                is_still_verifying = verif_in_prog.is_visible(timeout=300)
                if is_still_verifying:
                    is_confirmed = True
                    if sec % 5 == 0 or sec == 1:
                        log.info(f"QuinnBet: Auto-verification actively in progress ({sec}s/{max_poll_sec}s)...")

                # 6. Check for genuine authenticated session indicators
                auth_indicators = [
                    'button:has-text("DEPOSIT")', 'a:has-text("DEPOSIT")',
                    'a:has-text("Deposit")', 'button:has-text("Deposit")',
                    'a:has-text("My Account")', 'button:has-text("My Account")',
                    '[data-testid*="user-menu"]', '[data-testid*="balance"]',
                    '.user-balance', '.account-balance', '[class*="deposit-modal"]'
                ]
                for selector in auth_indicators:
                    try:
                        if page.locator(selector).first.is_visible(timeout=200):
                            is_confirmed = True
                            break
                    except Exception:
                        continue

                is_reg_open = page.locator('app-register:visible, input[name="email"]:visible').first.is_visible(timeout=200)
                if not is_reg_open:
                    is_confirmed = True

                # If past min_settle_sec and not actively stuck on in-progress spinner, we can conclude
                if sec >= min_settle_sec and not is_still_verifying:
                    log.info(f"QuinnBet settling completed cleanly at {sec}s!")
                    break

                page.wait_for_timeout(1000)

            # Final check and dismiss any remaining dialogs
            try:
                page.evaluate("""() => {
                    const dismissBtns = Array.from(document.querySelectorAll('button')).filter(b => 
                        b.innerText && (b.innerText.includes('NO, MAYBE LATER') || b.innerText.includes('MAYBE LATER') || b.innerText.includes('No thanks'))
                    );
                    dismissBtns.forEach(b => b.click());
                }""")
            except Exception:
                pass

            if is_confirmed or auto_verified_banner:
                if auto_verified_banner:
                    ref = "QuinnBet-Direct (Auto-Verified)"
                elif kyc_manual_required:
                    ref = "QuinnBet-Direct (KYC Document Required)"
                else:
                    ref = "QuinnBet-Direct (KYC In Progress)"

                log.info(f"QuinnBet registration confirmed: {ref}")
                success_shot = capture_login_proof_screenshot(page, client.client_id, self.site_id)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password,
                    account_reference=ref,
                    screenshot_path=success_shot,
                    login_verified=True,
                    login_screenshot_path=success_shot
                )
            else:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "verify_submission")
                log.warning("QuinnBet registration submission could not be confirmed within 30s")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Registration was not confirmed by QuinnBet within 30s",
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

            page.wait_for_timeout(3000)

            # Check and auto-dismiss Net Deposit Limit popup if triggered upon login
            deposit_limit_dismiss = page.locator('button:has-text("NO, MAYBE LATER"), button:has-text("No, Maybe Later"), button:has-text("NO, THANKS"), button:has-text("No thanks"), button:has-text("MAYBE LATER")').first
            if deposit_limit_dismiss.is_visible(timeout=1500):
                try:
                    log.info("Dismissing 'Set your Net Deposit limit' modal post-login on QuinnBet")
                    deposit_limit_dismiss.click(force=True)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

            # Check if login modal is still present
            login_modal = page.locator("app-login input#txtPassword, app-login button:has-text('LOG IN')").first
            is_modal_open = False
            try:
                if login_modal.is_visible(timeout=1500):
                    is_modal_open = True
            except Exception:
                pass

            auth_indicators = [
                'button:has-text("DEPOSIT")', 'a:has-text("DEPOSIT")',
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

            if (is_authenticated or not is_modal_open) and not err_msg:
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
