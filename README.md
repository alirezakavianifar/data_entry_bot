# Data Entry Bot — Client Signup Automation System

An automated, enterprise-grade data entry system built with **Python**, **CustomTkinter**, **Playwright**, **OpenPyXL**, and **GSpread**. The system reads client details from **Google Sheets** or local **Excel workbooks (`Test.xlsx`)**, executes multi-step account registration workflows across betting/bookmaker platforms, tracks progress idempotently via SQLite, and writes successful registration credentials back to the results sheet.

Includes both a **Modern Desktop GUI Application** and a **Command-Line Interface (CLI)**.

---

## Features

- **Modern Desktop GUI Application (`gui_app.py` / `run_desktop_app.bat`):**
  - Sleek dark theme interface with intuitive controls.
  - Interactive Data Source picker (`Excel` file browser vs `Google Sheets` URL).
  - Target website checklist with quick selection filters.
  - Real-time animated progress bar, status badges, and live statistics counters.
  - Multi-threaded execution keeping the UI smooth while Playwright runs.
  - Embedded real-time console log with autoscroll.
  - Quick-access button to open `logs/artifacts/` screenshots in Windows Explorer.
- **Dual Data Source Support:**
  - **Local Excel Mode:** Reads from `Test.xlsx` (`'Client Details'` tab starting at row 3) and writes credentials directly to `'Succesful Signuos'` tab.
  - **Google Sheets Mode:** Connects live via `gspread` service account credentials with identical input and output mapping.
- **Dynamic Promo Links (`config/promo_links.json`):**
  - Switch or update promotional URLs, campaigns, and affiliate tracking IDs without modifying Python code.
- **Multi-Modal Diagnostic & Failure Logging:**
  - Standardized console logs and rolling `logs/bot.log`.
  - Dedicated `logs/error.log` for warnings and errors with stack traces.
  - Automatic failure bundles in `logs/artifacts/` capturing full-page `.png` screenshots, raw HTML DOM snapshots (`.html`), and Playwright trace archives (`.zip`).
- **Resilient & Idempotent State Management (`core/state.py`):**
  - Tracks registration states (`PENDING`, `IN_PROGRESS`, `SUCCESS`, `FAILED`, `MANUAL_REVIEW`, `SKIPPED`) in SQLite (`state.db`).
  - Safely resumes interrupted jobs without repeating already completed accounts.
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
│   └── settings.py              # Application settings, timeouts, logging config
│
├── core/
│   ├── logger.py                # Multi-sink logging & FailureBundle capturer
│   ├── browser.py               # Playwright browser manager (Headed/Headless + Tracing)
│   ├── engine.py                # Core orchestration engine (Client × Site matrix)
│   ├── state.py                 # SQLite persistent state tracker
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
│   ├── __init__.py              # Site adapter registry & factory
│   ├── base.py                  # BaseSiteAdapter lifecycle & error handling
│   ├── fairplaybet.py           # Fairplay Bet adapter (Stage 1 Live Experiment Site)
│   ├── betfred.py               # Betfred registration adapter (Stage 2)
│   ├── quinnbet.py              # QuinnBet registration adapter (Stage 2)
│   ├── bresbet.py               # BresBet registration adapter (Stage 2)
│   ├── planetsportbet.py        # Planet Sport Bet adapter (Stage 2)
│   ├── starsports.py            # Star Sports (OLBG outbound) adapter (Stage 2)
│   ├── betgoodwin.py            # Betgoodwin (OddsMonkey outbound) adapter (Stage 2)
│   └── affiliate_redirects.py   # Betting Lounge affiliate redirect handler (Stage 2)
│
├── logs/
│   ├── bot.log                  # Rolling operational log
│   ├── error.log                # Filtered error-only log with stack traces
│   └── artifacts/               # Full-page screenshots (.png), DOM dumps (.html), Traces (.zip)
│
├── tests/                       # Pytest unit & integration test suite
│   ├── test_models.py
│   ├── test_excel_provider.py
│   ├── test_password_gen.py
│   ├── test_state.py
│   └── test_gui.py
│
├── Test.xlsx                    # Sample test workbook
├── .env.example                 # Environment configuration template
├── gui_app.py                   # Desktop GUI entry point
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
- **Run Visible Automation on Fairplay Bet:**
  ```powershell
  python app.py --headed --source excel --input Test.xlsx --sites fairplaybet --limit 5
  ```
- **Run Google Sheets Mode:**
  ```powershell
  python app.py --headed --source sheets --limit 20
  ```

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

---

## Diagnostic Logs & Troubleshooting

- **General Logs:** Check `logs/bot.log` for step-by-step breadcrumbs and timings.
- **Errors Only:** Check `logs/error.log` for stack traces and failed selector messages.
- **Visual Failure Artifacts (`logs/artifacts/`):**
  - When any step fails, inspect the `.png` screenshot and `.html` DOM snapshot.
  - Open traces: `playwright show-trace logs/artifacts/<trace_file>.zip`.

---

## Running Automated Tests

Run the complete pytest test suite:
```powershell
pytest
```
All 8 unit tests verify phone normalization, datetime DOB handling, password complexity, state management, Excel provider reading/writing, and GUI initialization.
