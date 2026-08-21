import sys
import json
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("config/promo_links.json", "r", encoding="utf-8") as f:
    promo_cfg = json.load(f)

print("=========================================================")
print("          AUDITING TARGET BOOKMAKERS UNDER UK IP         ")
print("=========================================================")

with sync_playwright() as p:
    try:
        browser = p.chromium.launch(channel="chrome", headless=True)
    except Exception:
        browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="en-GB",
        timezone_id="Europe/London"
    )

    results = {}
    for site_id, cfg in promo_cfg.items():
        name = cfg.get("name", site_id)
        url = cfg.get("url", "")
        print(f"\nTesting [{site_id}] {name}...")

        page = context.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=25000)
            status = resp.status if resp else None
            page.wait_for_timeout(3000)
            title = page.title()
            final_url = page.url
            body_text = page.inner_text("body").lower()

            is_geoblocked = any(kw in body_text for kw in [
                "unavailable in your location", "geographical restrictions",
                "outside uk", "not available in your country", "access denied", "403 forbidden"
            ]) or (status == 403)

            # Check for Cloudflare challenge
            is_cf = "cloudflare" in body_text or "just a moment" in body_text

            # Check for register / join CTA
            reg_locators = page.locator('a:has-text("Register"), button:has-text("Register"), a:has-text("Sign Up"), button:has-text("Sign Up"), a:has-text("Join"), button:has-text("Join"), a:has-text("Claim")')
            has_cta = reg_locators.count() > 0

            print(f" -> HTTP Status: {status}")
            print(f" -> Destination URL: {final_url}")
            print(f" -> Title: {title[:60]}")
            print(f" -> Geoblocked: {is_geoblocked}")
            print(f" -> Cloudflare Challenge: {is_cf}")
            print(f" -> Register/Claim CTA Present: {has_cta}")

            results[site_id] = {
                "name": name,
                "status": status,
                "accessible": (status == 200 and not is_geoblocked and not is_cf),
                "has_cta": has_cta,
                "url": final_url
            }

        except Exception as e:
            print(f" -> Error: {e}")
            results[site_id] = {"name": name, "accessible": False, "error": str(e)}
        finally:
            page.close()

    browser.close()

print("\n=========================================================")
print("                   AUDIT SUMMARY REPORT                  ")
print("=========================================================")
for sid, r in results.items():
    access_str = "✅ ACCESSIBLE & READY" if r.get("accessible") else "❌ BLOCKED / RESTRICTED"
    print(f"[{sid:15}] {r.get('name'):35} -> {access_str}")
