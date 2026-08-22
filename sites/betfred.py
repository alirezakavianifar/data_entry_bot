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

            # Click Continue on Step 1
            log.info("Submitting Step 1...")
            cont1_btn = page.locator('button[data-actionable="RegistrationPage.NavigationButtonsPage1.Continue"], button:has-text("Continue")').first
            if cont1_btn.is_visible(timeout=2000):
                cont1_btn.click(force=True)
                page.wait_for_timeout(3500)

            # Check for Network Error / Datacenter block modal
            net_err = page.locator(':has-text("Network Error"), :has-text("previous operation was unsuccessful"), [data-actionable="common.Alert.Background"]:visible').first
            if net_err.is_visible(timeout=2000):
                log.warning("Betfred API rejected registration with Network Error (HTTP 462 Datacenter IP Block)")
                bundle = capture_failure_bundle(page, client.client_id, self.site_id, "network_error_ip_block")
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    password=password,
                    error_summary="Betfred rejected IP: HTTP 462 Datacenter/VPN block (Requires UK Residential IP)",
                    screenshot_path=bundle.screenshot_path
                )

            # 3. STEP 2: Personal Details (Title, Name, DOB)
            fn_inp = page.locator('input[data-actionable="RegistrationPage.PersonalSection.first_name"], input[name="firstName"]').first
            ln_inp = page.locator('input[data-actionable="RegistrationPage.PersonalSection.last_name"], input[name="lastName"]').first

            if fn_inp.is_visible(timeout=3000):
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
            phone_inp = page.locator('input[data-actionable*="telephone"], input[name*="phone" i], input[type="tel"]').first
            if phone_inp.is_visible(timeout=3000):
                log.info("Filling Step 3 Contact Details")
                phone_inp.fill(client.phone)
                page.wait_for_timeout(300)

                # Security Question
                sq_select = page.locator('select, [data-actionable*="securityQuestion"]').first
                if sq_select.is_visible(timeout=1500):
                    sq_select.select_option(index=1)
                else:
                    page.locator('div:has-text("Choose your question"), [data-actionable*="question"]').first.click()
                    page.wait_for_timeout(500)
                    page.locator('li, div[role="option"]').first.click()

                ans_inp = page.locator('input[data-actionable*="answer" i], input[name*="answer" i]').first
                if ans_inp.is_visible(timeout=1000):
                    ans_inp.fill("London")

                cont3_btn = page.locator('button[data-actionable*="Continue"], button:has-text("Continue")').first
                if cont3_btn.is_visible(timeout=2000):
                    cont3_btn.click(force=True)
                    page.wait_for_timeout(3000)

            # 5. STEP 4: Address Details
            pc_inp = page.locator('input[data-actionable*="postcode" i], input[placeholder*="postcode" i]').first
            if pc_inp.is_visible(timeout=3000):
                log.info(f"Filling Step 4 Address Details: {client.postcode}")
                pc_inp.fill(client.postcode)
                find_addr = page.locator('button:has-text("Find Address"), button:has-text("Search")').first
                if find_addr.is_visible(timeout=2000):
                    find_addr.click(force=True)
                    page.wait_for_timeout(2000)

                addr_opt = page.locator('select[data-actionable*="address" i], select[name*="address" i]').first
                if addr_opt.is_visible(timeout=1500):
                    addr_opt.select_option(index=1)
                    page.wait_for_timeout(500)
                
                cont4_btn = page.locator('button[data-actionable*="Continue"], button:has-text("Continue")').first
                if cont4_btn.is_visible(timeout=2000):
                    cont4_btn.click(force=True)
                    page.wait_for_timeout(3000)

            # 6. STEP 5: Settings & Final Submit
            submit_btn = page.locator('button:has-text("Register"), button:has-text("Create my account"), button[type="submit"]:has-text("Register")').first
            if submit_btn.is_visible(timeout=3000):
                log.info("Submitting final registration on Betfred")
                submit_btn.click(force=True)
                page.wait_for_timeout(6000)

            # 7. Post-Submission & Result Verification
            error_modal = page.locator('div[class*="error"]:visible, div[role="alert"]:visible, .error-message:visible, [class*="Alert"]:visible').first
            if error_modal.is_visible(timeout=2000):
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
                        error_summary=f"Already registered: {clean_err}",
                        screenshot_path=bundle.screenshot_path,
                        dom_snapshot_path=bundle.dom_snapshot_path
                    )
                else:
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

            # Check for success indicators
            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-testid*="user-menu"]', '[data-testid*="balance"]',
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

            is_reg_open = page.locator('input[id*="password"]:visible, input[name*="password"]:visible').first.is_visible(timeout=1000)

            if has_auth or not is_reg_open:
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
                password=password,
                error_summary=bundle.error_summary or "Betfred registration not confirmed",
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

        except Exception as e:
            log.error(f"Registration error on Betfred: {e}")
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
        """Specialized login verification handler for Betfred."""
        cid = client_id or "client"
        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Navigating to Betfred login: https://www.betfred.com/")

        try:
            page.goto("https://www.betfred.com/", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            self.accept_cookies(page)

            # Locate and click Log In CTA
            login_btn = page.locator('button:has-text("Log In"), a:has-text("Log In"), button:has-text("Login"), a:has-text("Login")').first
            if login_btn.is_visible(timeout=3000):
                log.info("Clicking Log In on Betfred")
                login_btn.click(force=True)
                page.wait_for_timeout(1500)

            user_inp = page.locator('input[name*="user" i], input[name*="email" i], input[type="email"], input[id*="user" i], input[id*="email" i]').first
            pwd_inp = page.locator('input[name*="password" i], input[type="password"], input[id*="password" i]').first

            if not user_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
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


