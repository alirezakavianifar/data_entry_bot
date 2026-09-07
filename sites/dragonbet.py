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
    human_mouse_move,
    handle_playbook_deposit_step,
    handle_playbook_safer_gambling_no_limit,
    select_matching_playbook_address
)
from core.password_gen import generate_password
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle


class DragonBetAdapter(BaseSiteAdapter):
    """Adapter for DragonBet on Playbook Engineering platform with human-like interactions."""

    def __init__(self, promo_url: str = "https://bettinglounge.co.uk/out/ZRKfXhAAACkAStm_/?offer=betting"):
        super().__init__(
            site_id="dragonbet",
            site_name="DragonBet",
            default_promo_url=promo_url,
            requires_uk_ip=True
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        return self.register_client(client=client, page=page, dry_run=False, password=password)

    def register_client(self, client: Client, page: Page, dry_run: bool = False, password: Optional[str] = None) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="register_client")
        log.info(f"Starting DragonBet registration for {client.full_name} (Dry-run: {dry_run})")

        screenshot_path: Optional[str] = None
        dom_snapshot_path: Optional[str] = None
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
                account_reference="DRY-RUN-DRAGONBET",
                notes="Dry-run completed successfully"
            )

        try:
            target_url = self.default_promo_url
            log.info(f"Navigating to DragonBet promo URL: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2.0, 3.5)

            # Dismiss Cookiebot consent
            cookie_btn = page.locator(
                '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, '
                '#CybotCookiebotDialogBodyButtonAccept, '
                'button:has-text("Allow all"), '
                'button:has-text("Accept")'
            ).first
            if cookie_btn.is_visible(timeout=3000):
                log.info("Accepting Cookiebot consent on DragonBet with human click...")
                human_click(cookie_btn, page)
                human_pause(page, 0.8, 1.4)

            # Step 1: Open sign up drawer if needed
            email_sel = 'input[data-test="landing-page-email-input"], input[data-test="email-input"], input[placeholder*="Email"], input[type="email"]'
            email_inp = page.locator(email_sel).first
            if not email_inp.is_visible(timeout=5000):
                reg_btn = page.locator('a[data-test="account-navigation-signup-link"], a:has-text("Sign Up"), button:has-text("Sign Up"), a:has-text("Join")').first
                if reg_btn.is_visible(timeout=3000):
                    log.info("Clicking Sign Up CTA on DragonBet with human click...")
                    human_click(reg_btn, page)
                    human_pause(page, 2.0, 3.5)

            email_inp = page.locator(email_sel).first
            page.wait_for_selector(email_sel, timeout=12000)

            log.info(f"Filling Step 1: Email={client.email}")
            human_type(email_inp, client.email, page=page, min_delay_ms=25, max_delay_ms=60)
            human_pause(page, 0.3, 0.6)

            pw_inp = page.locator('input[data-test="landing-page-password-input"], input[data-test="password-input"], input[type="password"]').first
            log.info("Filling Step 1: Password")
            human_type(pw_inp, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
            human_pause(page, 0.4, 0.8)

            cont_btn = page.locator('button[data-test="landing-page-create-account-button"], button[data-test="sign-up-button"], button:has-text("Continue")').first
            log.info("Submitting Step 1 on DragonBet with human click...")
            human_click(cont_btn, page)
            human_pause(page, 2.0, 3.5)

            # Step 2: Personal details
            page.wait_for_selector('input[data-test="first-name-input"], input[data-test="input-name"]', timeout=12000)
            fn_inp = page.locator('input[data-test="first-name-input"], input[data-test="input-name"]').first
            human_type(fn_inp, client.first_name, page=page, min_delay_ms=30, max_delay_ms=65)
            human_pause(page, 0.3, 0.6)

            ln_inp = page.locator('input[data-test="last-name-input"], input[data-test="input-surname"]').first
            human_type(ln_inp, client.last_name, page=page, min_delay_ms=30, max_delay_ms=65)
            human_pause(page, 0.3, 0.6)

            phone_inp = page.locator('input[data-test="phone-input"], input[type="tel"]').first
            clean_phone = client.phone.lstrip("0") if client.phone.startswith("0") else client.phone
            human_type(phone_inp, clean_phone, page=page, min_delay_ms=35, max_delay_ms=75)
            human_pause(page, 0.3, 0.6)

            dob_d = page.locator('input[data-test="dob-day-input"]').first
            human_type(dob_d, client.dob_day, page=page, min_delay_ms=40, max_delay_ms=75)
            human_pause(page, 0.2, 0.4)

            dob_m = page.locator('input[data-test="dob-month-input"]').first
            human_type(dob_m, client.dob_month, page=page, min_delay_ms=40, max_delay_ms=75)
            human_pause(page, 0.2, 0.4)

            dob_y = page.locator('input[data-test="dob-year-input"]').first
            human_type(dob_y, client.dob_year, page=page, min_delay_ms=40, max_delay_ms=75)
            human_pause(page, 0.3, 0.6)

            cont_btn2 = page.locator('button[data-test="step-2-continue-button"], button:has-text("Continue")').first
            log.info("Submitting Step 2 on DragonBet with human click...")
            human_click(cont_btn2, page)
            human_pause(page, 2.0, 3.5)

            # Step 3: Address lookup
            postcode_inp = page.locator('input[data-test="postcode-input"]').first
            if postcode_inp.is_visible(timeout=5000):
                human_type(postcode_inp, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.5, 1.0)

                find_btn = page.locator('button[data-test="find-address-button"], button:has-text("Find Address")').first
                if find_btn.is_visible(timeout=2000):
                    human_click(find_btn, page)
                    human_pause(page, 1.5, 2.5)

                select_matching_playbook_address(page, client, log=log)

            cont_btn3 = page.locator('button[data-test="step-3-continue-button"], button:has-text("Continue")').first
            if cont_btn3.is_visible(timeout=3000):
                log.info("Submitting Step 3 on DragonBet with human click...")
                human_click(cont_btn3, page)
                human_pause(page, 2.0, 3.5)

            # Step 4: Safer gambling & Deposit skip
            handle_playbook_safer_gambling_no_limit(page)
            handle_playbook_deposit_step(page)

            if dry_run:
                log.info("Dry-run active: Skipping final Agree & Join on DragonBet")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password_used,
                    account_reference="DRY-RUN-DRAGONBET",
                    notes="Dry-run completed successfully"
                )

            # Review pause before final submission
            log.info("Reviewing details before submitting DragonBet registration...")
            human_scroll(page, distance_y=200, steps=4)
            human_pause(page, 1.5, 2.5)

            # Final Agree & Join
            agree_btn = page.locator('button[data-test="agree-and-join-button"], button:has-text("Agree & Join"), button:has-text("Complete")').first
            if agree_btn.is_visible(timeout=4000):
                log.info("Clicking Agree & Join on DragonBet with human click...")
                human_click(agree_btn, page)
                human_pause(page, 4.0, 7.0)

            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=client.email,
                password=password_used,
                account_reference=f"DRAGONBET_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

        except Exception as e:
            err = str(e)
            log.error(f"DragonBet registration error: {err}")
            try:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "register", e)
                screenshot_path = str(bundle.screenshot_path) if bundle else None
                dom_snapshot_path = str(bundle.dom_path) if bundle else None
            except Exception:
                pass

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
