import argparse
import sys
from pathlib import Path
from config.settings import (
    DATA_SOURCE,
    EXCEL_INPUT_PATH,
    GOOGLE_SHEET_URL,
    DAILY_CLIENT_LIMIT,
    BROWSER_HEADLESS
)
from data.factory import get_data_provider
from core.browser import BrowserManager
from core.state import StateManager
from core.engine import AutomationEngine
from core.logger import get_logger
from sites import get_site_adapters

logger = get_logger(step="CLI")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Data Entry Automation Bot for Automated Client Signups (Google Sheets & Local Excel)"
    )
    parser.add_argument(
        "--source",
        choices=["excel", "sheets"],
        default=DATA_SOURCE,
        help=f"Data provider source ('excel' or 'sheets'). Default: {DATA_SOURCE}"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(EXCEL_INPUT_PATH),
        help=f"Path to input Excel workbook. Default: {EXCEL_INPUT_PATH}"
    )
    parser.add_argument(
        "--sheet-url",
        type=str,
        default=GOOGLE_SHEET_URL,
        help="Google Sheets URL (when in 'sheets' mode)."
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in visible (headed) mode on desktop."
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in background (headless) mode."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DAILY_CLIENT_LIMIT,
        help=f"Maximum number of clients to process in this run. Default: {DAILY_CLIENT_LIMIT}"
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=None,
        help="Process only a specific client ID or name substring."
    )
    parser.add_argument(
        "--sites",
        type=str,
        default=None,
        help="Comma-separated list of specific site IDs to run (e.g. 'fairplaybet,betfred')."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data source and print client details without launching browser registrations."
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Save Playwright execution traces for debugging."
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Determine headless mode
    headless = True if args.headless else (False if args.headed else BROWSER_HEADLESS)

    # Parse site filters
    site_filters = [s.strip().lower() for s in args.sites.split(",")] if args.sites else None

    logger.info("=======================================================")
    logger.info("Starting Data Entry Client Signup Bot")
    logger.info(f"Source: {args.source.upper()} | Headless: {headless} | Limit: {args.limit}")
    logger.info("=======================================================")

    try:
        # 1. Initialize Data Provider
        provider = get_data_provider(
            source=args.source,
            excel_path=Path(args.input) if args.input else None,
            sheet_url=args.sheet_url
        )

        # 2. Initialize Browser Manager
        browser_mgr = BrowserManager(
            headless=headless,
            trace=args.trace
        )

        # 3. Initialize State Manager
        state_mgr = StateManager()

        # 4. Initialize Site Adapters
        adapters = get_site_adapters(filter_sites=site_filters)

        # 5. Initialize & Run Engine
        engine = AutomationEngine(
            provider=provider,
            state_mgr=state_mgr,
            browser_mgr=browser_mgr,
            site_adapters=adapters
        )

        engine.run(
            limit=args.limit,
            client_id_filter=args.client_id,
            site_filters=site_filters,
            dry_run=args.dry_run
        )

    except Exception as e:
        logger.exception(f"Fatal error running automation bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
