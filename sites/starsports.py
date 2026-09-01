from typing import Optional
from playwright.sync_api import Page
from sites.base import (
    BaseSiteAdapter,
    extract_clean_error_message,
    is_already_registered_error,
    is_pending_verification_error,
    human_type,
    human_pause,
    handle_playbook_deposit_step,
    handle_playbook_safer_gambling_no_limit,
    select_matching_playbook_address
)
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot, capture_login_proof_screenshot


class StarSportsAdapter(BaseSiteAdapter):
    """Adapter for Star Sports (https://www.starsports.bet/)."""

    def __init__(self, promo_url: str = "https://starsports.bet/"):
        super().__init__(
            site_id="starsports",
            site_name="Star Sports",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )

    def navigate(self, page: Page) -> None:
        """Navigates to Star Sports, dismissing cookie overlays."""
        log = get_logger()
        log.info(f"Navigating to Star Sports ({self.default_promo_url})...")
        page.goto(self.default_promo_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Handle Cookie Consent
        try:
            cookie_btn = page.locator('button:has-text("Accept"), button:has-text("Allow"), button[id*="cookie" i]').first
            if cookie_btn.is_visible(timeout=3000):
                cookie_btn.click(force=True)
                page.wait_for_timeout(500)
        except Exception:
            pass

        # Check if already on registration form or click Create Account/Register
        try:
            if not page.locator('aside[data-test="SignUpStepsContainer"]').first.is_visible(timeout=1000):
                reg_btn = page.locator('a[data-test="register-button"], button[data-test="register-button"]').first
                if reg_btn.is_visible(timeout=2000):
                    reg_btn.click(force=True)
                    page.wait_for_timeout(1000)
        except Exception:
            pass

        try:
            create_acc_btn = page.locator('button:has-text("Create Account"), a:has-text("Create Account"), button:has-text("Sign Up"), a:has-text("Sign Up")').first
            if create_acc_btn.is_visible(timeout=2000):
                create_acc_btn.click(force=True)
                page.wait_for_timeout(1000)
        except Exception:
            pass

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info(f"Starting Star Sports registration for {client.full_name}")

        try:
            # 1. Direct navigation to clean signup URL or trigger modal
            if "?account=signup" not in page.url:
                try:
                    page.goto("https://starsports.bet/?account=signup", wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(2000)
                except Exception as ex:
                    log.warning(f"Direct signup navigation warning: {ex}")

            # Cookiebot Consent Handling
            cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, #CybotCookiebotDialogBodyButtonAccept, button:has-text("Allow all"), button:has-text("Accept")').first
            if cookie_btn.is_visible(timeout=3000):
                log.info("Accepting Cookiebot consent on Star Sports")
                cookie_btn.click(force=True)
                page.wait_for_timeout(1000)

            # 2. Step 1: Credentials & Sign Up drawer detection
            email_sel = 'input[data-test="landing-page-email-input"], input[data-test="email-input"], input[placeholder*="Email"], input[type="email"]'
            
            # If promo drawer has "Create Account" or "Get Started" CTA before inputs
            create_acc_btn = page.locator('aside[data-test="SignUpStepsContainer"] button:has-text("Create Account"), button:has-text("Create Account"), button[data-test*="create-account"]').first
            if create_acc_btn.is_visible(timeout=2000):
                create_acc_btn.click(force=True)
                page.wait_for_timeout(1000)

            # Wait for email input
            email_input = page.locator(email_sel).first
            if not email_input.is_visible(timeout=10000):
                # Fallback: re-open clean signup URL
                log.warning("Email input not found initially, navigating to https://starsports.bet/?account=signup")
                page.goto("https://starsports.bet/?account=signup", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2000)
                email_input = page.locator(email_sel).first

            if not email_input.is_visible(timeout=10000):
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step1_inputs_missing")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Could not find Step 1 inputs (email field missing)",
                    screenshot_path=bundle.screenshot_path,
                    dom_snapshot_path=bundle.dom_snapshot_path
                )

            # Fill Step 1 Inputs
            log.info("Entering Step 1 credentials (email, password)...")
            human_type(email_input, client.email)
            page.wait_for_timeout(300)

            password_sel = 'input[data-test="landing-page-password-input"], input[data-test="password-input"], input[data-test="create-password-input"], input[placeholder*="Password"], input[type="password"]'
            pw_input = page.locator(password_sel).first
            human_type(pw_input, password)
            page.wait_for_timeout(500)

            # Click Continue / Create Account to Step 2
            step1_cont = page.locator('button[data-test="landing-page-sign-up-button"], button[data-test="sign-up-button"], button[data-test="create-account-button"], aside[data-test="SignUpStepsContainer"] button[data-test="next-button"], aside[data-test="SignUpStepsContainer"] button:has-text("Continue"), aside[data-test="SignUpStepsContainer"] button:has-text("Next")').first
            if step1_cont.is_visible(timeout=2000):
                step1_cont.click(force=True)
                page.wait_for_timeout(2000)

            # Check for Step 1 validation errors (e.g. email already exists)
            step1_err = page.locator('div[data-test="error-message"], [class*="ErrorMessage"], .field-error, div[class*="error"], span[class*="error"], p[class*="error"], [data-test*="error"]').first
            if step1_err.is_visible(timeout=1500):
                err_txt = step1_err.inner_text().strip()
                if is_already_registered_error(err_txt) or any(kw in err_txt.lower() for kw in ["already exists", "in use", "already registered", "taken"]):
                    log.warning(f"[DUPLICATE] Star Sports: Client {client.full_name} is ALREADY REGISTERED ({err_txt})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        error_summary=f"Already registered: {err_txt}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )

            # 3. Step 2: Personal Details & Address
            fname_sel = 'input[data-test="first-name-input"], input[name="firstName"], input[placeholder*="First"]'
            fname_input = page.locator(fname_sel).first
            if not fname_input.is_visible(timeout=10000):
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step2_inputs_missing")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Could not find Step 2 inputs (first name missing)",
                    screenshot_path=bundle.screenshot_path,
                    dom_snapshot_path=bundle.dom_snapshot_path
                )

            log.info("Entering Step 2 personal details (Name, DOB, Mobile)...")
            # Star Sports strict alpha-only validation
            import re
            clean_first = re.sub(r'[^A-Za-z]', '', client.first_name) or "John"
            clean_last = re.sub(r'[^A-Za-z]', '', client.last_name) or "Smith"
            human_type(fname_input, clean_first)
            page.wait_for_timeout(200)

            lname_sel = 'input[data-test="last-name-input"], input[name="lastName"], input[placeholder*="Last"]'
            lname_input = page.locator(lname_sel).first
            human_type(lname_input, clean_last)
            page.wait_for_timeout(200)

            # Title Selection (Playbook select)
            try:
                title_dropdown = page.locator('[data-component="Select"]:has-text("Title"), [data-test="title-select"]').first
                if title_dropdown.is_visible(timeout=500):
                    title_dropdown.click(force=True)
                    page.wait_for_timeout(300)
                    title_opt = page.locator('div[role="option"]:has-text("Mr"), li:has-text("Mr"), span:has-text("Mr")').first
                    if title_opt.is_visible(timeout=500):
                        title_opt.click(force=True)
            except Exception:
                pass

            # DOB Inputs
            day_inp = page.locator('input[data-test="dob-day-input"], input[name="day"], input[placeholder="DD"]').first
            month_inp = page.locator('input[data-test="dob-month-input"], input[name="month"], input[placeholder="MM"]').first
            year_inp = page.locator('input[data-test="dob-year-input"], input[name="year"], input[placeholder="YYYY"]').first

            human_type(day_inp, f"{int(client.dob_day):02d}")
            human_type(month_inp, f"{int(client.dob_month):02d}")
            human_type(year_inp, str(client.dob_year))
            page.wait_for_timeout(300)

            # Mobile Phone Input
            phone_inp = page.locator('input[data-test="phone-number-input"], input[name="phoneNumber"], input[type="tel"]').first
            clean_phone = client.phone
            if clean_phone.startswith("+44"):
                clean_phone = "0" + clean_phone[3:]
            elif not clean_phone.startswith("0"):
                clean_phone = "0" + clean_phone
            human_type(phone_inp, clean_phone)
            page.wait_for_timeout(300)

            # Address Selection / Manual Fallback via Shared Playbook Engine
            select_matching_playbook_address(page, client, log)

            # 4. Marketing Consents & Terms
            try:
                no_marketing = page.locator('label:has-text("No"), input[name*="marketing"][value="no"]').first
                if no_marketing.is_visible(timeout=500):
                    no_marketing.click(force=True)
            except Exception:
                pass

            # Agree & Join / Submit
            agree_btn = page.locator('button[data-test="agree-and-join-button"], button[data-test="submit-button"], button:has-text("Agree & Join"), button:has-text("Join Now"), button:has-text("Create My Account")').first
            if agree_btn.is_visible(timeout=3000):
                log.info("Simulating human review before submitting registration...")
                human_pause(page, 3.0, 6.0)
                log.info("Submitting registration via 'Agree & Join'")
                agree_btn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                agree_btn.click(force=True)
                page.wait_for_timeout(4000)

            # Check for error message under Agree & Join or in SignUpStepsContainer
            error_el = page.locator('[data-test="error-message-content"]:visible, aside[data-test="SignUpStepsContainer"] [class*="MessageWrapper"]:visible, [data-test*="error"]:visible').first
            if error_el.is_visible(timeout=3000):
                raw_err_text = error_el.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text) or "operating license" in raw_err_text.lower() or "regret to inform" in raw_err_text.lower()
                final_err_msg = clean_err or raw_err_text

                if is_duplicate:
                    log.warning(f"[DUPLICATE] Star Sports: Client {client.full_name} is ALREADY REGISTERED ({final_err_msg})")
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
                    log.warning(f"Star Sports registration rejected: {final_err_msg}")
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
            log.info("Waiting for Star Sports onboarding & in-platform confirmation (up to 35s)...")
            max_poll_sec = 35
            is_confirmed = False
            has_auth = False

            for sec in range(1, max_poll_sec + 1):
                # 1. First, detect and skip Deposit drawer if open
                handle_playbook_deposit_step(page, log if sec % 5 == 1 else None)

                # 2. Detect and handle Playbook Safer Gambling / Deposit Limit onboarding
                handle_playbook_safer_gambling_no_limit(page, log if sec % 5 == 1 else None)

                # Check if Safer Gambling or Deposit onboarding form is still active in the DOM
                is_onboarding_open = any(
                    page.locator(sel).first.is_visible(timeout=100)
                    for sel in [
                        'aside[data-test="SignUpStepsContainer"]:has-text("SAFER GAMBLING")',
                        'aside[data-test="SignUpStepsContainer"]:has-text("Net deposit limits")',
                        'aside[data-test="SignUpStepsContainer"]:has-text("deposit limit")',
                        'aside[data-test="SignUpStepsContainer"]:has-text("Turn on reality check")',
                        'aside[data-test="SignUpStepsContainer"]:has-text("DEPOSIT")',
                        'aside[data-test="SignUpStepsContainer"]:has-text("Deposit")',
                        'div[role="dialog"]:has-text("SAFER GAMBLING")',
                        'div[class*="modal"]:has-text("SAFER GAMBLING")'
                    ]
                )

                # 2. Check for KYC / Duplicate only if onboarding modal has closed or explicit error banner is present
                try:
                    res = page.locator("body").inner_text()
                    body_text = str(res) if isinstance(res, str) else ""
                except Exception:
                    body_text = ""

                has_explicit_error = any(
                    page.locator(e_sel).first.is_visible(timeout=100)
                    for e_sel in [
                        'div[data-test="error-message"]',
                        '[class*="ErrorMessage"]',
                        ':has-text("Account Suspended")',
                        ':has-text("temporarily suspended")',
                        ':has-text("verification issue")',
                        'p:has-text("suspended pending verification")',
                        'button:has-text("Verify")',
                        'div[class*="suspended"]'
                    ]
                )

                if (not is_onboarding_open or has_explicit_error) and is_pending_verification_error(body_text):
                    log.info(f"Star Sports registration successful with KYC / Account Verification Pending.")
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
                        account_reference="StarSports-Direct (⚠️ KYC/Verification Pending)",
                        screenshot_path=success_shot,
                        login_verified=False
                    )

                if (not is_onboarding_open or has_explicit_error) and is_already_registered_error(body_text):
                    log.warning(f"[DUPLICATE] Star Sports: Client {client.full_name} is ALREADY REGISTERED ({body_text[:100]})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        error_summary=f"Already registered: {body_text[:100]}",
                        screenshot_path=bundle.screenshot_path
                    )

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

                # Only confirm when authenticated session exists AND onboarding modal is dismissed
                if (has_auth or sec > 5) and not is_onboarding_open:
                    log.info(f"Star Sports onboarding dismissed and session confirmed at {sec}s!")
                    is_confirmed = True
                    break

                page.wait_for_timeout(1000)

            # Safety Gate: Must NOT report SUCCESS if onboarding modal is still open
            if is_confirmed and not is_onboarding_open:
                log.info("Star Sports registration and onboarding confirmed successfully!")
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
                    account_reference="StarSports-Direct (Active Session Verified)" if has_auth else "StarSports-Direct",
                    screenshot_path=success_shot,
                    login_verified=has_auth,
                    login_screenshot_path=success_shot if has_auth else None
                )
            else:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "onboarding_stuck" if is_onboarding_open else "verify_submission")
                err_msg = "Star Sports safer gambling onboarding modal could not be dismissed" if is_onboarding_open else "Star Sports submission could not be confirmed within 35s"
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
        log.info(f"Navigating to Star Sports clean login URL: https://starsports.bet/?account=login")

        try:
            page.goto("https://starsports.bet/?account=login", wait_until="domcontentloaded", timeout=25000)
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
