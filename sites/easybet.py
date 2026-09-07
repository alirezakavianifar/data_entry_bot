"""
easyBet Registration Adapter (Phase 2).
Platform: easyBet Sportsbook & Exchange Onboarding.
Website: https://welcome.easybet.net/EB20-Football
Registration Endpoint: https://exchange.easybet.net/registration?bonus-code=EB20
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

logger = get_logger(step="EasyBetAdapter")


class EasyBetAdapter(BaseSiteAdapter):
    """
    Adapter for easyBet registration.
    Preserves promo code EB20, dismisses CookieYes banners, and handles onboarding with
    realistic human cadence, Bezier mouse movements, and safe checkbox targeting.
    """

    def __init__(self, promo_url: Optional[str] = None):
        super().__init__(
            site_id="easybet",
            site_name="easyBet",
            default_promo_url=promo_url or "https://welcome.easybet.net/EB20-Football",
            requires_uk_ip=True
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        return self.register_client(client=client, page=page, dry_run=False, password=password)

    def register_client(self, client: Client, page: Page, dry_run: bool = False, password: Optional[str] = None) -> RegistrationResult:
        log = logger.bind(client=client.full_name, site=self.site_name)
        log.info(f"Starting registration on {self.site_name} (Dry-run: {dry_run})")

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
                account_reference="DRY-RUN-EASYBET",
                notes="Dry-run completed successfully"
            )

        try:
            target_url = self.default_promo_url
            log.info(f"Navigating to landing page: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2.0, 3.5)

            # If on welcome landing page, click Join Now or navigate to registration endpoint
            if "welcome.easybet.net" in page.url:
                log.info("Clicking 'Join Now' on welcome landing page...")
                join_btn = page.locator("a:has-text('Join Now'), a[href*='registration']").first
                if join_btn.is_visible(timeout=3000):
                    human_click(join_btn, page)
                    human_pause(page, 2.0, 3.5)
                else:
                    page.goto("https://exchange.easybet.net/registration?bonus-code=EB20", wait_until="domcontentloaded")
                    human_pause(page, 2.0, 3.0)

            # Dismiss CookieYes Banner
            try:
                cookie_btn = page.locator("button:has-text('Accept All'), #cookie-acceptAllBtn").first
                if cookie_btn.is_visible(timeout=3000):
                    log.info("Accepting CookieYes banner with human click...")
                    human_click(cookie_btn, page)
                    human_pause(page, 0.8, 1.4)
            except Exception as e:
                log.debug(f"Cookie banner not present: {e}")

            # Fill Username
            username_field = page.locator("input[name='username'], input#username, input[placeholder*='Username']").first
            if username_field.is_visible(timeout=6000):
                clean_uname = "".join(c for c in f"{client.first_name}{client.last_name}" if c.isalnum()).lower()[:12]
                birth_yr = client.dob_year[-2:] if client.dob else "92"
                final_uname = f"{clean_uname}{birth_yr}"
                log.info(f"Filling Username with human typing: {final_uname}")
                human_type(username_field, final_uname, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)
            else:
                final_uname = client.email

            # Fill Password
            pw_field = page.locator("input[name='password'], input#password, input[type='password']").first
            if pw_field.is_visible(timeout=4000):
                log.info("Filling Password with human typing...")
                human_type(pw_field, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
                human_pause(page, 0.3, 0.6)

            # Fill Email
            email_field = page.locator("input[name='email'], input#email, input[type='email']").first
            if email_field.is_visible(timeout=4000):
                log.info(f"Filling Email with human typing: {client.email}")
                human_type(email_field, client.email, page=page, min_delay_ms=25, max_delay_ms=60)
                human_pause(page, 0.3, 0.6)

            # Personal Details: First Name, Last Name
            fn_field = page.locator("input[name='firstName'], input#firstName, input[name='firstname']").first
            if fn_field.is_visible(timeout=3000):
                log.info(f"Filling First Name: {client.first_name}")
                human_type(fn_field, client.first_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            ln_field = page.locator("input[name='lastName'], input#lastName, input[name='lastname']").first
            if ln_field.is_visible(timeout=3000):
                log.info(f"Filling Last Name: {client.last_name}")
                human_type(ln_field, client.last_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # Date of Birth
            dob_day_field = page.locator("input[name*='day'], input#dob_day, select[name*='day']").first
            if dob_day_field.is_visible(timeout=2500):
                if dob_day_field.evaluate("el => el.tagName") == "SELECT":
                    human_click(dob_day_field, page)
                    dob_day_field.select_option(client.dob_day.lstrip("0") or "1")
                    human_pause(page, 0.2, 0.4)
                else:
                    human_type(dob_day_field, client.dob_day, page=page, min_delay_ms=40, max_delay_ms=75)
                    human_pause(page, 0.2, 0.4)

            dob_m_field = page.locator("input[name*='month'], input#dob_month, select[name*='month']").first
            if dob_m_field.is_visible(timeout=2500):
                if dob_m_field.evaluate("el => el.tagName") == "SELECT":
                    human_click(dob_m_field, page)
                    dob_m_field.select_option(client.dob_month.lstrip("0") or "1")
                    human_pause(page, 0.2, 0.4)
                else:
                    human_type(dob_m_field, client.dob_month, page=page, min_delay_ms=40, max_delay_ms=75)
                    human_pause(page, 0.2, 0.4)

            dob_y_field = page.locator("input[name*='year'], input#dob_year, select[name*='year']").first
            if dob_y_field.is_visible(timeout=2500):
                if dob_y_field.evaluate("el => el.tagName") == "SELECT":
                    human_click(dob_y_field, page)
                    dob_y_field.select_option(client.dob_year)
                    human_pause(page, 0.3, 0.5)
                else:
                    human_type(dob_y_field, client.dob_year, page=page, min_delay_ms=40, max_delay_ms=75)
                    human_pause(page, 0.3, 0.5)

            # Address & Postcode
            postcode_field = page.locator("input[name='postcode'], input#postcode, input[placeholder*='Postcode']").first
            if postcode_field.is_visible(timeout=3000):
                log.info(f"Filling Postcode: {client.postcode}")
                human_type(postcode_field, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.4, 0.8)

            addr_field = page.locator("input[name='address'], input#address, input[placeholder*='Address']").first
            if addr_field.is_visible(timeout=3000):
                log.info(f"Filling Address Line 1: {client.address_line1}")
                human_type(addr_field, client.address_line1, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            city_field = page.locator("input[name='city'], input#city, input[placeholder*='City']").first
            if city_field.is_visible(timeout=3000):
                log.info(f"Filling City: {client.town_city}")
                human_type(city_field, client.town_city, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # Phone Number
            phone_field = page.locator("input[name='phone'], input#phone, input[type='tel']").first
            if phone_field.is_visible(timeout=3000):
                log.info(f"Filling Phone: {client.phone}")
                human_type(phone_field, client.phone, page=page, min_delay_ms=35, max_delay_ms=75)
                human_pause(page, 0.3, 0.6)

            # Smooth scroll down through form
            human_scroll(page, distance_y=250, steps=5)
            human_pause(page, 0.4, 0.7)

            # Bonus code check (ensure EB20 is set)
            bonus_field = page.locator("input[name*='bonus'], input[name*='promo'], input#bonus_code").first
            if bonus_field.is_visible(timeout=2000):
                val = bonus_field.input_value()
                if not val or "EB20" not in val.upper():
                    log.info("Setting bonus code 'EB20' with human typing...")
                    human_type(bonus_field, "EB20", page=page, min_delay_ms=30, max_delay_ms=60)
                    human_pause(page, 0.3, 0.6)

            # Accept 18+ T&Cs with safe checkbox targeting
            log.info("Ticking terms & 18+ declaration on easyBet with safe box targeting...")
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

            # Fallback event enforcement for 18+ checkboxes
            page.evaluate("""() => {
                const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
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
                log.info("Dry-run active: Skipping final registration click on easyBet")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=final_uname,
                    password=password_used,
                    account_reference="DRY-RUN-EASYBET",
                    notes="Dry-run completed successfully"
                )

            # Review pause before final submit
            log.info("Reviewing form fields before submission...")
            human_scroll(page, distance_y=200, steps=4)
            human_pause(page, 1.5, 2.5)

            # Final submit
            submit_btn = page.locator(
                "button[type='submit'], button:has-text('Create Account'), button:has-text('Join Now'), button:has-text('Register')"
            ).first
            if submit_btn.is_visible(timeout=4000):
                log.info("Submitting registration on easyBet with human click...")
                human_click(submit_btn, page)
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
                account_reference=f"EASYBET_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

        except Exception as e:
            err_msg = str(e)
            log.error(f"Error during easyBet registration: {err_msg}")
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
