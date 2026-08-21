from pathlib import Path
from typing import Optional
from data.base_provider import BaseDataProvider
from data.excel_provider import ExcelDataProvider
from data.google_sheets import GoogleSheetsProvider
from config.settings import (
    DATA_SOURCE,
    EXCEL_INPUT_PATH,
    EXCEL_INPUT_SHEET,
    EXCEL_OUTPUT_SHEET,
    GOOGLE_SHEET_URL,
    GOOGLE_SERVICE_ACCOUNT_FILE
)


def get_data_provider(
    source: Optional[str] = None,
    excel_path: Optional[Path] = None,
    sheet_url: Optional[str] = None,
    credentials_file: Optional[Path] = None
) -> BaseDataProvider:
    """Factory function returning the configured DataProvider (Excel or Google Sheets)."""
    selected_source = (source or DATA_SOURCE).lower()

    if selected_source in ("excel", "xlsx", "csv"):
        path = excel_path or EXCEL_INPUT_PATH
        return ExcelDataProvider(
            file_path=path,
            input_sheet_name=EXCEL_INPUT_SHEET,
            output_sheet_name=EXCEL_OUTPUT_SHEET
        )
    elif selected_source in ("sheets", "google", "googlesheets"):
        url = sheet_url or GOOGLE_SHEET_URL
        creds = credentials_file or GOOGLE_SERVICE_ACCOUNT_FILE
        return GoogleSheetsProvider(
            sheet_url=url,
            credentials_file=creds,
            input_sheet_name=EXCEL_INPUT_SHEET,
            output_sheet_name=EXCEL_OUTPUT_SHEET
        )
    else:
        raise ValueError(f"Unknown data source mode: '{selected_source}'. Use 'excel' or 'sheets'.")
