import datetime
from pathlib import Path
from typing import List, Optional
import gspread
from google.oauth2.service_account import Credentials
from dateutil import parser as date_parser

from data.base_provider import BaseDataProvider
from data.models import Client, RegistrationResult
from core.logger import get_logger

logger = get_logger(step="GoogleSheetsProvider")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


class GoogleSheetsProvider(BaseDataProvider):
    """Google Sheets data provider supporting live sheets reading & writing via gspread."""

    def __init__(
        self,
        sheet_url: str,
        credentials_file: Path,
        input_sheet_name: str = "Client Details",
        output_sheet_name: str = "Succesful Signuos"
    ):
        self.sheet_url = sheet_url
        self.credentials_file = Path(credentials_file)
        self.input_sheet_name = input_sheet_name
        self.output_sheet_name = output_sheet_name
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None

    def _get_client(self) -> gspread.Client:
        if self._client:
            return self._client
        if not self.credentials_file.exists():
            raise FileNotFoundError(
                f"Google service account credentials not found at: {self.credentials_file}. "
                "Please provide credentials.json or switch to local Excel mode (--source excel)."
            )
        creds = Credentials.from_service_account_file(str(self.credentials_file), scopes=SCOPES)
        self._client = gspread.authorize(creds)
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        if self._spreadsheet:
            return self._spreadsheet
        client = self._get_client()
        self._spreadsheet = client.open_by_url(self.sheet_url)
        return self._spreadsheet

    def get_all_clients(self) -> List[Client]:
        try:
            ss = self._get_spreadsheet()
            worksheet = None
            for ws in ss.worksheets():
                if ws.title.strip().lower() == self.input_sheet_name.strip().lower():
                    worksheet = ws
                    break
            if not worksheet:
                worksheet = ss.get_worksheet(0)

            rows = worksheet.get_all_values()
            if not rows:
                logger.warning("Google Sheet is empty")
                return []

            # Find header row
            header_row_idx = 0
            col_map = {}
            for r_idx, row in enumerate(rows[:10]):
                lower_row = [str(c).strip().lower() for c in row]
                if "client" in lower_row or "first name" in lower_row or "email" in lower_row:
                    header_row_idx = r_idx
                    for col_idx, cell in enumerate(row):
                        if cell:
                            col_map[cell.strip().lower()] = col_idx
                    break

            if not col_map:
                logger.error("Could not locate header row in Google Sheet")
                return []

            clients: List[Client] = []
            for row_num, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
                def get_cell(key_fragment):
                    for k, col in col_map.items():
                        if key_fragment in k and col < len(row):
                            return row[col]
                    return ""

                client_val = get_cell("client")
                first_name = get_cell("first name")
                last_name = get_cell("last name")
                full_name = client_val.strip() if client_val else f"{first_name} {last_name}".strip()

                if not full_name and not first_name:
                    continue

                raw_dob = get_cell("dob")
                dob_date = None
                if raw_dob:
                    try:
                        dob_date = date_parser.parse(str(raw_dob), dayfirst=True).date()
                    except Exception:
                        dob_date = None

                email = get_cell("email").strip()
                phone = get_cell("phone").strip()
                addr1 = get_cell("address").strip()
                town = (get_cell("town") or get_cell("city")).strip()
                postcode = get_cell("postcode").strip()
                country = get_cell("country").strip() or "United Kingdom"
                card = get_cell("card").strip()
                va = (get_cell("allocated") or get_cell("va")).strip()
                notes = get_cell("note").strip()
                raw_title = (get_cell("title") or get_cell("salutation")).strip() or None

                client_id = f"CLI_{row_num:04d}_{''.join(c for c in full_name.lower() if c.isalnum())[:10]}"

                try:
                    client = Client(
                        client_id=client_id,
                        full_name=full_name,
                        first_name=first_name.strip() or full_name.split(" ")[0],
                        last_name=last_name.strip() or (full_name.split(" ")[-1] if " " in full_name else ""),
                        title=raw_title,
                        dob=dob_date,
                        email=email,
                        phone=phone,
                        address_line1=addr1,
                        town_city=town,
                        postcode=postcode,
                        country=country,
                        card_used=card if card else None,
                        allocated_va=va if va else None,
                        notes=notes if notes else None
                    )
                    clients.append(client)
                except Exception as e:
                    logger.warning(f"Skipping malformed sheet row {row_num}: {e}")

            logger.info(f"Loaded {len(clients)} clients from Google Sheet")
            return clients
        except Exception as e:
            logger.error(f"Failed to fetch clients from Google Sheets: {e}")
            return []

    def record_success(self, result: RegistrationResult) -> bool:
        try:
            ss = self._get_spreadsheet()
            worksheet = None
            for ws in ss.worksheets():
                if ws.title.strip().lower() in (self.output_sheet_name.strip().lower(), "successful signups", "succesful signuos"):
                    worksheet = ws
                    break
            
            if not worksheet:
                worksheet = ss.add_worksheet(title=self.output_sheet_name, rows="1000", cols="10")
                worksheet.append_row(["Name", "Account", "Email", "Username", "Password", "Timestamp", "Notes"])

            worksheet.append_row([
                result.client_name,
                result.site_name,
                result.email,
                result.username or result.email,
                result.password or "",
                result.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                result.account_reference or ""
            ])
            logger.info(f"Recorded success for {result.client_name} on {result.site_name} in Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Failed to record success to Google Sheets: {e}")
            return False

    def record_failure(self, result: RegistrationResult) -> bool:
        logger.warning(f"Google Sheets failure log: {result.client_name} on {result.site_name}: {result.error_summary}")
        return True

    def remove_success(self, client_name: str, site_name: str, email: str = "") -> int:
        """
        Removes matching rows from the Google Sheet successful signups tab.
        Returns count of deleted rows.
        """
        try:
            ss = self._get_spreadsheet()
            worksheet = None
            for ws in ss.worksheets():
                if ws.title.strip().lower() in (self.output_sheet_name.strip().lower(), "successful signups", "succesful signuos"):
                    worksheet = ws
                    break

            if not worksheet:
                return 0

            all_values = worksheet.get_all_values()
            if len(all_values) <= 1:
                return 0

            deleted_count = 0
            c_name_clean = client_name.strip().lower()
            site_clean = site_name.strip().lower()
            email_clean = email.strip().lower() if email else ""

            # Delete in reverse order
            for row_idx in range(len(all_values), 1, -1):
                row = all_values[row_idx - 1]
                row_name = (row[0] if len(row) > 0 else "").strip().lower()
                row_site = (row[1] if len(row) > 1 else "").strip().lower()
                row_email = (row[2] if len(row) > 2 else "").strip().lower()

                name_match = (row_name == c_name_clean or c_name_clean in row_name or row_name in c_name_clean) and (row_site == site_clean or site_clean in row_site)
                email_match = (email_clean and row_email == email_clean) and (row_site == site_clean or site_clean in row_site)

                if name_match or email_match:
                    logger.info(f"Deleting Google Sheets row {row_idx} ({row_name}, {row_site})")
                    worksheet.delete_rows(row_idx)
                    deleted_count += 1

            return deleted_count
        except Exception as e:
            logger.error(f"Failed to remove record from Google Sheets: {e}")
            return 0

