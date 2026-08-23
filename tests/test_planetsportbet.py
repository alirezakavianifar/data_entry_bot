import pytest
from unittest.mock import MagicMock, patch
from sites.planetsportbet import PlanetSportBetAdapter
from data.models import Client, RegistrationStatus


@pytest.fixture
def sample_client():
    return Client(
        client_id="CLI_PSB_001",
        full_name="Daniel Buckley",
        first_name="Daniel",
        last_name="Buckley",
        email="daniel.buckley.6491@gmail.com",
        phone="07700900111",
        dob="1990-05-12",
        address_line1="10 Downing Street",
        town_city="London",
        postcode="SW1A 2AA"
    )


def test_planetsportbet_adapter_init():
    adapter = PlanetSportBetAdapter()
    assert adapter.site_id == "planetsportbet"
    assert "planetsportbet.com" in adapter.default_promo_url


def test_planetsportbet_step1_already_exists_is_already_registered(sample_client):
    adapter = PlanetSportBetAdapter()
    mock_page = MagicMock()

    # Step 1 input visibility
    mock_email = MagicMock()
    mock_email.is_visible.return_value = True
    mock_pwd = MagicMock()
    mock_pwd.is_visible.return_value = True

    # Error banner indicating duplicate email
    mock_err = MagicMock()
    mock_err.is_visible.return_value = True
    mock_err.inner_text.return_value = "This e-mail already exists."
    mock_err.first.is_visible.return_value = True
    mock_err.first.inner_text.return_value = "This e-mail already exists."

    def locator_side_effect(selector):
        loc = MagicMock()
        if "email" in selector:
            return mock_email
        elif "password" in selector:
            return mock_pwd
        elif "error" in selector or "already exists" in selector:
            return mock_err
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            return loc

    mock_page.locator.side_effect = locator_side_effect

    with patch("sites.planetsportbet.capture_failure_bundle") as mock_bundle:
        mock_bundle.return_value = MagicMock(screenshot_path="proof.png", dom_snapshot_path="dom.html")
        result = adapter.fill_registration(mock_page, sample_client, "Planet2026!a")

    assert result.status == RegistrationStatus.ALREADY_REGISTERED
    assert "already exists" in result.error_summary.lower()
    assert result.account_reference == "PlanetSportBet-Existing"


def test_planetsportbet_step2_delayed_duplicate_banner_is_already_registered(sample_client):
    adapter = PlanetSportBetAdapter()
    mock_page = MagicMock()

    mock_email = MagicMock()
    mock_email.is_visible.return_value = True
    mock_email.first.is_visible.return_value = True
    mock_pwd = MagicMock()
    mock_pwd.is_visible.return_value = True
    mock_pwd.first.is_visible.return_value = True

    # Step 1 error initially not visible, but when Step 2 inputs are missing, duplicate banner is visible
    mock_dup = MagicMock()
    mock_dup.is_visible.return_value = True
    mock_dup.inner_text.return_value = "This e-mail already exists."
    mock_dup.first.is_visible.return_value = True
    mock_dup.first.inner_text.return_value = "This e-mail already exists."

    def locator_side_effect(selector):
        loc = MagicMock()
        if "email" in selector:
            return mock_email
        elif "password" in selector:
            return mock_pwd
        elif "first-name-input" in selector:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            return loc
        elif "already exists" in selector or "error" in selector:
            return mock_dup
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            return loc

    mock_page.locator.side_effect = locator_side_effect

    with patch("sites.planetsportbet.capture_failure_bundle") as mock_bundle:
        mock_bundle.return_value = MagicMock(screenshot_path="proof.png", dom_snapshot_path="dom.html")
        result = adapter.fill_registration(mock_page, sample_client, "Planet2026!a")

    assert result.status == RegistrationStatus.ALREADY_REGISTERED
    assert "already exists" in result.error_summary.lower()
