from playwright.sync_api import Page
from sites.base import BaseSiteAdapter
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle


class BetfredAdapter(BaseSiteAdapter):
    """Adapter for Betfred (https://www.betfred.com/)."""

    def __init__(self, promo_url: str = "https://www.betfred.com/promotion/sports-onboarding-bet-10-get-10?utm_source=Betfred&utm_medium=Email&utm_campaign=BeatFredResults&p=5"):
        super().__init__(
            site_id="betfred",
            site_name="Betfred",
            default_promo_url=promo_url,
            requires_uk_ip=True
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info("Starting Betfred registration form fill")

        # Locate Register CTA
        reg_btn = page.locator('a:has-text("Register"), button:has-text("Register"), a:has-text("Claim Here")').first
        if reg_btn.is_visible(timeout=5000):
            reg_btn.click(force=True)
            page.wait_for_timeout(2000)

        # Step 1: Account credentials
        user_inp = page.locator('input[name*="username" i], input[id*="username" i]').first
        pwd_inp = page.locator('input[name*="password" i], input[type="password"]').first
        email_inp = page.locator('input[name*="email" i], input[id*="email" i]').first

        if user_inp.is_visible(timeout=3000):
            user_inp.fill(client.email.split("@")[0] + "99")
        if pwd_inp.is_visible(timeout=3000):
            pwd_inp.fill(password)
        if email_inp.is_visible(timeout=3000):
            email_inp.fill(client.email)

        # Step 2: Personal details
        fn_inp = page.locator('input[name*="firstName" i], input[id*="firstName" i]').first
        ln_inp = page.locator('input[name*="lastName" i], input[id*="lastName" i]').first
        phone_inp = page.locator('input[name*="phone" i], input[name*="mobile" i]').first

        if fn_inp.is_visible(timeout=3000):
            fn_inp.fill(client.first_name)
        if ln_inp.is_visible(timeout=3000):
            ln_inp.fill(client.last_name)
        if phone_inp.is_visible(timeout=3000):
            phone_inp.fill(client.phone)

        # Step 3: Address & Postcode
        postcode_inp = page.locator('input[name*="postcode" i], input[id*="postcode" i]').first
        if postcode_inp.is_visible(timeout=3000):
            postcode_inp.fill(client.postcode)

        # Accept terms
        terms = page.locator('input[type="checkbox"][name*="terms" i], input[type="checkbox"][id*="terms" i]').first
        if terms.is_visible(timeout=2000) and not terms.is_checked():
            terms.check(force=True)

        # Submit
        submit_btn = page.locator('button:has-text("Register"), button:has-text("Create my account"), button[type="submit"]').first
        if submit_btn.is_visible(timeout=3000):
            submit_btn.click(force=True)
            page.wait_for_timeout(4000)

        # Check for success indicators
        body_text = page.inner_text("body").lower()
        if "welcome" in body_text or "deposit" in body_text or "account" in body_text:
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.SUCCESS,
                email=client.email,
                username=client.email,
                password=password,
                account_reference="Betfred-Registered"
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
            error_summary=bundle.error_summary,
            screenshot_path=bundle.screenshot_path,
            dom_snapshot_path=bundle.dom_snapshot_path
        )
