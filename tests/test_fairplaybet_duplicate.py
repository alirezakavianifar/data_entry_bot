import pytest
from unittest.mock import MagicMock
from sites.base import is_already_registered_error, extract_clean_error_message
from sites.fairplaybet import FairplayBetAdapter
from data.models import Client, RegistrationStatus


def test_fairplay_already_registered_pattern():
    raw_msg = "Error - Looks like you're already registered. Try logging in or contact cs@fairplayexchange.co.uk for further assistance. - Back"
    assert is_already_registered_error(raw_msg) is True
    clean = extract_clean_error_message(raw_msg)
    assert "Looks like you're already registered" in clean


def test_fairplay_duplicate_modal_mock():
    adapter = FairplayBetAdapter()
    client = Client(
        client_id="CLI_002",
        full_name="Daniel Buckley",
        first_name="Daniel",
        last_name="Buckley",
        email="daniel.buckley@example.com",
        phone="07123456789",
        dob="1990-01-01",
        address_line1="10 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    page = MagicMock()
    page.url = "https://fairplaybet.co.uk/"
    page.is_closed.return_value = False
    page.content.return_value = "<html><body>Error Looks like you're already registered.</body></html>"
    page.screenshot.return_value = b"screenshot"

    # Standard visible locator mock
    generic_visible = MagicMock()
    generic_visible.first = generic_visible
    generic_visible.is_visible.return_value = True
    generic_visible.is_checked.return_value = True
    generic_visible.count.return_value = 1

    error_modal = MagicMock()
    error_modal.first = error_modal
    error_modal.is_visible.return_value = True
    error_modal.inner_text.return_value = "Error\nLooks like you're already registered. Try logging in or contact cs@fairplayexchange.co.uk for further assistance.\nBack"

    def locator_side_effect(selector):
        if "dialog" in selector or "already registered" in selector or "Error" in selector or "alert" in selector or "modal" in selector.lower():
            return error_modal
        elif any(k in selector for k in ("More info needed", "electoral roll", "Proof of ID", "captcha", "recaptcha", "hcaptcha")):
            m = MagicMock()
            m.first = m
            m.is_visible.return_value = False
            return m
        return generic_visible

    page.locator.side_effect = locator_side_effect

    res = adapter.fill_registration(page, client, "Password123!")
    assert res.status == RegistrationStatus.ALREADY_REGISTERED
    assert "Already registered" in res.error_summary
    assert "Looks like you're already registered" in res.error_summary
