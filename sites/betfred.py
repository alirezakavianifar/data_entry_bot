from typing import Optional
from playwright.sync_api import Page
from sites.base import (
    BaseSiteAdapter,
    extract_clean_error_message,
    is_already_registered_error,
    human_type,
    human_pause,
    human_click,
    human_scroll
)
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

            from core.password_gen import generate_username
            raw_user = generate_username(client.first_name, client.last_name, str(client.dob_year or ""))
            log.info(f"Filling Step 1 credentials: Email={client.email}, Username={raw_user}")
            human_type(em_inp, client.email, page)
            human_pause(page, 0.3, 0.6)
            human_type(un_inp, raw_user, page)
            human_pause(page, 0.3, 0.6)
            human_type(pw_inp, password, page)
            human_pause(page, 0.4, 0.8)

            # Dismiss transient alert popup if present
            page.evaluate("""() => {
                const okBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText && b.innerText.trim() === 'Ok');
                if (okBtn) okBtn.click();
                const alertBg = document.querySelector('[data-actionable="common.Alert.Background"]');
                if (alertBg) alertBg.remove();
            }""")

            # Check Terms & Conditions checkbox
            page.locator('div[data-actionable="RegistrationPage.TermsAndConditions.agree_terms"]').first.click(force=True)
            human_pause(page, 0.5, 1.0)

            # Step 1 Submission with Automatic Network Error Recovery Loop
            max_step1_attempts = 3
            for attempt in range(1, max_step1_attempts + 1):
                log.info(f"Submitting Step 1 (Attempt {attempt}/{max_step1_attempts})...")
                cont1_btn = page.locator('button[data-actionable="RegistrationPage.NavigationButtonsPage1.Continue"], button:has-text("Continue")').first
                if cont1_btn.is_visible(timeout=2000):
                    cont1_btn.click(force=True)
                    human_pause(page, 2.0, 3.5)

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
                    human_pause(page, 1.5, 2.5)

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

            if fn_inp.is_visible(timeout=2000):
                log.info("Filling Step 2 Personal Details (Name, DOB)")
                t_clean = getattr(client, "resolved_title_clean", "Mr")
                title_pill = page.locator(f'button[data-actionable="RegistrationPage.PersonalSection.title.{t_clean}"], button:has-text("{t_clean}"), button[data-actionable="RegistrationPage.PersonalSection.title.Mr"], button:has-text("Mr")').first
                if title_pill.is_visible(timeout=1500):
                    title_pill.click(force=True)
                    human_pause(page, 0.2, 0.5)
                
                human_type(fn_inp, client.first_name, page)
                human_pause(page, 0.3, 0.6)
                if ln_inp.is_visible(timeout=1000):
                    human_type(ln_inp, client.last_name, page)
                    human_pause(page, 0.3, 0.6)

                # Segmented DOB (DD, MM, YYYY)
                day_inp = page.locator('input[data-actionable="RegistrationPage.DateOfBirthInput.day"]').first
                month_inp = page.locator('input[data-actionable="RegistrationPage.DateOfBirthInput.month"]').first
                year_inp = page.locator('input[data-actionable="RegistrationPage.DateOfBirthInput.year"]').first
                
                human_type(day_inp, str(int(client.dob_day)).zfill(2), page)
                human_pause(page, 0.2, 0.4)
                human_type(month_inp, str(int(client.dob_month)).zfill(2), page)
                human_pause(page, 0.2, 0.4)
                human_type(year_inp, str(client.dob_year), page)
                human_pause(page, 0.4, 0.8)

                cont2_btn = page.locator('button[data-actionable="RegistrationPage.NavigationButtonsPage2.Continue"], button:has-text("Continue")').first
                if cont2_btn.is_visible(timeout=2000):
                    cont2_btn.click(force=True)
                    human_pause(page, 2.0, 3.0)

            # 4. STEP 3: Contact Details (Mobile Number & Security Question)
            phone_inp = page.locator('input[data-actionable="RegistrationPage.TelephoneNumberInput.telephone.floatingHelp"], input[id="RegistrationPage.TelephoneNumberInput.telephone.telephone"], input[name="telephone"], input[data-actionable*="telephone" i], input[type="tel"]').first
            if phone_inp.is_visible(timeout=3000):
                log.info("Filling Step 3 Contact Details")
                human_type(phone_inp, client.phone, page)
                human_pause(page, 0.4, 0.8)

                # Security Question (Randomized selection to avoid identical patterns across accounts)
                import secrets
                from core.password_gen import generate_security_answer

                selected_question_text = ""
                sq_select = page.locator(
                    'select[data-actionable="RegistrationPage.Dropdown.securityQuestion"], '
                    'select[name="securityQuestion"], '
                    'select#RegistrationPage\\.Dropdown\\.securityQuestion, '
                    'select[data-actionable*="securityQuestion" i], '
                    'select[name*="securityQuestion" i]'
                ).first
                if sq_select.is_visible(timeout=2500):
                    try:
                        options = sq_select.locator('option')
                        opt_count = options.count()
                        if opt_count > 1:
                            chosen_idx = secrets.randbelow(opt_count - 1) + 1
                            sq_select.select_option(index=chosen_idx)
                            try:
                                selected_question_text = options.nth(chosen_idx).inner_text()
                            except Exception:
                                pass
                        else:
                            sq_select.select_option(index=1)
                    except Exception:
                        try:
                            fallback_labels = [
                                "Your mother's maiden name?",
                                "What was the name of your first pet?",
                                "In what city or town were you born?",
                                "What was your first school's name?",
                                "What is your favourite sports team?"
                            ]
                            chosen_label = secrets.choice(fallback_labels)
                            sq_select.select_option(label=chosen_label)
                            selected_question_text = chosen_label
                        except Exception:
                            pass
                    human_pause(page, 0.3, 0.6)
                else:
                    dropdown_trigger = page.locator('div:has-text("Choose your question"), [data-actionable*="securityQuestion" i]').first
                    if dropdown_trigger.is_visible(timeout=1500):
                        dropdown_trigger.click(force=True)
                        human_pause(page, 0.4, 0.8)
                        opt_items = page.locator('li:not(:has-text("Choose your question")), div[role="option"]:not(:has-text("Choose your question"))')
                        opt_count = opt_items.count()
                        if opt_count > 0:
                            chosen_opt_idx = secrets.randbelow(opt_count)
                            chosen_opt = opt_items.nth(chosen_opt_idx)
                            try:
                                selected_question_text = chosen_opt.inner_text()
                            except Exception:
                                pass
                            chosen_opt.click(force=True)
                        else:
                            opt_items.first.click(force=True)

                ans_inp = page.locator(
                    'input[data-actionable="RegistrationPage.ContactSection.security_answer"], '
                    'input[name="securityAnswer"], '
                    'input#RegistrationPage\\.ContactSection\\.security_answer, '
                    'input[data-actionable*="security_answer" i], '
                    'input[name*="answer" i]'
                ).first
                if ans_inp.is_visible(timeout=1500):
                    sec_ans = generate_security_answer(selected_question_text)
                    log.info(f"Step 3: Security Question='{selected_question_text or 'Random'}' -> Randomized Answer='{sec_ans}'")
                    human_type(ans_inp, sec_ans, page)
                    human_pause(page, 0.4, 0.8)

                cont3_btn = page.locator(
                    'button[data-actionable="RegistrationPage.NavigationButtonsPage3.Continue"], '
                    'button:has-text("Continue"):not(:has-text("Back"))'
                ).first
                if cont3_btn.is_visible(timeout=2000):
                    cont3_btn.click(force=True)
                    human_pause(page, 2.0, 3.0)

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
                human_type(pc_inp, search_query, page)
                human_pause(page, 1.0, 2.0)

                # Look for Loqate / PCA Predict suggestion item (.pcaitem) or select dropdown
                sug = page.locator('.pcaitem:visible, div[class*="pcaitem"]:visible, div[role="option"]:visible').first
                if sug.is_visible(timeout=3000):
                    log.info("Selecting address suggestion from dropdown...")
                    sug.click(force=True)
                    human_pause(page, 0.8, 1.5)
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
                    human_pause(page, 0.8, 1.5)

                cont4_btn = page.locator(
                    'button[data-actionable="RegistrationPage.NavigationButtonsPage4.Continue"], '
                    'button:has-text("Continue")'
                ).first
                if cont4_btn.is_visible(timeout=2000):
                    cont4_btn.click(force=True)
                    human_pause(page, 2.0, 3.0)

            # 6. STEP 5: Settings & Final Submit
            limit_later = page.locator('text="I will set a limit later", [data-actionable*="limit_later" i], div:has-text("set a limit later")').first
            if limit_later.is_visible(timeout=3000):
                log.info("Step 5: Selecting 'I will set a limit later'...")
                limit_later.click(force=True)
                human_pause(page, 0.4, 0.8)

            # Scroll down to make Register button visible
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            human_pause(page, 1.5, 3.0)

            submit_btn = page.locator(
                'button[data-actionable="RegistrationPage.NavigationButtonsPage5.Register"], '
                'button[data-actionable="RegistrationPage.NavigationButtonsPage5.Continue"], '
                'button:has-text("Register"):not(:has-text("Back")), '
                'button:has-text("Create my account")'
            ).first
            if submit_btn.is_visible(timeout=3000):
                log.info("Submitting final registration on Betfred")
                submit_btn.scroll_into_view_if_needed()
                submit_btn.click(force=True)
                page.wait_for_timeout(3000)

            # 7. Dynamic Adaptive Polling & Settle Loop (up to 60s) for Betfred registration & session confirmation
            log.info("Monitoring Betfred in-platform confirmation (30s initial settle, up to 60s)...")
            max_poll_sec = 60
            min_settle_sec = 30
            is_confirmed = False
            in_session_verified = False

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
                    elif any(k in raw_err_text.lower() for k in ("invalid", "rejected", "error", "failed", "restricted")):
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

                # Check page body for already registered or self-exclusion
                body_txt = ""
                try:
                    raw_txt = page.locator("body").inner_text()
                    if isinstance(raw_txt, str):
                        body_txt = raw_txt
                except Exception:
                    pass

                if body_txt and (is_already_registered_error(body_txt) or any(k in body_txt.lower() for k in ("already have an account", "already registered", "recovering your account", "you may already have an account", "self-exclusion", "active self-exclusion"))):
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

                # Check for welcome / active authenticated session modal (Image 1)
                welcome_indicators = [
                    ':has-text("thanks for joining Betfred")',
                    ':has-text("Add a Payment Method")',
                    ':has-text("Browse the Betfred Site")',
                    'button:has-text("Add a Payment Method")',
                    'button:has-text("Browse the Betfred Site")',
                    'h1:has-text("MY ACCOUNT")',
                    'a:has-text("Deposit")',
                    'button:has-text("Deposit")',
                    '[data-testid*="user-menu"]',
                    '.user-balance'
                ]
                for selector in welcome_indicators:
                    try:
                        if page.locator(selector).first.is_visible(timeout=200):
                            if not in_session_verified:
                                log.info(f"Betfred authenticated welcome/dashboard state detected via '{selector}'!")
                            is_confirmed = True
                            in_session_verified = True
                            break
                    except Exception:
                        continue

                # Automatically click 'Browse the Betfred Site' to enter the main sportsbook page
                welcome_action_buttons = [
                    'button:has-text("Browse the Betfred Site")',
                    'a:has-text("Browse the Betfred Site")',
                    'button:has-text("Browse")',
                    'a:has-text("Browse")',
                    'button:has-text("Add a Payment Method")',
                    'button[aria-label="Close"]',
                    'button.close',
                    'div[data-actionable*="close" i]'
                ]
                for btn_sel in welcome_action_buttons:
                    try:
                        action_btn = page.locator(btn_sel).first
                        if action_btn.is_visible(timeout=200):
                            log.info(f"Clicking Betfred post-registration action button: '{btn_sel}'")
                            action_btn.click(force=True)
                            page.wait_for_timeout(1000)
                            break
                    except Exception:
                        continue

                is_reg_open = page.locator('h1:has-text("Join Us"):visible, [data-actionable*="RegistrationPage.PersonalSection"]:visible, [data-actionable*="RegistrationPage.ContactSection"]:visible, [data-actionable*="NavigationButtonsPage"]:visible').first.is_visible(timeout=200)
                if not is_reg_open:
                    is_confirmed = True

                # If past min_settle_sec and authenticated session is verified, settle cleanly
                if sec >= min_settle_sec and in_session_verified:
                    log.info(f"Betfred settling completed cleanly at {sec}s!")
                    break

                page.wait_for_timeout(1000)

            if is_confirmed:
                log.info("Betfred registration settled and confirmed successfully in active session!")
                success_shot = capture_login_proof_screenshot(page, client.client_id, self.site_id) if in_session_verified else capture_success_screenshot(page, client.client_id, self.site_id)
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.SUCCESS,
                    email=client.email,
                    username=raw_user,
                    password=password,
                    account_reference="Betfred-Direct (Active Session Verified)" if in_session_verified else "Betfred-Direct",
                    screenshot_path=success_shot,
                    login_verified=in_session_verified,
                    login_screenshot_path=success_shot if in_session_verified else None
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
            human_type(user_inp, username_or_email, page)
            human_pause(page, 0.3, 0.6)
            human_type(pwd_inp, password, page)
            human_pause(page, 0.4, 0.8)

            modal = page.locator('div[class*="modal"], div[class*="login"], form').first
            submit_btn = modal.locator('button[type="submit"]:has-text("Log In"), button:has-text("Log In"), button[type="submit"]').first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.scroll_into_view_if_needed()
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            page.wait_for_timeout(5000)

            # Check for error messages (including restriction banners)
            err_el = page.locator('div[class*="error"]:visible, .error-message:visible, div[role="alert"]:visible, :has-text("not verified"):visible, :has-text("restricted"):visible, :has-text("Invalid"):visible').first
            err_text = None
            if err_el.is_visible(timeout=1500):
                raw_err = err_el.inner_text().strip().replace("\n", " - ")
                err_text = extract_clean_error_message(raw_err) or raw_err

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
                log.warning(f"Betfred login check result: {summary}")
                return False, proof_path, summary

        except Exception as e:
            log.error(f"Betfred login error: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)


