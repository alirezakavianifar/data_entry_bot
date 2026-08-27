"""Diagnostic script to inspect BresBet registration step by step."""
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import time
from playwright.sync_api import sync_playwright
from core.browser import BrowserManager
from data.excel_provider import ExcelDataProvider
from sites.base import handle_playbook_safer_gambling_no_limit

def main():
    provider = ExcelDataProvider("dist/Test (1).xlsx")
    clients = provider.get_all_clients()
    
    # Try CLI_0022_warrenstra
    target_client = None
    for c in clients:
        if c.client_id == "CLI_0022_warrenstra":
            target_client = c
            break

    print(f"Target: {target_client.full_name} ({target_client.email})")

    bm = BrowserManager(headless=True)
    bm.start()
    context, page = bm.new_page()

    try:
        from sites.bresbet import BresbetAdapter
        adapter = BresbetAdapter()
        
        # Run step by step
        adapter.navigate(page)
        adapter.accept_cookies(page)
        
        # Click Sign up
        su = page.locator('a[data-test="sign-up-button"], button[data-test="sign-up-button"], a:has-text("Sign Up"), button:has-text("Sign Up")').first
        if su.is_visible(timeout=5000):
            su.click(force=True)
            page.wait_for_timeout(2000)

        # Initial CTA
        ic = page.locator('aside[data-test="SignUpStepsContainer"] button:has-text("Create Account")').first
        if ic.is_visible(timeout=2000):
            print("Clicking initial Create Account CTA")
            ic.click(force=True)
            page.wait_for_timeout(1000)

        # Step 1
        em = page.locator('input[data-test="email-input"]').first
        pw = page.locator('input[data-test="password-input"]').first
        em.fill(target_client.email)
        pw.fill("AutoTest@2026!#")
        ca = page.locator('button[data-test="sign-up-create-account-button"]').first
        ca.click(force=True)
        page.wait_for_timeout(3000)

        # Step 2
        fn = page.locator('input[data-test="first-name-input"]').first
        ln = page.locator('input[data-test="last-name-input"]').first
        fn.wait_for(state="visible", timeout=10000)
        fn.fill(target_client.first_name)
        ln.fill(target_client.last_name)
        page.locator('input[data-test="day-input"]').fill(str(int(target_client.dob_day)).zfill(2))
        page.locator('input[data-test="month-input"]').fill(str(int(target_client.dob_month)).zfill(2))
        page.locator('input[data-test="year-input"]').fill(str(target_client.dob_year))
        
        cleaned_phone = target_client.phone.lstrip("0").replace("+44", "")
        page.locator('input[data-test="number-input"]').fill(cleaned_phone)
        page.locator('input[data-test="postcode-input"]').fill(target_client.postcode)
        
        # Click search address
        page.locator('button[data-test="sign-up-search-address-button"]').click(force=True)
        page.wait_for_timeout(2500)
        
        # Select first address or match
        addr_list = page.locator('li[data-component="AddressesListItemWrapper"]')
        if addr_list.count() > 0:
            print(f"Address dropdown has {addr_list.count()} options")
            addr_list.first.click(force=True)
            page.wait_for_timeout(1000)

        page.screenshot(path="logs/artifacts/diag_step2_filled.png")

        # Submit Agree & Join
        print("Clicking Agree & Join...")
        page.locator('button[data-test="agree-and-join-button"]').click(force=True)
        page.wait_for_timeout(3000)

        page.screenshot(path="logs/artifacts/diag_after_agree.png")
        print("Drawer text after Agree & Join:")
        drawer = page.locator('aside[data-test="SignUpStepsContainer"]')
        if drawer.is_visible(timeout=2000):
            print(drawer.inner_text())

        print("Calling handle_playbook_safer_gambling_no_limit with logging...")
        import logging
        logging.basicConfig(level=logging.INFO)
        log = logging.getLogger("diag")
        handle_playbook_safer_gambling_no_limit(page, log)

        page.screenshot(path="logs/artifacts/diag_after_safer_gambling.png")
        page.wait_for_timeout(3000)
        page.screenshot(path="logs/artifacts/diag_3s_later.png")
        
        if drawer.is_visible(timeout=2000):
            print("Drawer text 3s later:")
            print(drawer.inner_text())
        else:
            print("Drawer is CLOSED / HIDDEN!")

    finally:
        bm.close()

if __name__ == "__main__":
    main()
