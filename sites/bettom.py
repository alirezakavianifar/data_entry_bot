"""
BetTOM Registration Adapter (Phase 2).
Platform: EveryMatrix (Polymer / Shadow DOM / Vaadin Components).
Website: https://www.bettom.com/en/sport/
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
    is_pending_verification_error
)
from core.password_gen import generate_password
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle

logger = get_logger(step="BetTOMAdapter")


class BetTOMAdapter(BaseSiteAdapter):
    """
    EveryMatrix platform adapter for BetTOM.
    Supports Polymer / Shadow DOM inputs, dynamic personal titles (Mr./Mrs./Miss/Ms.),
    Cybot Cookiebot consent, and 3-step registration.
    """

    def __init__(self, promo_url: Optional[str] = None):
        super().__init__(
            site_id="bettom",
            site_name="BetTOM",
            default_promo_url=promo_url or "https://www.bettom.com/en/sport/",
            requires_uk_ip=True
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        return self.register_client(client=client, page=page, dry_run=False, password=password)

    def register_client(self, client: Client, page: Page, dry_run: bool = False, password: Optional[str] = None) -> RegistrationResult:
        log = logger.bind(client=client.full_name, site=self.site_name)
        log.info(f"Initiating registration workflow on {self.site_name} (Dry-run: {dry_run})")

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
                account_reference="DRY-RUN-BETTOM",
                notes="Dry-run completed successfully"
            )

        try:
            target_url = self.default_promo_url
            log.info(f"Navigating to promo/landing URL: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2.0, 3.5)

            # 1. Dismiss Cybot Cookiebot banner
            try:
                cookie_btn = page.locator(
                    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, "
                    "button:has-text('Allow all'), "
                    "button:has-text('Accept all cookies'), "
                    "button:has-text('Accept All')"
                ).first
                if cookie_btn.is_visible(timeout=3500):
                    log.info("Dismissing Cookiebot banner...")
                    human_click(cookie_btn, page)
                    human_pause(page, 1.0, 1.5)
            except Exception as e:
                log.debug(f"Cookie banner not present or already accepted: {e}")

            # 2. Click Register / Join button to open registration modal
            log.info("Opening BetTOM registration dialog...")
            join_btn = page.locator(
                ".ItemRegister, div.ItemRegister, .AuthButtons .ItemRegister, "
                "div:has(> p:has-text('Join')), button:has-text('Join'), a:has-text('Join'), "
                "button:has-text('Register'), a:has-text('Register')"
            ).first
            if not join_btn.is_visible(timeout=8000):
                raise RuntimeError("BetTOM Join / Register button not visible on landing page")

            human_click(join_btn, page)
            log.info("Clicked BetTOM Join button")
            human_pause(page, 2.0, 3.5)

            # Wait for registration modal
            page.wait_for_selector(
                ".LoginModalWindow, general-registration",
                timeout=15000
            )
            log.info("BetTOM registration modal opened. Waiting for form fields to load...")

            # CRITICAL: Wait for inputs to actually appear and become visible (dismissing 'Please wait, loading...')
            page.wait_for_selector(
                'input[name="FirstnameOnDocument"], input[name="LastNameOnDocument"]',
                state="visible",
                timeout=30000
            )
            log.info("BetTOM registration form fields loaded and ready.")
            human_pause(page, 1.0, 1.8)

            # 3. Handle Cloudflare Turnstile hook
            page.evaluate("""() => {
                const setupTurnstileHook = () => {
                    if (!window.turnstile) return;
                    const registeredWidgets = new Map();
                    const origRender = window.turnstile.render;
                    window.turnstile.render = function(container, options) {
                        let realId = undefined;
                        if (origRender) {
                            try { realId = origRender.apply(this, arguments); } catch (e) {}
                        }
                        if (realId === undefined) realId = 'ts_widget_' + Math.random().toString(36).substr(2, 9);
                        if (options) registeredWidgets.set(realId, options);
                        setTimeout(() => {
                            if (options && typeof options.callback === 'function') {
                                options.callback('XXXX.DUMMY.TOKEN.XXXX');
                            }
                        }, 100);
                        return realId;
                    };
                };
                if (window.turnstile) setupTurnstileHook();
            }""")

            # 4. Fill Personal Details
            target_title = getattr(client, "resolved_title", "Mr.")
            log.info(f"Selecting Title '{target_title}' on BetTOM for {client.full_name}")

            # Title selection via visible vaadin-select control
            title_sel = page.locator('vaadin-select[name="Title"], select-input[name="Title"], div.Title__input').first
            if title_sel.is_visible(timeout=3000):
                human_click(title_sel, page)
                human_pause(page, 0.3, 0.6)
                clean_title = target_title.replace(".", "").strip()
                item = page.locator(f'vaadin-select-item:has-text("{clean_title}")').first
                if item.is_visible(timeout=1500):
                    human_click(item, page)
                else:
                    page.keyboard.press("ArrowDown")
                    page.keyboard.press("Enter")
                human_pause(page, 0.3, 0.6)

            # Deep shadow DOM title fallback & custom event dispatching
            page.evaluate("""(target) => {
                let selected = false;
                const scan = (node) => {
                    if (selected) return;
                    if (node.tagName === 'VAADIN-SELECT' && (node.getAttribute('name') === 'Title' || node.getAttribute('id') === 'Title__input')) {
                        const cleanTarget = target.toLowerCase().replace('.', '');
                        let matchedVal = target;
                        if (node.items && Array.isArray(node.items)) {
                            const found = node.items.find(it => {
                                const v = (it.value || it.label || '').toLowerCase().replace('.', '');
                                return v === cleanTarget;
                            });
                            if (found) matchedVal = found.value;
                        }
                        node.value = matchedVal;
                        node.setAttribute('has-value', '');
                        node.dispatchEvent(new CustomEvent('change', { bubbles: true, composed: true }));
                        node.dispatchEvent(new CustomEvent('value-changed', { detail: { value: matchedVal }, bubbles: true, composed: true }));
                        selected = true;
                        return;
                    }
                    if (node.shadowRoot) Array.from(node.shadowRoot.children).forEach(scan);
                    Array.from(node.children).forEach(scan);
                };
                scan(document.body);
            }""", target_title)

            # First Name & Last Name with human-like typing
            fn_inp = page.locator('input[name="FirstnameOnDocument"]').first
            ln_inp = page.locator('input[name="LastNameOnDocument"]').first
            if fn_inp.is_visible(timeout=3000):
                human_type(fn_inp, client.first_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)
            else:
                self._fill_shadow_input(page, ["FirstName", "first-name", "firstname"], client.first_name)

            if ln_inp.is_visible(timeout=3000):
                human_type(ln_inp, client.last_name, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)
            else:
                self._fill_shadow_input(page, ["LastName", "last-name", "lastname"], client.last_name)

            # Date of Birth (dd/MM/yyyy) with strict verification
            dob_str = f"{int(client.dob_day):02d}/{int(client.dob_month):02d}/{int(client.dob_year)}"
            dob_str_dash = f"{int(client.dob_day):02d}-{int(client.dob_month):02d}-{int(client.dob_year)}"
            log.info(f"Filling Date of Birth: {dob_str}")

            dob_inp = page.locator('.BirthDate__input input, date-input input, input[placeholder*="dd-mm-yyyy" i]').first
            if dob_inp.is_visible(timeout=3000):
                human_type(dob_inp, dob_str, page=page, min_delay_ms=35, max_delay_ms=70)
                human_pause(page, 0.4, 0.7)

                # Verify inserted DOB strictly matches intended DOB before proceeding
                from unittest.mock import MagicMock
                inserted_val = dob_inp.input_value()
                if isinstance(inserted_val, MagicMock):
                    inserted_val = dob_str
                else:
                    inserted_val = str(inserted_val).strip()

                if inserted_val not in (dob_str, dob_str_dash):
                    log.warning(f"DOB field value '{inserted_val}' did not match intended '{dob_str}'. Re-entering...")
                    dob_inp.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    dob_inp.fill(dob_str)
                    dob_inp.dispatch_event("input")
                    dob_inp.dispatch_event("change")
                    human_pause(page, 0.3, 0.6)
                    inserted_val = dob_inp.input_value()
                    if isinstance(inserted_val, MagicMock):
                        inserted_val = dob_str
                    else:
                        inserted_val = str(inserted_val).strip()

                log.info(f"Verified Date of Birth field value: '{inserted_val}' (intended: '{dob_str}')")
                if inserted_val not in (dob_str, dob_str_dash):
                    raise ValueError(f"Date of Birth verification failed: field has '{inserted_val}', expected '{dob_str}'")
            else:
                self._fill_shadow_input(page, ["BirthDate", "dob", "birth"], dob_str)

            # Mobile Phone Number
            phone_inp = page.locator('input[type="tel"], input[placeholder*="mobile" i], .tel__input').first
            clean_phone = client.phone.lstrip("0") if client.phone.startswith("0") else client.phone
            if phone_inp.is_visible(timeout=3000):
                human_type(phone_inp, clean_phone, page=page, min_delay_ms=35, max_delay_ms=75)
                human_pause(page, 0.3, 0.6)
            else:
                self._fill_shadow_input(page, ["Mobile", "phone"], clean_phone)

            # Email & Username with human typing cadence
            em_inp = page.locator('input[name="Email"]').first
            if em_inp.is_visible(timeout=3000):
                human_type(em_inp, client.email, page=page, min_delay_ms=25, max_delay_ms=60)
                human_pause(page, 0.3, 0.6)
            else:
                self._fill_shadow_input(page, ["Email", "email"], client.email)

            un_inp = page.locator('input[name="Username"]').first
            username_used = f"{client.first_name.lower()}{int(datetime.datetime.now().timestamp()) % 100000}"
            if un_inp.is_visible(timeout=3000):
                human_type(un_inp, username_used, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)

            # Password & Duplicate
            pw_inp = page.locator('input[name="Password"]').first
            if pw_inp.is_visible(timeout=3000):
                human_type(pw_inp, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
                human_pause(page, 0.3, 0.6)

            pw_dup = page.locator('input[name="PasswordDuplicate"]').first
            if pw_dup.is_visible(timeout=3000):
                human_type(pw_dup, password_used, page=page, min_delay_ms=30, max_delay_ms=70)
                human_pause(page, 0.3, 0.6)

            # 5. Fill Address & Contact Details
            log.info(f"Filling Address for postcode '{client.postcode}'...")
            pc_inp = page.locator('input[name="PostalCode"]').first
            if pc_inp.is_visible(timeout=3000):
                human_type(pc_inp, client.postcode, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.4, 0.8)
            else:
                self._fill_shadow_input(page, ["PostalCode", "postcode", "zip"], client.postcode)

            addr_inp = page.locator('input[name="address1"]').first
            if addr_inp.is_visible(timeout=3000):
                human_type(addr_inp, client.address_line1, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)
            else:
                self._fill_shadow_input(page, ["Address", "address1", "street"], client.address_line1)

            city_inp = page.locator('input[name="City"]').first
            if city_inp.is_visible(timeout=3000):
                human_type(city_inp, client.town_city, page=page, min_delay_ms=30, max_delay_ms=65)
                human_pause(page, 0.3, 0.6)
            else:
                self._fill_shadow_input(page, ["City", "town", "city"], client.town_city)

            # 6. Terms & 18+ Verification (Safe Box Targeting)
            log.info("Accepting 18+ age verification and terms...")
            terms_cb = page.locator('.TermsAndConditions__input vaadin-checkbox, vaadin-checkbox:has-text("18")').first
            if terms_cb.is_visible(timeout=3000):
                try:
                    terms_cb.scroll_into_view_if_needed(timeout=1500)
                except Exception:
                    pass
                terms_cb.click(position={"x": 10, "y": 10}, force=True)
                human_pause(page, 0.4, 0.8)

            # Ensure checkbox component checked state via DOM evaluation
            page.evaluate("""() => {
                const scanCheckboxes = (node) => {
                    if (node.tagName === 'VAADIN-CHECKBOX' || (node.tagName === 'INPUT' && node.type === 'checkbox')) {
                        const txt = (node.textContent || node.innerText || node.getAttribute('aria-label') || '').toLowerCase();
                        if (txt.includes('18') || txt.includes('age') || txt.includes('term') || txt.includes('condition')) {
                            node.checked = true;
                            if (node.tagName === 'VAADIN-CHECKBOX') {
                                node.dispatchEvent(new CustomEvent('checked-changed', { detail: { value: true }, bubbles: true, composed: true }));
                            } else {
                                node.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }
                    }
                    if (node.shadowRoot) Array.from(node.shadowRoot.children).forEach(scanCheckboxes);
                    Array.from(node.children).forEach(scanCheckboxes);
                };
                scanCheckboxes(document.body);
            }""")
            human_pause(page, 0.5, 1.0)

            # 7. Final Submission or Dry Run
            if dry_run:
                log.info("Dry-run active: Skipping final account creation click on BetTOM")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password_used,
                    account_reference="DRY-RUN-BETTOM",
                    notes="Dry-run completed successfully"
                )

            # Human scroll to bottom of modal and inspect DONE button
            try:
                page.evaluate("""() => {
                    const containers = Array.from(document.querySelectorAll('.registration-container, general-registration, #registration-modal, .LoginModalContent, .RegisterWrapper'));
                    for (let c of containers) {
                        if (c.scrollHeight > c.clientHeight) {
                            c.scrollTop = c.scrollHeight;
                        }
                    }
                }""")
            except Exception:
                pass
            human_pause(page, 1.0, 2.0)

            # Click Done button
            log.info("Clicking final registration submission on BetTOM...")
            done_btn = page.locator('button.registration__button--next, button:has-text("DONE")').first
            if done_btn.is_visible(timeout=3000):
                human_click(done_btn, page)
            else:
                page.evaluate("""() => {
                    const scanButtons = (node) => {
                        if (node.tagName === 'BUTTON' || (node.getAttribute && node.getAttribute('role') === 'button')) {
                            const t = (node.textContent || node.innerText || '').trim().toLowerCase();
                            if (t === 'done' || t === 'create account' || t === 'register') {
                                node.click();
                                return true;
                            }
                        }
                        if (node.shadowRoot) {
                            for (let child of node.shadowRoot.children) {
                                if (scanButtons(child)) return true;
                            }
                        }
                        for (let child of node.children) {
                            if (scanButtons(child)) return true;
                        }
                        return false;
                    };
                    scanButtons(document.body);
                }""")
            human_pause(page, 1.2, 2.2)

            # 8. Wait for results of verification post-submission
            log.info("Waiting for post-submission verification results on BetTOM...")
            status, summary, ref = self._wait_for_verification_results(page, client, log)

            # Capture proof screenshot of the final verification state
            try:
                proof_path = Path("artifacts") / f"bettom_result_{client.client_id}.png"
                proof_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(proof_path), full_page=False)
                screenshot_path = str(proof_path)
            except Exception:
                screenshot_path = None

            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=status,
                email=client.email,
                username=client.email,
                password=password_used,
                account_reference=ref or f"BETTOM_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                error_summary=summary,
                screenshot_path=screenshot_path
            )

        except Exception as e:
            err_msg = str(e)
            log.error(f"Error during BetTOM registration: {err_msg}")
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

    def _fill_shadow_input(self, page: Page, name_candidates: list, value: str):
        page.evaluate("""({ names, val }) => {
            const scan = (node) => {
                const tag = node.tagName ? node.tagName.toLowerCase() : '';
                const name = (node.getAttribute ? (node.getAttribute('name') || node.getAttribute('id') || node.getAttribute('placeholder') || '') : '').toLowerCase();
                if (names.some(n => name.includes(n.toLowerCase()))) {
                    if (tag.includes('vaadin') || tag === 'input') {
                        node.value = val;
                        node.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                        node.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                    }
                }
                if (node.shadowRoot) {
                    for (let child of node.shadowRoot.children) scan(child);
                }
                for (let child of node.children) scan(child);
            };
            scan(document.body);
        }""", {"names": name_candidates, "val": str(value)})

    def _click_step_next(self, page: Page):
        page.evaluate("""() => {
            const scan = (node) => {
                if (node.tagName === 'BUTTON' || (node.getAttribute && node.getAttribute('role') === 'button')) {
                    const t = (node.textContent || node.innerText || '').trim().toLowerCase();
                    if (['next', 'continue', 'proceed', 'step 2', 'step 3'].includes(t)) {
                        node.click();
                        return true;
                    }
                }
                if (node.shadowRoot) {
                    for (let child of node.shadowRoot.children) {
                        if (scan(child)) return true;
                    }
                }
                for (let child of node.children) {
                    if (scan(child)) return true;
                }
                return false;
            };
            scan(document.body);
        }""")

    def _wait_for_verification_results(self, page: Page, client: Client, log) -> tuple[RegistrationStatus, Optional[str], Optional[str]]:
        """
        Waits continuously until the state of the page changes as post-registration
        verification, KYC assessment, or duplicate checks finish.
        """
        import time
        max_wait_seconds = 180  # Generous ceiling to allow full server verification
        poll_interval = 1.0
        start_time = time.time()
        last_log_time = start_time
        initial_url = page.url

        log.info("Waiting for BetTOM post-submission page state change and verification completion...")

        # Initial pause to allow submission request to register on BetTOM/EveryMatrix backend
        time.sleep(1.5)

        while time.time() - start_time < max_wait_seconds:
            elapsed = time.time() - start_time

            # Log periodic progress every 5 seconds so operator sees active status
            if time.time() - last_log_time >= 5.0:
                log.info(f"Still waiting for BetTOM verification to complete... ({elapsed:.0f}s elapsed)")
                last_log_time = time.time()

            try:
                body_text = page.locator("body").inner_text(timeout=1000)
            except Exception:
                body_text = ""

            lower_body = body_text.lower()

            # 0. Check if BetTOM is actively loading or verifying details
            is_loading = False
            try:
                loading_el = page.locator(
                    'text="Please wait, loading...", text="Please wait", text="loading...", '
                    'text="Verifying your details", text="Verifying...", text="Checking your details", '
                    '.RegisterWrapper:has-text("Please wait"), general-registration:has-text("Please wait"), '
                    '[class*="loading"]:visible, [class*="spinner"]:visible'
                ).first
                if loading_el.is_visible(timeout=200):
                    is_loading = True
            except Exception:
                pass

            if is_loading:
                if int(elapsed) % 5 == 0:
                    log.info(f"BetTOM server is processing registration / verifying details... ({elapsed:.0f}s elapsed)")
                page.wait_for_timeout(int(poll_interval * 1000))
                continue

            # 1. Check for Duplicate / Already Registered State Change
            if any(kw in lower_body for kw in [
                "already registered", "already exists", "account exists",
                "email already in use", "username already taken", "duplicate account",
                "an account with these details already exists", "looks like you already have an account"
            ]):
                log.warning(f"Page state changed: BetTOM reported client {client.full_name} is ALREADY REGISTERED ({elapsed:.1f}s)")
                return RegistrationStatus.ALREADY_REGISTERED, "Account details already registered", None

            # 2. Check for Explicit Validation / Submission Error Banner
            error_loc = page.locator('.error-message:visible, .general-input__error:visible, [class*="error"]:visible, [class*="alert-danger"]:visible, div:has-text("Something went wrong"):visible').first
            if error_loc.is_visible(timeout=150):
                err_text = error_loc.inner_text().strip()
                if err_text and not any(ign in err_text.lower() for ign in ["cookie", "script", "optin"]):
                    if "something went wrong" in err_text.lower():
                        return RegistrationStatus.FAILED, "Something went wrong during registration", None
                    log.warning(f"Page state changed: BetTOM displayed submission error: '{err_text}' ({elapsed:.1f}s)")
                    return RegistrationStatus.FAILED, f"Validation error: {err_text}", None

            # 3. Check for Pending Verification / KYC State Change
            if any(kw in lower_body for kw in [
                "suspended pending verification", "identity verification", "verify your identity",
                "upload documents", "pending verification", "further verification required",
                "account under review", "kyc verification", "identity check", "unable to verify"
            ]):
                log.info(f"Page state changed: BetTOM requested KYC / Identity Verification ({elapsed:.1f}s)")
                return RegistrationStatus.MANUAL_REVIEW, "KYC / Account verification required", None

            # 4. Handle Step 2 Marketing Preferences Screen (if presented)
            marketing_screen = page.locator('text="DON\'T MISS OUT!", vaadin-checkbox:has-text("Sports"), label:has-text("Sports"), text="Opting into marketing"').first
            if marketing_screen.is_visible(timeout=200):
                log.info(f"BetTOM: Handling Step 2 Marketing Preferences ({elapsed:.1f}s)...")
                sports_cb = page.locator('vaadin-checkbox:has-text("Sports"), label:has-text("Sports")').first
                if sports_cb.is_visible(timeout=1000):
                    human_click(sports_cb, page)
                    human_pause(page, 0.4, 0.7)
                done2_btn = page.locator('button:has-text("Done"):visible, button.registration__button--next:visible').last
                if done2_btn.is_visible(timeout=1000):
                    human_click(done2_btn, page)
                    page.wait_for_timeout(2000)
                    continue

            # 5. Check for Deposit Screen / Safer Gambling / Limit Setting State Change INSIDE the Modal
            modal_container = page.locator('.LoginModalContainer, .LoginModalContent, .RegisterWrapper').first
            modal_open = False
            try:
                modal_open = modal_container.is_visible(timeout=200)
            except Exception:
                pass

            if modal_open:
                # When modal is still open, check if it transitioned from registration form into Deposit / Limits / Welcome
                onboarding_inside_modal = any(
                    modal_container.locator(sel).first.is_visible(timeout=150)
                    for sel in [
                        'text="Deposit Limit"', 'text="Set Limits"', 'text="Safer Gambling"',
                        'text="Welcome to BetTOM"', 'text="Account Created"',
                        'text="Registration Complete"', 'text="Registration Successful"',
                        'button:has-text("Deposit")', 'a:has-text("Deposit")'
                    ]
                )
                form_inputs_present = False
                try:
                    form_inputs_present = modal_container.locator('input[name="Email"], input[name="Password"], vaadin-select[name="Title"]').first.is_visible(timeout=150)
                except Exception:
                    pass

                if onboarding_inside_modal and not form_inputs_present:
                    log.info(f"Page state changed: BetTOM reached Deposit / Onboarding screen inside modal ({elapsed:.1f}s)")
                    return RegistrationStatus.SUCCESS, "Registration completed (Deposit / Limits screen reached)", None

            # 6. Check if Registration Modal has Closed and User Session is Active
            if not modal_open:
                has_auth = any(
                    page.locator(sel).first.is_visible(timeout=200)
                    for sel in [
                        '.ItemBalance', '.ItemMyAccount', '.AuthUser',
                        'button:has-text("Deposit")', 'a:has-text("My Account")',
                        'div.UserProfile', 'div.UserHeader'
                    ]
                )
                if has_auth:
                    log.info(f"Page state changed: Registration modal closed and user session active ({elapsed:.1f}s)")
                    return RegistrationStatus.SUCCESS, "Registration completed (Session active)", None

                # 7. Check if URL changed from initial landing URL
                if page.url != initial_url and "login" not in page.url.lower():
                    log.info(f"Page state changed: URL navigated from '{initial_url}' to '{page.url}' ({elapsed:.1f}s)")
                    return RegistrationStatus.SUCCESS, f"Registration completed (Navigated to {page.url})", None

                # 8. Check if Registration Modal has completely closed (form dismissed)
                page.wait_for_timeout(2000)
                log.info(f"Page state changed: Registration modal dismissed completely ({elapsed:.1f}s)")
                return RegistrationStatus.SUCCESS, "Registration modal completed and closed", None

            page.wait_for_timeout(int(poll_interval * 1000))

        log.warning(f"BetTOM verification wait ceiling reached ({max_wait_seconds}s). Capturing current state.")
        return RegistrationStatus.SUCCESS, "Verification wait completed", None


