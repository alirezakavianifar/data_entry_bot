"""
DragonBet Registration Adapter (Playbook Engineering Platform).
Target: DragonBet (https://dragonbet.co.uk/)
Origin: Affiliate redirect via https://bettinglounge.co.uk/out/ZRKfXhAAACkAStm_/?offer=betting
"""

import datetime
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from sites.base import (
    BaseSiteAdapter,
    extract_clean_error_message,
    is_already_registered_error,
    is_pending_verification_error,
    human_type,
    human_click,
    human_pause,
    human_scroll,
    handle_playbook_deposit_step,
    handle_playbook_safer_gambling_no_limit,
    select_matching_playbook_address,
)
from core.password_gen import generate_password
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import (
    get_logger,
    capture_failure_bundle,
    capture_success_screenshot,
    capture_login_proof_screenshot,
)


class DragonBetAdapter(BaseSiteAdapter):
    """Adapter for DragonBet on Playbook Engineering platform with human-like interactions."""

    def __init__(
        self,
        promo_url: str = "https://bettinglounge.co.uk/out/ZRKfXhAAACkAStm_/?offer=betting",
        site_id: str = "dragonbet",
        site_name: str = "DragonBet"
    ):
        super().__init__(
            site_id=site_id,
            site_name=site_name,
            default_promo_url=promo_url,
            requires_uk_ip=True
        )

    def navigate(self, page: Page, promo_url: Optional[str] = None) -> bool:
        """Navigates to DragonBet via promo affiliate link with direct fallback."""
        url = promo_url or self.default_promo_url
        log = get_logger(site_id=self.site_id, step="navigate")
        log.info(f"Navigating to {self.site_name} target URL: {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            log.warning(f"Initial navigation to {url} hit timeout/error: {e}")

        # Wait for redirect to finish if currently on bettinglounge
        for _ in range(15):
            if "dragonbet.co.uk" in (page.url or ""):
                break
            page.wait_for_timeout(1000)

        # Fallback if redirect did not complete
        if "dragonbet.co.uk" not in (page.url or ""):
            log.warning(f"Affiliate redirect did not reach dragonbet.co.uk (current: {page.url}). Falling back to direct URL...")
            try:
                page.goto("https://dragonbet.co.uk/", wait_until="domcontentloaded", timeout=30000)
            except Exception as ex:
                log.error(f"Fallback navigation to dragonbet.co.uk failed: {ex}")
                return False

        page.wait_for_timeout(2000)
        return True

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        return self.register_client(client=client, page=page, dry_run=False, password=password)

    def register_client(self, client: Client, page: Page, dry_run: bool = False, password: Optional[str] = None) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="register_client")
        log.info(f"Starting {self.site_name} registration for {client.full_name} (Dry-run: {dry_run})")

        password_used = password or generate_password()

        if dry_run and page is None:
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=client.email,
                password=password_used,
                account_reference=f"DRY-RUN-{self.site_id.upper()}",
                notes="Dry-run completed successfully"
            )

        try:
            # 1. Navigation & Redirect Wait (ensure on dragonbet.co.uk)
            for _ in range(10):
                if "dragonbet.co.uk" in (page.url or ""):
                    break
                page.wait_for_timeout(1000)

            if "dragonbet.co.uk" not in (page.url or ""):
                target_url = self.default_promo_url
                log.info(f"Navigating to {self.site_name} promo URL: {target_url}")
                page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_url(lambda u: "dragonbet.co.uk" in u, timeout=15000)
                except Exception:
                    pass
                human_pause(page, 2.0, 3.5)

            # 2. Dismiss Cookiebot consent banner if visible
            cookie_btn = page.locator(
                '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, '
                '#CybotCookiebotDialogBodyButtonAccept, '
                'button:has-text("Allow all"), '
                'button:has-text("Accept")'
            ).first
            if cookie_btn.is_visible(timeout=4000):
                log.info(f"Accepting Cookiebot consent on {self.site_name}...")
                human_click(cookie_btn, page)
                human_pause(page, 0.8, 1.5)

            # 3. Open sign up drawer if credentials form is not already open
            email_sel = 'input[data-test="email-input"], input[data-test="landing-page-email-input"], input[placeholder*="Email"], input[type="email"]'
            email_inp = page.locator(email_sel).first
            if not email_inp.is_visible(timeout=3000):
                reg_btn = page.locator(
                    'a[data-test="account-navigation-signup-link"], '
                    'button[data-test="account-navigation-signup-link"], '
                    'a:has-text("Sign Up"), '
                    'button:has-text("Sign Up"), '
                    'a:has-text("Join")'
                ).first
                if reg_btn.is_visible(timeout=3000):
                    log.info(f"Clicking Sign Up CTA on {self.site_name}...")
                    human_click(reg_btn, page)
                    human_pause(page, 2.0, 3.5)

            # Fallback if drawer didn't open: navigate to direct signup URL
            email_inp = page.locator(email_sel).first
            if not email_inp.is_visible(timeout=3000):
                log.info(f"Opening direct signup URL on {self.site_name}...")
                page.goto("https://dragonbet.co.uk/?account=signup", wait_until="domcontentloaded", timeout=25000)
                human_pause(page, 2.0, 3.0)
                if cookie_btn.is_visible(timeout=2000):
                    human_click(cookie_btn, page)
                    human_pause(page, 0.5, 1.0)

            # Wait for email input
            page.wait_for_selector(email_sel, timeout=12000)
            email_inp = page.locator(email_sel).first

            # 4. Fill Step 1: Credentials
            log.info(f"Filling Step 1: Email={client.email}")
            human_type(email_inp, client.email, page=page, min_delay_ms=25, max_delay_ms=60)
            human_pause(page, 0.3, 0.6)

            pw_inp = page.locator(
                'input[data-test="create-password-input"], '
                'input[data-test="landing-page-password-input"], '
                'input[data-test="password-input"], '
                'input[placeholder*="Password"], '
                'input[type="password"]'
            ).first
            log.info("Filling Step 1: Password")
            human_type(pw_inp, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
            human_pause(page, 0.4, 0.8)

            cont_btn = page.locator(
                'button[data-test="create-account-button"], '
                'button[data-test="landing-page-create-account-button"], '
                'button[data-test="sign-up-button"], '
                'button:has-text("Create Account"), '
                'button:has-text("Continue")'
            ).first
            log.info(f"Submitting Step 1 on {self.site_name}...")
            human_click(cont_btn, page)
            human_pause(page, 2.5, 4.0)

            # Check for Step 1 validation errors (e.g. email already exists)
            step1_err = page.locator('div[data-test="error-message"], [class*="ErrorMessage"], .field-error, div[class*="error"], span[class*="error"], p[class*="error"], [data-test*="error"]').first
            if step1_err.is_visible(timeout=1500):
                err_txt = step1_err.inner_text().strip()
                if is_already_registered_error(err_txt) or any(kw in err_txt.lower() for kw in ["already exists", "in use", "already registered", "taken"]):
                    log.warning(f"[DUPLICATE] {self.site_name}: Client {client.full_name} is ALREADY REGISTERED ({err_txt})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password_used,
                        error_summary=f"Already registered: {err_txt}",
                        screenshot_path=bundle.screenshot_path if bundle else None,
                        dom_snapshot_path=bundle.dom_snapshot_path if bundle else None
                    )

            # 5. Step 2: Personal Details & Address
            fn_sel = 'input[data-test="first-name-input"], input[name="first-name"], input[data-test="input-name"]'
            page.wait_for_selector(fn_sel, timeout=12000)

            # Title Selection (Mr / Ms)
            title_val = getattr(client, "resolved_title", None) or getattr(client, "title", None) or "Mr."
            is_female = str(title_val).strip().lower() in ["mrs", "mrs.", "ms", "ms.", "miss"]
            prefix = "ms" if is_female else "mr"
            title_text = "Ms" if is_female else "Mr"
            log.info(f"Selecting '{title_text}' title on {self.site_name}")
            
            title_label = page.locator(
                f'label:has(input[name="{prefix}"]), '
                f'div[data-component="TitleChooseBox"]:has([data-test="{prefix}-title-choose-box"]) label, '
                f'[data-test="{prefix}-title-choose-box"]'
            ).first
            if title_label.is_visible(timeout=3000):
                human_click(title_label, page)
                human_pause(page, 0.3, 0.6)

            # Guarantee radio is checked
            title_radio = page.locator(f'input[name="{prefix}"], input[value="{prefix}"]').first
            if title_radio.count() > 0 and not title_radio.is_checked():
                try:
                    title_radio.check(force=True)
                    log.info(f"Forced check on {prefix} radio button")
                except Exception:
                    pass

            # First and Last Name
            fn_inp = page.locator(fn_sel).first
            log.info(f"Filling First Name: {client.first_name}")
            human_type(fn_inp, client.first_name, page=page, min_delay_ms=30, max_delay_ms=65)
            human_pause(page, 0.2, 0.4)

            ln_inp = page.locator('input[data-test="last-name-input"], input[name="last-name"], input[data-test="input-surname"]').first
            log.info(f"Filling Last Name: {client.last_name}")
            human_type(ln_inp, client.last_name, page=page, min_delay_ms=30, max_delay_ms=65)
            human_pause(page, 0.2, 0.4)

            # Date of Birth (day, month, year)
            dob_d = page.locator('input[data-test="day-input"], input[data-test="dob-day-input"], input[name="day"]').first
            dob_d.fill(str(int(client.dob_day)).zfill(2))
            human_pause(page, 0.2, 0.3)

            dob_m = page.locator('input[data-test="month-input"], input[data-test="dob-month-input"], input[name="month"]').first
            dob_m.fill(str(int(client.dob_month)).zfill(2))
            human_pause(page, 0.2, 0.3)

            dob_y = page.locator('input[data-test="year-input"], input[data-test="dob-year-input"], input[name="year"]').first
            dob_y.fill(str(client.dob_year))
            human_pause(page, 0.2, 0.4)

            # Phone Number
            phone_inp = page.locator('input[data-test="number-input"], input[data-test="phone-input"], input[type="tel"]').first
            cleaned_phone = client.phone
            if cleaned_phone.startswith("+44"):
                cleaned_phone = cleaned_phone[3:]
            cleaned_phone = cleaned_phone.lstrip("0")
            log.info(f"Filling Phone: {cleaned_phone}")
            human_type(phone_inp, cleaned_phone, page=page, min_delay_ms=30, max_delay_ms=70)
            human_pause(page, 0.3, 0.6)

            # Address Lookup
            postcode_inp = page.locator('input[data-test="postcode-input"]').first
            if postcode_inp.is_visible(timeout=3000):
                log.info(f"Entering Postcode: {client.postcode}")
                human_type(postcode_inp, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.5, 1.0)
                select_matching_playbook_address(page, client, log=log)
                human_pause(page, 1.0, 2.0)

            # 6. Dry-run Check
            if dry_run:
                log.info(f"Dry-run active: Skipping final Agree & Join on {self.site_name}")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password_used,
                    account_reference=f"DRY-RUN-{self.site_id.upper()}",
                    notes="Dry-run completed successfully"
                )

            # 7. Final Agree & Join Submission
            log.info(f"Reviewing details before submitting {self.site_name} registration...")
            agree_btn = page.locator('button[data-test="agree-and-join-button"], button:has-text("Agree & Join"), button:has-text("Complete")').first
            if agree_btn.is_visible(timeout=4000):
                agree_btn.scroll_into_view_if_needed()
                human_pause(page, 1.5, 2.5)
                log.info(f"Clicking Agree & Join on {self.site_name}...")
                human_click(agree_btn, page)
                human_pause(page, 3.0, 5.0)

            # 8. Check for immediate submission error (e.g. Operating license duplicate or KYC)
            page.wait_for_timeout(4000)
            error_el = page.locator(
                '[data-test="error-message-content"]:visible, '
                'aside[data-test="SignUpStepsContainer"] [class*="MessageWrapper"]:visible, '
                '[data-test*="error"]:visible'
            ).first
            if error_el.is_visible(timeout=2500):
                raw_err_text = error_el.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text) or "operating license" in raw_err_text.lower() or "regret to inform" in raw_err_text.lower()
                final_err_msg = clean_err or raw_err_text

                if is_duplicate:
                    log.warning(f"[DUPLICATE] {self.site_name}: Client {client.full_name} is ALREADY REGISTERED ({final_err_msg})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password_used,
                        error_summary=f"Already registered: {final_err_msg}",
                        screenshot_path=bundle.screenshot_path if bundle else None,
                        dom_snapshot_path=bundle.dom_snapshot_path if bundle else None
                    )
                else:
                    log.warning(f"{self.site_name} registration rejected: {final_err_msg}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "server_error", Exception(final_err_msg))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        password=password_used,
                        error_summary=final_err_msg,
                        screenshot_path=bundle.screenshot_path if bundle else None,
                        dom_snapshot_path=bundle.dom_snapshot_path if bundle else None
                    )

            # 9. Post-Submission Polling & Verification Loop
            import time
            log.info(f"Waiting for {self.site_name} onboarding & in-platform confirmation (up to 35s)...")
            start_poll = time.time()
            is_confirmed = False
            has_auth = False
            poll_count = 0

            while time.time() - start_poll < 35:
                poll_count += 1
                elapsed = int(time.time() - start_poll)

                # 1. Skip Deposit drawer if open
                if handle_playbook_deposit_step(page, log if poll_count % 4 == 1 else None):
                    log.info(f"{self.site_name}: Pressed SKIP on deposit step at {elapsed}s")
                    page.wait_for_timeout(1000)

                # 2. Only handle Safer Gambling if genuine onboarding modal/step is active
                is_safer_gambling_active = any(
                    page.locator(s).first.is_visible(timeout=150)
                    for s in [
                        'text="Net deposit limits"',
                        'aside[data-test="SignUpStepsContainer"] legend:has-text("SAFER GAMBLING")',
                        'aside[data-test="SignUpStepsContainer"] h2:has-text("SAFER GAMBLING")',
                        'aside[data-test="SignUpStepsContainer"] h1:has-text("SAFER GAMBLING")',
                        'aside[data-test="SignUpStepsContainer"] button[data-test="next-button"]',
                    ]
                )
                if is_safer_gambling_active:
                    handle_playbook_safer_gambling_no_limit(page, log if poll_count % 4 == 1 else None)
                    if handle_playbook_deposit_step(page, log if poll_count % 4 == 1 else None):
                        log.info(f"{self.site_name}: Pressed SKIP on deposit step following Safer Gambling at {elapsed}s")
                        page.wait_for_timeout(1000)

                # Check if onboarding drawer/modal is still active
                is_onboarding_open = any(
                    page.locator(sel).first.is_visible(timeout=100)
                    for sel in [
                        'aside[data-test="SignUpStepsContainer"]:has-text("Net deposit limits")',
                        'aside[data-test="SignUpStepsContainer"] [data-test="skip-button"]',
                        'div[role="dialog"]:has-text("SAFER GAMBLING")',
                        'div[class*="modal"]:has-text("SAFER GAMBLING")'
                    ]
                )

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
                    log.info(f"{self.site_name} registration successful with KYC / Account Verification Pending.")
                    success_shot = capture_success_screenshot(page, client.client_id, self.site_id)
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.SUCCESS,
                        email=client.email,
                        username=client.email,
                        password=password_used,
                        account_reference=f"{self.site_name}-Direct (⚠️ KYC/Verification Pending)",
                        screenshot_path=success_shot,
                        login_verified=False
                    )

                if (not is_onboarding_open or has_explicit_error) and is_already_registered_error(body_text):
                    log.warning(f"[DUPLICATE] {self.site_name}: Client {client.full_name} is ALREADY REGISTERED ({body_text[:100]})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password_used,
                        error_summary=f"Already registered: {body_text[:100]}",
                        screenshot_path=bundle.screenshot_path if bundle else None
                    )

                # Authenticated session check
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

                if (has_auth or elapsed > 5) and not is_onboarding_open:
                    log.info(f"{self.site_name} onboarding dismissed and session confirmed at {elapsed}s!")
                    is_confirmed = True
                    break

                page.wait_for_timeout(1000)

            # Safety Gate
            if is_confirmed and not is_onboarding_open:
                log.info(f"{self.site_name} registration confirmed successfully!")
                success_shot = capture_login_proof_screenshot(page, client.client_id, self.site_id) if has_auth else capture_success_screenshot(page, client.client_id, self.site_id)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password_used,
                    account_reference=f"{self.site_name}-Direct (Active Session Verified)" if has_auth else f"{self.site_name}-Direct",
                    screenshot_path=success_shot,
                    login_verified=has_auth,
                    login_screenshot_path=success_shot if has_auth else None
                )
            else:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "onboarding_stuck" if is_onboarding_open else "verify_submission")
                err_msg = f"{self.site_name} safer gambling onboarding modal could not be dismissed" if is_onboarding_open else f"{self.site_name} submission could not be confirmed within 35s"
                log.warning(err_msg)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password_used,
                    error_summary=err_msg,
                    screenshot_path=bundle.screenshot_path if bundle else None,
                    dom_snapshot_path=bundle.dom_snapshot_path if bundle else None
                )

        except Exception as e:
            err = str(e)
            log.error(f"{self.site_name} registration error: {err}")
            try:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "register", e)
                screenshot_path = str(bundle.screenshot_path) if bundle else None
                dom_snapshot_path = str(bundle.dom_path) if bundle else None
            except Exception:
                screenshot_path = None
                dom_snapshot_path = None

            status = RegistrationStatus.MANUAL_REVIEW if is_pending_verification_error(err) else RegistrationStatus.FAILED
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=status,
                email=client.email,
                error_summary=err,
                screenshot_path=screenshot_path,
                dom_snapshot_path=dom_snapshot_path
            )


class BettingLounge2Adapter(DragonBetAdapter):
    """Adapter specifically for DragonBet under the Betting Lounge #2 configuration."""

    def __init__(
        self,
        promo_url: str = "https://bettinglounge.co.uk/out/ZRKfXhAAACkAStm_/?offer=betting",
        site_id: str = "bettinglounge2",
        site_name: str = "DragonBet (Betting Lounge #2)"
    ):
        super().__init__(
            promo_url=promo_url,
            site_id=site_id,
            site_name=site_name
        )
