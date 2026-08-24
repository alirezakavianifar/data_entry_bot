from typing import Optional
from playwright.sync_api import Page
from sites.base import BaseSiteAdapter, extract_clean_error_message, is_already_registered_error
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot, capture_login_proof_screenshot


class BetfredAdapter(BaseSiteAdapter):
    """Adapter for Betfred (https://www.betfred.com/)."""

    def __init__(self, promo_url: str = "https://www.betfred.com/promotion/sports-onboarding-bet-10-get-10?utm_source=Betfred&utm_medium=Email&utm_campaign=BeatFredResults&p=5"):
        super().__init__(
            site_id="betfred",
            site_name="Betfred",
            default_promo_url=promo_url,
            requires_uk_ip=False
        )


    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info(f"Starting Betfred multi-step registration for {client.full_name}")

        try:
            # 1. Direct navigation to registration page
            log.info("Navigating to Betfred registration page: https://www.betfred.com/registration")
            page.goto("https://www.betfred.com/registration", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)

            # Dismiss Cookie & Policy Overlays
            page.evaluate("""() => {
                const btn = document.getElementById('onetrust-accept-btn-handler') || Array.from(document.querySelectorAll('button')).find(b => b.innerText && b.innerText.includes('Accept All'));
                if (btn) btn.click();

                ['CookieReportsOverlay', 'CookieReportsPanel', 'onetrust-banner-sdk'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.remove();
                });
            }""")
            page.wait_for_timeout(1000)

            # Check if geographical restriction screen is shown
            geo_block = page.locator(':has-text("Betfred is unavailable in your location"), :has-text("geographical restrictions")').first
            if geo_block.is_visible(timeout=1500):
                log.warning("Betfred geographical restriction detected (Non-UK or Datacenter IP)")
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "geo_blocked")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Betfred blocked location/datacenter IP (Requires UK Residential IP)",
                    screenshot_path=bundle.screenshot_path
                )

            # 2. STEP 1: Account (Email, Username, Password, Terms)
            em_inp = page.locator('input[id*="email"], input[name="email"]').first
            un_inp = page.locator('input[id*="username"], input[name="username"]').first
            pw_inp = page.locator('input[id*="password"], input[name="password"]').first

            if not em_inp.is_visible(timeout=4000) or not pw_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "step1_inputs_missing")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Step 1 inputs not found on Betfred registration page",
                    screenshot_path=bundle.screenshot_path
                )

            raw_user = client.email.split("@")[0].replace(".", "")[:12]
            log.info(f"Filling Step 1 credentials: Email={client.email}, Username={raw_user}")
            em_inp.fill(client.email)
            un_inp.fill(raw_user)
            pw_inp.fill(password)
            page.wait_for_timeout(500)

            # Dismiss transient alert popup if present
            page.evaluate("""() => {
                const okBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText && b.innerText.trim() === 'Ok');
                if (okBtn) okBtn.click();
                const alertBg = document.querySelector('[data-actionable="common.Alert.Background"]');
                if (alertBg) alertBg.remove();
            }""")

            # Check Terms & Conditions checkbox
            page.locator('div[data-actionable="RegistrationPage.TermsAndConditions.agree_terms"]').first.click(force=True)
            page.wait_for_timeout(500)

            # Step 1 Submission with Automatic Network Error Recovery Loop
            max_step1_attempts = 3
            for attempt in range(1, max_step1_attempts + 1):
                log.info(f"Submitting Step 1 (Attempt {attempt}/{max_step1_attempts})...")
                cont1_btn = page.locator('button[data-actionable="RegistrationPage.NavigationButtonsPage1.Continue"], button:has-text("Continue")').first
                if cont1_btn.is_visible(timeout=2000):
                    cont1_btn.click(force=True)
                    page.wait_for_timeout(3000)

                # 1. Check for Step 1 inline validation errors & already registered notifications
                step1_err = page.locator(
                    '[data-actionable*="email.error" i], '
                    '[data-actionable*="error" i], '
                    'span[class*="error" i]:visible, '
                    'div[class*="error" i]:visible, '
                    'p[class*="error" i]:visible, '
                    ':has-text("already have an account"):visible, '
                    ':has-text("already registered"):visible'
                ).first

                if step1_err.is_visible(timeout=1500):
                    raw_err = step1_err.inner_text().strip().replace("\n", " - ")
                    clean_err = extract_clean_error_message(raw_err)
                    if is_already_registered_error(raw_err) or any(k in raw_err.lower() for k in ("already have an account", "already registered", "account set up with this", "already exists", "log in to your account")):
                        log.warning(f"⚠️ Betfred: Client {client.full_name} is ALREADY REGISTERED ({clean_err or raw_err})")
                        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.ALREADY_REGISTERED,
                            email=client.email,
                            password=password,
                            account_reference="Betfred-Existing",
                            error_summary=f"Already registered: {clean_err or raw_err}",
                            screenshot_path=bundle.screenshot_path,
                            dom_snapshot_path=bundle.dom_snapshot_path
                        )

                # 2. Check if Step 2 Personal Details has appeared (Success!)
                fn_inp = page.locator('input[data-actionable="RegistrationPage.PersonalSection.first_name"], input[name="firstName"]').first
                if fn_inp.is_visible(timeout=2000):
                    log.info("Step 1 succeeded! Advanced to Step 2 (Personal Details).")
                    break

                # 3. Check for Network Error modal ("previous operation was unsuccessful")
                net_err = page.locator(':has-text("Network Error"), :has-text("previous operation was unsuccessful"), [data-actionable="common.Alert.Background"]:visible, button:has-text("Ok"):visible').first
                if net_err.is_visible(timeout=2000):
                    log.warning(f"Transient Network Error popup detected on Step 1 (Attempt {attempt}/{max_step1_attempts}). Dismissing and retrying...")
                    # Dismiss modal by clicking 'Ok' or closing overlay
                    page.evaluate("""() => {
                        const okBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText && (b.innerText.trim() === 'Ok' || b.innerText.trim() === 'OK'));
                        if (okBtn) okBtn.click();
                        const closeBtn = document.querySelector('button[class*="close"], [aria-label="Close"]');
                        if (closeBtn) closeBtn.click();
                        const alertBg = document.querySelector('[data-actionable="common.Alert.Background"]');
                        if (alertBg) alertBg.remove();
                    }""")
                    page.wait_for_timeout(2000)

                    # Ensure Terms checkbox remains checked
                    try:
                        terms_box = page.locator('div[data-actionable="RegistrationPage.TermsAndConditions.agree_terms"]').first
                        if terms_box.is_visible(timeout=1000):
                            terms_box.click(force=True)
                    except Exception:
                        pass
                    page.wait_for_timeout(1000)

                    if attempt == max_step1_attempts:
                        # Before declaring failure, check if the email was already taken on Betfred
                        body_txt = ""
                        try:
                            raw_t = page.locator("form, body").first.inner_text()
                            if isinstance(raw_t, str):
                                body_txt = raw_t
                        except Exception:
                            pass
                        if body_txt and (is_already_registered_error(body_txt) or "already have an account" in body_txt.lower() or "account set up with this" in body_txt.lower()):
                            clean_err = extract_clean_error_message(body_txt)
                            log.warning(f"⚠️ Betfred: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                            return RegistrationResult(
                                client_id=client.client_id,
                                client_name=client.full_name,
                                site_id=self.site_id,
                                site_name=self.site_name,
                                status=RegistrationStatus.ALREADY_REGISTERED,
                                email=client.email,
                                password=password,
                                account_reference="Betfred-Existing",
                                error_summary=f"Already registered: {clean_err or 'It looks like you already have an account set up with this email address'}",
                                screenshot_path=bundle.screenshot_path,
                                dom_snapshot_path=bundle.dom_snapshot_path
                            )

                        log.warning("Betfred Network Error persisted after multiple retries.")
                        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "network_error_ip_block")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.FAILED,
                            email=client.email,
                            password=password,
                            error_summary="Betfred rejected request: Network Error (Transient server rate limit / network block)",
                            screenshot_path=bundle.screenshot_path
                        )

            # 3. STEP 2: Personal Details (Title, Name, DOB)
            fn_inp = page.locator('input[data-actionable="RegistrationPage.PersonalSection.first_name"], input[name="firstName"]').first
            ln_inp = page.locator('input[data-actionable="RegistrationPage.PersonalSection.last_name"], input[name="lastName"]').first

            if fn_inp.is_visible(timeout=1000):
                log.info("Filling Step 2 Personal Details (Name, DOB)")
                mr_pill = page.locator('button[data-actionable="RegistrationPage.PersonalSection.title.Mr"], button:has-text("Mr")').first
                if mr_pill.is_visible(timeout=1000):
                    mr_pill.click(force=True)
                
                fn_inp.fill(client.first_name)
                if ln_inp.is_visible(timeout=1000):
                    ln_inp.fill(client.last_name)

                # Segmented DOB (DD, MM, YYYY)
                page.locator('input[data-actionable="RegistrationPage.DateOfBirthInput.day"]').fill(str(int(client.dob_day)).zfill(2))
                page.locator('input[data-actionable="RegistrationPage.DateOfBirthInput.month"]').fill(str(int(client.dob_month)).zfill(2))
                page.locator('input[data-actionable="RegistrationPage.DateOfBirthInput.year"]').fill(str(client.dob_year))
                page.wait_for_timeout(500)

                cont2_btn = page.locator('button[data-actionable="RegistrationPage.NavigationButtonsPage2.Continue"], button:has-text("Continue")').first
                if cont2_btn.is_visible(timeout=2000):
                    cont2_btn.click(force=True)
                    page.wait_for_timeout(3000)

            # 4. STEP 3: Contact Details (Mobile Number & Security Question)
            phone_inp = page.locator('input[data-actionable="RegistrationPage.TelephoneNumberInput.telephone.floatingHelp"], input[id="RegistrationPage.TelephoneNumberInput.telephone.telephone"], input[name="telephone"], input[data-actionable*="telephone" i], input[type="tel"]').first
            if phone_inp.is_visible(timeout=3000):
                log.info("Filling Step 3 Contact Details")
                phone_inp.fill(client.phone)
                page.wait_for_timeout(300)

                # Security Question (Specific selector to avoid matching the telephone areaCode select)
                sq_select = page.locator(
                    'select[data-actionable="RegistrationPage.Dropdown.securityQuestion"], '
                    'select[name="securityQuestion"], '
                    'select#RegistrationPage\\.Dropdown\\.securityQuestion, '
                    'select[data-actionable*="securityQuestion" i], '
                    'select[name*="securityQuestion" i]'
                ).first
                if sq_select.is_visible(timeout=2500):
                    try:
                        sq_select.select_option(index=1)
                    except Exception:
                        sq_select.select_option(label="Your mother's maiden name?")
                    page.wait_for_timeout(300)
                else:
                    dropdown_trigger = page.locator('div:has-text("Choose your question"), [data-actionable*="securityQuestion" i]').first
                    if dropdown_trigger.is_visible(timeout=1500):
                        dropdown_trigger.click(force=True)
                        page.wait_for_timeout(500)
                        page.locator('li:not(:has-text("Choose your question")), div[role="option"]:not(:has-text("Choose your question"))').first.click(force=True)

                ans_inp = page.locator(
                    'input[data-actionable="RegistrationPage.ContactSection.security_answer"], '
                    'input[name="securityAnswer"], '
                    'input#RegistrationPage\\.ContactSection\\.security_answer, '
                    'input[data-actionable*="security_answer" i], '
                    'input[name*="answer" i]'
                ).first
                if ans_inp.is_visible(timeout=1500):
                    ans_inp.fill("London")
                    page.wait_for_timeout(300)

                cont3_btn = page.locator(
                    'button[data-actionable="RegistrationPage.NavigationButtonsPage3.Continue"], '
                    'button:has-text("Continue"):not(:has-text("Back"))'
                ).first
                if cont3_btn.is_visible(timeout=2000):
                    cont3_btn.click(force=True)
                    page.wait_for_timeout(3000)

            # 5. STEP 4: Address Details
            pc_inp = page.locator(
                'input[data-actionable="RegistrationPage.search_address"], '
                'input#search, '
                'input[data-actionable*="search_address"], '
                'input[data-actionable*="postcode" i], '
                'input[placeholder*="address" i], '
                'input[placeholder*="postcode" i]'
            ).first
            if pc_inp.is_visible(timeout=3000):
                search_query = f"{client.address_line1}, {client.postcode}" if client.address_line1 else client.postcode
                log.info(f"Filling Step 4 Address Details: {search_query}")
                pc_inp.click()
                page.keyboard.type(search_query, delay=50)
                page.wait_for_timeout(1500)

                # Look for Loqate / PCA Predict suggestion item (.pcaitem) or select dropdown
                sug = page.locator('.pcaitem:visible, div[class*="pcaitem"]:visible, div[role="option"]:visible').first
                if sug.is_visible(timeout=3000):
                    log.info("Selecting address suggestion from dropdown...")
                    sug.click(force=True)
                    page.wait_for_timeout(1000)
                else:
                    # Fallback: Check select dropdown or press enter
                    addr_opt = page.locator('select[data-actionable*="address" i], select[name*="address" i]').first
                    if addr_opt.is_visible(timeout=2000):
                        try:
                            addr_opt.select_option(index=1)
                        except Exception:
                            addr_opt.click(force=True)
                    else:
                        page.keyboard.press("ArrowDown")
                        page.wait_for_timeout(300)
                        page.keyboard.press("Enter")
                    page.wait_for_timeout(1000)

                cont4_btn = page.locator(
                    'button[data-actionable="RegistrationPage.NavigationButtonsPage4.Continue"], '
                    'button:has-text("Continue")'
                ).first
                if cont4_btn.is_visible(timeout=2000):
                    cont4_btn.click(force=True)
                    page.wait_for_timeout(3000)

            # 6. STEP 5: Settings & Final Submit
            limit_later = page.locator('text="I will set a limit later", [data-actionable*="limit_later" i], div:has-text("set a limit later")').first
            if limit_later.is_visible(timeout=3000):
                log.info("Step 5: Selecting 'I will set a limit later'...")
                limit_later.click(force=True)
                page.wait_for_timeout(500)

            # Scroll down to make Register button visible
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(500)

            submit_btn = page.locator(
                'button[data-actionable="RegistrationPage.NavigationButtonsPage5.Register"], '
                'button[data-actionable="RegistrationPage.NavigationButtonsPage5.Continue"], '
                'button:has-text("Register"):not(:has-text("Back")), '
                'button:has-text("Create my account")'
            ).first
            if submit_btn.is_visible(timeout=3000):
                log.info("Submitting final registration on Betfred")
                submit_btn.click(force=True)
                page.wait_for_timeout(2000)

            # 7. Polling Loop (up to 30s) to wait for Betfred registration confirmation & auto-verification
            log.info("Waiting for Betfred in-platform confirmation (up to 30s)...")
            max_poll_sec = 30
            is_confirmed = False

            for sec in range(1, max_poll_sec + 1):
                # Check for explicit error banner
                error_modal = page.locator('div[class*="error"]:visible, div[role="alert"]:visible, .error-message:visible, [class*="Alert"]:visible').first
                if error_modal.is_visible(timeout=300):
                    raw_err_text = error_modal.inner_text().strip().replace("\n", " - ")
                    clean_err = extract_clean_error_message(raw_err_text)
                    is_duplicate = is_already_registered_error(raw_err_text)

                    if is_duplicate:
                        log.warning(f"⚠️ Betfred: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
                        bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                        return RegistrationResult(
                            client_id=client.client_id,
                            client_name=client.full_name,
                            site_id=self.site_id,
                            site_name=self.site_name,
                            status=RegistrationStatus.ALREADY_REGISTERED,
                            email=client.email,
                            password=password,
                            account_reference="Betfred-Existing",
                            error_summary=f"Already registered: {clean_err}",
                            screenshot_path=bundle.screenshot_path,
                            dom_snapshot_path=bundle.dom_snapshot_path
                        )
                    elif any(k in raw_err_text.lower() for k in ("invalid", "rejected", "error", "failed")):
                        log.warning(f"Betfred registration rejected: {clean_err}")
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

                # Check page body for already registered
                body_txt = ""
                try:
                    raw_txt = page.locator("body").inner_text()
                    if isinstance(raw_txt, str):
                        body_txt = raw_txt
                except Exception:
                    pass

                if body_txt and (is_already_registered_error(body_txt) or any(k in body_txt.lower() for k in ("already have an account", "already registered", "recovering your account", "you may already have an account"))):
                    clean_err = extract_clean_error_message(body_txt)
                    log.warning(f"⚠️ Betfred: Client {client.full_name} is ALREADY REGISTERED ({clean_err or 'You may already have an account'})")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        account_reference="Betfred-Existing",
                        error_summary=f"Already registered: {clean_err or 'You may already have an account'}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )

                # Check for session indicators / deposit screen
                auth_indicators = [
                    'a:has-text("Deposit")', 'button:has-text("Deposit")',
                    'a:has-text("My Account")', 'button:has-text("My Account")',
                    '[data-testid*="user-menu"]', '[data-testid*="balance"]',
                    '.user-balance', '.account-balance', '[class*="deposit-modal"]'
                ]
                has_auth = False
                for selector in auth_indicators:
                    try:
                        if page.locator(selector).first.is_visible(timeout=300):
                            has_auth = True
                            break
                    except Exception:
                        continue

                is_reg_open = page.locator('h1:has-text("Join Us"):visible, [data-actionable*="RegistrationPage.PersonalSection"]:visible, [data-actionable*="RegistrationPage.ContactSection"]:visible, [data-actionable*="NavigationButtonsPage"]:visible').first.is_visible(timeout=300)

                if has_auth or not is_reg_open:
                    log.info(f"Betfred registration confirmed at {sec}s!")
                    is_confirmed = True
                    break

                page.wait_for_timeout(1000)

            if is_confirmed:
                log.info("Betfred registration confirmed successfully!")
                success_shot = capture_success_screenshot(page, client.client_id, self.site_id)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=raw_user,
                    password=password,
                    account_reference="Betfred-Direct",
                    screenshot_path=success_shot
                )

            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "verify_submission")
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                username=raw_user,
                password=password,
                error_summary=bundle.error_summary or "Betfred registration not confirmed within 30s",
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

        except Exception as e:
            log.error(f"Registration error on Betfred: {e}")
            try:
                raw_b = page.locator("body").inner_text()
                body_txt = raw_b if isinstance(raw_b, str) else ""
                if body_txt and (is_already_registered_error(body_txt) or "already have an account" in body_txt.lower() or "account set up with this" in body_txt.lower()):
                    clean_err = extract_clean_error_message(body_txt)
                    log.warning(f"⚠️ Betfred: Client {client.full_name} is ALREADY REGISTERED (caught in exception handler)")
                    bundle = capture_failure_bundle(page, client.client_id, self.site_id, "already_registered")
                    return RegistrationResult(
                        client_id=client.client_id,
                        client_name=client.full_name,
                        site_id=self.site_id,
                        site_name=self.site_name,
                        status=RegistrationStatus.ALREADY_REGISTERED,
                        email=client.email,
                        password=password,
                        account_reference="Betfred-Existing",
                        error_summary=f"Already registered: {clean_err or 'It looks like you already have an account set up with this email address'}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
            except Exception:
                pass

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
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

    def login(
        self,
        page: Page,
        username_or_email: str,
        password: str,
        client_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Specialized login verification handler for Betfred."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Navigating to Betfred login: https://www.betfred.com/")

        try:
            page.goto("https://www.betfred.com/", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            self.accept_cookies(page)

            # Dismiss "We've logged you out... session expired" modal if present
            session_popup = page.locator('div:has-text("logged you out"), div:has-text("session has expired")').first
            if session_popup.is_visible(timeout=1500):
                try:
                    log.info("Dismissing Betfred 'session expired' notification")
                    close_btn = session_popup.locator('button, [aria-label="Close"], [class*="close"], svg').first
                    if close_btn.is_visible(timeout=1000):
                        close_btn.click(force=True)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            # Locate and click Log In CTA
            login_btn = page.locator('button:has-text("Log In"), a:has-text("Log In"), button:has-text("Login"), a:has-text("Login"), [data-actionable*="login" i]').first
            if login_btn.is_visible(timeout=3000):
                log.info("Clicking Log In on Betfred")
                login_btn.click(force=True)
                page.wait_for_timeout(2000)

            user_inp = page.locator('input[name*="user" i], input[name*="email" i], input[type="email"], input[id*="user" i], input[id*="email" i]').first
            pwd_inp = page.locator('input[name*="password" i], input[type="password"], input[id*="password" i]').first

            if not user_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                # Retry clicking login button if modal didn't appear
                login_btn_retry = page.locator('button:has-text("Log In"), a:has-text("Log In")').first
                if login_btn_retry.is_visible(timeout=1000):
                    login_btn_retry.click(force=True)
                    page.wait_for_timeout(2000)
                    user_inp = page.locator('input[name*="user" i], input[name*="email" i], input[type="email"], input[id*="user" i], input[id*="email" i]').first
                    pwd_inp = page.locator('input[name*="password" i], input[type="password"], input[id*="password" i]').first

            if not user_inp.is_visible(timeout=3000) or not pwd_inp.is_visible(timeout=3000):
                from core.logger import capture_login_proof_screenshot
                proof_path = capture_login_proof_screenshot(page, cid, self.site_id)
                return False, proof_path, "Betfred login inputs not visible"

            log.info(f"Filling credentials for {username_or_email}")
            user_inp.fill(username_or_email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            modal = page.locator('div[class*="modal"], div[class*="login"], form').first
            submit_btn = modal.locator('button[type="submit"]:has-text("Log In"), button:has-text("Log In"), button[type="submit"]').first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            page.wait_for_timeout(5000)

            # Check for error messages
            err_el = page.locator('div[class*="error"]:visible, .error-message:visible, div[role="alert"]:visible, :has-text("not verified"):visible, :has-text("Invalid"):visible').first
            err_text = None
            if err_el.is_visible(timeout=1000):
                err_text = err_el.inner_text().strip().replace("\n", " - ")

            from core.logger import capture_login_proof_screenshot
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

            is_login_open = page.locator('input[name*="password"]:visible, input[type="password"]:visible').first.is_visible(timeout=1000)

            if has_auth and not is_login_open and not err_text:
                log.info(f"Betfred login successfully verified! Proof: {proof_path}")
                return True, proof_path, None
            else:
                summary = err_text or "Login failed: Credentials rejected or session indicators not found"
                log.warning(f"Betfred login failed: {summary}")
                return False, proof_path, summary

        except Exception as e:
            log.error(f"Betfred login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)


