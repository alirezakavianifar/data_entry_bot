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


def test_client_first_and_last_name_sanitization():
    # Test middle name entered into last name (Leoni kay Samuda)
    c1 = Client(
        client_id="CLI_007",
        full_name="Leoni kay Samuda",
        first_name="Leoni",
        last_name="kay Samuda",
        email="leoni@example.com",
        phone="07123456789",
        address_line1="10 High St",
        town_city="Romford",
        postcode="RM3 7AX"
    )
    assert c1.first_name == "Leoni"
    assert c1.last_name == "Samuda"
    assert c1.alphabetic_first_name == "Leoni"
    assert c1.alphabetic_last_name == "Samuda"

    # Test title prefix in first name
    c2 = Client(
        client_id="CLI_008",
        full_name="Mr. Thomas Delaney",
        first_name="Mr. Thomas",
        last_name="Delaney",
        email="thomas@example.com",
        phone="07123456789",
        address_line1="10 High St",
        town_city="London",
        postcode="SW1A 1AA"
    )
    assert c2.first_name == "Thomas"
    assert c2.last_name == "Delaney"

    # Test compound surnames with particles and hyphens
    c3 = Client(
        client_id="CLI_009",
        full_name="Patrick O'Connor",
        first_name="Patrick",
        last_name="O'Connor",
        email="patrick@example.com",
        phone="07123456789",
        address_line1="10 High St",
        town_city="Belfast",
        postcode="BT1 1AA"
    )
    assert c3.last_name == "O'Connor"

    c4 = Client(
        client_id="CLI_010",
        full_name="John St John",
        first_name="John",
        last_name="St John",
        email="john@example.com",
        phone="07123456789",
        address_line1="10 High St",
        town_city="Oxford",
        postcode="OX1 1AA"
    )
    assert c4.last_name == "St-John"

    # Test multi-word first name
    c5 = Client(
        client_id="CLI_011",
        full_name="Mary Jane Watson",
        first_name="Mary Jane",
        last_name="Watson",
        email="mary@example.com",
        phone="07123456789",
        address_line1="10 High St",
        town_city="London",
        postcode="NW1 1AA"
    )
    assert c5.first_name == "Mary"
    assert c5.last_name == "Watson"

