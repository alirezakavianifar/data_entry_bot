# Data Entry Bot — Client Signup Automation System

An automated, enterprise-grade data entry system built with **Python**, **CustomTkinter**, **Playwright**, **OpenPyXL**, and **GSpread**. The system reads client details from **Google Sheets** or local **Excel workbooks (`Test.xlsx`)**, executes multi-step account registration workflows across betting/bookmaker platforms, tracks progress idempotently via SQLite, and writes successful registration credentials back to the results sheet.

Includes both a **Modern Desktop GUI Application** and a **Command-Line Interface (CLI)**.

---

## Features

- **Automated & On-Demand Post-Registration Login Verification:**
  - Automatically logs into the bookmaker account immediately upon successful registration to verify authentication and capture definitive logged-in dashboard proof (`_LOGIN_PROOF.png`).
  - **Smart Verification & Activation Protection:** Distinguishes between false positive registrations (invalid credentials, which are removed from the results sheet) and valid accounts that require user email confirmation or KYC document upload (which are **safely preserved** in the results sheet and state with an `✉️ Email Pending` or `⚠️ KYC Pending` indicator).
  - **Desktop GUI Registered Accounts Hub:**
    - Displays `🔐 Verified`, `✉️ Email Pending`, `⚠️ KYC Pending`, `ℹ️ Existing`, and `⏳ Unverified` badges per registered account.
    - **`🔑 Verify` Button:** Triggers on-demand login execution in a background worker thread, tests authentication live, updates the database, and captures a fresh proof image.
    - **`🖼️ Proof` Button:** Opens the high-resolution logged-in screen proof immediately in the default viewer or Explorer.
    - **`📋 Copy` Button:** One-click clipboard copy for the generated password.
- **Playbook Platforms & Responsible Gambling No-Deposit Limit Automation:**
  - Physically completes and dismisses the post-Step 2 Safer Gambling / Rolling Net Deposit Limit onboarding form across all Playbook Engineering platforms (**Star Sports**, **Bet St George**, **BresBet**, **Planet Sport Bet**).
  - Handles internal scroll containers by actively scrolling explanatory text boxes to the bottom (`scrollTop = scrollHeight`) to unlock below-the-fold controls.
  - Supports automatic deposit limit input population (£100–£500) and preset chips, or explicit selection of *"No I don't want to set a deposit limit"*.
  - Switches acknowledgment toggles ON (`aria-checked="true"`), strips disabled attributes, and drives progression CTAs (`Next`, `I'm Happy with this`, `Accept`, `Save & Continue`, `Done`) through multi-vector Playwright + synthetic DOM + React Fiber execution.
  - **Smart Postcode Lookup & Address Matching (`select_matching_playbook_address` / `sanitize_playbook_address`):** Tokenizes client address lines and uses confidence scoring (house numbers +50, street tokens +15 each, mismatch penalties -40) to select exact addresses rather than blind first-item clicks, with automatic fallback to manual address typing. Automatically sanitizes address lines against strict Playbook platform validation restrictions (e.g. normalizing Scottish flat slashes like `0/1` into `0-1`, converting ampersands to `and`, and stripping disallowed symbols).
  - **Deposit Step SKIP Automation (`handle_playbook_deposit_step`):** Detects the final post-registration Deposit / Payment step (`DepositSignupLayout`) on **Planet Sport Bet** (`https://planetsportbet.com/`), **Star Sports**, **BresBet**, and **Bet St George**. Automatically scrolls internal drawer containers into view and actively presses the **"SKIP"** button (`button[data-test="skip-button"]`, `button:has-text("SKIP")`, `button:has-text("Skip")`) when choosing whether to deposit, closing the aside drawer cleanly and transitioning directly into the verified user session.
  - Prevents premature browser teardown and incomplete signups by actively polling until the onboarding container is fully dismissed and authentic session credentials/balances are established.
- **🛡️ Anti-Bot Stealth Shield & Device Fingerprint Masking:**
  - Complete elimination of `navigator.webdriver` and CDP automation flags.
  - Realistic emulation of authentic `window.chrome` runtime (`runtime`, `loadTimes`, `csi`, `app`), discrete GPU WebGL unmasked vendors (`Google Inc. (NVIDIA)` / `ANGLE`), genuine `navigator.plugins`, `languages`, `hardwareConcurrency` (8 cores), and `deviceMemory` (8GB).
- **🖱️ Human Mouse & Behavioral Dynamics (Bézier Physics):**
  - Multi-point cubic Bézier curve mouse trajectories with realistic acceleration, jitter, and target hover pauses before clicking.
  - Smooth physics-based momentum wheel scrolling replacing deterministic instant jumps.
- **🔐 Betfred Multi-Step Flow & Dynamic Security Q&A:**
  - Humanized natural typing cadence across all 5 registration steps with randomized inter-key delay and Bézier mouse coordinates.
  - Randomized security question selection and category-matched realistic UK answers (Maiden Names, First Pets, Birth Cities, School Names, Football Clubs).
  - In-session authenticated proof capture upon landing on the welcome screen with automatic progression into the main sportsbook dashboard (`Browse the Betfred Site`).
- **⏳ QuinnBet Promotional Offer Targeting & Auto-Verification:**
  - Prioritizes the promotional offer CTA button at the bottom of the offer section (`a.btn-green`) rather than generic top-right header buttons, guaranteeing customer qualification for the highest welcome bonuses and terms.
  - Dynamic adaptive monitoring (30s baseline settle, extending up to 90s while the auto-verification KYC spinner is active).
  - Automatically detects in-platform verification completion toasts, dismisses net deposit limit modals, and recognizes manual document upload requests while safely preserving valid credentials.
- **🏇 BetGoodwin Human-Paced Registration Engine:**
  - **Dynamic Title Selection (`Mr.`, `Mrs.`, `Miss`, `Ms.`):** Resolves the client's personal title from explicit sheet data, name prefixes, or UK name heuristics, and accurately selects the title across EveryMatrix multi-tiered Polymer shadow DOM (`vaadin-select[name="Title"]`), dispatching authentic component events and overlay clicks.
  - Enforces password lengths strictly between 8 and 14 characters meeting BetGoodwin security policies.
  - Simulates realistic human typing cadence with inter-key digraph jitter across all fields (Name, Email, Mobile, Username, Password, Postcode, Address).
  - Integrates natural reading/thinking pauses (0.3s–1.8s) between form controls.
  - Ticks the 18+ and Terms & Conditions checkbox with realistic mouse targeting.
  - Executes a human review pause before pressing the bottom Done button, preventing anti-bot velocity triggers.
- **🎯 Fairplay Bet Multi-Step Registration & Electronic Verification:**
  - Robust 3-step registration drawer handling email credentials, password generation, and personal details.
  - Active verification polling (up to 3 minutes / 180s) specifically monitoring the `"Verifying..."` electronic identity check state, guaranteeing the bot waits for the verification process to finish rather than exiting prematurely.
  - Accurately classifies final outcomes: session authentication (`SUCCESS`), explicit email activation requests (`SUCCESS` with email reminder), manual KYC document verification (`MANUAL_REVIEW`), or electronic verification rejection (`FAILED`).
- **🚀 Phase 2 Bookmakers & Human-Like Behavioral Automation:**
  - **Identical Human-Like Behavior Across All Adapters:**
    - **Natural Typing Rhythms (`human_type`):** Character-by-character typing cadence with randomized inter-key delay (25ms–75ms), special pause buffers for punctuation (`@`, `.`, ` `, `-`, `_`), and initial mouse movement via Bézier physics before focusing inputs.
    - **Cognitive Reading & Digging Pauses (`human_pause`):** Realistic human pauses (0.3s–0.6s between field transitions, 1.5s–3.5s after clicking buttons, and 1.5s–2.5s review pauses before final submissions).
    - **Smooth Bézier Mouse Trajectories & Clicks (`human_click` / `human_mouse_move`):** Cubic Bézier curves with natural jitter and randomized target coordinates within element bounding boxes, simulating authentic mouse physics.
    - **Momentum Wheel Scrolling (`human_scroll`):** Multi-step mouse-wheel scrolling with momentum easing and jitter down the page.
    - **Safe Checkbox Targeting:** Specifically targets the box square (`[part="checkbox"]` or coordinate offset `x+10, y+10`) rather than the text label to eliminate accidental clicks on "Terms" or "Privacy Policy" external links, and automatically closes any unwanted popup tabs.
  - **BetTOM (`https://www.bettom.com/en/sport/`):** Full EveryMatrix Polymer shadow DOM integration with Cybot Cookiebot bypass, dynamic UK personal title selection (`Mr.`, `Mrs.`, `Miss`, `Ms.`), ISO DOB handling, address matching, and safe 18+ declaration.
  - **easyBet (`https://welcome.easybet.net/EB20-Football`):** Automated sports exchange onboarding preserving the welcome bonus code `EB20`, CookieYes consent dismissal, and human-cadence multi-step form entry.
  - **247 Bet (`https://www.247bet.com/en-gb/register`):** Multi-step White Hat Gaming UK account creation covering credentials, personal details, address lookup, safe checkbox ticking, and marketing preferences.
  - **Paddy Power (`https://redirect.rp-offers.com/?id=9708`):** Flutter Entertainment registration with active Session Warming (visits promo landing page, accepts cookies, simulates natural browsing/scrolling, and transits via authentic in-page CTA with natural Referer), OneTrust auto-dismissal observer, reCAPTCHA Enterprise detection & operator pause handling, and deposit limit flow.
  - **Betfair (`https://redirect.rp-offers.com/?id=8827`):** Flutter Entertainment registration with active Session Warming, welcome promo code `ZSKAOL` retention, OneTrust auto-dismissal observer, reCAPTCHA Enterprise detection & operator pause handling, and security question configuration.
  - **DragonBet (`https://bettinglounge.co.uk/out/ZRKfXhAAACkAStm_/?offer=betting`):** Playbook Engineering platform adapter featuring full human-paced interaction, responsible gambling deposit limit bypass, and deposit skip handling.
  - **Mandatory 25-Day Betting Embargo Rule:**
    - Automatically enforces the cooling-off policy on **Paddy Power** and **Betfair**.
    - Calculates the registration date (`signup_date = DD/MM/YYYY`) and the acceptable betting date (`acceptable_to_bet_date = signup_date + 25 days`).
    - Explicitly records the required instruction into the spreadsheet (`Succesful Signuos`):
      `"successful. Please do not place any bets until within 25 days. Signed up: <DD/MM/YYYY>. Acceptable to bet on: <DD/MM/YYYY>."`
- **🌐 Residential & Mobile Proxy Integration:**
  - Built-in support for UK Residential and 4G/5G Mobile Proxies (`PROXY_SERVER`, `PROXY_USERNAME`, `PROXY_PASSWORD`) ensuring requests originate from residential UK ASNs.
- **Human Pacing & Anti-Bot Fingerprint Cooldown (15–20s):**
  - Character-by-character typing simulation, randomized pauses during form input, and cooldowns between account creation steps.


  - **🌐 Test URL in Browser:** Click "Test" to instantly open any promo/landing page in your default browser to verify it is active and not returning 404 or expired.
  - **➕ Add Custom Links:** Add new affiliate redirect or promo campaigns on the fly.
  - **🔄 Reset to Defaults:** Revert any single site or all sites to official factory default URLs at any time.
  - **Instant Live Synchronization:** Saving promo changes immediately updates the Target Websites Matrix on the dashboard for subsequent runs.
- **Modern Desktop GUI Application (`gui_app.py` / `run_desktop_app.bat`):**
  - Sleek dark theme interface with intuitive controls.
  - Interactive Data Source picker (`Excel` file browser vs `Google Sheets` URL).
  - Target website checklist with quick selection filters.
  - Auto-Verify via Login toggle switch.
  - Real-time animated progress bar, status badges, and live statistics counters.
  - Multi-threaded execution keeping the UI smooth while Playwright runs.
  - Embedded real-time console log with autoscroll.
  - Quick-access button to open `logs/artifacts/` screenshots in Windows Explorer.
- **Dual Data Source Support:**
  - **Local Excel Mode:** Reads from `Test.xlsx` (`'Client Details'` tab starting at row 3) and writes credentials directly to `'Succesful Signuos'` tab.
  - **Google Sheets Mode:** Connects live via `gspread` service account credentials with identical input and output mapping.
- **Multi-Modal Diagnostic & Failure Logging:**
  - Standardized console logs and rolling `logs/bot.log`.
  - Dedicated `logs/error.log` for warnings and errors with stack traces.
  - Visual proof screenshots (`logs/artifacts/<timestamp>_<client>_<site>_LOGIN_PROOF.png`).
  - Automatic failure bundles in `logs/artifacts/` capturing full-page `.png` screenshots, raw HTML DOM snapshots (`.html`), and Playwright trace archives (`.zip`).
- **Resilient & Idempotent State Management (`core/state.py`):**
  - Tracks registration and login verification states (`PENDING`, `IN_PROGRESS`, `SUCCESS`, `FAILED`, `MANUAL_REVIEW`, `SKIPPED`) in SQLite (`state.db`).
  - **Automatic Batch Advancement & Failed Record Skipping:** Automatically skips previously finished (`SUCCESS`, `ALREADY_REGISTERED`) as well as previously failed (`FAILED`, `MANUAL_REVIEW`) records on subsequent batch runs so the engine moves smoothly to fresh clients.
  - **Flexible Retry Controls:** Re-attempt failed records on-demand via the GUI (`🔁 Retry Failed Records` toggle or row-by-row `🔁 Retry` button in the Failures tab) or CLI (`--retry-failed`).
- **Strong Password & Username Generator (`core/password_gen.py`):**
  - Generates secure, compliant passwords satisfying uppercase, lowercase, numeric, and special character policies.
- **UK Data Normalization (`data/models.py`):**
  - Normalizes UK phone numbers (including float inputs like `7466317822.0` $\rightarrow$ `07466317822`).
  - Parses native Excel `datetime` objects and text strings (DD/MM/YYYY) into standardized components.
  - Validates and formats UK postcodes and address fields.

---

## Project Structure

```text
data_entry_bot/
│
├── config/
│   ├── promo_links.json         # Configurable promo URLs & affiliate mapping
│   └── settings.py              # Application settings, timeouts, login verify config
│
├── core/
│   ├── logger.py                # Multi-sink logging & Login Proof capturer
│   ├── browser.py               # Playwright browser manager (Headed/Headless + Tracing)
│   ├── engine.py                # Core orchestration engine & verify_single_account helper
│   ├── state.py                 # SQLite persistent state tracker & login verification store
│   └── password_gen.py          # Compliant strong password & username generator
│
├── data/
│   ├── __init__.py
│   ├── base_provider.py         # Abstract DataProvider interface
│   ├── google_sheets.py         # Google Sheets reader & writer (gspread)
│   ├── excel_provider.py        # Excel reader & writer (tuned for Test.xlsx)
│   ├── factory.py               # DataProvider factory (sheets vs excel)
│   └── models.py                # Pydantic Client and RegistrationResult models
│
├── gui/
│   ├── __init__.py              # GUI package
│   └── main_gui.py              # CustomTkinter modern desktop GUI app
│
├── sites/
│   ├── __init__.py              # Site adapter registry, promo config manager & factory
│   ├── base.py                  # BaseSiteAdapter lifecycle, login verification & error handling
│   ├── fairplaybet.py           # Fairplay Bet registration & login adapter
│   ├── betfred.py               # Betfred registration & login adapter
│   ├── quinnbet.py              # QuinnBet registration & login adapter
│   ├── bresbet.py               # BresBet registration & login adapter
│   ├── planetsportbet.py        # Planet Sport Bet registration & login adapter
│   ├── starsports.py            # Star Sports registration & login adapter
│   ├── betgoodwin.py            # Betgoodwin registration & login adapter
│   ├── betstgeorge.py           # Bet St George registration & login adapter
│   ├── bettom.py                # BetTOM EveryMatrix platform adapter (Phase 2)
│   ├── easybet.py               # easyBet exchange registration adapter (Phase 2)
│   ├── twentyfour7bet.py        # 247 Bet White Hat Gaming adapter (Phase 2)
│   ├── paddypower.py            # Paddy Power Flutter adapter with 25-day embargo (Phase 2)
│   ├── betfair.py               # Betfair Flutter adapter with 25-day embargo (Phase 2)
│   ├── dragonbet.py             # DragonBet Playbook Engineering adapter (Phase 2)
│   └── affiliate_redirects.py   # Betting Lounge affiliate redirect handler
│
├── logs/
│   ├── bot.log                  # Rolling operational log
│   ├── error.log                # Filtered error-only log with stack traces
│   └── artifacts/               # Login proof screenshots, DOM dumps, traces
│
├── tests/                       # Pytest unit & integration test suite
│   ├── test_models.py
│   ├── test_excel_provider.py
│   ├── test_password_gen.py
│   ├── test_state.py
│   ├── test_promo_links_config.py
│   ├── test_phase2_cooling_off.py
│   ├── test_phase2_adapters.py
│   ├── test_batch_advancement.py
│   ├── test_single_instance.py
│   └── test_gui.py
│
├── Test.xlsx                    # Sample test workbook
├── .env.example                 # Environment configuration template
├── gui_app.py                   # Desktop GUI entry point (single-instance mutex)
├── run_desktop_app.bat          # Desktop 1-click launcher for GUI
├── app.py                       # CLI entry point
├── run_bot.bat                  # Desktop 1-click batch runner (CLI)
└── requirements.txt             # Dependencies
```

---

## Quick Launch Options

### 1. Launch the Desktop GUI Application (Recommended)
- **Option A (One-Click):** Double-click `run_desktop_app.bat` in File Explorer.
- **Option B (Command Line):**
  ```powershell
  python gui_app.py
  ```

### 2. Run via Command Line (CLI)
- **Validate Data (Dry-Run):**
  ```powershell
  python app.py --dry-run --source excel --input Test.xlsx
  ```
- **Run Automation on Fairplay Bet (Advances to next pending clients):**
  ```powershell
  python app.py --headed --source excel --input Test.xlsx --sites fairplaybet --limit 5
  ```
- **Re-attempt Failed Records:**
  ```powershell
  python app.py --headed --source excel --input Test.xlsx --retry-failed --limit 10
  ```
- **Run Google Sheets Mode:**
  ```powershell
  python app.py --headed --source sheets --limit 20
  ```

---

## Managing Promo & Affiliate Links

In the Desktop GUI:
1. Open the **"🔗 Promo Links & Sites"** tab.
2. Edit any URL in the text box (e.g. updating a new campaign code or affiliate URL).
3. Click **`🌐 Test`** to verify the landing page opens and works in your browser.
4. Toggle the **Active / Inactive** switch to enable or disable specific sites.
5. Click **`💾 Save All Changes`** to persist the updates to `config/promo_links.json`.
6. To restore baseline URLs, click **`🔄 Reset`** on any row, or **`🔄 Reset All Defaults`** at the top.
7. To add a new partner site or campaign, click **`➕ Add Custom Link`**.

---

## Batch Advancement & Failure Handling

1. **Automatic Batch Advancement:**
   - On every batch run, `AutomationEngine` checks which clients still have pending registrations on the active site adapters.
   - Any client who has already finished or failed on all selected sites is skipped, and the batch window automatically advances to the next set of unprocessed clients up to the chosen limit.
2. **Handling Failures in the GUI ("⚠️ Failures & Review" Tab):**
   - **Website Filter Dropdown & Search Bar:** Filter failure records by a specific website (e.g. `BresBet`, `BetGoodwin`) or search for any client name, site, or error text.
   - **Multi-Selection Checkboxes & "Select All":** Select individual failure items or click "Select All" to target only the currently visible/filtered records.
   - **`🔁 Retry Selected (N)` Button:** Runs sequential fresh registrations in a background worker for all selected failed records, displaying real-time progress and live logs.
   - **`🗑️ Dismiss Selected (N)` Button:** Removes all selected failure records from the database in one batch operation, resetting their state so they can be re-evaluated.
   - **`🔁 Retry` Button:** Runs on-demand registration for a single failed client/site.
   - **`🗑️ Dismiss` Button:** Removes a single failure record from the local SQLite state.
   - **`🧹 Clear All Failures` Button:** Clears all recorded failures in one click to allow a fresh run across the entire list.
   - **`🔁 Retry Failed Records` Toggle:** When enabled in the sidebar, batch runs will include previously failed records instead of skipping them.

---

## Login Verification & Automatic False-Positive Cleanup

1. **Automatic Verification (Post-Registration):**
   - When a client account registration completes and `AUTO_VERIFY_LOGIN=true` (or the GUI switch is checked), the bot immediately opens a clean browser session to log in with the new credentials.
   - It validates active session indicators (Deposit button, account balance, user menu).
   - If login succeeds, it captures a logged-in dashboard proof (`_LOGIN_PROOF.png`), flags the record as `🔐 Verified` in SQLite, and writes the credentials to `'Succesful Signuos'` in Excel/Google Sheets.
   - **Automatic False-Positive Downgrade:** If login fails (e.g. `Invalid credentials` or registration was rejected by the server), the bot **downgrades** the result to `FAILED`, removes any false entry from `'Succesful Signuos'`, records the error in the database, and frees the client record so a fresh registration can be executed.

2. **On-Demand Manual Verification (Desktop GUI):**
   - Open the **✅ Registered Accounts** tab in the Desktop GUI.
   - Beside any account, click **`🔑 Verify`**.
   - A background worker launches Playwright, attempts authentication, and captures fresh proof.
   - If the site rejects the credentials (e.g. invalid credentials):
     - The row is **automatically removed** from the `'Succesful Signuos'` sheet in Excel / Google Sheets.
     - The database status is reset to `FAILED` / `PENDING`.
     - The user is notified via dialog, and the record can now be freshly re-registered.
   - Click **`🖼️ Proof`** to instantly open the verified logged-in screenshot proof.

---

## Installation & Setup

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.11 - 3.14)
- **Google Chrome** installed on the system (or Playwright Chromium)
- **Windows OS** (Supported on Windows 10/11 and Windows Server VPS)

### 2. Clone Repository & Install Dependencies
```powershell
git clone https://github.com/alirezakavianifar/data_entry_bot.git
cd data_entry_bot

pip install -r requirements.txt
playwright install chromium
```

### 3. Google Sheets Setup (Optional)
To use a live Google Sheet instead of local Excel:
1. Follow the comprehensive walkthrough in **[`GOOGLE_SHEETS_SETUP_GUIDE.md`](GOOGLE_SHEETS_SETUP_GUIDE.md)** to generate your `credentials.json` service account key.
2. Place `credentials.json` in the application root directory.
3. Share your Google Spreadsheet with the service account email (with **Editor** permissions).
4. Select **Google Sheets** in the desktop GUI and paste your sheet URL.

---

## 👁️ Visual Non-Headless Verification & Testing

To visually observe registration, address matching, form progression, and deposit handling live on your screen in a visible Google Chrome window:

### 1. Playbook Engineering Sites (BresBet, Star Sports, Planet Sport Bet, Bet St George)
- **Interactive Launcher**: Double-click **`run_visual_verification.bat`** in the project root.
- **Command Line**:
  ```powershell
  python scripts\verify_nonheadless.py bresbet
  python scripts\verify_nonheadless.py starsports
  python scripts\verify_nonheadless.py planetsportbet
  python scripts\verify_nonheadless.py betstgeorge
  python scripts\verify_nonheadless.py playbook    # All 4 Playbook sites sequentially
  python scripts\verify_nonheadless.py all         # All 8 supported bookmakers
  ```

### 2. Remaining Bookmakers (Betfred, QuinnBet, Betgoodwin, Fairplay Bet)
- **Interactive Launcher**: Double-click **`run_visual_verification_other.bat`** in the project root:
  - `1` for **Betfred**
  - `2` for **QuinnBet**
  - `3` for **Betgoodwin**
  - `4` for **Fairplay Bet**
  - `5` for **All Remaining Sites** (sequential)
- **Command Line**:
  ```powershell
  python scripts\verify_nonheadless_other.py betfred
  python scripts\verify_nonheadless_other.py quinnbet
  python scripts\verify_nonheadless_other.py betgoodwin
  python scripts\verify_nonheadless_other.py fairplaybet
  python scripts\verify_nonheadless_other.py all       # All 4 remaining sites sequentially
  ```

The browser window will open on your desktop, type fields with human pacing, handle modals, and leave the result screen open for 8 seconds for inspection.

---

## Diagnostic Logs & Troubleshooting

- **General Logs:** Check `logs/bot.log` for step-by-step breadcrumbs and timings.
- **Errors Only:** Check `logs/error.log` for stack traces and failed selector messages.
- **Visual Failure & Proof Artifacts (`logs/artifacts/`):**
  - High-res logged-in proof: `<timestamp>_<client>_<site>_LOGIN_PROOF.png`
  - When any step fails: `<timestamp>_<client>_<site>_<step>.png` and `.html` DOM snapshot.
  - Open traces: `playwright show-trace logs/artifacts/<trace_file>.zip`.

---

## Standalone Executable (.exe) & Portable Distribution

The repository includes an automated PowerShell build script (`scripts/build-standalone.ps1`) to compile the entire Data Entry Bot into a single standalone `.exe` that can be copied and run on any other Windows PC without installing Python, Git, or dependencies.

### 1. Build Single Standalone Executable
To compile `dist/DataEntryBot.exe`:
```powershell
.\scripts\build-standalone.ps1 -Clean
```

### 2. Build with Portable ZIP Archive
To compile the `.exe` and package it into `DataEntryBot-Portable.zip` with sample files and documentation:
```powershell
.\scripts\build-standalone.ps1 -Clean -CreateZip
```

### 3. Build with Offline Bundled Browser
To package Playwright's Chromium browser binaries directly inside the distribution folder (`dist/browsers`) for 100% offline environments without internet access:
```powershell
.\scripts\build-standalone.ps1 -Clean -BundleBrowser -CreateZip
```

### 4. Running on Another PC
1. Copy `dist/DataEntryBot.exe` (or extract `DataEntryBot-Portable.zip`) onto the target Windows PC.
2. Double-click **`DataEntryBot.exe`** to launch the GUI.
3. **Browser Execution:**
   - The standalone executable automatically connects to host **Google Chrome** or **Microsoft Edge**.
   - If no browser is installed, it will automatically download its internal Chromium engine on first launch.
4. **Data Persistence:**
   - The SQLite database (`state.db`), logs (`logs/`), screenshots, and custom promo configuration (`config/promo_links.json`) are automatically persisted in the folder alongside the `.exe`.

---

## Running Automated Tests

Run the complete pytest test suite:
```powershell
pytest
```
All unit tests verify phone normalization, datetime DOB handling, password complexity, state management, promo links configuration & persistence, login verification records, Excel provider reading/writing, and GUI initialization.
