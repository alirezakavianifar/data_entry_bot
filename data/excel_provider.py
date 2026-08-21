import datetime
from pathlib import Path
from typing import List, Optional
import openpyxl
from dateutil import parser as date_parser

from data.base_provider import BaseDataProvider
from data.models import Client, RegistrationResult
from core.logger import get_logger

logger = get_logger(step="ExcelDataProvider")


class ExcelDataProvider(BaseDataProvider):
    """Excel data provider supporting Test.xlsx and standard spreadsheets."""

    def __init__(
        self,
        file_path: Path,
        input_sheet_name: str = "Client Details",
        output_sheet_name: str = "Succesful Signuos"
    ):
        self.file_path = Path(file_path)
        self.input_sheet_name = input_sheet_name
        self.output_sheet_name = output_sheet_name

    def _get_or_create_workbook(self) -> openpyxl.Workbook:
        if self.file_path.exists():
            return openpyxl.load_workbook(str(self.file_path))
        wb = openpyxl.Workbook()
        wb.active.title = self.input_sheet_name
        return wb

    def get_all_clients(self) -> List[Client]:
        """Loads and parses clients from Excel."""
        if not self.file_path.exists():
            logger.error(f"Excel file not found at: {self.file_path}")
            return []

        wb = openpyxl.load_workbook(str(self.file_path), data_only=True)
        
        # Locate input sheet
        sheet = None
        for name in wb.sheetnames:
            if name.strip().lower() == self.input_sheet_name.strip().lower():
                sheet = wb[name]
                break
        if not sheet:
            sheet = wb.active
            logger.warning(f"Sheet '{self.input_sheet_name}' not found; using active sheet '{sheet.title}'")

        # Find header row (search rows 1 through 10)
        header_row_idx = 1
        col_map = {}
        for r in range(1, min(10, sheet.max_row + 1)):
            row_vals = [sheet.cell(r, c).value for c in range(1, sheet.max_column + 1)]
            str_vals = [str(v).strip().lower() if v is not None else "" for v in row_vals]
            if "client" in str_vals or "first name" in str_vals or "email" in str_vals:
                header_row_idx = r
                for col_idx, raw_val in enumerate(row_vals, start=1):
                    if raw_val:
                        norm_key = str(raw_val).strip().lower()
                        col_map[norm_key] = col_idx
                break

        if not col_map:
            logger.error(f"Could not locate client header row in {self.file_path}")
            return []

        logger.info(f"Loaded sheet '{sheet.title}', header found at row {header_row_idx}. Parsing clients...")

        clients: List[Client] = []
        for row_idx in range(header_row_idx + 1, sheet.max_row + 1):
            def get_val(key_fragment):
                for k, col in col_map.items():
                    if key_fragment in k:
                        return sheet.cell(row_idx, col).value
                return None

            client_val = get_val("client")
            first_name = get_val("first name") or ""
            last_name = get_val("last name") or ""
            full_name = str(client_val).strip() if client_val else f"{first_name} {last_name}".strip()

            if not full_name and not first_name:
                continue  # Empty row

            raw_dob = get_val("dob")
            dob_date = None
            if isinstance(raw_dob, (datetime.datetime, datetime.date)):
                dob_date = raw_dob.date() if isinstance(raw_dob, datetime.datetime) else raw_dob
            elif raw_dob:
                try:
                    # Handles DD/MM/YYYY or text
                    dob_date = date_parser.parse(str(raw_dob), dayfirst=True).date()
                except Exception:
                    dob_date = None

            email = str(get_val("email") or "").strip()
            phone = str(get_val("phone") or "").strip()
            addr1 = str(get_val("address") or "").strip()
            town = str(get_val("town") or get_val("city") or "").strip()
            postcode = str(get_val("postcode") or "").strip()
            country = str(get_val("country") or "United Kingdom").strip()
            card = str(get_val("card") or "").strip()
            va = str(get_val("allocated") or get_val("va") or "").strip()
            notes = str(get_val("note") or "").strip()

            client_id = f"CLI_{row_idx:04d}_{''.join(c for c in full_name.lower() if c.isalnum())[:10]}"

            try:
                client = Client(
                    client_id=client_id,
                    full_name=full_name,
                    first_name=str(first_name).strip() or full_name.split(" ")[0],
                    last_name=str(last_name).strip() or (full_name.split(" ")[-1] if " " in full_name else ""),
                    dob=dob_date,
                    email=email,
                    phone=phone,
                    address_line1=addr1,
                    town_city=town,
                    postcode=postcode,
                    country=country if country else "United Kingdom",
                    card_used=card if card else None,
                    allocated_va=va if va else None,
                    notes=notes if notes else None
                )
                clients.append(client)
            except Exception as e:
                logger.warning(f"Skipping malformed row {row_idx}: {e}")

        logger.info(f"Successfully loaded {len(clients)} client records from {self.file_path.name}")
        return clients

    def record_success(self, result: RegistrationResult) -> bool:
        """Appends a successful registration into the results worksheet."""
        try:
            wb = self._get_or_create_workbook()
            
            # Find output sheet (handling 'Succesful Signuos' typo and correct spelling)
            target_sheet = None
            for name in wb.sheetnames:
                if name.strip().lower() in (self.output_sheet_name.strip().lower(), "successful signups", "succesful signuos"):
                    target_sheet = wb[name]
                    break
            
            if not target_sheet:
                target_sheet = wb.create_sheet(title=self.output_sheet_name)
                # Add headers
                target_sheet.append(["Name", "Account", "Email", "Username", "Password", "Timestamp", "Notes"])

            # Check if headers exist
            if target_sheet.max_row == 0 or (target_sheet.max_row == 1 and not target_sheet.cell(1, 1).value):
                target_sheet.append(["Name", "Account", "Email", "Username", "Password", "Timestamp", "Notes"])

            target_sheet.append([
                result.client_name,
                result.site_name,
                result.email,
                result.username or result.email,
                result.password or "",
                result.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                result.account_reference or ""
            ])

            wb.save(str(self.file_path))
            logger.info(f"Recorded success for {result.client_name} on {result.site_name} in {self.file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to record success to Excel: {e}")
            return False

    def record_failure(self, result: RegistrationResult) -> bool:
        """Logs failure into console and state (Excel results sheet focuses on successful accounts)."""
        logger.warning(f"Registration failure recorded for {result.client_name} on {result.site_name}: {result.error_summary}")
        return True

    def remove_success(self, client_name: str, site_name: str, email: str = "") -> int:
        """
        Removes any matching rows from the successful registrations sheet.
        Returns the count of deleted rows.
        """
        try:
            wb = self._get_or_create_workbook()
            target_sheet = None
            for name in wb.sheetnames:
                if name.strip().lower() in (self.output_sheet_name.strip().lower(), "successful signups", "succesful signuos"):
                    target_sheet = wb[name]
                    break

            if not target_sheet or target_sheet.max_row <= 1:
                return 0

            # Scan from bottom to top to safely delete rows
            deleted_count = 0
            c_name_clean = client_name.strip().lower()
            site_clean = site_name.strip().lower()
            email_clean = email.strip().lower() if email else ""

            for row_idx in range(target_sheet.max_row, 1, -1):
                row_name = str(target_sheet.cell(row_idx, 1).value or "").strip().lower()
                row_site = str(target_sheet.cell(row_idx, 2).value or "").strip().lower()
                row_email = str(target_sheet.cell(row_idx, 3).value or "").strip().lower()

                # Match by Name + Site or Email + Site
                name_match = (row_name == c_name_clean or c_name_clean in row_name or row_name in c_name_clean) and (row_site == site_clean or site_clean in row_site)
                email_match = (email_clean and row_email == email_clean) and (row_site == site_clean or site_clean in row_site)

                if name_match or email_match:
                    logger.info(f"Removing invalid registration row {row_idx} ({row_name}, {row_site}) from {self.file_path.name}")
                    target_sheet.delete_rows(row_idx, 1)
                    deleted_count += 1

            if deleted_count > 0:
                wb.save(str(self.file_path))
                logger.info(f"Successfully deleted {deleted_count} row(s) from Excel '{target_sheet.title}'")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to remove false positive record from Excel: {e}")
            return 0

