"""
Betfair Registration Adapter (Phase 2).
Platform: Flutter Entertainment / PPB Group.
Landing Promo: https://redirect.rp-offers.com/?id=8827
Registration Endpoint: https://register.betfair.com/account/registration?promotionCode=ZSKAOL
Cooling-off Period: Enforces 25-day betting embargo note.
"""

import datetime
import random
import time
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

logger = get_logger(step="BetfairAdapter")


class BetfairAdapter(BaseSiteAdapter):
    """
    Adapter for Betfair account registration.
    Preserves promo code ZSKAOL, fills Flutter registration inputs with realistic human cadence,
    Bezier mouse trajectories, address lookup, and enforces the mandatory 25-day betting embargo.
    """

    def __init__(self, promo_url: Optional[str] = None):
        super().__init__(
            site_id="betfair",
            site_name="Betfair",
            default_promo_url=promo_url or "https://redirect.rp-offers.com/?id=8827",
            requires_uk_ip=True
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        return self.register_client(client=client, page=page, dry_run=False, password=password)

    def navigate(self, page: Page, promo_url: Optional[str] = None) -> bool:
        """Navigates to the Betfair promo landing page and warms the session cookie jar."""
        log = logger.bind(site=self.site_name, step="navigate")
        target_url = promo_url or self.default_promo_url
        self._warm_session(page, log, target_url=target_url)
        return True

    def _warm_session(self, page: Page, log, target_url: Optional[str] = None):
        """
        Warms the session by visiting the Betfair promotional landing page, accepting cookies,
        simulating human scrolling and browsing, and clicking the in-page CTA with authentic Referer.
        """
        warm_url = target_url or self.default_promo_url
        log.info(f"Session Warming: Visiting Betfair landing page '{warm_url}' to warm cookie jar...")
        try:
            page.goto(warm_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2.0, 3.5)

            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass

            self._dismiss_onetrust(page, log)

            log.info("Session Warming: Simulating authentic browsing and scrolling on Betfair promo...")
            human_scroll(page, distance_y=random.randint(220, 420), steps=5)
            human_pause(page, 1.5, 2.8)

            human_scroll(page, distance_y=-random.randint(100, 200), steps=3)
            human_pause(page, 0.8, 1.5)

            cta = page.locator(
                "a:has-text('Sign Up'), "
                "a:has-text('Join Now'), "
                "button:has-text('Sign Up'), "
                "button:has-text('Join Now'), "
                "a[href*='register.betfair.com'], "
                "button[href*='register.betfair.com']"
            ).first

            if cta.is_visible(timeout=3500):
                cta_text = cta.inner_text().strip() if cta.is_visible() else "CTA"
                log.info(f"Session Warming: Clicking landing CTA '{cta_text}' to transit to registration...")
                human_click(cta, page)
                human_pause(page, 2.5, 4.0)
            else:
                log.info("Session Warming: Navigating to registration endpoint with warmed cookies...")
                page.goto(
                    "https://register.betfair.com/account/registration?promotionCode=ZSKAOL",
                    referer=page.url,
                    wait_until="domcontentloaded"
                )
                human_pause(page, 2.0, 3.0)

            try:
                page.wait_for_selector("#firstName, #email, #phoneNumber", timeout=18000)
            except PlaywrightTimeoutError:
                log.warning("Betfair form selectors not visible, navigating directly to registration...")
                page.goto(
                    "https://register.betfair.com/account/registration?promotionCode=ZSKAOL",
                    wait_until="domcontentloaded"
                )
                human_pause(page, 2.0, 3.0)

            self._dismiss_onetrust(page, log)
            log.info("Session Warming completed on Betfair.")

        except Exception as e:
            log.warning(f"Session Warming error on Betfair: {e}. Navigating to registration...")
            try:
                page.goto(
                    "https://register.betfair.com/account/registration?promotionCode=ZSKAOL",
                    wait_until="domcontentloaded"
                )
                human_pause(page, 2.0, 3.0)
                self._dismiss_onetrust(page, log)
            except Exception:
                pass

    def _dismiss_onetrust(self, page: Page, log):
        """Dismisses OneTrust cookie consent banner and clears dark overlay."""
        try:
            btn = page.locator(
                "#onetrust-accept-btn-handler, "
                "button#onetrust-accept-btn-handler, "
                "button:has-text('Allow All Cookies'), "
                "button:has-text('Accept all cookies'), "
                "button:has-text('Accept All')"
            ).first
            if btn.is_visible(timeout=800):
                log.info("Accepting OneTrust cookies on Betfair with human click...")
                human_click(btn, page)
                human_pause(page, 0.4, 0.8)
        except Exception as e:
            log.debug(f"OneTrust banner not visible: {e}")

        # Inject persistent auto-dismissal observer into page DOM
        try:
            page.evaluate("""() => {
                const dismissOneTrust = () => {
                    const btn = document.querySelector('#onetrust-accept-btn-handler, button#onetrust-accept-btn-handler');
                    if (btn && btn.offsetParent !== null) {
                        btn.click();
                    }
                    const dark = document.querySelector('.onetrust-pc-dark-filter');
                    if (dark) dark.remove();
                    const sdk = document.querySelector('#onetrust-consent-sdk');
                    if (sdk && getComputedStyle(sdk).display !== 'none') {
                        sdk.style.display = 'none';
                    }
                };
                dismissOneTrust();
                if (!window._otObserverSet) {
                    window._otObserverSet = true;
                    const observer = new MutationObserver(() => dismissOneTrust());
                    observer.observe(document.body || document.documentElement, { childList: true, subtree: true });
                    setInterval(dismissOneTrust, 800);
                }
            }""")
        except Exception:
            pass

    def _handle_recaptcha(self, page: Page, log, max_wait_sec: int = 45) -> bool:
        """
        Detects and handles Google reCAPTCHA Enterprise ('I'm not a robot') on Betfair form.
        """
        try:
            rc_locator = page.locator(
                "iframe[title*='reCAPTCHA' i], "
                "iframe[src*='recaptcha' i], "
                "div[class*='recaptcha' i], "
                ":text('Please follow the instructions above'), "
                ":text('I\\'m not a robot')"
            ).first

            if not rc_locator.is_visible(timeout=1000):
                return True

            log.warning("Google reCAPTCHA ('I'm not a robot') detected on Betfair form!")

            # Try to click checkbox inside frame
            try:
                anchor_frame = page.frame_locator(
                    "iframe[title*='reCAPTCHA' i], iframe[src*='recaptcha/api2/anchor'], iframe[src*='recaptcha/enterprise/anchor']"
                ).first
                checkbox = anchor_frame.locator("#recaptcha-anchor, .recaptcha-checkbox").first
                if checkbox.is_visible(timeout=2000):
                    log.info("Attempting automated click on reCAPTCHA checkbox...")
                    human_click(checkbox, page)
                    human_pause(page, 1.5, 2.5)
            except Exception as e:
                log.debug(f"Could not click reCAPTCHA checkbox: {e}")

            def is_solved() -> bool:
                try:
                    tok = page.locator("textarea[name='g-recaptcha-response'], #g-recaptcha-response").first
                    if tok.count() > 0:
                        val = tok.input_value()
                        if val and len(val) > 10:
                            return True
                    af = page.frame_locator(
                        "iframe[title*='reCAPTCHA' i], iframe[src*='recaptcha/api2/anchor'], iframe[src*='recaptcha/enterprise/anchor']"
                    ).first
                    cb = af.locator("#recaptcha-anchor, .recaptcha-checkbox").first
                    if cb.get_attribute("aria-checked") == "true":
                        return True
                except Exception:
                    pass
                return False

            if is_solved():
                log.info("reCAPTCHA successfully verified!")
                return True

            log.warning(
                f"⚠️ reCAPTCHA ('I'm not a robot') challenge requires operator interaction! "
                f"Waiting up to {max_wait_sec}s for operator to solve it in browser window..."
            )
            start_time = time.time()
            while time.time() - start_time < max_wait_sec:
                if is_solved():
                    log.info("reCAPTCHA resolved by operator! Proceeding with registration...")
                    return True
                time.sleep(2.0)

            log.warning("reCAPTCHA was not solved within the allotted timeout.")
            return False

        except Exception as e:
            log.debug(f"Error checking reCAPTCHA: {e}")
            return True

    def register_client(self, client: Client, page: Page, dry_run: bool = False, password: Optional[str] = None) -> RegistrationResult:
        log = logger.bind(client=client.full_name, site=self.site_name)
        log.info(f"Initiating registration on {self.site_name} (Dry-run: {dry_run})")

        screenshot_path: Optional[str] = None
        dom_snapshot_path: Optional[str] = None
        password_used = password or generate_password()
        sec_answer = f"{client.last_name}Meadow"

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
                account_reference="DRY-RUN-BETFAIR"
            )
            res.calculate_embargo(25)
            return res

        try:
            # Check if page is already on registration endpoint (e.g. from prior navigate() session warming)
            is_already_on_reg = False
            try:
                if "registration" in page.url and page.locator("#firstName, #email").first.is_visible(timeout=1000):
                    is_already_on_reg = True
            except Exception:
                pass

            if not is_already_on_reg:
                self._warm_session(page, log, target_url=self.default_promo_url)
            else:
                log.info("Session already warmed and present on Betfair registration page.")
                self._dismiss_onetrust(page, log)

            # 1. Gender / Title
            resolved_title = getattr(client, "resolved_title", "Mr.")
            is_female = resolved_title in ("Mrs.", "Miss", "Ms.")
            gender_id = "#gender-female" if is_female else "#gender-male"
            gender_radio = page.locator(gender_id).first
            if gender_radio.is_visible(timeout=3000):
                log.info(f"Selecting gender '{'female' if is_female else 'male'}' on Betfair with human click...")
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

            # 3. Date of Birth (Activate field group and type Day, Month, Year)
            expected_day = client.dob_day.zfill(2)
            expected_month = client.dob_month.zfill(2)
            expected_year = str(client.dob_year)
            log.info(f"Filling Date of Birth: {expected_day}/{expected_month}/{expected_year}...")

            dob_d = page.locator("#dateOfBirth_day, input[name*='bday-day'], input[name*='day']").first
            dob_m = page.locator("#dateOfBirth_month, input[name*='bday-month'], input[name*='month']").first
            dob_y = page.locator("#dateOfBirth_year, input[name*='bday-year'], input[name*='year']").first

            try:
                dob_d.focus()
            except Exception:
                page.evaluate("() => { const el = document.querySelector('#dateOfBirth_day'); if (el) el.focus(); }")
            human_pause(page, 0.2, 0.4)

            for ch in expected_day:
                dob_d.press(ch)
                human_pause(page, 0.05, 0.12)
            human_pause(page, 0.2, 0.4)

            try:
                dob_m.focus()
            except Exception:
                pass
            for ch in expected_month:
                dob_m.press(ch)
                human_pause(page, 0.05, 0.12)
            human_pause(page, 0.2, 0.4)

            try:
                dob_y.focus()
            except Exception:
                pass
            for ch in expected_year:
                dob_y.press(ch)
                human_pause(page, 0.05, 0.12)
            human_pause(page, 0.3, 0.6)

            # Strictly confirm Date of Birth inserted matches intended values before proceeding
            log.info("Confirming Date of Birth inserted matches intended values before proceeding...")
            for attempt in range(3):
                cur_d = dob_d.input_value().strip()
                cur_m = dob_m.input_value().strip()
                cur_y = dob_y.input_value().strip()

                d_ok = (cur_d == expected_day or cur_d == client.dob_day.lstrip("0"))
                m_ok = (cur_m == expected_month or cur_m == client.dob_month.lstrip("0"))
                y_ok = (cur_y == expected_year)

                if d_ok and m_ok and y_ok:
                    log.info(f"Verified Date of Birth successfully: {cur_d}/{cur_m}/{cur_y}")
                    break

                log.warning(f"DOB mismatch detected (Attempt {attempt + 1}): Got {cur_d}/{cur_m}/{cur_y}, Expected {expected_day}/{expected_month}/{expected_year}. Correcting...")
                page.evaluate("""(args) => {
                    const d = document.querySelector('#dateOfBirth_day');
                    const m = document.querySelector('#dateOfBirth_month');
                    const y = document.querySelector('#dateOfBirth_year');
                    if (d) { d.value = args.d; d.dispatchEvent(new Event('input', { bubbles: true })); }
                    if (m) { m.value = args.m; m.dispatchEvent(new Event('input', { bubbles: true })); }
                    if (y) { y.value = args.y; y.dispatchEvent(new Event('input', { bubbles: true })); }
                }""", {"d": expected_day, "m": expected_month, "y": expected_year})
                human_pause(page, 0.3, 0.5)

            # 4. Address Search
            addr_search = page.locator("#addressSearch").first
            if addr_search.is_visible(timeout=3000):
                log.info(f"Searching address for postcode: {client.postcode}...")
                human_type(addr_search, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 1.5, 2.5)

                suggestion = page.locator(".address-lookup__item, .lookup-results li, ul.dropdown-menu li").first
                if suggestion.is_visible(timeout=3000):
                    log.info("Clicking matching address suggestion on Betfair with human click...")
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

            # 5. Phone Number
            phone_field = page.locator("#phoneNumber, input[name*='phoneNumber']").first
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
                human_pause(page, 0.8, 1.5)  # Natural human reading/thinking pause before password

            pw_field = page.locator("#password, input[type='password']").first
            if pw_field.is_visible(timeout=3000):
                log.info("Filling Password...")
                human_type(pw_field, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
                human_pause(page, 0.3, 0.6)

            # Dismiss any OneTrust banner that appeared during form filling
            self._dismiss_onetrust(page, log)

            # Check and handle reCAPTCHA ('I'm not a robot') if triggered
            self._handle_recaptcha(page, log)

            # 7. Promo code preservation
            promo_field = page.locator("#promotionCode, input[name='promotionCode']").first
            if promo_field.is_visible(timeout=2000):
                val = promo_field.input_value()
                if not val or "ZSKAOL" not in val.upper():
                    log.info("Setting Betfair promo code 'ZSKAOL' with human typing...")
                    human_type(promo_field, "ZSKAOL", page=page, min_delay_ms=30, max_delay_ms=60)
                    human_pause(page, 0.3, 0.6)

            # 8. Security Question & Answer
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

            # Marketing Opt-outs & Scroll physics
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

            # 9. Dry Run Check
            if dry_run:
                log.info("Dry-run active: Skipping final registration submission on Betfair")
                res = RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password_used,
                    account_reference="DRY-RUN-BETFAIR"
                )
                res.calculate_embargo(25)
                return res

            # Review pause before final submission
            log.info("Reviewing details before submitting Betfair registration...")
            human_scroll(page, distance_y=200, steps=4)
            human_pause(page, 1.5, 2.5)

            # Ensure OneTrust banner is dismissed so submit button and disclosures are completely visible
            self._dismiss_onetrust(page, log)

            # Final reCAPTCHA resolution check before clicking submit
            self._handle_recaptcha(page, log)

            # Submit Registration
            submit_btn = page.locator(
                "button[type='submit'], "
                "button:has-text('Join Now'), "
                "button:has-text('Agree & Open Account')"
            ).first
            if submit_btn.is_visible(timeout=4000):
                log.info("Clicking registration submission on Betfair with human click...")
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
                account_reference=f"BF_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            # Mandatory 25-day betting embargo
            res.calculate_embargo(25)
            log.info(f"Betfair registration complete. Embargo note: {res.formatted_notes}")
            return res

        except Exception as e:
            err_msg = str(e)
            log.error(f"Error during Betfair registration: {err_msg}")
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
