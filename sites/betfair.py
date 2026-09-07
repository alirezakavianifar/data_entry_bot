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
                account_reference="DRY-RUN-BETFAIR"
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
                log.info("Session already warmed and present on Betfair registration page.")
                self._dismiss_onetrust(page, log)

            # Ensure form elements are fully rendered before proceeding
            try:
                page.wait_for_selector("#firstName, input[name='firstName'], #email", timeout=20000)
                human_pause(page, 0.5, 1.0)
            except Exception:
                log.warning("Initial form selector wait timed out, continuing...")

            # 1. Gender / Title
            resolved_title = getattr(client, "resolved_title", "Mr.")
            is_female = resolved_title in ("Mrs.", "Miss", "Ms.")
            gender_id = "#gender-female" if is_female else "#gender-male"
            gender_lbl = "label[for='gender-female']" if is_female else "label[for='gender-male']"
            gender_el = page.locator(f"{gender_lbl}, {gender_id}").first
            if gender_el.is_visible(timeout=3000):
                log.info(f"Selecting gender '{'female' if is_female else 'male'}' on Betfair with human click...")
                human_click(gender_el, page)
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

            dob_d = page.locator("#dateOfBirth_day, input[name*='bday-day'], input[name*='day'], input[data-qa-selector='dateOfBirth_day']").first
            dob_m = page.locator("#dateOfBirth_month, input[name*='bday-month'], input[name*='month'], input[data-qa-selector='dateOfBirth_month']").first
            dob_y = page.locator("#dateOfBirth_year, input[name*='bday-year'], input[name*='year'], input[data-qa-selector='dateOfBirth_year']").first

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
                log.info(f"Searching address for postcode: {client.postcode}...")
                human_type(addr_search, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 1.5, 2.5)

                suggestion = page.locator(".address-lookup__item, .lookup-results li, ul.dropdown-menu li, .rgx-dropdown__option, li[class*='address']").first
                if suggestion.is_visible(timeout=3000):
                    log.info("Clicking matching address suggestion on Betfair with human click...")
                    human_click(suggestion, page)
                    human_pause(page, 0.5, 1.0)
                    address_filled = True

            if not address_filled:
                manual_btn = page.locator("button:has-text('Enter address manually'), a:has-text('Enter address manually'), span:has-text('Enter address manually')").first
                if manual_btn.is_visible(timeout=2000):
                    log.info("Entering address manually on Betfair...")
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
                "input[name*='phoneNumber'], "
                "input[name*='mobileNumber'], "
                "input[placeholder*='Mobile number'], "
                "input[placeholder*='Mobile'], "
                "input[type='tel']"
            ).first
            if phone_field.is_visible(timeout=3000):
                clean_phone = client.phone.lstrip("0") if client.phone.startswith("0") else client.phone
                log.info(f"Filling Phone: {clean_phone}")
                human_type(phone_field, clean_phone, page=page, min_delay_ms=35, max_delay_ms=75)
                # Unfocus phone field to trigger website inline validation
                try:
                    phone_field.evaluate("el => { el.dispatchEvent(new Event('blur', { bubbles: true })); el.blur(); }")
                except Exception:
                    pass
                human_pause(page, 0.6, 1.0)

                # Check if website rejected or failed to validate the mobile number
                phone_err = page.locator(
                    "span.validation-message.error, "
                    ".phone-number-items .validation-message, "
                    ".phone-number-items .error, "
                    ".phone-number-items .state-read-invalid, "
                    "span:has-text('could not validate your mobile number'), "
                    "div:has-text('could not validate your mobile number'), "
                    ".state-read-invalid input#phoneNumber, "
                    "[data-qa-selector*='phoneNumber'] ~ .validation-message"
                ).first
                if phone_err.is_visible(timeout=1500):
                    err_txt = ""
                    try:
                        err_span = page.locator("span.validation-message.error, .phone-number-items .validation-message, span:has-text('could not validate')").first
                        if err_span.is_visible(timeout=800):
                            err_txt = err_span.inner_text().strip()
                    except Exception:
                        pass
                    if not err_txt:
                        err_txt = "We could not validate your mobile number, please check and try again."

                    log.warning(f"❌ Mobile phone validation failed on Betfair for {client.full_name}: '{err_txt}' (Phone entered: {clean_phone})")
                    screenshot_path = None
                    try:
                        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "phone_validation", Exception(err_txt))
                        screenshot_path = str(bundle.screenshot_path) if bundle else None
                    except Exception:
                        pass

                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        error_summary=f"Invalid phone number: {err_txt}",
                        notes=f"Phone number validation failed on Betfair: '{err_txt}'. Please check client mobile number ({client.phone}).",
                        screenshot_path=screenshot_path
                    )


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

            # 7. Promo code preservation (Right Column)
            promo_field = page.locator("#promotionCode, input[name='promotionCode']").first
            if promo_field.is_visible(timeout=2000):
                val = promo_field.input_value()
                if not val or "ZSKAOL" not in val.upper():
                    log.info("Setting Betfair promo code 'ZSKAOL' with human typing...")
                    human_type(promo_field, "ZSKAOL", page=page, min_delay_ms=30, max_delay_ms=60)
                    human_pause(page, 0.3, 0.6)

            # 8. Security Question & Answer (Right Column)
            sec_q = page.locator("select#securityQuestion, select[data-qa-selector='securityQuestion'], select[name='securityQuestion']").first
            if sec_q.is_visible(timeout=2500):
                try:
                    human_click(sec_q, page)
                    sec_q.select_option(index=1)
                    human_pause(page, 0.3, 0.5)
                except Exception:
                    pass
                page.evaluate("""() => {
                    const sel = document.querySelector("select#securityQuestion, select[data-qa-selector='securityQuestion']");
                    if (sel) {
                        if (!sel.value) sel.selectedIndex = 1;
                        sel.dispatchEvent(new Event('input', { bubbles: true }));
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""")
                human_pause(page, 0.2, 0.4)

            sec_a = page.locator("input#securityAnswer, input[data-qa-selector='securityAnswer'], input[name='securityAnswer']").first
            if sec_a.is_visible(timeout=2500):
                log.info(f"Filling Security Answer: {sec_answer}")
                try:
                    human_click(sec_a, page)
                except Exception:
                    sec_a.click(force=True)
                human_type(sec_a, sec_answer, page=page, min_delay_ms=30, max_delay_ms=65)
                page.evaluate("""(val) => {
                    const inp = document.querySelector("input#securityAnswer, input[data-qa-selector='securityAnswer']");
                    if (inp) {
                        inp.focus();
                        if (!inp.value || inp.value.trim() === '') {
                            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                            if (nativeSetter) nativeSetter.call(inp, String(val));
                            else inp.value = String(val);
                        }
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                        inp.dispatchEvent(new Event('blur', { bubbles: true }));
                        inp.blur();
                    }
                }""", sec_answer)
                human_pause(page, 0.3, 0.6)

            # 9. Deposit Limit (Time period & Limit amount - Lower Right)
            log.info("Configuring Deposit Limit...")
            limit_freq = page.locator("select#depositLimitPeriod, select[data-qa-selector='depositLimitPeriod'], select[name*='depositLimit'], select#depositLimitFrequency").first
            if limit_freq.is_visible(timeout=2000):
                try:
                    limit_freq.select_option(value="DAY")
                except Exception:
                    try:
                        limit_freq.select_option(label="Daily")
                    except Exception:
                        pass
                page.evaluate("""() => {
                    const sel = document.querySelector("select[data-qa-selector='depositLimitPeriod'], select#depositLimitPeriod, select[name*='depositLimit']");
                    if (sel) {
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""")
                human_pause(page, 0.3, 0.6)

            limit_amt = page.locator("input#depositLimitAmount, input[data-qa-selector='depositLimitAmount'], input[name*='depositLimitAmount']").first
            if limit_amt.is_visible(timeout=2000):
                try:
                    page.wait_for_selector("input#depositLimitAmount:not([disabled]), input[data-qa-selector='depositLimitAmount']:not([disabled])", timeout=4000)
                except Exception:
                    pass
                deposit_val = getattr(client, "deposit_limit", None) or "250"
                log.info(f"Filling Deposit Limit amount: £{deposit_val}")
                human_type(limit_amt, str(deposit_val), page=page, min_delay_ms=30, max_delay_ms=60)
                try:
                    page.evaluate("""(val) => {
                        const inp = document.querySelector('input#depositLimitAmount, input[data-qa-selector="depositLimitAmount"]');
                        if (inp && (!inp.value || inp.value.trim() === '')) {
                            inp.focus();
                            inp.value = String(val);
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                            inp.blur();
                        }
                    }""", deposit_val)
                except Exception:
                    pass
                human_pause(page, 0.3, 0.6)

            # 10. Funds Protection / Terms Acknowledgement (Mandatory to enable Sign Up)
            log.info("Acknowledging Funds Protection policy...")
            self._dismiss_onetrust(page, log)
            funds_btn = page.locator(
                "button[data-qa-selector='customerFundsProtection'], "
                "button[data-testid='customerFundsProtection'], "
                ".rgx-funds-protection button[role='checkbox'], "
                "button[role='checkbox'].rgx-checkbox"
            ).first
            if funds_btn.is_visible(timeout=1500):
                is_checked = funds_btn.get_attribute("aria-checked") == "true"
                if not is_checked:
                    log.info("Toggling Funds Protection button...")
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
                tc_checkbox = page.locator(
                    "#customerFundsProtection, "
                    "input[data-qa-selector='customerFundsProtection'], "
                    "input[name='customerFundsProtection'], "
                    "#termsAndConditions_acknowledgement, "
                    "input[name='termsAndConditions_acknowledgement']"
                ).first
                if tc_checkbox.count() > 0:
                    if not tc_checkbox.is_checked():
                        tc_label = page.locator(
                            "label[data-qa-selector='label_customerFundsProtection'], "
                            "label[for='customerFundsProtection'], "
                            "label:has(#customerFundsProtection), "
                            "label[for='termsAndConditions_acknowledgement'], "
                            ".rgx-checkbox-container:has(#termsAndConditions_acknowledgement), "
                            "label:has-text('Betfair holds my funds'), "
                            "label:has-text('Paddy Power holds my funds'), "
                            "label:has-text('holds my funds'), "
                            "label:has-text('I acknowledge')"
                        ).first
                        if tc_label.is_visible(timeout=1500):
                            log.info("Clicking Funds Protection label...")
                            try:
                                human_click(tc_label, page)
                            except Exception:
                                tc_label.click(force=True)
                            human_pause(page, 0.4, 0.8)
                        else:
                            tc_checkbox.check(force=True)

                    if not tc_checkbox.is_checked():
                        page.evaluate("""() => {
                            const cb = document.querySelector('#customerFundsProtection, input[data-qa-selector=\"customerFundsProtection\"], #termsAndConditions_acknowledgement, input[name=\"termsAndConditions_acknowledgement\"]');
                            if (cb) {
                                cb.checked = true;
                                cb.dispatchEvent(new Event('input', { bubbles: true }));
                                cb.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }""")
            human_pause(page, 0.4, 0.8)

            # Marketing Opt-outs & Scroll physics
            human_scroll(page, distance_y=250, steps=5)
            human_pause(page, 0.4, 0.8)

            page.evaluate("""() => {
                const optOuts = Array.from(document.querySelectorAll('input[type=\"checkbox\"], input[type=\"radio\"]'));
                for (let el of optOuts) {
                    if (el.id === 'termsAndConditions_acknowledgement' || el.name === 'termsAndConditions_acknowledgement' ||
                        el.id === 'customerFundsProtection' || el.name === 'customerFundsProtection' ||
                        el.getAttribute('data-qa-selector') === 'customerFundsProtection') {
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

            # Pre-submission form validation check: Scan for visible error messages
            visible_errs = page.locator("span.validation-message.error, .validation-message.error, .form-error, .error-message").all()
            err_texts = [e.inner_text().strip() for e in visible_errs if e.is_visible() and e.inner_text().strip()]
            if err_texts:
                err_summary = "; ".join(dict.fromkeys(err_texts))
                log.warning(f"❌ Betfair registration form has validation errors before submit: {err_summary}")
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "pre_submit_validation", Exception(err_summary))
                screenshot_path = str(bundle.screenshot_path) if bundle else None
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    error_summary=f"Form validation failed: {err_summary}",
                    notes=f"Betfair form validation error: '{err_summary}'. Please check client details.",
                    screenshot_path=screenshot_path
                )

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
                btn_class = submit_btn.get_attribute("class") or ""
                if "invalid-form-btn" in btn_class:
                    # Attempt recovery: ensure securityAnswer and fundsProtection are triggered
                    page.evaluate("""() => {
                        const sec = document.querySelector("input#securityAnswer, input[data-qa-selector='securityAnswer']");
                        if (sec && sec.value) {
                            sec.dispatchEvent(new Event('input', { bubbles: true }));
                            sec.dispatchEvent(new Event('change', { bubbles: true }));
                            sec.dispatchEvent(new Event('blur', { bubbles: true }));
                        }
                        const dep = document.querySelector("input#depositLimitAmount, input[data-qa-selector='depositLimitAmount']");
                        if (dep && dep.value) {
                            dep.dispatchEvent(new Event('input', { bubbles: true }));
                            dep.dispatchEvent(new Event('change', { bubbles: true }));
                            dep.dispatchEvent(new Event('blur', { bubbles: true }));
                        }
                    }""")
                    human_pause(page, 0.5, 0.8)
                    btn_class = submit_btn.get_attribute("class") or ""

                if "invalid-form-btn" in btn_class:
                    inv_messages = page.evaluate("""() => {
                        const errors = [];
                        // 1. True error elements (excluding password strength indicators like 'Strong. Well done!')
                        document.querySelectorAll('.validation-message.error, .error-message, .form-error, .state-read-invalid .validation-message').forEach(el => {
                            const txt = el.innerText.trim();
                            if (txt && !errors.includes(txt)) {
                                const lower = txt.toLowerCase();
                                if (!lower.includes('strong') && !lower.includes('well done') && !lower.includes('good') && !lower.includes('cookie')) {
                                    errors.push(txt);
                                }
                            }
                        });
                        // 2. Identify any uncompleted or empty required fields
                        document.querySelectorAll('input:not([type="hidden"]), select').forEach(el => {
                            const qa = el.getAttribute('data-qa-selector') || el.id || el.name || '';
                            const state = el.getAttribute('data-qa-state');
                            const val = (el.value || '').trim();
                            if (['promotionCode', 'languageSelector', 'country'].includes(qa)) return;
                            if (state === 'is-invalid') {
                                errors.push(`${qa || 'Field'} is invalid`);
                            } else if (!val && el.offsetParent !== null) {
                                if (el.type === 'checkbox' && !el.checked) {
                                    errors.push(`${qa || 'Checkbox'} is required`);
                                } else if (el.type !== 'checkbox' && el.type !== 'radio') {
                                    errors.push(`${qa || 'Field'} is not filled`);
                                }
                            }
                        });
                        return errors;
                    }""")
                    inv_summary = "; ".join(dict.fromkeys(inv_messages)) if inv_messages else "Join button disabled due to incomplete/invalid field(s)"
                    log.warning(f"❌ Cannot submit Betfair form: {inv_summary}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "submit_disabled", Exception(inv_summary))
                    screenshot_path = str(bundle.screenshot_path) if bundle else None
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        error_summary=f"Form submission blocked: {inv_summary}",
                        notes=f"Betfair registration blocked: {inv_summary}",
                        screenshot_path=screenshot_path
                    )

                log.info("Clicking registration submission on Betfair with human click...")
                human_click(submit_btn, page)

            # Post-submission state monitoring (up to 15s)
            log.info("Waiting for Betfair post-submission confirmation or verification...")
            post_start = time.time()
            post_err_found = None
            while time.time() - post_start < 15:
                cur_url = page.url.lower()
                if any(x in cur_url for x in ["deposit", "onboarding", "success", "verification", "kyc", "portal"]):
                    log.info(f"Page navigated to post-registration target: {page.url}")
                    break

                # Check for post-submission error messages / banners
                post_err_loc = page.locator("span.validation-message.error, .notification--error, .error-banner, div[role='alert'], .alert-danger").first
                if post_err_loc.is_visible(timeout=400):
                    txt = post_err_loc.inner_text().strip()
                    if txt and not any(ign in txt.lower() for ign in ["cookie", "18+"]):
                        post_err_found = txt
                        break

                time.sleep(1.0)

            if post_err_found:
                log.warning(f"❌ Betfair rejected submission: {post_err_found}")
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "post_submit_error", Exception(post_err_found))
                screenshot_path = str(bundle.screenshot_path) if bundle else None
                status = RegistrationStatus.MANUAL_REVIEW if is_pending_verification_error(post_err_found) else RegistrationStatus.FAILED
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=status,
                    email=client.email,
                    error_summary=post_err_found,
                    notes=f"Betfair registration error: {post_err_found}",
                    screenshot_path=screenshot_path
                )

            # If still on the registration form with submit button, verify it did not silently fail
            if "/account/registration" in page.url.lower():
                submit_check = page.locator("button[data-qa-selector='joinButton'], button:has-text('Sign Up')").first
                if submit_check.is_visible(timeout=1000):
                    remaining_errs = page.locator("span.validation-message.error, .validation-message").all()
                    rem_texts = [e.inner_text().strip() for e in remaining_errs if e.is_visible() and e.inner_text().strip()]
                    rem_summary = "; ".join(dict.fromkeys(rem_texts)) if rem_texts else "Registration submission did not advance"
                    log.warning(f"❌ Betfair registration did not complete: {rem_summary}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "submission_stalled", Exception(rem_summary))
                    screenshot_path = str(bundle.screenshot_path) if bundle else None
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        error_summary=rem_summary,
                        notes=f"Betfair submission stalled on form: {rem_summary}",
                        screenshot_path=screenshot_path
                    )

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
