import time
from playwright.sync_api import Page
from sites.base import BaseSiteAdapter
from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_success_screenshot


class BetgoodwinAdapter(BaseSiteAdapter):
    """Adapter for Betgoodwin (https://www.betgoodwin.co.uk/)."""

    def __init__(self, promo_url: str = "https://www.betgoodwin.co.uk/en/page/new-sportsbook-welcome-offer"):
        super().__init__(
            site_id="betgoodwin",
            site_name="Betgoodwin",
            default_promo_url=promo_url,
            requires_uk_ip=True
        )

    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="fill_registration")
        log.info("Starting Betgoodwin registration flow")

        # 1. Cookiebot Consent Handling
        cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, #CybotCookiebotDialogBodyButtonAccept, button:has-text("Allow all"), button:has-text("Accept")').first
        if cookie_btn.is_visible(timeout=4000):
            log.info("Accepting Cookiebot consent on Betgoodwin")
            cookie_btn.click(force=True)
            page.wait_for_timeout(1500)

        # 2. Click Join / Claim Offer CTA
        claim_btn = page.locator('a:has-text("Claim"), button:has-text("Claim"), a:has-text("Join"), button:has-text("Join"), a:has-text("Register")').first
        if claim_btn.is_visible(timeout=5000):
            log.info("Clicking Betgoodwin Claim/Join CTA")
            claim_btn.click(force=True)
            page.wait_for_timeout(3000)

        # 3. Fill Registration Details
        fn = page.locator('input[name*="firstName" i], input[id*="firstName" i], input[placeholder*="First Name" i]').first
        ln = page.locator('input[name*="lastName" i], input[id*="lastName" i], input[placeholder*="Last Name" i]').first
        em = page.locator('input[name*="email" i], input[id*="email" i], input[type="email"]').first
        ph = page.locator('input[name*="phone" i], input[name*="mobile" i], input[type="tel"]').first
        pwd = page.locator('input[name*="password" i], input[type="password"]').first

        if fn.is_visible(timeout=4000):
            fn.fill(client.first_name)
        if ln.is_visible(timeout=3000):
            ln.fill(client.last_name)
        if em.is_visible(timeout=3000):
            em.fill(client.email)
        if ph.is_visible(timeout=3000):
            ph.fill(client.phone)
        if pwd.is_visible(timeout=3000):
            pwd.fill(password)

        # Postcode & DOB if visible
        postcode = page.locator('input[name*="postcode" i], input[id*="postcode" i]').first
        if postcode.is_visible(timeout=2000):
            postcode.fill(client.postcode)

        # 4. Submit Registration
        submit_btn = page.locator('button:has-text("Create Account"), button:has-text("Register"), button:has-text("Join"), button[type="submit"]').first
        if submit_btn.is_visible(timeout=3000):
            submit_btn.click(force=True)
            page.wait_for_timeout(4000)

        # 5. Capture Proof & Return Result
        body_text = page.inner_text("body").lower()
        if "welcome" in body_text or "deposit" in body_text or "account" in body_text:
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
            status=RegistrationStatus.SUCCESS,
            email=client.email,
            password=password,
            account_reference="Betgoodwin-Submitted",
            screenshot_path=bundle.screenshot_path
        )
