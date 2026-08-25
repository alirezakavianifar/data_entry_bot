import secrets
import string

ALLOWED_SPECIAL = "!@#$%^&*"


def generate_password(length: int = 14) -> str:
    """
    Generates a secure password compliant with bookmaker password policies:
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 allowed special character (!@#$%^&*)
    - Total length default: 14 characters
    """
    if length < 10:
        length = 10

    # Ensure at least one character from each required class
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice(ALLOWED_SPECIAL)

    # Fill the remaining characters
    all_chars = string.ascii_letters + string.digits + ALLOWED_SPECIAL
    remaining_length = length - 4
    remaining = [secrets.choice(all_chars) for _ in range(remaining_length)]

    # Combine and shuffle
    password_chars = [upper, lower, digit, special] + remaining
    # Use secrets for cryptographically safe shuffle
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def generate_username(first_name: str, last_name: str, dob_year: str = "") -> str:
    """Generates a clean username if an account requires a separate username from email."""
    clean_first = "".join(c for c in first_name.lower() if c.isalnum())
    clean_last = "".join(c for c in last_name.lower() if c.isalnum())
    suffix = str(dob_year)[-2:] if dob_year else str(secrets.randbelow(90) + 10)
    rand_digits = str(secrets.randbelow(900) + 100)
    
    username = f"{clean_first}{clean_last[:4]}{suffix}{rand_digits}"
    return username[:16]


SECURITY_ANSWERS = {
    "maiden": [
        "Taylor", "Davies", "Walker", "Wright", "Robinson", "Wood", "Thompson",
        "White", "Watson", "Jackson", "Harris", "Clark", "Lewis", "Hall",
        "Roberts", "Edwards", "Turner", "Phillips", "Campbell", "Parker", "Evans"
    ],
    "pet": [
        "Bella", "Milo", "Buddy", "Luna", "Charlie", "Cooper", "Daisy", "Bailey",
        "Lola", "Max", "Teddy", "Buster", "Rocky", "Toby", "Ruby", "Oscar", "Coco"
    ],
    "city": [
        "Bristol", "Leeds", "Sheffield", "Manchester", "Norwich", "York", "Bath",
        "Exeter", "Oxford", "Cambridge", "Derby", "Chester", "Gloucester", "Salisbury"
    ],
    "school": [
        "StMarys", "StJohns", "Oakwood", "Greenfield", "Highfield", "Hillside",
        "Parkview", "Meadowbrook", "Westgate", "Kingsway", "Redland", "Brookfield"
    ],
    "team": [
        "Arsenal", "Chelsea", "Liverpool", "Everton", "AstonVilla", "Newcastle",
        "Brighton", "Brentford", "Fulham", "Tottenham", "Southampton", "Leicester"
    ]
}


def generate_security_answer(question_text: str = "") -> str:
    """
    Returns a randomized, realistic answer tailored to the category of the selected security question.
    """
    q_lower = (question_text or "").lower()
    if any(k in q_lower for k in ("mother", "maiden", "surname", "parent")):
        return secrets.choice(SECURITY_ANSWERS["maiden"])
    elif any(k in q_lower for k in ("pet", "dog", "cat", "animal")):
        return secrets.choice(SECURITY_ANSWERS["pet"])
    elif any(k in q_lower for k in ("city", "town", "born", "birthplace", "place")):
        return secrets.choice(SECURITY_ANSWERS["city"])
    elif any(k in q_lower for k in ("school", "college", "primary")):
        return secrets.choice(SECURITY_ANSWERS["school"])
    elif any(k in q_lower for k in ("team", "sport", "football", "club")):
        return secrets.choice(SECURITY_ANSWERS["team"])
    else:
        all_options = [ans for sublist in SECURITY_ANSWERS.values() for ans in sublist]
        return secrets.choice(all_options)

