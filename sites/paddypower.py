"""
Paddy Power Registration Adapter (Phase 2).
Platform: Flutter Entertainment / PPB Group.
Landing Promo: https://redirect.rp-offers.com/?id=9708
Registration Endpoint: https://register.paddypower.com/account/registration
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

logger = get_logger(step="PaddyPowerAdapter")


class PaddyPowerAdapter(BaseSiteAdapter):
    """
    Adapter for Paddy Power account registration.
    Handles Flutter Entertainment registration inputs with realistic human cadence,
    Bezier mouse trajectories, address lookup, robust Date of Birth input activation,
    and automatically enforces the mandatory 25-day betting embargo.
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

    def navigate(self, page: Page, promo_url: Optional[str] = None) -> bool:
        """Navigates to the promo landing page and performs session warming before registration."""
        log = logger.bind(site=self.site_name, step="navigate")
        target_url = promo_url or self.default_promo_url
        self._warm_session(page, log, target_url=target_url)
        return True

    def _warm_session(self, page: Page, log, target_url: Optional[str] = None):
        """
        Warms the session's cookie jar by visiting the promotional landing page or home page first,
        accepting cookies, simulating natural browsing/scrolling, and clicking the in-page CTA.
        This establishes authentic session cookies, analytics identifiers, and natural HTTP Referer headers.
        """
        warm_url = target_url or self.default_promo_url
        log.info(f"Session Warming: Visiting promotional landing page '{warm_url}' to warm cookie jar...")
        try:
            page.goto(warm_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2.0, 3.5)

            # Let tracking and redirects settle
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass

            # Accept cookies immediately so session cookies and consent are stored
            self._dismiss_onetrust(page, log)

            # Simulate authentic human browsing on the landing page
            log.info("Session Warming: Simulating authentic user browsing, mouse movement, and scrolling...")
            human_scroll(page, distance_y=random.randint(220, 420), steps=5)
            human_pause(page, 1.5, 2.8)

            # Slight scroll back to simulate reviewing the offer
            human_scroll(page, distance_y=-random.randint(100, 200), steps=3)
            human_pause(page, 0.8, 1.5)

            # If on landing page, transit to registration via natural CTA click with authentic Referer
            cta = page.locator(
                "a:has-text('Join Here'), "
                "a:has-text('Join Now'), "
                "a:has-text('Sign Up'), "
                "button:has-text('Join Here'), "
                "button:has-text('Join Now'), "
                "button:has-text('Sign Up'), "
                "a[href*='register.paddypower.com'], "
                "button[href*='register.paddypower.com']"
            ).first

            if cta.is_visible(timeout=3500):
                cta_text = cta.inner_text().strip() if cta.is_visible() else "CTA"
                log.info(f"Session Warming: Clicking landing page CTA '{cta_text}' to transit to registration...")
                human_click(cta, page)
                human_pause(page, 2.5, 4.0)
            else:
                log.info("Session Warming: CTA not found, navigating to registration endpoint with warmed cookies and referer...")
                page.goto(
                    "https://register.paddypower.com/account/registration",
                    referer=page.url,
                    wait_until="domcontentloaded"
                )
                human_pause(page, 2.0, 3.0)

            # Ensure we are fully loaded on registration page
            try:
                page.wait_for_selector("#firstName, #email, #phoneNumber", timeout=18000)
            except PlaywrightTimeoutError:
                log.warning("Paddy Power form selectors not immediately visible, retrying direct registration...")
                page.goto("https://register.paddypower.com/account/registration", wait_until="domcontentloaded")
                human_pause(page, 2.0, 3.0)

            # Check and dismiss OneTrust on registration domain
            self._dismiss_onetrust(page, log)
            log.info("Session Warming successfully completed: Registration page loaded with pre-warmed cookie jar.")

        except Exception as e:
            log.warning(f"Session Warming fallback due to error: {e}. Navigating to registration...")
            try:
                page.goto("https://register.paddypower.com/account/registration", wait_until="domcontentloaded")
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
                log.info("Accepting OneTrust cookies with human click...")
                human_click(btn, page)
                human_pause(page, 0.4, 0.8)
        except Exception as e:
            log.debug(f"OneTrust banner not visible: {e}")

        # Inject persistent auto-dismissal observer into the page DOM
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
        Detects and handles Google reCAPTCHA Enterprise ('I'm not a robot') on the form.
        1. Attempts automated click on the reCAPTCHA anchor checkbox.
        2. In visual / non-headless runs, alerts the operator and pauses so they can solve any puzzle challenge.
        3. Returns True if verified/clear, or False if blocked.
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

            log.warning("Google reCAPTCHA ('I'm not a robot') detected on Paddy Power form!")

            # Try to locate and click the checkbox anchor inside the frame
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
                    # Check token in response textarea
                    tok = page.locator("textarea[name='g-recaptcha-response'], #g-recaptcha-response").first
                    if tok.count() > 0:
                        val = tok.input_value()
                        if val and len(val) > 10:
                            return True
                    # Check iframe aria-checked
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

            # If manual challenge is shown, alert operator and wait in visual/desktop runs
            log.warning(
                f"⚠️ reCAPTCHA ('I'm not a robot') challenge requires operator interaction! "
                f"Waiting up to {max_wait_sec}s for operator to solve it in the browser window..."
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
        sec_answer = f"{client.last_name}Vale"

        if dry_run and (page is None or not hasattr(page, "goto") or type(page).__name__ == "MagicMock"):
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
            # Check if page is already on registration endpoint (e.g. from prior navigate() session warming)
            is_already_on_reg = False
            try:
                if "registration" in page.url:
                    is_already_on_reg = True
            except Exception:
                pass

            if not is_already_on_reg:
                self._warm_session(page, log, target_url=self.default_promo_url)
            else:
                log.info("Session already warmed and present on Paddy Power registration page.")
                self._dismiss_onetrust(page, log)

            # Ensure form elements are fully rendered before proceeding
            try:
                page.wait_for_selector("#firstName, input[name='firstName'], #email", timeout=20000)
                human_pause(page, 0.5, 1.0)
            except Exception:
                log.warning("Initial form selector wait timed out, continuing...")

            # 1. Title / Gender selection (Top Left)
            resolved_title = getattr(client, "resolved_title", "Mr.")
            is_female = resolved_title in ("Mrs.", "Miss", "Ms.")
            gender_id = "#gender-MRS" if is_female else "#gender-MR"
            gender_lbl = "label[for='gender-MRS']" if is_female else "label[for='gender-MR']"
            gender_el = page.locator(f"{gender_lbl}, {gender_id}").first
            if gender_el.is_visible(timeout=3000):
                log.info(f"Selecting gender/title '{resolved_title}' with human click...")
                human_click(gender_el, page)
            else:
                page.evaluate(f"() => {{ const el = document.querySelector('{gender_id}'); if (el) el.click(); }}")
            human_pause(page, 0.3, 0.6)

            # 2. First Name & Last Name (Top Left)
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

            # 3. Date of Birth (Left Column)
            expected_day = client.dob_day.zfill(2)
            expected_month = client.dob_month.zfill(2)
            expected_year = str(client.dob_year)
            log.info(f"Filling Date of Birth: {expected_day}/{expected_month}/{expected_year}...")

            # 1. Activate Date of Birth container to expand day/month/year inputs without pointer interception
            dob_container = page.locator("div[data-qa-selector='dateOfBirth-wrapper'], .rgx-date-wrapper, .rgx-date-inputs").first
            if dob_container.is_visible(timeout=3000):
                try:
                    dob_container.click(force=True)
                except Exception:
                    page.evaluate("() => { const el = document.querySelector(\"div[data-qa-selector='dateOfBirth-wrapper'], .rgx-date-wrapper\"); if (el) el.click(); }")
                human_pause(page, 0.3, 0.5)

            dob_d = page.locator("#dateOfBirth_day, input[name*='bday-day'], input[data-qa-selector='dateOfBirth_day']").first
            dob_m = page.locator("#dateOfBirth_month, input[name*='bday-month'], input[data-qa-selector='dateOfBirth_month']").first
            dob_y = page.locator("#dateOfBirth_year, input[name*='bday-year'], input[data-qa-selector='dateOfBirth_year']").first

            # Ensure day input is visible/ready
            try:
                dob_d.wait_for(state="visible", timeout=3000)
            except Exception:
                pass

            # Focus and type Day digits
            try:
                dob_d.click(force=True)
                dob_d.press_sequentially(expected_day, delay=60)
            except Exception:
                try:
                    dob_d.focus()
                    dob_d.press_sequentially(expected_day, delay=60)
                except Exception:
                    pass
            human_pause(page, 0.15, 0.3)

            # Focus and type Month digits
            try:
                dob_m.click(force=True)
                dob_m.press_sequentially(expected_month, delay=60)
            except Exception:
                try:
                    dob_m.focus()
                    dob_m.press_sequentially(expected_month, delay=60)
                except Exception:
                    pass
            human_pause(page, 0.15, 0.3)

            # Focus and type Year digits
            try:
                dob_y.click(force=True)
                dob_y.press_sequentially(expected_year, delay=60)
            except Exception:
                try:
                    dob_y.focus()
                    dob_y.press_sequentially(expected_year, delay=60)
                except Exception:
                    pass
            human_pause(page, 0.2, 0.4)

            # Commit date
            try:
                page.keyboard.press("Tab")
            except Exception:
                pass
            human_pause(page, 0.3, 0.5)

            # Strictly verify Date of Birth was populated; apply native React setter fallback if unpopulated
            cur_d = dob_d.input_value().strip() if dob_d.count() > 0 else ""
            cur_y = dob_y.input_value().strip() if dob_y.count() > 0 else ""
            if not cur_d or not cur_y:
                log.warning(f"DOB unpopulated after keystrokes (day='{cur_d}', year='{cur_y}'), applying native React/Angular value setter fallback...")
                page.evaluate("""(args) => {
                    function setReactValue(input, value) {
                        if (!input) return;
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        if (setter) {
                            setter.call(input, value);
                        } else {
                            input.value = value;
                        }
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        input.dispatchEvent(new Event('blur', { bubbles: true }));
                    }
                    setReactValue(document.querySelector('#dateOfBirth_day'), args.d);
                    setReactValue(document.querySelector('#dateOfBirth_month'), args.m);
                    setReactValue(document.querySelector('#dateOfBirth_year'), args.y);
                }""", {"d": expected_day, "m": expected_month, "y": expected_year})
                human_pause(page, 0.2, 0.4)

            # Dismiss any OneTrust banner that appeared during form filling
            self._dismiss_onetrust(page, log)

            # Check and handle reCAPTCHA ('I'm not a robot') if triggered
            self._handle_recaptcha(page, log)

            # 4. Address Search / Manual Entry (Left Column)
            addr_search = page.locator(
                "#addressSearch, "
                "#addressLookup, "
                "input[placeholder*='Postcode or Address'], "
                "input[placeholder*='Postcode'], "
                "input[placeholder*='Address'], "
                "input[name*='addressSearch'], "
                "input[name*='addressLookup']"
            ).first
            address_filled = False
            if addr_search.is_visible(timeout=3000):
                log.info(f"Searching address by postcode: {client.postcode}...")
                human_type(addr_search, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 1.5, 2.5)

                suggestion = page.locator(".address-lookup__item, .lookup-results li, ul.dropdown-menu li, .rgx-dropdown__option, li[class*='address']").first
                if suggestion.is_visible(timeout=3000):
                    log.info("Clicking matching address suggestion with human click...")
                    human_click(suggestion, page)
                    human_pause(page, 0.5, 1.0)
                    address_filled = True

            if not address_filled:
                manual_btn = page.locator("button:has-text('Enter address manually'), a:has-text('Enter address manually'), span:has-text('Enter address manually')").first
                if manual_btn.is_visible(timeout=2000):
                    log.info("Entering address manually...")
                    human_click(manual_btn, page)
                    human_pause(page, 0.5, 1.0)
                    for sel, val in [
                        ("#address1, #addressLine1, input[name*='address1'], input[name*='address'], input[placeholder*='Address']", client.address_line1),
                        ("#city, input[name*='city'], input[name*='town'], input[placeholder*='Town'], input[placeholder*='City']", client.town_city),
                        ("#postcode, #postCode, input[name*='postcode'], input[name*='postCode'], input[placeholder*='Postcode']", client.postcode)
                    ]:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=1500):
                            human_type(loc, val, page=page, min_delay_ms=30, max_delay_ms=65)
                            human_pause(page, 0.3, 0.6)

            # 5. Phone Number (UK national format - Left Column)
            phone_field = page.locator(
                "#phoneNumber, "
                "#mobileNumber, "
                "input[name*='tel-national'], "
                "input[name*='mobileNumber'], "
                "input[name*='phoneNumber'], "
                "input[placeholder*='Mobile number'], "
                "input[placeholder*='Mobile'], "
                "input[type='tel']"
            ).first
            if phone_field.is_visible(timeout=3000):
                clean_phone = client.phone.lstrip("0") if client.phone.startswith("0") else client.phone
                log.info(f"Filling Phone: {clean_phone}")
                human_type(phone_field, clean_phone, page=page, min_delay_ms=35, max_delay_ms=75)
                human_pause(page, 0.3, 0.6)

            # 6. Email & Password (Right Column)
            email_field = page.locator("#email, input[type='email'], input[name='email']").first
            if email_field.is_visible(timeout=3000):
                log.info(f"Filling Email: {client.email}")
                human_type(email_field, client.email, page=page, min_delay_ms=25, max_delay_ms=60)
                human_pause(page, 0.8, 1.5)  # Natural human reading/thinking pause before password

            pw_field = page.locator("#password, input[type='password'], input[name='password']").first
            if pw_field.is_visible(timeout=3000):
                log.info("Filling Password...")
                human_type(pw_field, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
                human_pause(page, 0.4, 0.7)

            # 7. Security Question & Answer (Right Column)
            sec_q = page.locator("#securityQuestion, select[name='securityQuestion']").first
            if sec_q.is_visible(timeout=2500):
                try:
                    sec_q.select_option(index=1)
                    human_pause(page, 0.3, 0.5)
                except Exception:
                    pass
            sec_a = page.locator("#securityAnswer, input[name='securityAnswer']").first
            if sec_a.is_visible(timeout=2000):
                log.info("Filling Security Answer...")
                human_type(sec_a, sec_answer, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # 8. Deposit Limit (Time period & Limit amount - Lower Right)
            log.info("Configuring Deposit Limit...")
            limit_freq = page.locator("#depositLimitPeriod, [data-qa-selector='depositLimitPeriod'], #depositLimitFrequency, select[name*='depositLimit']").first
            if limit_freq.is_visible(timeout=2000):
                try:
                    limit_freq.select_option(value="DAY")
                except Exception:
                    try:
                        limit_freq.select_option(label="Daily")
                    except Exception:
                        pass
                page.evaluate("""() => {
                    const sel = document.querySelector('#depositLimitPeriod, [data-qa-selector="depositLimitPeriod"], select[name*="depositLimit"]');
                    if (sel) {
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""")
                human_pause(page, 0.3, 0.6)

            limit_amt = page.locator("#depositLimitAmount, [data-qa-selector='depositLimitAmount'], input[name*='depositLimitAmount']").first
            if limit_amt.is_visible(timeout=2000):
                try:
                    page.wait_for_selector("#depositLimitAmount:not([disabled]), [data-qa-selector='depositLimitAmount']:not([disabled])", timeout=4000)
                except Exception:
                    pass
                deposit_val = getattr(client, "deposit_limit", None) or "250"
                log.info(f"Filling Deposit Limit amount: £{deposit_val}")
                human_type(limit_amt, str(deposit_val), page=page, min_delay_ms=30, max_delay_ms=60)
                page.evaluate("""(val) => {
                    const inp = document.querySelector('#depositLimitAmount, [data-qa-selector="depositLimitAmount"]');
                    if (inp && (!inp.value || inp.value.trim() === '')) {
                        inp.focus();
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                        if (nativeSetter) nativeSetter.call(inp, String(val));
                        else inp.value = String(val);
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                        inp.blur();
                    }
                }""", deposit_val)
                human_pause(page, 0.3, 0.6)

            # 9. Funds Protection / Terms Acknowledgement (Bottom Right)
            log.info("Acknowledging Funds Protection policy...")
            self._dismiss_onetrust(page, log)
            funds_btn = page.locator(
                "button[data-qa-selector='customerFundsProtection'], "
                "button[data-testid='customerFundsProtection'], "
                ".rgx-funds-protection button[role='checkbox'], "
                "button[role='checkbox'].rgx-checkbox"
            ).first
            if funds_btn.is_visible(timeout=2000):
                is_checked = funds_btn.get_attribute("aria-checked") == "true"
                if not is_checked:
                    log.info("Toggling Funds Protection checkbox...")
                    try:
                        human_click(funds_btn, page)
                    except Exception:
                        funds_btn.click(force=True)
                    human_pause(page, 0.4, 0.8)
                    if funds_btn.get_attribute("aria-checked") != "true":
                        page.evaluate("""() => {
                            const btn = document.querySelector("button[data-qa-selector='customerFundsProtection'], button[data-testid='customerFundsProtection']");
                            if (btn && btn.getAttribute('aria-checked') !== 'true') {
                                btn.click();
                            }
                        }""")
            else:
                tc_checkbox = page.locator("#termsAndConditions_acknowledgement, input[name='termsAndConditions_acknowledgement']").first
                if tc_checkbox.count() > 0:
                    if not tc_checkbox.is_checked():
                        tc_label = page.locator(
                            "label[for='termsAndConditions_acknowledgement'], "
                            ".rgx-checkbox-container:has(#termsAndConditions_acknowledgement), "
                            "label:has-text('I acknowledge that Paddy Power holds my funds'), "
                            "label:has-text('I acknowledge')"
                        ).first
                        if tc_label.is_visible(timeout=2000):
                            human_click(tc_label, page)
                            human_pause(page, 0.4, 0.8)
                        else:
                            tc_checkbox.check(force=True)

                    if not tc_checkbox.is_checked():
                        page.evaluate("""() => {
                            const cb = document.querySelector('#termsAndConditions_acknowledgement, input[name=\"termsAndConditions_acknowledgement\"]');
                            if (cb) {
                                cb.checked = true;
                                cb.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }""")
            human_pause(page, 0.4, 0.8)

            # 10. Marketing Preferences
            page.evaluate("""() => {
                const optOuts = Array.from(document.querySelectorAll('input[type=\"checkbox\"], input[type=\"radio\"]'));
                for (let el of optOuts) {
                    if (el.id === 'termsAndConditions_acknowledgement' || el.name === 'termsAndConditions_acknowledgement') {
                        continue;
                    }
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

            # Ensure OneTrust banner is dismissed so submit button and disclosures are completely visible
            self._dismiss_onetrust(page, log)

            # Final reCAPTCHA resolution check before clicking submit
            self._handle_recaptcha(page, log)

            # Submit Registration
            submit_btn = page.locator(
                "button[data-qa-selector='joinButton'], "
                "button[data-testid='joinButton'], "
                "button:has-text('Sign Up'), "
                "button[type='submit'], "
                "button:has-text('Join Now'), "
                "button:has-text('Agree & Open Account'), "
                "button:has-text('Open Account')"
            ).first
            if submit_btn.is_visible(timeout=4000):
                log.info("Clicking registration submission on Paddy Power with human click...")
                human_click(submit_btn, page)

            # Dynamic wait for verification results post-submission
            log.info("Waiting for post-submission verification results on Paddy Power...")
            status, summary, ref = self._wait_for_verification_results(page, client, log)

            # Capture proof screenshot of final verification state
            try:
                proof_path = Path("artifacts") / f"paddypower_result_{client.client_id}.png"
                proof_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(proof_path), full_page=False)
                screenshot_path = str(proof_path)
            except Exception:
                screenshot_path = None

            res = RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=status,
                email=client.email,
                username=client.email,
                password=password_used,
                account_reference=ref or f"PP_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                error_summary=summary,
                screenshot_path=screenshot_path
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
            res = RegistrationResult(
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
            res.calculate_embargo(25)
            return res

    def _wait_for_verification_results(self, page: Page, client: Client, log) -> tuple[RegistrationStatus, Optional[str], Optional[str]]:
        """
        Waits continuously until the state of the page changes as post-registration
        verification, KYC assessment, or duplicate checks finish.
        """
        max_wait_seconds = 180
        start_time = time.time()
        last_log_time = start_time

        log.info("Waiting for Paddy Power post-submission page state change and verification completion...")

        time.sleep(2.0)

        while time.time() - start_time < max_wait_seconds:
            elapsed = time.time() - start_time

            if time.time() - last_log_time >= 5.0:
                log.info(f"Still waiting for Paddy Power verification to complete... ({elapsed:.0f}s elapsed)")
                last_log_time = time.time()

            try:
                body_text = page.locator("body").inner_text(timeout=1000)
            except Exception:
                body_text = ""

            lower_body = body_text.lower()
            current_url = page.url.lower()

            # 1. Duplicate / Already Registered State
            if any(kw in lower_body for kw in [
                "already registered", "already exists", "account exists",
                "email already in use", "username already taken", "duplicate account",
                "an account with these details already exists"
            ]):
                log.warning(f"Page state changed: Paddy Power reported client {client.full_name} is ALREADY REGISTERED ({elapsed:.1f}s)")
                return RegistrationStatus.ALREADY_REGISTERED, "Account details already registered", None

            # 2. reCAPTCHA Error
            if any(kw in lower_body for kw in [
                "please follow the instructions above", "not a robot", "recaptcha"
            ]):
                log.warning(f"Page state changed: Paddy Power reCAPTCHA required verification ({elapsed:.1f}s)")
                return RegistrationStatus.MANUAL_REVIEW, "CAPTCHA verification required ('I\\'m not a robot')", None

            # 3. Validation / Submission Error
            error_loc = page.locator(
                '.rgx-field-error, .rgx-message--error, [class*="error-message"]:visible, [role="alert"]:visible'
            ).first
            if error_loc.is_visible(timeout=100):
                err_text = error_loc.inner_text().strip()
                if (
                    err_text
                    and len(err_text) > 3
                    and not any(ign in err_text.lower() for ign in ["cookie", "script", "select", "optional"])
                ):
                    log.warning(f"Page state changed: Paddy Power displayed submission error: '{err_text}' ({elapsed:.1f}s)")
                    return RegistrationStatus.FAILED, f"Validation error: {err_text}", None

            # 3. Pending Verification / KYC State
            if any(kw in lower_body for kw in [
                "identity verification", "verify your identity", "upload documents",
                "pending verification", "further verification required", "account under review",
                "kyc verification", "identity check"
            ]):
                log.info(f"Page state changed: Paddy Power requested KYC / Identity Verification ({elapsed:.1f}s)")
                return RegistrationStatus.MANUAL_REVIEW, "KYC / Account verification required", None

            # 4. Deposit Screen / Navigation away from registration
            if "registration" not in current_url:
                log.info(f"Page state changed: Paddy Power navigated to post-registration page '{page.url}' ({elapsed:.1f}s)")
                return RegistrationStatus.SUCCESS, "Registration completed successfully", None

            deposit_visible = any(
                page.locator(sel).first.is_visible(timeout=150)
                for sel in [
                    'button:has-text("Deposit")', 'a:has-text("Deposit")',
                    '[data-qa-selector*="deposit"]', '[class*="deposit" i]'
                ]
            )
            if deposit_visible:
                log.info(f"Page state changed: Paddy Power displayed deposit screen ({elapsed:.1f}s)")
                return RegistrationStatus.SUCCESS, "Registration succeeded (Deposit screen displayed)", None

            time.sleep(1.0)

        log.warning(f"Timeout of {max_wait_seconds}s reached waiting for Paddy Power verification.")
        return RegistrationStatus.MANUAL_REVIEW, "Timeout waiting for post-submission page change", None
