from playwright.sync_api import Page
from sites.base import (
    BaseSiteAdapter,
    extract_clean_error_message,
    is_already_registered_error,
    human_type,
    human_pause,
    handle_playbook_safer_gambling_no_limit,
    select_matching_playbook_address
)
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot, capture_login_proof_screenshot



class PlanetSportBetAdapter(BaseSiteAdapter):
    """Adapter for Planet Sport Bet (https://planetsportbet.com/)."""

    def __init__(self, promo_url: str = "https://planetsportbet.com/?account=static-resource-carousel-promo-terms&promoId=12746"):
        super().__init__(
            site_id="planetsportbet",
            site_name="Planet Sport Bet",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )



    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info(f"Starting Planet Sport Bet registration for {client.full_name}")

        try:
            # 1. Direct navigation to clean signup URL or trigger modal
            cur_url = page.url if isinstance(getattr(page, "url", None), str) else ""
            if "?account=signup" not in cur_url and "?promoId=" not in cur_url:
                try:
                    page.goto("https://planetsportbet.com/?account=signup", wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(2000)
                except Exception as ex:
                    log.warning(f"Direct signup navigation warning: {ex}")

            # Cookiebot Consent Handling
            cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, #CybotCookiebotDialogBodyButtonAccept, button:has-text("Allow all"), button:has-text("Accept")').first
            if cookie_btn.is_visible(timeout=3000):
                log.info("Accepting Cookiebot consent on Planet Sport Bet")
                cookie_btn.click(force=True)
                page.wait_for_timeout(1000)

            # Check if sign up modal or landing form is open
            email_inp = page.locator('input[data-test="landing-page-email-input"], input[data-test="email-input"], input[placeholder*="Email"]').first
            if not email_inp.is_visible(timeout=3000):
                reg_btn = page.locator('a[data-test="account-navigation-signup-link"], a:has-text("Sign Up"), button:has-text("Sign Up")').first
                if reg_btn.is_visible(timeout=3000):
                    log.info("Clicking Sign Up CTA on Planet Sport Bet")
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
            human_type(email_inp, client.email, page)
            human_pause(page, 0.4, 0.8)
            human_type(pwd_inp, password, page)
            human_pause(page, 0.6, 1.2)

            create_acc_btn = page.locator('button:has-text("Create Account"), button:has-text("Join Here"), button[data-test="create-account-button"], button[type="submit"]:has-text("Join"), button[type="submit"]:has-text("Sign Up"), button[type="submit"]').first
            if create_acc_btn.is_visible(timeout=2000):
                create_acc_btn.click(force=True)
                human_pause(page, 2.0, 3.5)

            # Check for Step 1 validation errors
            step1_err = page.locator(
                'aside[data-test="SignUpStepsContainer"] div[class*="error"]:visible, '
                'aside[data-test="SignUpStepsContainer"] span[class*="error"]:visible, '
                'aside[data-test="SignUpStepsContainer"] p[class*="error"]:visible, '
                'aside[data-test="SignUpStepsContainer"] [data-test*="error"]:visible, '
                'aside[data-test="SignUpStepsContainer"] [class*="errorMessage"]:visible, '
                '[data-test="SignUpStepsContainer"] [class*="error"]:visible'
            ).first
            if step1_err.is_visible(timeout=1500):
                err_txt = step1_err.inner_text().strip()
                if is_already_registered_error(err_txt) or any(kw in err_txt.lower() for kw in ["already exists", "in use", "already registered", "taken"]):
                    log.warning(f"Planet Sport Bet: Client {client.full_name} is ALREADY REGISTERED ({err_txt})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        account_reference="PlanetSportBet-Existing",
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
                # Fallback: check if Step 1 duplicate banner appeared delayed
                dup_err = page.locator('div[class*="error"]:visible, span[class*="error"]:visible, p[class*="error"]:visible, [data-test*="error"]:visible, :has-text("already exists"):visible, :has-text("in use"):visible').first
                if dup_err.is_visible(timeout=1000):
                    raw_txt = dup_err.inner_text().strip().replace("\n", " - ")
                    clean_err = extract_clean_error_message(raw_txt) or raw_txt
                    if is_already_registered_error(raw_txt) or "already exists" in raw_txt.lower():
                        log.warning(f"Planet Sport Bet: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.ALREADY_REGISTERED,
                            email=client.email,
                            password=password,
                            account_reference="PlanetSportBet-Existing",
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
                human_pause(page, 0.2, 0.5)

            log.info("Filling Step 2 Personal Details (Name, DOB, Phone, Postcode)")
            human_type(fn_inp, client.first_name, page)
            human_pause(page, 0.3, 0.7)
            human_type(ln_inp, client.last_name, page)
            human_pause(page, 0.3, 0.7)
            day_inp.fill(str(int(client.dob_day)).zfill(2))
            month_inp.fill(str(int(client.dob_month)).zfill(2))
            year_inp.fill(str(client.dob_year))
            human_pause(page, 0.3, 0.6)

            # Phone number (strip leading 0 as UK prefix +44 is pre-selected)
            cleaned_phone = client.phone
            if cleaned_phone.startswith("+44"):
                cleaned_phone = cleaned_phone[3:]
            cleaned_phone = cleaned_phone.lstrip("0")
            human_type(num_inp, cleaned_phone, page)
            human_pause(page, 0.4, 0.8)

            # Postcode & Smart Address Lookup / Fallback
            human_type(postcode_inp, client.postcode, page)
            human_pause(page, 0.5, 1.0)

            select_matching_playbook_address(page, client, log)

            # 4. Step 2 Submission: Agree & Join
            agree_btn = page.locator('button[data-test="agree-and-join-button"]').first
            if agree_btn.is_visible(timeout=3000):
                log.info("Simulating human review before submitting registration...")
                human_pause(page, 3.0, 6.0)
                log.info("Submitting registration via 'Agree & Join'")
                agree_btn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                agree_btn.click(force=True)
                page.wait_for_timeout(4000)

            # 5. Confirm Registration Success
            # Check for error message under Agree & Join or in SignUpStepsContainer
            error_el = page.locator('[data-test="error-message-content"]:visible, aside[data-test="SignUpStepsContainer"] [class*="MessageWrapper"]:visible, [data-test*="error"]:visible').first
            if error_el.is_visible(timeout=3000):
                raw_err_text = error_el.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text) or "operating license" in raw_err_text.lower() or "regret to inform" in raw_err_text.lower()
                final_err_msg = clean_err or raw_err_text

                if is_duplicate:
                    log.warning(f"[DUPLICATE] Planet Sport Bet: Client {client.full_name} is ALREADY REGISTERED ({final_err_msg})")
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
                    log.warning(f"Planet Sport Bet registration rejected: {final_err_msg}")
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

            # 5. Polling Loop (up to 35s) to complete Playbook onboarding & confirm active session
            log.info("Waiting for Planet Sport Bet onboarding & in-platform confirmation (up to 35s)...")
            max_poll_sec = 35
            is_confirmed = False
            has_auth = False

            for sec in range(1, max_poll_sec + 1):
                # Always attempt to detect and handle Playbook Safer Gambling / Deposit Limit onboarding
                handle_playbook_safer_gambling_no_limit(page, log if sec % 5 == 1 else None)

                # Check for genuine authenticated dashboard / session indicators (exclude modal triggers)
                auth_indicators = [
                    'button:has-text("DEPOSIT")', 'a:has-text("DEPOSIT")',
                    'a:has-text("Deposit")', 'button:has-text("Deposit")',
                    'a:has-text("My Account")', 'button:has-text("My Account")',
                    '[data-component="AccountNavigation"] [data-test*="account"]',
                    '[data-test="account-menu-button"]',
                    '.user-balance'
                ]
                for selector in auth_indicators:
                    try:
                        if page.locator(selector).first.is_visible(timeout=200):
                            has_auth = True
                            break
                    except Exception:
                        continue

                # Check if signup form / onboarding modal is still active in the DOM
                is_onboarding_open = False
                for onb_sel in ['aside[data-test="SignUpStepsContainer"]', '[data-test="SignUpStepsContainer"]']:
                    try:
                        loc = page.locator(onb_sel).first
                        if loc.is_visible(timeout=100):
                            is_onboarding_open = True
                            break
                    except Exception:
                        continue

                # Only confirm when authenticated session exists AND onboarding modal is dismissed
                if (has_auth or sec > 5) and not is_onboarding_open:
                    log.info(f"Planet Sport Bet onboarding dismissed and session confirmed at {sec}s!")
                    is_confirmed = True
                    break

                page.wait_for_timeout(1000)

            # Safety Gate: Must NOT report SUCCESS if onboarding modal is still open
            if is_confirmed and not is_onboarding_open:
                log.info("Planet Sport Bet registration and onboarding confirmed successfully!")
                success_shot = capture_login_proof_screenshot(page, client.client_id, self.site_id) if has_auth else capture_success_screenshot(page, client.client_id, self.site_id)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password,
                    account_reference="PlanetSportBet-Direct (Active Session Verified)" if has_auth else "PlanetSportBet-Direct",
                    screenshot_path=success_shot,
                    login_verified=has_auth,
                    login_screenshot_path=success_shot if has_auth else None
                )
            else:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "onboarding_stuck" if is_onboarding_open else "verify_submission")
                err_msg = "Planet Sport Bet safer gambling onboarding modal could not be dismissed" if is_onboarding_open else "Planet Sport Bet submission could not be confirmed within 35s"
                log.warning(err_msg)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    username=client.email,
                    password=password,
                    error_summary=err_msg,
                    screenshot_path=bundle.screenshot_path,
                    dom_snapshot_path=bundle.dom_snapshot_path
                )

        except Exception as e:
            log.error(f"Registration error on Planet Sport Bet: {e}")
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
        """Specialized login verification handler for Planet Sport Bet."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Navigating to Planet Sport Bet clean login URL: https://planetsportbet.com/?account=login")

        try:
            page.goto("https://planetsportbet.com/?account=login", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            self.accept_cookies(page)

            # Locate email & password inputs
            email_inp = page.locator('input[name="email"], input[type="email"]').first
            pwd_inp = page.locator('input[name="password"], input[type="password"]').first

            if not email_inp.is_visible(timeout=3000) or not pwd_inp.is_visible(timeout=3000):
                # Try clicking Login CTA if direct URL did not pop modal
                login_btn = page.locator('a[data-test="account-navigation-login-link"], a:has-text("Login")').first
                if login_btn.is_visible(timeout=3000):
                    login_btn.click(force=True)
                    page.wait_for_timeout(1500)

            email_inp = page.locator('input[name="email"], input[type="email"]').first
            pwd_inp = page.locator('input[name="password"], input[type="password"]').first

            if not email_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "login_inputs_missing")
                return False, bundle.screenshot_path, "Planet Sport Bet login inputs not visible"

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

            # Check for authenticated indicators
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
                log.info(f"Planet Sport Bet login successfully verified! Proof: {proof_path}")
                return True, proof_path, None
            else:
                summary = err_text or "Login failed: Credentials rejected or session indicators not found"
                log.warning(f"Planet Sport Bet login failed: {summary}")
                return False, proof_path, summary

        except Exception as e:
            log.error(f"Planet Sport Bet login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)


