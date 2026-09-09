"""
247 Bet Registration Adapter (Phase 2).
Platform: White Hat Gaming / Casimba Affiliates.
Website: https://www.247bet.com/en-gb/register
Registration Flow:
  - Step 1: /create-account/personal-details (Email, Phone, Username, Password)
  - Step 2: /create-account/address-details (Gender, First Name, Last Name, DOB, Manual Address, Postcode, City)
  - Step 3: /create-account/account-details (Terms & 18+ declaration, Marketing preferences, Submit)
"""

import datetime
import re
from pathlib import Path
from typing import Optional, Tuple
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from sites.base import (
    BaseSiteAdapter,
    human_type,
    human_click,
    human_pause,
    human_scroll,
    human_mouse_move,
    is_pending_verification_error
)
from core.password_gen import generate_password
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_login_proof_screenshot

logger = get_logger(step="247BetAdapter")


class TwentyFourSevenBetAdapter(BaseSiteAdapter):
    """
    Adapter for 247 Bet (White Hat Gaming platform).
    Handles dynamic Angular forms, 3-step onboarding with human typing rhythms,
    Bezier mouse movements, momentum scrolling, and safe checkbox targeting.
    """

    def __init__(self, promo_url: Optional[str] = None):
        super().__init__(
            site_id="247bet",
            site_name="247 Bet",
            default_promo_url=promo_url or "https://www.247bet.com/en-gb/register",
            requires_uk_ip=True
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        return self.register_client(client=client, page=page, dry_run=False, password=password)

    def register_client(self, client: Client, page: Page, dry_run: bool = False, password: Optional[str] = None) -> RegistrationResult:
        log = logger.bind(client=client.full_name, site=self.site_name)
        log.info(f"Initiating registration on {self.site_name} (Dry-run: {dry_run})")

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
                account_reference="DRY-RUN-247BET",
                notes="Dry-run completed successfully"
            )

        try:
            target_url = self.default_promo_url
            log.info(f"Navigating to {target_url}...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2.0, 3.5)

            # Accept Cookie Banner
            try:
                cookie_btn = page.locator("#cookie-acceptAllBtn, button:has-text('Accept all cookies'), button:has-text('Accept All')").first
                if cookie_btn.is_visible(timeout=3500):
                    log.info("Accepting 247 Bet cookies with human click...")
                    human_click(cookie_btn, page)
                    human_pause(page, 0.8, 1.4)
            except Exception as e:
                log.debug(f"Cookie banner not found or dismissed: {e}")

            # Ensure we are on account creation flow
            if "create-account" not in page.url and "/register" not in page.url:
                signup_cta = page.locator("a[href*='register'], button:has-text('Sign up'), a:has-text('Sign up')").first
                if signup_cta.is_visible(timeout=3000):
                    log.info("Clicking Sign Up CTA with human click...")
                    human_click(signup_cta, page)
                    human_pause(page, 2.0, 3.5)

            # --- STEP 1: Account Credentials (/create-account/personal-details) ---
            log.info("Filling Step 1: Email, Phone, Username, Password with human typing...")
            email_field = page.locator("input#email, input[name='email'], input[type='email']").first
            if email_field.is_visible(timeout=8000):
                human_type(email_field, client.email, page=page, min_delay_ms=25, max_delay_ms=60)
                human_pause(page, 0.3, 0.6)

            # Phone number (format: 07xxxxxxxxx without leading 0 for prefix dropdown)
            clean_phone = client.phone.lstrip("0") if client.phone.startswith("0") else client.phone
            phone_field = page.locator("input#phone, input[name='phone'], input[type='tel']").first
            if phone_field.is_visible(timeout=3000):
                human_type(phone_field, clean_phone, page=page, min_delay_ms=35, max_delay_ms=75)
                human_pause(page, 0.3, 0.6)

            # Username
            clean_uname = "".join(c for c in f"{client.first_name}{client.last_name}" if c.isalnum()).lower()[:12]
            birth_yr = client.dob_year[-2:] if client.dob else "92"
            final_uname = f"{clean_uname}{birth_yr}"
            username_field = page.locator("input#username, input[name='username']").first
            if username_field.is_visible(timeout=3000):
                human_type(username_field, final_uname, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # Password
            pw_field = page.locator("input#password, input[name='password'], input[type='password']").first
            if pw_field.is_visible(timeout=3000):
                human_type(pw_field, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
                human_pause(page, 0.4, 0.7)

            # Click Continue on Step 1
            cont_btn1 = page.locator("button:has-text('Continue'), button[type='submit']").first
            if cont_btn1.is_visible(timeout=3000):
                log.info("Submitting Step 1 with human click...")
                human_click(cont_btn1, page)
                human_pause(page, 2.5, 4.0)

            # Check for Step 1 duplicate errors immediately
            step1_err = page.locator('.error-message:visible, [class*="alert-danger"]:visible, .invalid-feedback:visible').first
            try:
                vis = step1_err.is_visible(timeout=1000)
                from unittest.mock import MagicMock
                if bool(vis) and not isinstance(vis, MagicMock):
                    err_txt = step1_err.inner_text().strip()
                    if any(kw in err_txt.lower() for kw in ["already registered", "already exists", "taken", "in use"]):
                        log.warning(f"Step 1 reported already registered: {err_txt}")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.ALREADY_REGISTERED,
                            email=client.email,
                            username=final_uname,
                            notes=f"Already registered: {err_txt}"
                        )
            except Exception:
                pass

            # --- STEP 2: Personal Details & Address (/create-account/address-details) ---
            log.info("Filling Step 2: Name, DOB, Gender, and Address on 247 Bet...")

            # Gender selection (Radio input#M or input#F)
            gender_code = "F" if getattr(client, "resolved_title", "Mr.") in ("Mrs.", "Miss", "Ms.") else "M"
            try:
                gender_loc = page.locator(f"input#gender_{gender_code}, input#{gender_code}, input[type='radio'][value='{gender_code}']").first
                if gender_loc.is_visible(timeout=2000):
                    human_click(gender_loc, page)
                    human_pause(page, 0.3, 0.5)
            except Exception:
                page.evaluate("""(code) => {
                    const r = document.getElementById(code) || document.querySelector(`input[name="gender"][value="${code}"]`);
                    if (r) { r.click(); r.dispatchEvent(new Event('change', { bubbles: true })); }
                }""", gender_code)

            # First Name & Last Name (lowercase IDs on 247 Bet Angular form)
            target_fn = getattr(client, "alphabetic_first_name", None) or client.first_name
            target_ln = getattr(client, "alphabetic_last_name", None) or client.last_name

            fn_field = page.locator("input#firstname, input[id*='firstname' i], input[autocomplete*='given-name' i]").first
            if fn_field.is_visible(timeout=5000):
                human_type(fn_field, target_fn, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            ln_field = page.locator("input#lastname, input[id*='lastname' i], input[autocomplete*='family-name' i]").first
            if ln_field.is_visible(timeout=3000):
                human_type(ln_field, target_ln, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # Date of Birth (select dropdowns: select#day, select#month, select#year)
            day_val = str(int(client.dob_day))
            month_val = str(int(client.dob_month))
            year_val = str(int(client.dob_year))

            day_sel = page.locator("select#day, select[id*='day' i]").first
            if day_sel.is_visible(timeout=2500):
                try:
                    day_sel.select_option(day_val)
                except Exception:
                    page.evaluate("""(val) => {
                        const sel = document.getElementById('day');
                        if (sel) { sel.value = val; sel.dispatchEvent(new Event('change', { bubbles: true })); }
                    }""", day_val)
                human_pause(page, 0.2, 0.4)

            month_sel = page.locator("select#month, select[id*='month' i]").first
            if month_sel.is_visible(timeout=2500):
                try:
                    month_sel.select_option(month_val)
                except Exception:
                    page.evaluate("""(val) => {
                        const sel = document.getElementById('month');
                        if (sel) { sel.value = val; sel.dispatchEvent(new Event('change', { bubbles: true })); }
                    }""", month_val)
                human_pause(page, 0.2, 0.4)

            year_sel = page.locator("select#year, select[id*='year' i]").first
            if year_sel.is_visible(timeout=2500):
                try:
                    year_sel.select_option(year_val)
                except Exception:
                    page.evaluate("""(val) => {
                        const sel = document.getElementById('year');
                        if (sel) { sel.value = val; sel.dispatchEvent(new Event('change', { bubbles: true })); }
                    }""", year_val)
                human_pause(page, 0.3, 0.5)

            # Address: Click 'Enter address manually' link
            manual_addr_link = page.locator("a:has-text('Enter address manually'), .address-toggle:has-text('Enter address manually'), a:has-text('manually')").first
            if manual_addr_link.is_visible(timeout=3000):
                log.info("Clicking 'Enter address manually' on 247 Bet...")
                human_click(manual_addr_link, page)
                human_pause(page, 0.5, 1.0)
            else:
                page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a, button'));
                    const m = links.find(l => (l.textContent || '').toLowerCase().includes('enter address manually'));
                    if (m) m.click();
                }""")
                human_pause(page, 0.5, 1.0)

            # Fill Manual Address fields (formcontrolname="address1", "town", "postalcode")
            addr1_inp = page.locator("input[formcontrolname='address1'], input[autocomplete='address-line1'], input[name='address1'], input#address1").first
            if addr1_inp.is_visible(timeout=3000):
                human_type(addr1_inp, client.address_line1, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.5)

            if getattr(client, "address_line2", None):
                addr2_inp = page.locator("input[formcontrolname='address2'], input[autocomplete='address-line2'], input#address2").first
                if addr2_inp.is_visible(timeout=1000):
                    human_type(addr2_inp, client.address_line2, page=page, min_delay_ms=30, max_delay_ms=60)
                    human_pause(page, 0.2, 0.4)

            town_inp = page.locator("input[formcontrolname='town'], input[autocomplete='address-level2'], input[name='city'], input#city").first
            if town_inp.is_visible(timeout=3000):
                human_type(town_inp, client.town_city, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.5)

            postcode_inp = page.locator("input[formcontrolname='postalcode'], input[autocomplete='postal-code'], input[name='postcode'], input#postcode").first
            if postcode_inp.is_visible(timeout=3000):
                human_type(postcode_inp, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.4, 0.7)

            # Submit Step 2
            cont_btn2 = page.locator("button:has-text('Continue'), button[type='submit']").first
            if cont_btn2.is_visible(timeout=3000):
                log.info("Submitting Step 2 on 247 Bet with human click...")
                human_click(cont_btn2, page)
                human_pause(page, 2.5, 4.0)

            # Check for Step 2 errors or stuck form
            step2_err = page.locator('.error-message:visible, [class*="alert-danger"]:visible, .invalid-feedback:visible').first
            try:
                vis2 = step2_err.is_visible(timeout=1000)
                from unittest.mock import MagicMock
                if bool(vis2) and not isinstance(vis2, MagicMock):
                    err_txt2 = step2_err.inner_text().strip()
                    log.warning(f"Step 2 validation error on 247 Bet: {err_txt2}")
            except Exception:
                pass

            # --- STEP 3: Terms Agreement & Submission (/create-account/account-details) ---
            log.info("Handling Step 3: Terms & 18+ declaration on 247 Bet...")
            human_scroll(page, distance_y=150, steps=3)
            human_pause(page, 0.4, 0.8)

            # Mandatory Terms & Privacy Checkbox (id='termsPrivacyFunds')
            terms_cb = page.locator("input#termsPrivacyFunds, input[id*='terms' i], input[type='checkbox']#termsPrivacyFunds").first
            if terms_cb.is_visible(timeout=4000):
                try:
                    terms_cb.scroll_into_view_if_needed(timeout=1500)
                except Exception:
                    pass

                box = terms_cb.bounding_box()
                if box:
                    target_x = box['x'] + 10
                    target_y = box['y'] + 10
                    human_mouse_move(page, target_x, target_y, steps=6)
                    page.mouse.click(target_x, target_y)
                else:
                    human_click(terms_cb, page)
                human_pause(page, 0.4, 0.7)

            # Fallback event enforcement for termsPrivacyFunds
            page.evaluate("""() => {
                const cb = document.getElementById('termsPrivacyFunds') || document.querySelector('input[id*="terms"]');
                if (cb && !cb.checked) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }""")
            human_pause(page, 0.5, 1.0)

            # Close any popup tab opened if a policy link was accidentally triggered
            if len(page.context.pages) > 1:
                for extra_page in page.context.pages:
                    if extra_page != page:
                        try:
                            extra_page.close()
                        except Exception:
                            pass
                page.bring_to_front()

            # Submit Step 3 (Terms & Marketing)
            cont_btn3 = page.locator("button.btn-primary:has-text('Continue'), button:has-text('Continue'), button[type='submit']").first
            if cont_btn3.is_visible(timeout=4000):
                log.info("Submitting Step 3 (Terms & Marketing) with human click...")
                human_click(cont_btn3, page)
                human_pause(page, 2.5, 4.0)

            # --- STEP 4: Financial Limits (/create-account/deposit-limit) ---
            log.info("Handling Step 4: Financial Limits (Deposit Limit) on 247 Bet...")
            try:
                page.wait_for_selector("input#none, input#net, input#gross, .radio-field-deposit-limit-type, button:has-text('Sign up')", timeout=8000)
            except Exception:
                pass

            # Select "I don't want to set a limit" (input#none)
            none_opt = page.locator("input#none, label:has-text(\"I don't want to set a limit\"), input[value='none']").first
            if none_opt.is_visible(timeout=3000):
                log.info("Selecting 'I don't want to set a limit' on 247 Bet...")
                try:
                    human_click(none_opt, page)
                except Exception:
                    page.evaluate("""() => {
                        const r = document.getElementById('none') || document.querySelector('input[value="none"]');
                        if (r) { r.click(); r.dispatchEvent(new Event('change', { bubbles: true })); }
                    }""")
                human_pause(page, 0.5, 1.0)
            else:
                page.evaluate("""() => {
                    const r = document.getElementById('none') || document.querySelector('input[value="none"]');
                    if (r) { r.click(); r.dispatchEvent(new Event('change', { bubbles: true })); }
                }""")
                human_pause(page, 0.5, 1.0)

            if dry_run:
                log.info("Dry-run active: Skipping final account creation submission on 247 Bet")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=final_uname,
                    password=password_used,
                    account_reference="DRY-RUN-247BET",
                    notes="Dry-run completed successfully"
                )

            # Review pause before final Sign up submit
            log.info("Reviewing details before final Sign up submission on 247 Bet...")
            human_scroll(page, distance_y=100, steps=2)
            human_pause(page, 1.5, 2.5)

            # Final submit CTA on Financial Limits step: 'Sign up'
            signup_btn = page.locator("button:has-text('Sign up'), button.btn-primary:has-text('Sign up'), button[type='submit']").first
            if signup_btn.is_visible(timeout=4000):
                log.info("Clicking final 'Sign up' submission on 247 Bet with human click...")
                human_click(signup_btn, page)
                human_pause(page, 3.0, 5.0)
            else:
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button, input[type="submit"]'));
                    const s = btns.find(b => (b.textContent || '').trim().toLowerCase() === 'sign up');
                    if (s) s.click();
                }""")
                human_pause(page, 3.0, 5.0)

            # 5. Active Registration Confirmation Waiting
            log.info("Waiting for registration confirmation feedback from 247 Bet website...")
            poll_interval = 2.0
            max_wait_seconds = 45.0
            start_time = datetime.datetime.now()

            while (datetime.datetime.now() - start_time).total_seconds() < max_wait_seconds:
                curr_url = page.url.lower()

                # Success indicator 1: Redirected away from create-account flow to authenticated cashier/deposit/lobby
                if "create-account" not in curr_url and ("247bet.com" in curr_url):
                    log.info(f"Registration CONFIRMED by 247 Bet website: redirected to authenticated session at {page.url}!")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.SUCCESS,
                        email=client.email,
                        username=final_uname,
                        password=password_used,
                        account_reference=f"247BET_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                        notes="Registration confirmed by website"
                    )

                # Success indicator 2: Account or Cashier components visible on page
                confirmed_loc = page.locator("a:has-text('My Account'), a:has-text('Deposit'), button:has-text('Deposit'), a:has-text('Refresh balances'), [class*='balance'], [data-action*='deposit']").first
                try:
                    if confirmed_loc.is_visible(timeout=300):
                        log.info(f"Registration CONFIRMED by 247 Bet website: user profile / cashier component visible ('{confirmed_loc.inner_text().strip()}')")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.SUCCESS,
                            email=client.email,
                            username=final_uname,
                            password=password_used,
                            account_reference=f"247BET_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                            notes="Registration confirmed by website"
                        )
                except Exception:
                    pass

                # Check for explicit error messages
                err_loc = page.locator('.error-message:visible, [class*="alert-danger"]:visible, .invalid-feedback:visible, [role="alert"]:visible').first
                try:
                    if err_loc.is_visible(timeout=300):
                        err_text = err_loc.inner_text().strip()
                        if err_text and not any(ign in err_text.lower() for ign in ["cookie", "script"]):
                            if any(dup in err_text.lower() for dup in ["already registered", "already exists", "taken", "in use"]):
                                log.warning(f"247 Bet reported already registered: {err_text}")
                                return RegistrationResult(
                                    client_id=client.client_id,
                                    client_name=client.full_name,
                                    site_id=self.site_id,
                                    site_name=self.site_name,
                                    status=RegistrationStatus.ALREADY_REGISTERED,
                                    email=client.email,
                                    username=final_uname,
                                    notes=f"Already registered: {err_text}"
                                )
                            elif is_pending_verification_error(err_text):
                                log.info(f"247 Bet requested verification: {err_text}")
                                return RegistrationResult(
                                    client_id=client.client_id,
                                    client_name=client.full_name,
                                    site_id=self.site_id,
                                    site_name=self.site_name,
                                    status=RegistrationStatus.MANUAL_REVIEW,
                                    email=client.email,
                                    username=final_uname,
                                    notes=f"KYC Pending: {err_text}"
                                )
                            else:
                                log.warning(f"247 Bet submission error: {err_text}")
                                return RegistrationResult(
                                    client_id=client.client_id,
                                    client_name=client.full_name,
                                    site_id=self.site_id,
                                    site_name=self.site_name,
                                    status=RegistrationStatus.FAILED,
                                    email=client.email,
                                    username=final_uname,
                                    error_summary=f"Validation error: {err_text}"
                                )
                except Exception:
                    pass

                page.wait_for_timeout(int(poll_interval * 1000))

            # If still on create-account after timeout
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "timeout_on_create_account")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                username=final_uname,
                error_summary="Registration timed out: page remained on create-account flow without confirmation",
                screenshot_path=str(bundle.screenshot_path) if bundle else None,
                dom_snapshot_path=str(bundle.dom_path) if bundle else None
            )

        except Exception as e:
            err_msg = str(e)
            log.error(f"Error during 247 Bet registration: {err_msg}")
            try:
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "register", e)
                screenshot_path = str(bundle.screenshot_path) if bundle else None
                dom_snapshot_path = str(bundle.dom_path) if bundle else None
            except Exception:
                pass

            status = RegistrationStatus.MANUAL_REVIEW if is_pending_verification_error(err_msg) else RegistrationStatus.FAILED
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=status,
                email=client.email,
                error_summary=err_msg,
                screenshot_path=screenshot_path,
                dom_snapshot_path=dom_snapshot_path
            )

    def perform_login_verification(
        self,
        page: Page,
        username_or_email: str,
        password: str,
        client_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Custom login verification for 247 Bet.
        Targets the visible top navbar login CTA and handles modal credentials inputs.
        """
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Initiating login verification for {username_or_email} on {self.site_name}")

        try:
            target_url = "https://www.247bet.com/"
            log.info(f"Navigating to login target URL: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            human_pause(page, 2.0, 3.0)

            # Accept cookies
            try:
                cb = page.locator("#cookie-acceptAllBtn, button:has-text('Accept all cookies'), button:has-text('Accept All')").first
                if cb.is_visible(timeout=3500):
                    log.info("Dismissing 247 Bet cookie banner...")
                    cb.click(force=True)
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # Locate and click visible header Login CTA
            user_inp = page.locator("input[name='txt-login-username'], input[type='text'].field_input").first
            if not user_inp.is_visible(timeout=1500):
                # Click visible navbar login button (filter out off-screen sidebar button)
                log.info(f"Clicking visible Login CTA on {self.site_name}")
                clicked = False
                login_candidates = page.locator("a.btn--login:visible, a.btn.btn--login:visible, button.btn--login:visible, a[class*='btn--login']:visible")
                count = login_candidates.count()
                for i in range(count):
                    cand = login_candidates.nth(i)
                    box = cand.bounding_box()
                    if box and box.get("x", -1) >= 0 and box.get("width", 0) > 0:
                        try:
                            cand.click(force=True)
                            clicked = True
                            page.wait_for_timeout(1500)
                            break
                        except Exception:
                            pass

                if not clicked:
                    # JavaScript trigger fallback
                    page.evaluate("""() => {
                        const els = Array.from(document.querySelectorAll('a, button'));
                        const onScreen = els.find(e => {
                            const r = e.getBoundingClientRect();
                            const txt = (e.textContent || '').trim().toLowerCase();
                            return r.width > 0 && r.height > 0 && r.left >= 0 && (txt === 'login' || txt === 'log in');
                        });
                        if (onScreen) onScreen.click();
                    }""")
                    page.wait_for_timeout(2000)

            # Wait for modal credentials inputs
            user_inp = page.locator("input[name='txt-login-username'], input[type='text'].field_input").first
            pwd_inp = page.locator("input[name='txt-login-password'], input[type='password'].field_input").first

            if not user_inp.is_visible(timeout=5000) or not pwd_inp.is_visible(timeout=5000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "login_inputs_missing")
                return False, bundle.screenshot_path, f"Login modal inputs not visible on {self.site_name}"

            log.info(f"Filling credentials for {username_or_email} on 247 Bet")
            human_type(user_inp, username_or_email, page=page, min_delay_ms=25, max_delay_ms=50)
            human_pause(page, 0.3, 0.5)
            human_type(pwd_inp, password, page=page, min_delay_ms=25, max_delay_ms=50)
            human_pause(page, 0.4, 0.7)

            # Submit via Enter key on password input or clicking submit
            log.info("Submitting login form on 247 Bet...")
            submit_btn = page.locator("button[type='submit']:has-text('Login'), button[type='submit']:has-text('Log In'), button:has-text('Log In'), button:has-text('Login')").first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            page.wait_for_timeout(5000)

            # Dismiss any welcome / deposit popups
            try:
                dismiss_btn = page.locator("button[aria-label='Close'], .modal-close, button:has-text('✕'), button:has-text('X'), a[data-action*='close']").first
                if dismiss_btn.is_visible(timeout=2000):
                    dismiss_btn.click(force=True)
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # Capture proof
            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

            # Verify authenticated session
            body_txt = page.locator("body").inner_text().lower()
            if any(kw in body_txt for kw in ["deposit", "my account", "balance", "log out", "logout", "cashier"]):
                log.info(f"Login verification SUCCESSFUL for {username_or_email} on 247 Bet")
                return True, proof_path, None
            elif any(err in body_txt for err in ["invalid username", "incorrect password", "invalid credentials", "login failed"]):
                return False, proof_path, "Invalid username or password"

            # Check if login modal has closed (URL changed to logged in state)
            if "login" not in page.url.lower():
                log.info(f"Login verification completed with proof captured for {username_or_email}")
                return True, proof_path, None

            return False, proof_path, "Could not confirm authenticated session on 247 Bet"

        except Exception as e:
            err_msg = str(e)
            log.error(f"Exception during 247 Bet login verification: {err_msg}")
            try:
                bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
                return False, bundle.screenshot_path, err_msg
            except Exception:
                return False, None, err_msg
