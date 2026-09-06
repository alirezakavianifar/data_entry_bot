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
    title: Optional[str] = None
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

    @property
    def resolved_title(self) -> str:
        """
        Resolves the appropriate personal title ('Mr.', 'Mrs.', 'Miss', 'Ms.') for the client.
        1. Uses self.title if explicitly specified.
        2. Checks for standard title prefixes in self.full_name or self.first_name.
        3. Uses comprehensive UK first name gender heuristic.
        4. Defaults to 'Mr.' if undetermined.
        """
        # 1. Explicit title
        if self.title and str(self.title).strip():
            t = str(self.title).strip().lower().replace(".", "")
            if t == "mrs":
                return "Mrs."
            elif t == "miss":
                return "Miss"
            elif t == "ms":
                return "Ms."
            elif t in ("mr", "mister", "dr", "master"):
                return "Mr."

        # 2. Prefix in full_name or first_name
        name_to_check = f"{self.full_name} {self.first_name}".strip()
        prefix_match = re.match(r"^(Mr|Mrs|Ms|Miss|Dr|Master)\b\.?", name_to_check, re.IGNORECASE)
        if prefix_match:
            p = prefix_match.group(1).lower()
            if p == "mrs":
                return "Mrs."
            elif p == "miss":
                return "Miss"
            elif p == "ms":
                return "Ms."
            elif p in ("mr", "master", "dr"):
                return "Mr."

        # 3. UK first name gender heuristic
        fn = re.split(r"[\s\-]", str(self.first_name).strip().lower())[0] if self.first_name else ""
        female_names = {
            "holly", "courtney", "laura", "leoni", "sarah", "gabriella", "hannah", "helen", "debbie",
            "bobbie", "shannon", "emily", "sophie", "chloe", "jessica", "charlotte", "megan", "olivia",
            "emma", "katie", "amy", "lucy", "ellie", "georgia", "rebecca", "jade", "amber", "bethany",
            "lauren", "alice", "abigail", "eleanor", "hollie", "paige", "grace", "molly", "poppy", "daisy",
            "rosie", "elizabeth", "freya", "ruby", "isabelle", "ella", "zoe", "sienna", "florence", "lily",
            "scarlett", "layla", "maya", "harriet", "clara", "mary", "patricia", "jennifer", "linda",
            "barbara", "susan", "margaret", "dorothy", "lisa", "nancy", "karen", "betty", "carol", "anna",
            "sandra", "ashley", "donna", "ruth", "sharon", "michelle", "melissa", "amanda", "stephanie",
            "carolyn", "christine", "marie", "janet", "catherine", "frances", "ann", "joyce", "diane",
            "victoria", "vanessa", "kelly", "christina", "joan", "evelyn", "judith", "andrea", "cheryl",
            "yvonne", "fiona", "gillian", "kerry", "nicola", "claire", "gemma", "tracey", "joanne",
            "denise", "lynne", "wendy", "sally", "valerie", "maureen", "pauline", "pamela", "jean",
            "brenda", "eileen", "marion", "doreen", "audrey", "shirley", "gwen", "dawn", "hazel",
            "sheila", "heather", "hilary", "alison", "lesley", "morag", "lorna", "rhona", "catriona",
            "kirsty", "isla", "anne", "teresa", "samantha", "danielle", "hayley", "kayleigh", "natasha",
            "chelsea", "beth", "naomi", "claudia", "francesca", "zoey", "lucia", "lydia", "harriet",
            "tash", "kay", "katy", "bethan", "rhiannon", "sian", "carys", "clara", "tina", "jo"
        }
        if fn in female_names:
            return "Mrs."

        # 4. Default to Mr.
        return "Mr."

    @property
    def resolved_title_clean(self) -> str:
        """Returns the resolved title without trailing dot, e.g. 'Mr', 'Mrs', 'Miss', 'Ms'."""
        return self.resolved_title.rstrip(".")

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

    @field_validator("town_city", mode="before")
    @classmethod
    def clean_town_city(cls, v) -> str:
        """Cleans UK town/city string to prevent bookmaker validation errors (e.g. commas, counties, special characters)."""
        if not v:
            return ""
        # Split by commas, slashes, colons, or newlines
        parts = [p.strip() for p in re.split(r"[,/:\n]", str(v)) if p.strip()]
        if not parts:
            return ""
        val = parts[0]
        # If the first part has digits (e.g. 'Unit E3 45 Dace Road...'), look for a non-digit city part (e.g. 'London')
        if any(ch.isdigit() for ch in val) and len(parts) > 1:
            for p in parts[1:]:
                if not any(ch.isdigit() for ch in p) and len(p) >= 3:
                    val = p
                    break
        # Keep only alphabet letters, spaces, hyphens, and apostrophes
        val = re.sub(r"[^a-zA-Z\s\-']", "", val).strip()
        # Collapse multiple spaces
        val = re.sub(r"\s+", " ", val)
        return val or str(v).strip()

    @field_validator("address_line1", mode="before")
    @classmethod
    def clean_address_line1(cls, v) -> str:
        if not v:
            return ""
        val = str(v).strip().rstrip(",").rstrip(".").strip()
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

