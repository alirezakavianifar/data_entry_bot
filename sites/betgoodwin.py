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

            # 2. Click Join / Claim Offer CTA
            claim_btn = page.locator('a:has-text("Claim"), button:has-text("Claim"), a:has-text("Join"), button:has-text("Join"), a:has-text("Register")').first
            if claim_btn.is_visible(timeout=4000):
                log.info("Clicking Betgoodwin Claim/Join CTA")
                claim_btn.click(force=True)
                page.wait_for_timeout(2500)

            # 3. Fill Registration Details
            fn = page.locator('input[name*="firstName" i], input[id*="firstName" i], input[placeholder*="First Name" i]').first
            ln = page.locator('input[name*="lastName" i], input[id*="lastName" i], input[placeholder*="Last Name" i]').first
            em = page.locator('input[name*="email" i], input[id*="email" i], input[type="email"]').first
            ph = page.locator('input[name*="phone" i], input[name*="mobile" i], input[type="tel"]').first
            pwd = page.locator('input[name*="password" i], input[type="password"]').first

            if fn.is_visible(timeout=3000):
                fn.fill(client.first_name)
            if ln.is_visible(timeout=2000):
                ln.fill(client.last_name)
            if em.is_visible(timeout=2000):
                em.fill(client.email)
            if ph.is_visible(timeout=2000):
                ph.fill(client.phone)
            if pwd.is_visible(timeout=2000):
                pwd.fill(password)

            # Postcode & terms
            postcode = page.locator('input[name*="postcode" i], input[id*="postcode" i]').first
            if postcode.is_visible(timeout=2000):
                postcode.fill(client.postcode)

            terms = page.locator('input[type="checkbox"][name*="terms" i], input[type="checkbox"][id*="terms" i]').first
            if terms.is_visible(timeout=2000) and not terms.is_checked():
                terms.check(force=True)

            # 4. Submit Registration
            submit_btn = page.locator('button:has-text("Create Account"), button:has-text("Register"), button:has-text("Join"), button[type="submit"]').first
            if submit_btn.is_visible(timeout=3000):
                submit_btn.click(force=True)
                page.wait_for_timeout(5000)

            # 5. Capture Proof & Return Result
            auth_indicators = [
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '.user-balance', '.account-balance', '[class*="deposit-modal"]'
            ]
            join_btn = page.locator('a:has-text("Join"), button:has-text("Join"), a:has-text("Register")').first
            is_join_visible = join_btn.is_visible(timeout=1500)

            has_auth = False
            for selector in auth_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1500):
                        has_auth = True
                        break
                except Exception:
                    continue

            # Check for error banners first
            error_modal = page.locator('div[class*="error"]:visible, div[role="alert"]:visible, .error-message:visible').first
            if error_modal.is_visible(timeout=1500):
                raw_err_text = error_modal.inner_text().strip().replace("\n", " - ")
                clean_err = extract_clean_error_message(raw_err_text)
                is_duplicate = is_already_registered_error(raw_err_text)

                if is_duplicate:
                    log.warning(f"⚠️ Betgoodwin: Client {client.full_name} is ALREADY REGISTERED ({clean_err})")
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


            is_reg_open = page.locator('input[name*="user" i]:visible, input[name*="email" i]:visible, input#email:visible').first.is_visible(timeout=1000)

            if has_auth and not is_reg_open:
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
            login_btn = page.locator('button:has-text("Log In"), a:has-text("Log In"), button:has-text("Login"), a:has-text("Login")').first
            if login_btn.is_visible(timeout=3000):
                log.info("Clicking Log In on Betgoodwin")
                login_btn.click(force=True)
                page.wait_for_timeout(1500)

            user_inp = page.locator('input[name*="user" i], input[name*="email" i], input[type="email"], input[id*="user" i], input[id*="email" i]').first
            pwd_inp = page.locator('input[name*="password" i], input[type="password"], input[id*="password" i]').first

            if not user_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                proof_path = capture_login_proof_screenshot(page, cid, self.site_id)
                return False, proof_path, "Betgoodwin login inputs not visible"

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


