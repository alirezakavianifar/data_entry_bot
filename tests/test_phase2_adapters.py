import pytest
from unittest.mock import MagicMock
from data.models import Client, RegistrationStatus
from sites import get_site_adapters
from sites.bettom import BetTOMAdapter
from sites.easybet import EasyBetAdapter
from sites.twentyfour7bet import TwentyFourSevenBetAdapter
from sites.paddypower import PaddyPowerAdapter
from sites.betfair import BetfairAdapter
from sites.dragonbet import DragonBetAdapter


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


def test_easybet_dry_run(sample_client):
    adapter = EasyBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://welcome.easybet.net/EB20-Football"

    result = adapter.register_client(sample_client, mock_page, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "easybet"
    assert "Please do not place any bets" not in result.formatted_notes


def test_247bet_dry_run(sample_client):
    adapter = TwentyFourSevenBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://www.247bet.com/en-gb/register"

    result = adapter.register_client(sample_client, mock_page, dry_run=True)
    assert result.status == RegistrationStatus.SUCCESS
    assert result.site_id == "247bet"
    assert "Please do not place any bets" not in result.formatted_notes
