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
