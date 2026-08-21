import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Data Source
DATA_SOURCE = os.getenv("DATA_SOURCE", "excel").lower()

# Excel Configuration
EXCEL_INPUT_PATH = Path(os.getenv("EXCEL_INPUT_PATH", "Test.xlsx"))
if not EXCEL_INPUT_PATH.is_absolute():
    EXCEL_INPUT_PATH = BASE_DIR / EXCEL_INPUT_PATH

EXCEL_INPUT_SHEET = os.getenv("EXCEL_INPUT_SHEET", "Client Details")
EXCEL_OUTPUT_SHEET = os.getenv("EXCEL_OUTPUT_SHEET", "Succesful Signuos")

# Google Sheets Configuration
GOOGLE_SHEET_URL = os.getenv(
    "GOOGLE_SHEET_URL",
    "https://docs.google.com/spreadsheets/d/17ohWhpYEER6nKaWz65FjfS95nX6JI61zHUBFbG7e27c/edit?usp=sharing"
)
GOOGLE_SERVICE_ACCOUNT_FILE = Path(os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json"))
if not GOOGLE_SERVICE_ACCOUNT_FILE.is_absolute():
    GOOGLE_SERVICE_ACCOUNT_FILE = BASE_DIR / GOOGLE_SERVICE_ACCOUNT_FILE

# Browser Settings
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes")
BROWSER_SLOW_MO_MS = int(os.getenv("BROWSER_SLOW_MO_MS", "100"))
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "20000"))

# State Database Path
STATE_DB_PATH = BASE_DIR / "state.db"

# Logs & Artifacts Directories
LOGS_DIR = BASE_DIR / "logs"
ARTIFACTS_DIR = LOGS_DIR / "artifacts"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_PLAYWRIGHT_TRACE = os.getenv("ENABLE_PLAYWRIGHT_TRACE", "false").lower() in ("true", "1", "yes")

# Promo links config
PROMO_LINKS_FILE = BASE_DIR / "config" / "promo_links.json"

# Processing Defaults
DAILY_CLIENT_LIMIT = int(os.getenv("DAILY_CLIENT_LIMIT", "20"))
AUTO_VERIFY_LOGIN = os.getenv("AUTO_VERIFY_LOGIN", "true").lower() in ("true", "1", "yes")

# Ensure runtime directories exist
LOGS_DIR.mkdir(exist_ok=True, parents=True)
ARTIFACTS_DIR.mkdir(exist_ok=True, parents=True)

