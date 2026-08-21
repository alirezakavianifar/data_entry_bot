import sys
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("https://www.betgoodwin.co.uk/en/page/new-sportsbook-welcome-offer", wait_until="domcontentloaded", timeout=25000)
    page.wait_for_timeout(2000)

    # 1. Accept cookies
    cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, #CybotCookiebotDialogBodyButtonAccept, button:has-text("Allow all"), button:has-text("Accept")').first
    if cookie_btn.is_visible(timeout=3000):
        print("Clicking Cookiebot accept button...")
        cookie_btn.click()
        page.wait_for_timeout(2000)

    # 2. Look for Join Now / Register
    join_btn = page.locator('a:has-text("Join"), button:has-text("Join"), a:has-text("Register"), a[href*="register"]').first
    if join_btn.is_visible(timeout=3000):
        print("Found Join button:", join_btn.inner_text().strip(), "| Clicking...")
        join_btn.click()
        page.wait_for_timeout(3000)
        print("Registration Page URL:", page.url)
        print("Form inputs found:")
        for inp in page.locator("input, select").all():
            print("  - Input Name:", inp.get_attribute("name"), "| ID:", inp.get_attribute("id"), "| Placeholder:", inp.get_attribute("placeholder"))
    else:
        print("Join button not found directly, checking all header buttons...")
        for b in page.locator("header a, header button").all():
            print("  - Header CTA:", b.inner_text().strip(), "| Href:", b.get_attribute("href"))

    browser.close()
