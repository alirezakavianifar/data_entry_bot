"""
247 Bet Registration Adapter (Phase 2).
Platform: White Hat Gaming / Casimba Affiliates.
Website: https://www.247bet.com/en-gb/register
Registration Flow: /create-account/personal-details
"""

import datetime
from pathlib import Path
from typing import Optional
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
from core.logger import get_logger, capture_failure_bundle

logger = get_logger(step="247BetAdapter")


class TwentyFourSevenBetAdapter(BaseSiteAdapter):
    """
    Adapter for 247 Bet (White Hat Gaming platform).
    Handles dynamic Angular forms, step-by-step onboarding with human typing rhythms,
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

            # Phone number (format: 07xxxxxxxxx without leading 0 if prefix dropdown is present)
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

            # Click Continue / Next
            cont_btn = page.locator("button:has-text('Continue'), button[type='submit']").first
            if cont_btn.is_visible(timeout=3000):
                log.info("Submitting Step 1 with human click...")
                human_click(cont_btn, page)
                human_pause(page, 2.0, 3.5)

            # --- STEP 2: Personal Details (First Name, Last Name, DOB, Gender) ---
            fn_field = page.locator("input#firstName, input[name='firstName'], input#first-name").first
            if fn_field.is_visible(timeout=5000):
                log.info("Filling Step 2: Personal details with human typing...")
                human_type(fn_field, client.first_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            ln_field = page.locator("input#lastName, input[name='lastName'], input#last-name").first
            if ln_field.is_visible(timeout=3000):
                human_type(ln_field, client.last_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # Gender selection
            gender_target = "female" if getattr(client, "resolved_title", "Mr.") in ("Mrs.", "Miss", "Ms.") else "male"
            gender_loc = page.locator(
                f"input[type='radio'][value*='{gender_target}' i], "
                f"input[type='radio']#{gender_target}, "
                f"label:has-text('{gender_target.capitalize()}'), "
                f"button:has-text('{gender_target.capitalize()}')"
            ).first
            if gender_loc.is_visible(timeout=2000):
                human_click(gender_loc, page)
                human_pause(page, 0.3, 0.6)
            else:
                page.evaluate("""(target) => {
                    const radios = Array.from(document.querySelectorAll('input[type=\"radio\"], button[role=\"radio\"]'));
                    for (let r of radios) {
                        const txt = (r.value || r.id || r.textContent || '').toLowerCase();
                        if (txt.includes(target)) {
                            r.click();
                            break;
                        }
                    }
                }""", gender_target)
                human_pause(page, 0.3, 0.5)

            # Date of Birth
            dob_day = page.locator("input#dob-day, input[name='day'], input#day").first
            if dob_day.is_visible(timeout=2500):
                human_type(dob_day, client.dob_day, page=page, min_delay_ms=40, max_delay_ms=75)
                human_pause(page, 0.2, 0.4)

            dob_month = page.locator("input#dob-month, input[name='month'], input#month").first
            if dob_month.is_visible(timeout=2500):
                human_type(dob_month, client.dob_month, page=page, min_delay_ms=40, max_delay_ms=75)
                human_pause(page, 0.2, 0.4)

            dob_year = page.locator("input#dob-year, input[name='year'], input#year").first
            if dob_year.is_visible(timeout=2500):
                human_type(dob_year, client.dob_year, page=page, min_delay_ms=40, max_delay_ms=75)
                human_pause(page, 0.3, 0.6)

            cont_btn2 = page.locator("button:has-text('Continue'), button[type='submit']").first
            if cont_btn2.is_visible(timeout=3000):
                log.info("Submitting Step 2 with human click...")
                human_click(cont_btn2, page)
                human_pause(page, 2.0, 3.5)

            # --- STEP 3: Address & Postcode ---
            postcode_field = page.locator("input#postcode, input[name='postcode'], input#postal-code").first
            if postcode_field.is_visible(timeout=5000):
                log.info(f"Filling Step 3: Postcode {client.postcode} with human typing...")
                human_type(postcode_field, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.4, 0.8)

                # Click Find Address / Search
                find_btn = page.locator("button:has-text('Find Address'), button:has-text('Search')").first
                if find_btn.is_visible(timeout=2000):
                    human_click(find_btn, page)
                    human_pause(page, 1.5, 2.5)

            addr_field = page.locator("input#address1, input[name='addressLine1'], input#street").first
            if addr_field.is_visible(timeout=3000):
                human_type(addr_field, client.address_line1, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            city_field = page.locator("input#city, input[name='city'], input#town").first
            if city_field.is_visible(timeout=3000):
                human_type(city_field, client.town_city, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # --- STEP 4: Terms Agreement & 18+ Confirmation ---
            log.info("Accepting Terms & 18+ declaration on 247 Bet with safe box targeting...")
            human_scroll(page, distance_y=250, steps=5)
            human_pause(page, 0.4, 0.8)

            terms_cb = page.locator("input[type='checkbox'], label:has-text('18'), label:has-text('terms')").first
            if terms_cb.is_visible(timeout=2500):
                try:
                    terms_cb.scroll_into_view_if_needed(timeout=1500)
                except Exception:
                    pass
                box = terms_cb.bounding_box()
                if box:
                    target_x = box['x'] + 10
                    target_y = box['y'] + 10
                    human_mouse_move(page, target_x, target_y, steps=8)
                    page.mouse.click(target_x, target_y)
                else:
                    human_click(terms_cb, page)
                human_pause(page, 0.4, 0.7)

            # Fallback event enforcement for checkboxes
            page.evaluate("""() => {
                const checkboxes = Array.from(document.querySelectorAll('input[type=\"checkbox\"]'));
                for (let cb of checkboxes) {
                    const txt = (cb.parentElement ? cb.parentElement.innerText : '').toLowerCase();
                    if (txt.includes('18') || txt.includes('age') || txt.includes('terms') || txt.includes('agree')) {
                        if (!cb.checked) {
                            cb.checked = true;
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                }
            }""")
            human_pause(page, 0.5, 1.0)

            # Close any popup tab opened if a policy link was triggered
            if len(page.context.pages) > 1:
                for extra_page in page.context.pages:
                    if extra_page != page:
                        try:
                            extra_page.close()
                        except Exception:
                            pass
                page.bring_to_front()

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

            # Review pause before final submit
            log.info("Reviewing details before submitting 247 Bet...")
            human_scroll(page, distance_y=200, steps=4)
            human_pause(page, 1.5, 2.5)

            # Final submit
            final_btn = page.locator("button:has-text('Create Account'), button:has-text('Complete'), button[type='submit']").first
            if final_btn.is_visible(timeout=4000):
                log.info("Clicking final registration submission on 247 Bet with human click...")
                human_click(final_btn, page)
                human_pause(page, 4.0, 7.0)

            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=final_uname,
                password=password_used,
                account_reference=f"247BET_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
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
