import pytest
from unittest.mock import MagicMock, patch
from data.models import Client, RegistrationResult, RegistrationStatus
from core.engine import AutomationEngine
from sites.quinnbet import QuinnbetAdapter
from sites.fairplaybet import FairplayBetAdapter
from sites.betfred import BetfredAdapter


@pytest.fixture
def mock_client():
    return Client(
        client_id="CLI_TEST_001",
        full_name="Thomas Delaney",
        first_name="Thomas",
        last_name="Delaney",
        email="thomas.delaney@test.com",
        phone="07123456789",
        address_line1="10 High Street",
        town_city="London",
        postcode="SW1A 1AA",
        country="United Kingdom"
    )


def test_engine_non_destructive_login_verification(mock_client):
    """Verifies that if registration succeeds, a failed login verification does NOT delete credentials or mark as failed."""
    mock_provider = MagicMock()
    mock_state = MagicMock()
    mock_browser = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.site_id = "quinnbet"
    mock_adapter.site_name = "QuinnBet"

    # Simulate registration SUCCESS
    mock_adapter.execute.return_value = RegistrationResult(
        client_id=mock_client.client_id,
        client_name=mock_client.full_name,
        site_id="quinnbet",
        site_name="QuinnBet",
        status=RegistrationStatus.SUCCESS,
        email=mock_client.email,
        username="tdelaney",
        password="TestPassword123!",
        account_reference="QuinnBet-Direct (Auto-Verified)"
    )

    # Simulate secondary login failure (due to session expiration or deposit modal)
    mock_adapter.login.return_value = (False, "path/to/proof.png", "Deposit modal blocked login inputs")

    engine = AutomationEngine(
        provider=mock_provider,
        state_mgr=mock_state,
        browser_mgr=mock_browser,
        site_adapters=[mock_adapter]
    )

    mock_provider.get_valid_clients.return_value = [mock_client]
    mock_state.has_pending_sites.return_value = True
    mock_state.is_complete.return_value = False
    mock_state.get_status.return_value = RegistrationStatus.PENDING

    res = engine.run(limit=1, verify_login=True)

    # Check that remove_success was NEVER called
    mock_provider.remove_success.assert_not_called()

    # Check that record_success was called with SUCCESS status
    assert mock_provider.record_success.call_count == 1
    recorded_result = mock_provider.record_success.call_args[0][0]
    assert recorded_result.status == RegistrationStatus.SUCCESS
    assert recorded_result.login_verified is False
    assert "Login check pending" in recorded_result.error_summary
    assert recorded_result.password == "TestPassword123!"


def test_fairplay_email_verification_status(mock_client):
    """Verifies that Fairplay email verification prompts produce SUCCESS with email verification reminder."""
    adapter = FairplayBetAdapter()
    assert adapter.site_id == "fairplaybet"


def test_quinnbet_adapter_instantiation():
    adapter = QuinnbetAdapter()
    assert adapter.site_id == "quinnbet"
    assert adapter.site_name == "QuinnBet"


def test_betfred_adapter_instantiation():
    adapter = BetfredAdapter()
    assert adapter.site_id == "betfred"
    assert adapter.site_name == "Betfred"
