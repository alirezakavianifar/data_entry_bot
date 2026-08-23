import re
from typing import Optional
from playwright.sync_api import Page
from sites.base import BaseSiteAdapter, extract_clean_error_message, is_already_registered_error
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot, capture_login_proof_screenshot


class BetgoodwinAdapter(BaseSiteAdapter):
    """Adapter for Betgoodwin (https://www.betgoodwin.co.uk/)."""

    def __init__(self, promo_url: str = "https://www.betgoodwin.co.uk/en/page/new-sportsbook-welcome-offer"):
        super().__init__(
            site_id="betgoodwin",
            site_name="Betgoodwin",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )


    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info(f"Starting Betgoodwin registration flow for {client.full_name}")

        try:
            # 1. Cookiebot Consent Handling
            cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, #CybotCookiebotDialogBodyButtonAccept, button:has-text("Allow all"), button:has-text("Accept")').first
            if cookie_btn.is_visible(timeout=3000):
                log.info("Accepting Cookiebot consent on Betgoodwin")
                cookie_btn.click(force=True)
                page.wait_for_timeout(1000)

            # 2. Click JOIN / Claim Offer CTA
            join_btn = page.locator('text=JOIN, button:has-text("JOIN"), a:has-text("JOIN"), button:has-text("Join"), a:has-text("Claim"), div.ItemRegister').first
            if join_btn.is_visible(timeout=2000):
                log.info("Clicking Betgoodwin JOIN CTA via locator")
                join_btn.click(force=True)
            else:
                log.info("Clicking Betgoodwin JOIN CTA via deep JS evaluation")
                page.evaluate("""() => {
                    let target = null;
                    const scan = (node) => {
                        if (target) return;
                        const txt = (node.innerText || '').trim();
                        if ((node.tagName === 'BUTTON' || node.tagName === 'A' || node.tagName === 'DIV') && (txt === 'JOIN' || txt === 'Join' || txt === 'JOIN NOW')) {
                            target = node;
                            return;
                        }
                        if (node.shadowRoot) Array.from(node.shadowRoot.children).forEach(scan);
                        if (node.children) Array.from(node.children).forEach(scan);
                    };
                    scan(document.body);
                    if (target) target.click();
                }""")
            page.wait_for_timeout(3000)

            # 3. Fill Registration Form
            # Title Selection
            title_select = page.locator('vaadin-select[name="Title"], select-input.general-input--Title, general-input.general-input--Title').first
            if title_select.is_visible(timeout=3000):
                log.info("Selecting Title on Betgoodwin")
                title_select.click(force=True)
                page.wait_for_timeout(500)
                title_item = page.locator('vaadin-select-item:has-text("Mr"), [role="option"]:has-text("Mr")').first
                if title_item.is_visible(timeout=2000):
                    title_item.click(force=True)
                    page.wait_for_timeout(300)

            # First & Last Name
            fn_inp = page.locator('input[name="FirstnameOnDocument"], input[name*="firstName" i]').first
            ln_inp = page.locator('input[name="LastNameOnDocument"], input[name*="lastName" i]').first
            if fn_inp.is_visible(timeout=3000):
                fn_inp.fill(client.first_name)
            if ln_inp.is_visible(timeout=2000):
                ln_inp.fill(client.last_name)

            # Date of Birth (ISO YYYY-MM-DD for vaadin-date-picker)
            dob_iso = f"{int(client.dob_year)}-{int(client.dob_month):02d}-{int(client.dob_day):02d}"
            log.info(f"Setting Date of Birth on Betgoodwin: {dob_iso}")
            page.evaluate(f"""() => {{
                const scan = (node) => {{
                    if (node.tagName === 'VAADIN-DATE-PICKER' || (node.tagName && node.tagName.includes('DATE'))) {{
                        node.value = '{dob_iso}';
                        node.dispatchEvent(new CustomEvent('change', {{ bubbles: true }}));
                        node.dispatchEvent(new CustomEvent('value-changed', {{ detail: {{ value: '{dob_iso}' }} }}));
                    }}
                    if (node.shadowRoot) Array.from(node.shadowRoot.children).forEach(scan);
                    Array.from(node.children).forEach(scan);
                }};
                scan(document.body);
            }}""")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)

            # Mobile Phone (strip +44 and leading 0)
            cleaned_phone = client.phone
            if cleaned_phone.startswith("+44"):
                cleaned_phone = cleaned_phone[3:]
            cleaned_phone = cleaned_phone.lstrip("0")
            phone_inp = page.locator('input[placeholder*="Enter mobile number"], input[type="tel"], input[name="PhoneNumber"]').first
            if phone_inp.is_visible(timeout=2000):
                phone_inp.fill(cleaned_phone)

            # Email & Username
            em_inp = page.locator('input[name="Email"], input[type="email"]').first
            if em_inp.is_visible(timeout=2000):
                em_inp.fill(client.email)

            un_inp = page.locator('input[name="Username"], input[placeholder*="Enter your username"]').first
            if un_inp.is_visible(timeout=2000):
                # Generate clean username from email prefix or name
                raw_user = client.email.split("@")[0].replace(".", "")[:12]
                un_inp.fill(raw_user)

            # Password & Confirmation
            pw1_inp = page.locator('input[name="Password"]').first
            pw2_inp = page.locator('input[name="PasswordDuplicate"]').first
            if pw1_inp.is_visible(timeout=2000):
                pw1_inp.fill(password)
            if pw2_inp.is_visible(timeout=2000):
                pw2_inp.fill(password)

            # Address Details (Postcode, Street, City)
            pc_inp = page.locator('input[name="PostalCode"], input[placeholder*="Postcode"]').first
            if pc_inp.is_visible(timeout=2000):
                pc_inp.fill(client.postcode)
                page.wait_for_timeout(1000)

            ad1_inp = page.locator('input[name="address1"], input[placeholder*="Address"]').first
            if ad1_inp.is_visible(timeout=2000):
                ad1_inp.fill(client.address_line1)

            city_inp = page.locator('input[name="City"], input[placeholder*="Town"]').first
            if city_inp.is_visible(timeout=2000):
                # Ensure no special characters, commas, numbers or colons
                clean_c = re.split(r"[,/:\n]", str(client.town_city))[0].strip()
                clean_c = re.sub(r"[^a-zA-Z\s\-']", "", clean_c).strip()
                clean_c = re.sub(r"\s+", " ", clean_c) or "London"
                city_inp.fill(clean_c)

            # Affiliate / Promo Code
            btag_inp = page.locator('input[name="Btag"]').first
            if btag_inp.is_visible(timeout=1000):
                btag_inp.fill("WELCOME15")

            # Terms & Conditions Checkbox
            page.evaluate("""() => {
                const scan = (node) => {
                    if (node.tagName === 'VAADIN-CHECKBOX' && (node.className.includes('checkbox__input') || (node.parentElement && node.parentElement.tagName === 'CHECKBOX-INPUT'))) {
                        node.checked = true;
                        node.dispatchEvent(new CustomEvent('change', { bubbles: true }));
                        node.dispatchEvent(new CustomEvent('checked-changed', { detail: { value: true } }));
                    }
                    if (node.shadowRoot) Array.from(node.shadowRoot.children).forEach(scan);
                    Array.from(node.children).forEach(scan);
                };
                scan(document.body);
            }""")
            page.wait_for_timeout(1000)

            # 4. Check for Inline Field Errors / Submit Registration via 'Done' Button
            inline_error = page.locator('[class*="error"]:visible, [class*="invalid"]:visible, div:has-text("No addresses found"):visible, span:has-text("No addresses found"):visible, p:has-text("No addresses found"):visible, div:has-text("No address found"):visible').first
            if inline_error.is_visible(timeout=1500):
                raw_err = inline_error.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err) or raw_err
                if is_already_registered_error(raw_err):
                    log.warning(f"Betgoodwin: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        account_reference="Betgoodwin-Existing",
                        error_summary=f"Already registered: {clean_err}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                else:
                    log.warning(f"Betgoodwin registration rejected due to inline field error: {clean_err}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "field_validation_error", Exception(clean_err))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        password=password,
                        error_summary=clean_err,
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )

            done_btn = page.locator('button:has-text("Done"), button[type="submit"]:has-text("Done")').first
            if done_btn.is_visible(timeout=3000):
                log.info("Submitting Betgoodwin registration via 'Done'")
                done_btn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                done_btn.click(force=True)

                # Wait dynamically while 'Please wait, loading...' or spinner is active (up to 45 seconds)
                log.info("Waiting for Betgoodwin server processing / 'Please wait, loading...' to complete...")
                loading_loc = page.locator('text="Please wait, loading...", text="Please wait", text="loading...", [class*="loading"]:visible, [class*="spinner"]:visible')
                for _ in range(45):
                    page.wait_for_timeout(1000)
                    is_loading = False
                    try:
                        is_loading = loading_loc.first.is_visible(timeout=500)
                    except Exception:
                        pass

                    if not is_loading:
                        # Check if a definitive next state is ready (marketing modal, deposit, auth, or error)
                        try:
                            if page.locator('text="DON\'T MISS OUT!", vaadin-checkbox:has-text("Sports"), div[class*="error"]:visible, [role="alert"]:visible, [class*="toast"]:visible, :has-text("issue with your account registration"):visible, text="Deposit", text="My Account"').first.is_visible(timeout=500):
                                break
                        except Exception:
                            pass

            # 5. Handle Marketing Preferences Screen (if presented)
            marketing_screen = page.locator('text="DON\'T MISS OUT!", vaadin-checkbox:has-text("Sports"), label:has-text("Sports")').first
            if marketing_screen.is_visible(timeout=3000):
                log.info("Betgoodwin: Handling Step 2 Marketing Preferences...")
                sports_cb = page.locator('vaadin-checkbox:has-text("Sports"), label:has-text("Sports"), vaadin-checkbox:has-text("Casino")').first
                if sports_cb.is_visible(timeout=2000):
                    sports_cb.click(force=True)
                    page.wait_for_timeout(500)

                # Scroll modal to ensure Done button is in view
                page.evaluate("""() => {
                    const scrollables = Array.from(document.querySelectorAll('div, form')).filter(el => el.scrollHeight > el.clientHeight);
                    scrollables.forEach(s => s.scrollTop = s.scrollHeight);
                }""")
                page.wait_for_timeout(300)

                done2_btn = page.locator('button:has-text("Done"):visible, button.registration__button--next:visible').first
                if done2_btn.is_visible(timeout=2000):
                    done2_btn.click(force=True)
                    log.info("Waiting for Step 2 completion / 'Please wait, loading...'...")
                    loading_loc = page.locator('text="Please wait, loading...", text="Please wait", text="loading...", [class*="loading"]:visible, [class*="spinner"]:visible')
                    for _ in range(30):
                        page.wait_for_timeout(1000)
                        is_loading = False
                        try:
                            is_loading = loading_loc.first.is_visible(timeout=500)
                        except Exception:
                            pass
                        if not is_loading:
                            try:
                                if page.locator('text="Deposit", text="My Account", div[class*="error"]:visible, [class*="toast"]:visible, :has-text("issue with your account registration"):visible').first.is_visible(timeout=500):
                                    break
                            except Exception:
                                pass

                # Dismiss modal via close button or Escape if still visible
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)

            # 6. Capture Proof & Return Result
            # Check for error banners / modals / toasts / validation alerts first
            error_modal = page.locator('div[class*="error"]:visible, div[role="alert"]:visible, .error-message:visible, [class*="alert"]:visible, [class*="toast"]:visible, div:has-text("issue with your account registration"):visible, div:has-text("contact Customer Services"):visible, :has-text("No addresses found"):visible, :has-text("No address found"):visible').first
            if error_modal.is_visible(timeout=2000):
                raw_err_text = error_modal.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text)

                if is_duplicate:
                    log.warning(f"Betgoodwin: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        account_reference="Betgoodwin-Existing",
                        error_summary=f"Already registered: {clean_err}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                else:
                    log.warning(f"Betgoodwin registration rejected: {clean_err}")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "server_error", Exception(clean_err))
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.FAILED,
                        email=client.email,
                        password=password,
                        error_summary=clean_err,
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )

            # Page body duplicate check (exclude static header link 'Already have an account? Login')
            body_txt = ""
            try:
                raw_txt = page.locator("body").inner_text()
                if isinstance(raw_txt, str):
                    body_txt = raw_txt
            except Exception:
                pass

            clean_err = extract_clean_error_message(body_txt)
            is_static_link = "already have an account? login" in clean_err.lower() or clean_err.strip() == "Already have an account? Login"

            if not is_static_link and body_txt and (is_already_registered_error(body_txt) or any(k in body_txt.lower() for k in ("self-exclusion", "account with this email already exists", "email already exists", "email address is already", "username already exists"))):
                log.warning(f"Betgoodwin: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.ALREADY_REGISTERED,
                    email=client.email,
                    password=password,
                    account_reference="Betgoodwin-Existing",
                    error_summary=f"Already registered: {clean_err or 'Account already exists'}",
                    screenshot_path=bundle.screenshot_path,
                    dom_snapshot_path=bundle.dom_snapshot_path
                )

            # Authenticated indicators / Deposit modal
            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '.user-balance', '.account-balance', '[class*="deposit-modal"]'
            ]
            has_auth = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1500):
                        has_auth = True
                        break
                except Exception:
                    continue

            is_reg_open = page.locator('input[name="FirstnameOnDocument"]:visible, input[name="Email"]:visible').first.is_visible(timeout=1000)

            if has_auth or not is_reg_open:
                log.info("Betgoodwin registration confirmed successfully!")
                success_shot = capture_success_screenshot(page, client.client_id, self.site_id)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=client.email,
                    password=password,
                    account_reference="Betgoodwin-Direct",
                    screenshot_path=success_shot
                )

            # Fallback verification bundle
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "verify_submission")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                password=password,
                error_summary="Registration was not confirmed by Betgoodwin",
                screenshot_path=bundle.screenshot_path
            )

        except Exception as e:
            log.error(f"Registration error on Betgoodwin: {e}")
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "registration_exception", e)
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                password=password,
                error_summary=str(e),
                screenshot_path=bundle.screenshot_path
            )

    def login(
        self,
        page: Page,
        username_or_email: str,
        password: str,
        client_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Specialized login verification handler for Betgoodwin."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Navigating to Betgoodwin clean login URL: https://www.betgoodwin.co.uk/")

        try:
            page.goto("https://www.betgoodwin.co.uk/", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            self.accept_cookies(page)

            # Locate and click Log In CTA
            login_btn = page.locator('button:has-text("LOG IN"), button:has-text("Log In"), a:has-text("LOG IN"), a:has-text("Log In"), .SignInButton').first
            if login_btn.is_visible(timeout=3000):
                log.info("Clicking Log In on Betgoodwin")
                login_btn.click(force=True)
            else:
                log.info("Clicking Betgoodwin Log In CTA via deep JS evaluation")
                page.evaluate("""() => {
                    let target = null;
                    const scan = (node) => {
                        if (target) return;
                        const txt = (node.innerText || '').trim();
                        if ((node.tagName === 'BUTTON' || node.tagName === 'A' || node.tagName === 'DIV') && (txt === 'LOG IN' || txt === 'Log In')) {
                            target = node;
                            return;
                        }
                        if (node.shadowRoot) Array.from(node.shadowRoot.children).forEach(scan);
                        if (node.children) Array.from(node.children).forEach(scan);
                    };
                    scan(document.body);
                    if (target) target.click();
                }""")
            page.wait_for_timeout(2000)

            user_inp = page.locator('input[name*="user" i], input[name*="email" i], input[type="email"], input[id*="user" i], input[id*="email" i]').first
            pwd_inp = page.locator('input[name*="password" i], input[type="password"], input[id*="password" i]').first

            if not user_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                proof_path = capture_login_proof_screenshot(page, cid, self.site_id)
                return False, proof_path, "Betgoodwin login inputs not visible"

            log.info(f"Filling credentials for {username_or_email}")
            user_inp.fill(username_or_email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            # Submit login form
            submit_btn = page.locator('button:has-text("LOG IN"):visible, button:has-text("Log In"):visible, button[type="submit"]:visible').last
            if submit_btn.is_visible(timeout=2000):
                log.info("Clicking modal LOG IN submit button")
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            page.wait_for_timeout(6000)

            # Check for error messages
            err_el = page.locator('div[class*="error"]:visible, .error-message:visible, div[role="alert"]:visible, :has-text("not verified"):visible, :has-text("Invalid"):visible').first
            err_text = None
            if err_el.is_visible(timeout=1000):
                err_text = err_el.inner_text().strip().replace("\n", " - ")

            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-testid*="user-menu"]', '[data-testid*="balance"]',
                '.user-balance', '.account-balance', '.wallet-balance'
            ]
            has_auth = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1000):
                        has_auth = True
                        break
                except Exception:
                    continue

            is_login_open = page.locator('input[type="password"]:visible').first.is_visible(timeout=1000)

            if has_auth and not is_login_open and not err_text:
                log.info(f"Betgoodwin login successfully verified! Proof: {proof_path}")
                return True, proof_path, None
            else:
                summary = err_text or "Login failed: Credentials rejected or session indicators not found"
                log.warning(f"Betgoodwin login failed: {summary}")
                return False, proof_path, summary

        except Exception as e:
            log.error(f"Betgoodwin login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)


