"""
Non-Headless Visual Verification Script
=======================================
Launches an interactive, visible Google Chrome / Chromium browser window on the desktop
and executes live registration and onboarding steps so operators can visually observe
field typing, address lookups, deposit limit handling, and status detection in real time.

Usage:
    python scripts/verify_nonheadless.py [bresbet|starsports|planetsportbet|betstgeorge|all]
"""

import sys
import os
import time

# Ensure UTF-8 console output for Windows cmd / PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.browser import BrowserManager
from core.password_gen import generate_password
from data.models import Client, RegistrationStatus
from sites.bresbet import BresbetAdapter
from sites.starsports import StarSportsAdapter
from sites.planetsportbet import PlanetSportBetAdapter
from sites.betstgeorge import BetStGeorgeAdapter
from sites.betfred import BetfredAdapter
from sites.quinnbet import QuinnbetAdapter
from sites.betgoodwin import BetgoodwinAdapter
from sites.fairplaybet import FairplayBetAdapter
from sites.bettom import BetTOMAdapter
from sites.easybet import EasyBetAdapter
from sites.twentyfour7bet import TwentyFourSevenBetAdapter
from sites.paddypower import PaddyPowerAdapter
from sites.betfair import BetfairAdapter
from sites.dragonbet import DragonBetAdapter
from core.logger import get_logger

log = get_logger(step="VisualVerification")

PLAYBOOK_ADAPTERS = {
    "bresbet": BresbetAdapter,
    "starsports": StarSportsAdapter,
    "planetsportbet": PlanetSportBetAdapter,
    "betstgeorge": BetStGeorgeAdapter,
    "dragonbet": DragonBetAdapter,
}

OTHER_ADAPTERS = {
    "betfred": BetfredAdapter,
    "quinnbet": QuinnbetAdapter,
    "betgoodwin": BetgoodwinAdapter,
    "fairplaybet": FairplayBetAdapter,
}

PHASE2_ADAPTERS = {
    "bettom": BetTOMAdapter,
    "easybet": EasyBetAdapter,
    "247bet": TwentyFourSevenBetAdapter,
    "paddypower": PaddyPowerAdapter,
    "betfair": BetfairAdapter,
    "dragonbet": DragonBetAdapter,
}

AVAILABLE_ADAPTERS = {**PLAYBOOK_ADAPTERS, **OTHER_ADAPTERS, **PHASE2_ADAPTERS}

def run_visual_verification(target: str = "bresbet"):
    target_clean = target.lower().strip()
    
    if target_clean == "all":
        adapters_to_run = [cls() for cls in AVAILABLE_ADAPTERS.values()]
    elif target_clean in ("phase2", "phase_2"):
        adapters_to_run = [cls() for cls in PHASE2_ADAPTERS.values()]
    elif target_clean in ("playbook", "playmakers"):
        adapters_to_run = [cls() for cls in PLAYBOOK_ADAPTERS.values()]
    elif target_clean in ("other", "others", "rest", "nonplaybook"):
        adapters_to_run = [cls() for cls in OTHER_ADAPTERS.values()]
    elif target_clean in AVAILABLE_ADAPTERS:
        adapters_to_run = [AVAILABLE_ADAPTERS[target_clean]()]
    else:
        print(f"Unknown target '{target}'. Available options: {', '.join(AVAILABLE_ADAPTERS.keys())}, 'phase2', 'playbook', 'other', or 'all'")
        adapters_to_run = [BresbetAdapter()]

    print("\n" + "=" * 65)
    print(" 🚀 LAUNCHING NON-HEADLESS VISUAL VERIFICATION")
    print(f" Target Site(s): {[a.site_name for a in adapters_to_run]}")
    print("=" * 65)

    # Launch visible browser on the desktop with slow_mo to make actions clearly observable
    bm = BrowserManager(headless=False, slow_mo_ms=80)
    bm.start()

    try:
        for idx, adapter in enumerate(adapters_to_run, 1):
            unique_ts = int(time.time())
            
            FIRST_NAMES = ["Hamish", "Calum", "Archie", "Innes", "Alasdair", "Rory", "Ewan", "Finlay", "Gregor", "Lachlan", "Murdo", "Niall", "Callum", "Fergus", "Brodie", "Fraser", "Douglas", "Graham", "Stuart", "Cameron"]
            LAST_NAMES = ["Balfour", "Macleod", "Drummond", "Crawford", "Guthrie", "Macintosh", "Campbell", "Sinclair", "Morrison", "Livingston", "Macdonald", "Mackenzie", "Ferguson", "Robertson", "Paterson"]
            ADDRESSES = [
                ("15 Victoria Street", "Perth", "PH2 8JW", "1990-04-14"),
                ("34 St Andrews Square", "Glasgow", "G1 5PP", "1989-08-22"),
                ("12 Castle Terrace", "Edinburgh", "EH1 2EL", "1992-12-03"),
                ("88 High Street", "Stirling", "FK8 1EJ", "1987-06-17"),
                ("45 Commercial Street", "Dundee", "DD1 2AD", "1994-01-29"),
                ("27 Queen Street", "Aberdeen", "AB10 1ZA", "1991-03-12"),
                ("19 Bridge Street", "Inverness", "IV1 1HG", "1988-11-05"),
                ("56 Market Street", "St Andrews", "KY16 9NT", "1993-07-19"),
                ("82 George Street", "Edinburgh", "EH2 3BU", "1995-09-24"),
                ("14 Buchanan Street", "Glasgow", "G1 3LB", "1986-10-30")
            ]
            import random
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            addr, city, pc, dob = random.choice(ADDRESSES)
            
            # Synthetic UK client with realistic identity details
            client = Client(
                client_id=f"CLI_VIS_{adapter.site_id[:3]}_{unique_ts}",
                full_name=f"{first} {last}",
                first_name=first,
                last_name=last,
                email=f"{first.lower()}.{last.lower()}.{unique_ts}@gmail.com",
                phone="07700900" + str(random.randint(100, 999)),
                dob=dob,
                address_line1=addr,
                town_city=city,
                postcode=pc
            )
            password = generate_password()

            print(f"\n[{idx}/{len(adapters_to_run)}] Testing: {adapter.site_name.upper()}")
            print(f"Client: {client.full_name} | {client.email}")
            print(f"Address: {client.address_line1}, {client.town_city}, {client.postcode}")
            print("-" * 65)

            ctx, page = bm.new_page()

            try:
                # 1. Navigation
                print(f"Navigating to {adapter.site_name}...")
                adapter.navigate(page)
                page.wait_for_timeout(2500)

                # 2. Live Registration Execution
                print("Executing form registration live on screen...")
                result = adapter.fill_registration(page, client, password)

                print("\n" + "=" * 45)
                print(f" STATUS: {result.status.value}")
                print(f" Account Ref: {result.account_reference}")
                print(f" Login Verified: {result.login_verified}")
                print(f" Summary: {result.error_summary or 'Completed'}")
                if result.screenshot_path:
                    print(f" Proof Image: {result.screenshot_path}")
                print("=" * 45)

                # Keep visible for operator inspection
                print("\nPausing 15 seconds for visual verification before proceeding...")
                page.wait_for_timeout(15000)

            finally:
                ctx.close()
                time.sleep(2)

    finally:
        bm.close()
        print("\n✅ Visual verification finished. Browser closed cleanly.")

if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else "bresbet"
    run_visual_verification(choice)
