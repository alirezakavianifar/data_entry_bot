import re
import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class RegistrationStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"
    SKIPPED = "SKIPPED"



class Client(BaseModel):
    client_id: str
    full_name: str
    first_name: str
    last_name: str
    dob: Optional[datetime.date] = None
    email: str
    phone: str
    address_line1: str
    town_city: str
    postcode: str
    country: str = "United Kingdom"
    card_used: Optional[str] = None
    allocated_va: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_uk_phone(cls, v) -> str:
        """Normalizes UK phone strings, floats, and ints to 07xxxxxxxxx format."""
        if v is None:
            return ""
        # Handle float from Excel like 7466317822.0
        if isinstance(v, (int, float)):
            v = str(int(v))
        val = str(v).strip().replace(" ", "").replace("-", "")
        if val.endswith(".0"):
            val = val[:-2]
        # If number starts with 44 or +44
        if val.startswith("+44"):
            val = "0" + val[3:]
        elif val.startswith("44") and len(val) == 12:
            val = "0" + val[2:]
        # If missing leading zero on UK 10-digit number like 7466317822
        elif len(val) == 10 and val.startswith("7"):
            val = "0" + val
        return val

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v) -> str:
        if not v:
            return ""
        return str(v).strip().lower()

    @field_validator("postcode", mode="before")
    @classmethod
    def clean_postcode(cls, v) -> str:
        if not v:
            return ""
        val = str(v).strip().upper()
        # Ensure single space before inward code if formatted e.g. RM37AX -> RM3 7AX
        val = re.sub(r"\s+", " ", val)
        return val

    @property
    def dob_day(self) -> str:
        return str(self.dob.day).zfill(2) if self.dob else "01"

    @property
    def dob_month(self) -> str:
        return str(self.dob.month).zfill(2) if self.dob else "01"

    @property
    def dob_month_name(self) -> str:
        return self.dob.strftime("%B") if self.dob else "January"

    @property
    def dob_year(self) -> str:
        return str(self.dob.year) if self.dob else "1995"

    @property
    def is_valid_for_signup(self) -> tuple[bool, str]:
        """Returns True if client has minimum required fields for account registration."""
        if not self.email or "@" not in self.email:
            return False, "Missing or invalid email"
        if not self.first_name:
            return False, "Missing first name"
        if not self.last_name:
            return False, "Missing last name"
        if not self.phone or len(self.phone) < 10:
            return False, "Missing or invalid phone number"
        if not self.postcode:
            return False, "Missing postcode"
        if not self.dob:
            return False, "Missing date of birth"
        return True, "Valid"


class RegistrationResult(BaseModel):
    client_id: str
    client_name: str
    site_id: str
    site_name: str
    status: RegistrationStatus
    email: str
    username: Optional[str] = None
    password: Optional[str] = None
    account_reference: Optional[str] = None
    error_summary: Optional[str] = None
    screenshot_path: Optional[str] = None
    dom_snapshot_path: Optional[str] = None
    login_verified: bool = False
    login_screenshot_path: Optional[str] = None
    login_error: Optional[str] = None
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

