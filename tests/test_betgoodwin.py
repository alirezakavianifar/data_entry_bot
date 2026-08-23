import pytest
from unittest.mock import MagicMock, patch
from sites.betgoodwin import BetgoodwinAdapter
from data.models import Client, RegistrationStatus


@pytest.fixture
def sample_client():
    return Client(
        client_id="CLI_BG_999",
        full_name="Marcus Vance",
        first_name="Marcus",
        last_name="Vance",
        email="marcus.vance.999@gmail.com",
        phone="07700900333",
        dob="1992-08-14",
        address_line1="18 High Street",
        town_city="Bristol",
        postcode="BS1 2AA"
    )


def test_betgoodwin_adapter_init():
    adapter = BetgoodwinAdapter()
    assert adapter.site_id == "betgoodwin"
    assert "betgoodwin.co.uk" in adapter.default_promo_url


def test_betgoodwin_already_registered_detection(sample_client):
    adapter = BetgoodwinAdapter()
    mock_page = MagicMock()

    # Simulate error banner indicating duplicate account
    mock_error = MagicMock()
    mock_error.is_visible.return_value = True
    mock_error.inner_text.return_value = "An account with this email already exists"
    mock_page.locator.return_value.first = mock_error

    with patch("sites.betgoodwin.capture_failure_bundle") as mock_bundle:
        mock_bundle.return_value = MagicMock(screenshot_path="proof.png", dom_snapshot_path="dom.html")
        result = adapter.fill_registration(mock_page, sample_client, "Goodwin2026!a")

    assert result.status == RegistrationStatus.ALREADY_REGISTERED
    assert "already exists" in result.error_summary.lower()


def test_betgoodwin_customer_services_issue_notice_is_already_registered(sample_client):
    adapter = BetgoodwinAdapter()
    mock_page = MagicMock()

    # Simulate Betgoodwin customer service issue notice
    mock_toast = MagicMock()
    mock_toast.is_visible.return_value = True
    mock_toast.inner_text.return_value = "There's an issue with your account registration, please contact Customer Services so we can assist you further."
    mock_page.locator.return_value.first = mock_toast

    with patch("sites.betgoodwin.capture_failure_bundle") as mock_bundle:
        mock_bundle.return_value = MagicMock(screenshot_path="proof.png", dom_snapshot_path="dom.html")
        result = adapter.fill_registration(mock_page, sample_client, "Goodwin2026!a")

    assert result.status == RegistrationStatus.ALREADY_REGISTERED
    assert "issue with your account registration" in result.error_summary.lower()
    assert result.account_reference == "Betgoodwin-Existing"


def test_betgoodwin_postcode_not_found_is_failed(sample_client):
    adapter = BetgoodwinAdapter()
    mock_page = MagicMock()

    # Simulate inline error 'No addresses found for this postal code'
    mock_inline = MagicMock()
    mock_inline.is_visible.return_value = True
    mock_inline.inner_text.return_value = "No addresses found for this postal code"
    mock_page.locator.return_value.first = mock_inline

    with patch("sites.betgoodwin.capture_failure_bundle") as mock_bundle:
        mock_bundle.return_value = MagicMock(screenshot_path="err_screenshot.png", dom_snapshot_path="err_dom.html")
        result = adapter.fill_registration(mock_page, sample_client, "Goodwin2026!a")

    assert result.status == RegistrationStatus.FAILED
    assert "No addresses found for this postal code" in result.error_summary
    assert result.screenshot_path == "err_screenshot.png"
    assert result.dom_snapshot_path == "err_dom.html"


def test_betgoodwin_something_went_wrong_is_failed(sample_client):
    adapter = BetgoodwinAdapter()
    mock_page = MagicMock()

    # Simulate server error 'Something went wrong... Please try again.'
    mock_err = MagicMock()
    mock_err.is_visible.return_value = True
    mock_err.inner_text.return_value = "Something went wrong... Please try again."
    mock_page.locator.return_value.first = mock_err

    with patch("sites.betgoodwin.capture_failure_bundle") as mock_bundle:
        mock_bundle.return_value = MagicMock(screenshot_path="sww_screenshot.png", dom_snapshot_path="sww_dom.html")
        result = adapter.fill_registration(mock_page, sample_client, "Goodwin2026!a")

    assert result.status == RegistrationStatus.FAILED
    assert "Something went wrong" in result.error_summary
    assert result.screenshot_path == "sww_screenshot.png"


def test_betgoodwin_success_flow(sample_client):
    adapter = BetgoodwinAdapter()
    mock_page = MagicMock()

    # Simulate normal form interaction without error banners
    def locator_side_effect(selector):
        loc = MagicMock()
        if "error" in selector:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
        elif "body" in selector:
            loc.inner_text.return_value = ""
        elif "Deposit" in selector or "My Account" in selector:
            loc.first.is_visible.return_value = True
        elif "input" in selector:
            loc.first.is_visible.return_value = False
        else:
            loc.first.is_visible.return_value = False
            loc.is_visible.return_value = False
        return loc

    mock_page.locator.side_effect = locator_side_effect
    mock_page.locator.return_value.first.is_visible.return_value = False

    with patch("sites.betgoodwin.capture_success_screenshot", return_value="success.png"):
        result = adapter.fill_registration(mock_page, sample_client, "Goodwin2026!a")

    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "betgoodwin"
