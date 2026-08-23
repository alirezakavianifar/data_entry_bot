import datetime
import pytest
from data.models import Client, RegistrationStatus, RegistrationResult


def test_client_phone_normalization():
    # Test float from Excel
    c1 = Client(
        client_id="CLI_001",
        full_name="Test User",
        first_name="Test",
        last_name="User",
        dob=datetime.date(1995, 5, 20),
        email="test@example.com",
        phone=7466317822.0,
        address_line1="10 Downing St",
        town_city="London",
        postcode="SW1A 2AA"
    )
    assert c1.phone == "07466317822"

    # Test +44 prefix
    c2 = Client(
        client_id="CLI_002",
        full_name="Test User 2",
        first_name="Test",
        last_name="User",
        dob=datetime.date(1995, 5, 20),
        email="test2@example.com",
        phone="+447466317822",
        address_line1="10 Downing St",
        town_city="London",
        postcode="SW1A 2AA"
    )
    assert c2.phone == "07466317822"


def test_client_dob_properties():
    c = Client(
        client_id="CLI_003",
        full_name="Alice Smith",
        first_name="Alice",
        last_name="Smith",
        dob=datetime.date(1998, 4, 7),
        email="alice@example.com",
        phone="07123456789",
        address_line1="1 High St",
        town_city="Bristol",
        postcode="BS1 4AA"
    )
    assert c.dob_day == "07"
    assert c.dob_month == "04"
    assert c.dob_year == "1998"
    assert c.dob_month_name == "April"


def test_client_validation():
    valid_c = Client(
        client_id="CLI_004",
        full_name="John Doe",
        first_name="John",
        last_name="Doe",
        dob=datetime.date(1990, 1, 1),
        email="john@example.com",
        phone="07123456789",
        address_line1="1 Road",
        town_city="City",
        postcode="AB12 3CD"
    )
    is_valid, reason = valid_c.is_valid_for_signup
    assert is_valid is True
    assert reason == "Valid"

    invalid_c = Client(
        client_id="CLI_005",
        full_name="No Email",
        first_name="No",
        last_name="Email",
        email="",
        phone="07123456789",
        address_line1="1 Road",
        town_city="City",
        postcode="AB12 3CD"
    )
    is_valid, reason = invalid_c.is_valid_for_signup
    assert is_valid is False


def test_client_town_city_and_address_sanitization():
    c = Client(
        client_id="CLI_006",
        full_name="Gary Oldman",
        first_name="Gary",
        last_name="Oldman",
        dob=datetime.date(1989, 11, 23),
        email="gary@example.com",
        phone="07700900888",
        address_line1="45 Victoria Road, ",
        town_city="Nottingham, Nottinghamshire: East",
        postcode="NG3 7HE"
    )
    assert c.town_city == "Nottingham"
    assert c.address_line1 == "45 Victoria Road"
