"""
Paddy Power Registration Adapter (Phase 2).
Platform: Flutter Entertainment / PPB Group.
Landing Promo: https://redirect.rp-offers.com/?id=9708
Registration Endpoint: https://register.paddypower.com/account/registration
Cooling-off Period: Enforces 25-day betting embargo note.
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

logger = get_logger(step="PaddyPowerAdapter")


class PaddyPowerAdapter(BaseSiteAdapter):
    """
    Adapter for Paddy Power account registration.
    Handles Flutter Entertainment registration inputs with realistic human cadence,
    Bezier mouse trajectories, address lookup, and automatically enforces the mandatory 25-day betting embargo.
    """

    def __init__(self, promo_url: Optional[str] = None):
        super().__init__(
            site_id="paddypower",
            site_name="Paddy Power",
            default_promo_url=promo_url or "https://redirect.rp-offers.com/?id=9708",
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
        sec_answer = f"{client.last_name}Vale"

        if dry_run and page is None:
            res = RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=client.email,
                password=password_used,
                account_reference="DRY-RUN-PADDYPOWER"
            )
            res.calculate_embargo(25)
            return res

        try:
            target_url = self.default_promo_url
            log.info(f"Navigating to promo link: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2.0, 3.5)

            # Accept OneTrust Cookie Banner
            try:
                cookie_btn = page.locator(
                    "#onetrust-accept-btn-handler, "
                    "button#onetrust-accept-btn-handler, "
                    "button:has-text('Accept all cookies'), "
                    "button:has-text('Accept All')"
                ).first
                if cookie_btn.is_visible(timeout=4000):
                    log.info("Accepting OneTrust cookies with human click...")
                    human_click(cookie_btn, page)
                    human_pause(page, 0.8, 1.4)
            except Exception as e:
                log.debug(f"Cookie banner not present: {e}")

            # If on promotional landing page, click Join Now / Sign Up CTA
            if "promotions.paddypower.com" in page.url or "rp-offers" in page.url:
                log.info("Clicking Sign Up on promotion landing page with human click...")
                cta = page.locator(
                    "a:has-text('Join Now'), "
                    "a:has-text('Sign Up'), "
                    "button:has-text('Join Now'), "
                    "button:has-text('Sign Up'), "
                    "a[href*='register.paddypower.com']"
                ).first
                if cta.is_visible(timeout=4000):
                    human_click(cta, page)
                    human_pause(page, 2.5, 4.0)
                else:
                    page.goto("https://register.paddypower.com/account/registration", wait_until="domcontentloaded")
                    human_pause(page, 2.5, 3.5)

            # Ensure we are on register.paddypower.com
            try:
                page.wait_for_selector("#firstName, #email, #phoneNumber", timeout=20000)
            except PlaywrightTimeoutError:
                log.warning("Paddy Power form selectors not immediately visible, retrying registration URL...")
                page.goto("https://register.paddypower.com/account/registration", wait_until="domcontentloaded")
                human_pause(page, 2.0, 3.0)

            # 1. Title / Gender selection
            resolved_title = getattr(client, "resolved_title", "Mr.")
            is_female = resolved_title in ("Mrs.", "Miss", "Ms.")
            gender_id = "#gender-MRS" if is_female else "#gender-MR"
            gender_radio = page.locator(gender_id).first
            if gender_radio.is_visible(timeout=3000):
                log.info(f"Selecting gender/title '{resolved_title}' ({gender_id}) with human click...")
                human_click(gender_radio, page)
            else:
                page.evaluate(f"() => {{ const el = document.querySelector('{gender_id}'); if (el) el.click(); }}")

            human_pause(page, 0.3, 0.6)

            # 2. First Name & Last Name
            fn_field = page.locator("#firstName, input[name='firstName']").first
            if fn_field.is_visible(timeout=3000):
                log.info(f"Filling First Name: {client.first_name}")
                human_type(fn_field, client.first_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            ln_field = page.locator("#lastName, input[name='lastName']").first
            if ln_field.is_visible(timeout=3000):
                log.info(f"Filling Last Name: {client.last_name}")
                human_type(ln_field, client.last_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # 3. Date of Birth
            dob_d = page.locator("#dateOfBirth_day, input[name*='bday-day']").first
            if dob_d.is_visible(timeout=3000):
                human_type(dob_d, client.dob_day, page=page, min_delay_ms=40, max_delay_ms=75)
                human_pause(page, 0.2, 0.4)

            dob_m = page.locator("#dateOfBirth_month, input[name*='bday-month']").first
            if dob_m.is_visible(timeout=3000):
                human_type(dob_m, client.dob_month, page=page, min_delay_ms=40, max_delay_ms=75)
                human_pause(page, 0.2, 0.4)

            dob_y = page.locator("#dateOfBirth_year, input[name*='bday-year']").first
            if dob_y.is_visible(timeout=3000):
                human_type(dob_y, client.dob_year, page=page, min_delay_ms=40, max_delay_ms=75)
                human_pause(page, 0.3, 0.6)

            # 4. Address Search / Manual Entry
            addr_search = page.locator("#addressSearch").first
            if addr_search.is_visible(timeout=3000):
                log.info(f"Searching address by postcode: {client.postcode}...")
                human_type(addr_search, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 1.5, 2.5)

                suggestion = page.locator(".address-lookup__item, .lookup-results li, ul.dropdown-menu li").first
                if suggestion.is_visible(timeout=3000):
                    log.info("Clicking matching address suggestion with human click...")
                    human_click(suggestion, page)
                    human_pause(page, 0.5, 1.0)
                else:
                    manual_btn = page.locator("button:has-text('Enter address manually'), a:has-text('Enter address manually')").first
                    if manual_btn.is_visible(timeout=2000):
                        human_click(manual_btn, page)
                        human_pause(page, 0.5, 1.0)
                        for sel, val in [("#addressLine1", client.address_line1), ("#city", client.town_city), ("#postcode", client.postcode)]:
                            loc = page.locator(sel).first
                            if loc.is_visible(timeout=1500):
                                human_type(loc, val, page=page, min_delay_ms=30, max_delay_ms=65)
                                human_pause(page, 0.3, 0.6)

            # 5. Phone Number (UK national format)
            phone_field = page.locator("#phoneNumber, input[name*='tel-national']").first
            if phone_field.is_visible(timeout=3000):
                clean_phone = client.phone.lstrip("0") if client.phone.startswith("0") else client.phone
                log.info(f"Filling Phone: {clean_phone}")
                human_type(phone_field, clean_phone, page=page, min_delay_ms=35, max_delay_ms=75)
                human_pause(page, 0.3, 0.6)

            # 6. Email & Password
            email_field = page.locator("#email, input[type='email']").first
            if email_field.is_visible(timeout=3000):
                log.info(f"Filling Email: {client.email}")
                human_type(email_field, client.email, page=page, min_delay_ms=25, max_delay_ms=60)
                human_pause(page, 0.3, 0.6)

            pw_field = page.locator("#password, input[type='password']").first
            if pw_field.is_visible(timeout=3000):
                log.info("Filling Password...")
                human_type(pw_field, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
                human_pause(page, 0.3, 0.6)

            # 7. Security Question & Answer
            sec_q = page.locator("#securityQuestion, select[name='securityQuestion']").first
            if sec_q.is_visible(timeout=2500):
                try:
                    human_click(sec_q, page)
                    sec_q.select_option(index=1)
                    human_pause(page, 0.3, 0.5)
                except Exception:
                    pass
            sec_a = page.locator("#securityAnswer, input[name='securityAnswer']").first
            if sec_a.is_visible(timeout=2000):
                log.info("Filling Security Answer...")
                human_type(sec_a, sec_answer, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # 8. Marketing Preferences & Scroll down
            human_scroll(page, distance_y=250, steps=5)
            human_pause(page, 0.4, 0.8)

            page.evaluate("""() => {
                const optOuts = Array.from(document.querySelectorAll('input[type=\"checkbox\"], input[type=\"radio\"]'));
                for (let el of optOuts) {
                    const txt = (el.value || el.id || el.name || '').toLowerCase();
                    if (txt.includes('no') || txt.includes('optout')) {
                        el.click();
                    }
                }
            }""")
            human_pause(page, 0.3, 0.6)

            # Close any popup tab opened
            if len(page.context.pages) > 1:
                for extra_page in page.context.pages:
                    if extra_page != page:
                        try:
                            extra_page.close()
                        except Exception:
                            pass
                page.bring_to_front()

            # 9. Dry Run Verification
            if dry_run:
                log.info("Dry-run active: Skipping final registration submission on Paddy Power")
                res = RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password_used,
                    account_reference="DRY-RUN-PADDYPOWER"
                )
                res.calculate_embargo(25)
                return res

            # Review pause before final submission
            log.info("Reviewing details before submitting Paddy Power registration...")
            human_scroll(page, distance_y=200, steps=4)
            human_pause(page, 1.5, 2.5)

            # Submit Registration
            submit_btn = page.locator(
                "button[type='submit'], "
                "button:has-text('Join Now'), "
                "button:has-text('Agree & Open Account')"
            ).first
            if submit_btn.is_visible(timeout=4000):
                log.info("Clicking registration submission on Paddy Power with human click...")
                human_click(submit_btn, page)
                human_pause(page, 4.0, 7.0)

            res = RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=client.email,
                password=password_used,
                account_reference=f"PP_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            # Mandatory 25-day betting embargo
            res.calculate_embargo(25)
            log.info(f"Paddy Power registration complete. Embargo note: {res.formatted_notes}")
            return res

        except Exception as e:
            err_msg = str(e)
            log.error(f"Error during Paddy Power registration: {err_msg}")
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
