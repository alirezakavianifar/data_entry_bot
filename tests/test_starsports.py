import pytest
from unittest.mock import MagicMock
from sites.base import is_already_registered_error, extract_clean_error_message
from sites.starsports import StarSportsAdapter
from data.models import Client, RegistrationStatus


def test_already_registered_pattern_matching():
    # Test Star Sports exact message from screenshot
    assert is_already_registered_error("This e-mail already exists.") is True
    assert is_already_registered_error("This email already exists.") is True
    assert is_already_registered_error("This e-mail is already registered") is True
    assert is_already_registered_error("E-mail already exists") is True
    assert is_already_registered_error("email already in use") is True
    assert is_already_registered_error("An account with this email already exists") is True
    assert is_already_registered_error("Looks like you're already registered") is True


def test_extract_clean_error_message():
    msg = extract_clean_error_message("This e-mail already exists.")
    assert "This e-mail already exists" in msg


def test_starsports_step1_already_exists_mock():
    adapter = StarSportsAdapter()
    client = Client(
        client_id="CLI_001",
        full_name="Courtney Weaver",
        first_name="Courtney",
        last_name="Weaver",
        email="courtney.weaver.5580@gmail.com",
        phone="07123456789",
        dob="1990-01-01",
        address_line1="10 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    page = MagicMock()
    page.url = "https://starsports.bet/?account=signup"
    page.is_closed.return_value = False
    page.content.return_value = "<html><body>This e-mail already exists.</body></html>"
    page.screenshot.return_value = b"screenshot_bytes"

    # Mock locators
    cookie_btn = MagicMock()
    cookie_btn.first = cookie_btn
    cookie_btn.is_visible.return_value = False

    email_inp = MagicMock()
    email_inp.first = email_inp
    email_inp.is_visible.return_value = True

    pwd_inp = MagicMock()
    pwd_inp.first = pwd_inp
    pwd_inp.is_visible.return_value = True

    create_acc_btn = MagicMock()
    create_acc_btn.first = create_acc_btn
    create_acc_btn.is_visible.return_value = True

    step1_err = MagicMock()
    step1_err.first = step1_err
    step1_err.is_visible.return_value = True
    step1_err.inner_text.return_value = "This e-mail already exists."

    def locator_side_effect(selector):
        if "Cookiebot" in selector or "Accept" in selector:
            return cookie_btn
        elif 'data-test="email-input"' in selector:
            return email_inp
        elif 'data-test="create-password-input"' in selector:
            return pwd_inp
        elif 'data-test="create-account-button"' in selector:
            return create_acc_btn
        elif "error" in selector:
            return step1_err
        m = MagicMock()
        m.first = m
        m.is_visible.return_value = False
        return m

    page.locator.side_effect = locator_side_effect

    res = adapter.fill_registration(page, client, "Password123!")
    assert res.status == RegistrationStatus.ALREADY_REGISTERED
    assert "Already registered" in res.error_summary
    assert "This e-mail already exists." in res.error_summary


def test_starsports_navigate_signature():
    adapter = StarSportsAdapter()
    page = MagicMock()
    page.goto.return_value = MagicMock(status=200)
    page.inner_text.return_value = "Normal page content"

    # Test 1 argument (page only)
    assert adapter.navigate(page) is True

    # Test 2 arguments (page, promo_url) - exactly as called by BaseSiteAdapter.execute
    assert adapter.navigate(page, "https://starsports.bet/?promo=welcome") is True

