import pytest
from unittest.mock import MagicMock
from data.models import Client, RegistrationStatus
from sites import get_site_adapters
from sites.bettom import BetTOMAdapter
from sites.easybet import EasyBetAdapter
from sites.twentyfour7bet import TwentyFourSevenBetAdapter
from sites.paddypower import PaddyPowerAdapter
from sites.betfair import BetfairAdapter
from sites.dragonbet import DragonBetAdapter, BettingLounge2Adapter


@pytest.fixture
def sample_client():
    return Client(
        client_id="CLI_TEST_001",
        full_name="Sarah Connor",
        first_name="Sarah",
        last_name="Connor",
        email="sarah.connor@example.com",
        phone="07700900077",
        address_line1="10 Downing Street",
        town_city="London",
        postcode="SW1A 2AA",
        country="United Kingdom"
    )


def test_phase2_site_adapter_factory():
    adapters = get_site_adapters(filter_sites=["bettom", "easybet", "247bet", "paddypower", "betfair", "dragonbet"])
    adapter_map = {a.site_id: a for a in adapters}

    assert "bettom" in adapter_map
    assert isinstance(adapter_map["bettom"], BetTOMAdapter)
    assert adapter_map["bettom"].site_name == "BetTOM"

    assert "easybet" in adapter_map
    assert isinstance(adapter_map["easybet"], EasyBetAdapter)
    assert adapter_map["easybet"].site_name == "easyBet"

    assert "247bet" in adapter_map
    assert isinstance(adapter_map["247bet"], TwentyFourSevenBetAdapter)
    assert adapter_map["247bet"].site_name == "247 Bet"

    assert "paddypower" in adapter_map
    assert isinstance(adapter_map["paddypower"], PaddyPowerAdapter)
    assert adapter_map["paddypower"].site_name == "Paddy Power"

    assert "betfair" in adapter_map
    assert isinstance(adapter_map["betfair"], BetfairAdapter)
    assert adapter_map["betfair"].site_name == "Betfair"

    assert "dragonbet" in adapter_map
    assert isinstance(adapter_map["dragonbet"], DragonBetAdapter)
    assert adapter_map["dragonbet"].site_name == "DragonBet"

    adapters_bl2 = get_site_adapters(filter_sites=["bettinglounge2"])
    assert len(adapters_bl2) == 1
    assert isinstance(adapters_bl2[0], BettingLounge2Adapter)
    assert adapters_bl2[0].site_id == "bettinglounge2"


def test_paddypower_dry_run_and_embargo(sample_client):
    adapter = PaddyPowerAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://register.paddypower.com/account/registration"

    result = adapter.register_client(sample_client, mock_page, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "paddypower"
    assert result.signup_date is not None
    assert result.acceptable_to_bet_date is not None
    assert (result.acceptable_to_bet_date - result.signup_date).days == 25
    assert "Please do not place any bets until within 25 days." in result.formatted_notes


def test_betfair_dry_run_and_embargo(sample_client):
    adapter = BetfairAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://register.betfair.com/account/registration?promotionCode=ZSKAOL"

    result = adapter.register_client(sample_client, mock_page, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "betfair"
    assert result.signup_date is not None
    assert result.acceptable_to_bet_date is not None
    assert (result.acceptable_to_bet_date - result.signup_date).days == 25
    assert "Please do not place any bets until within 25 days." in result.formatted_notes


def test_bettom_dry_run(sample_client):
    adapter = BetTOMAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://www.bettom.com/en/sport/"

    result = adapter.register_client(sample_client, mock_page, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "bettom"
    assert result.username == sample_client.email
    assert "Please do not place any bets" not in result.formatted_notes


def test_bettom_name_sanitization_and_safeguards():
    """Verifies that BetTOM sanitizes multi-word names like 'Leoni kay Samuda' to avoid 'Only alphabetic characters are allowed' errors."""
    client = Client(
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
    assert client.first_name == "Leoni"
    assert client.last_name == "Samuda"
    assert client.alphabetic_last_name == "Samuda"
    assert " " not in client.alphabetic_last_name


def test_bettom_verification_congratulations_screen(sample_client):
    """Verifies that BetTOM immediately finishes waiting and marks registration as SUCCESS when CONGRATULATIONS modal appears."""
    adapter = BetTOMAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://www.bettom.com/en/sport/"

    def locator_side_effect(selector):
        loc = MagicMock()
        loc.first = loc
        if any(s in selector for s in ("CONGRATULATIONS", "Your account was successfully registered", "GO TO LOGIN")):
            loc.is_visible.return_value = True
            loc.inner_text.return_value = "CONGRATULATIONS!\nYour account was successfully registered!\nPlease check your email and continue the registration process.\nGO TO LOGIN"
        elif "body" in selector:
            loc.inner_text.return_value = "CONGRATULATIONS! Your account was successfully registered! Please check your email and continue the registration process. GO TO LOGIN"
        else:
            loc.is_visible.return_value = False
        return loc

    mock_page.locator.side_effect = locator_side_effect
    log = MagicMock()

    status, summary, ref = adapter._wait_for_verification_results(mock_page, sample_client, log)
    assert status == RegistrationStatus.SUCCESS
    assert ref == "BETTOM_SUCCESS"
    assert "Registration successful" in summary
    assert "CONGRATULATIONS" in log.info.call_args_list[-1][0][0]



def test_easybet_dry_run(sample_client):
    adapter = EasyBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://welcome.easybet.net/EB20-Football"

    result = adapter.register_client(sample_client, mock_page, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "easybet"
    assert "Please do not place any bets" not in result.formatted_notes


def test_easybet_verification_confirmation_deposit_screen(sample_client):
    adapter = EasyBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://exchange.easybet.net/"

    def locator_side_effect(selector):
        loc = MagicMock()
        loc.first = loc
        if any(s in selector for s in ('button:has-text("Deposit")', 'a:has-text("Deposit")', '[data-hook*="deposit"]')):
            loc.is_visible.return_value = True
            loc.inner_text.return_value = "Deposit"
        elif "body" in selector:
            loc.inner_text.return_value = "Welcome to easyBet Deposit now to get started"
        else:
            loc.is_visible.return_value = False
        return loc

    mock_page.locator.side_effect = locator_side_effect
    log = MagicMock()

    status, summary, ref = adapter._wait_for_verification_results(mock_page, sample_client, log)
    assert status == RegistrationStatus.SUCCESS
    assert ref == "EASYBET_AUTH_CONFIRMED"
    assert "confirmed by easyBet" in summary
    assert "Deposit" in summary


def test_easybet_verification_onboarding_modal(sample_client):
    adapter = EasyBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://exchange.easybet.net/"

    def locator_side_effect(selector):
        loc = MagicMock()
        loc.first = loc
        if "CustomerOnboarding" in selector or "Pick a side" in selector:
            loc.is_visible.return_value = True
        elif "body" in selector:
            loc.inner_text.return_value = "Pick a side. Bet YES or NO on the biggest questions"
        else:
            loc.is_visible.return_value = False
        return loc

    mock_page.locator.side_effect = locator_side_effect
    log = MagicMock()

    status, summary, ref = adapter._wait_for_verification_results(mock_page, sample_client, log)
    assert status == RegistrationStatus.SUCCESS
    assert ref == "EASYBET_AUTH_CONFIRMED"
    assert "confirmed by easyBet" in summary


def test_easybet_login_success():
    adapter = EasyBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://exchange.easybet.net/"

    def locator_side_effect(selector):
        loc = MagicMock()
        loc.first = loc
        if "username" in selector or "password" in selector or "login" in selector.lower():
            loc.is_visible.return_value = True
        elif any(s in selector for s in ('button:has-text("Deposit")', 'a:has-text("Deposit")', '[data-hook*="deposit"]')):
            loc.is_visible.return_value = True
        else:
            loc.is_visible.return_value = False
        return loc

    mock_page.locator.side_effect = locator_side_effect
    from unittest.mock import patch
    with patch("sites.easybet.capture_login_proof_screenshot", return_value="artifacts/proof.png"):
        success, proof, err = adapter.login(mock_page, "courtn0108", "Pass12345!")
        assert success is True
        assert proof == "artifacts/proof.png"
        assert err is None
        mock_page.goto.assert_called_with("https://exchange.easybet.net/", wait_until="domcontentloaded", timeout=30000)


def test_247bet_dry_run(sample_client):
    adapter = TwentyFourSevenBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://www.247bet.com/en-gb/register"

    result = adapter.register_client(sample_client, mock_page, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "247bet"
    assert "Please do not place any bets" not in result.formatted_notes


def test_247bet_login_verification():
    adapter = TwentyFourSevenBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://www.247bet.com/en-gb/"

    login_btn_mock = MagicMock()
    login_btn_mock.bounding_box.return_value = {"x": 1400, "y": 10, "width": 60, "height": 40}
    login_btn_mock.is_visible.return_value = True

    candidates_mock = MagicMock()
    candidates_mock.count.return_value = 1
    candidates_mock.nth.return_value = login_btn_mock

    def locator_side_effect(selector):
        if "btn--login" in selector:
            return candidates_mock
        loc = MagicMock()
        loc.first = loc
        loc.is_visible.return_value = True
        return loc

    mock_page.locator.side_effect = locator_side_effect
    from unittest.mock import patch
    with patch("sites.twentyfour7bet.capture_login_proof_screenshot", return_value="artifacts/247bet_proof.png"):
        success, proof, err = adapter.perform_login_verification(mock_page, "jadelongden95", "Pass12345!")
        assert success is True
        assert proof == "artifacts/247bet_proof.png"
        assert err is None


def test_247bet_financial_limits_and_confirmation(sample_client):
    adapter = TwentyFourSevenBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://www.247bet.com/en-gb/?cashier=1"

    loc = MagicMock()
    loc.first = loc
    loc.is_visible.return_value = True
    mock_page.locator.return_value = loc

    result = adapter.register_client(sample_client, mock_page, dry_run=False, password="Pass12345!Test")
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "247bet"
    assert "Registration confirmed by website" in (result.notes or "")


def test_dragonbet_dry_run(sample_client):
    adapter = DragonBetAdapter()
    result = adapter.register_client(sample_client, None, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "dragonbet"
    assert result.username == sample_client.email


def test_bettinglounge2_dry_run(sample_client):
    adapter = BettingLounge2Adapter()
    result = adapter.register_client(sample_client, None, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "bettinglounge2"
    assert "DragonBet" in result.site_name
    assert result.username == sample_client.email

