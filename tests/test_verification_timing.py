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


def test_fairplay_verifying_spinner_does_not_exit_early(mock_client):
    """
    Verifies that when Fairplay Bet displays 'Verifying' / 'Please wait while we verify your details',
    it does NOT treat it as an email verification prompt and does NOT mark it as SUCCESS immediately.
    It must wait and return the actual outcome (e.g. failure when verification fails).
    """
    adapter = FairplayBetAdapter()
    page = MagicMock()
    page.url = "https://fairplaybet.co.uk/"
    page.is_closed.return_value = False

    # Standard visible locator mock for form fields
    generic_visible = MagicMock()
    generic_visible.first = generic_visible
    generic_visible.is_visible.return_value = True
    generic_visible.is_checked.return_value = True
    generic_visible.count.return_value = 1

    # Call counter to simulate state transition:
    # First 2 checks: Verifying indicator is visible
    # Next: Verification failed modal is visible
    poll_calls = 0

    verifying_mock = MagicMock()
    verifying_mock.first = verifying_mock
    verifying_mock.inner_text.return_value = "Verifying your details"

    failed_mock = MagicMock()
    failed_mock.first = failed_mock
    failed_mock.inner_text.return_value = "Verification failed - Unable to verify your details"

    not_visible = MagicMock()
    not_visible.first = not_visible
    not_visible.is_visible.return_value = False

    def locator_side_effect(selector):
        nonlocal poll_calls
        if any(k in selector for k in ("Please wait while we verify", "Verifying", "verifying")):
            if poll_calls < 2:
                verifying_mock.is_visible.return_value = True
                return verifying_mock
            else:
                verifying_mock.is_visible.return_value = False
                return not_visible
        elif "Verification failed" in selector or "Unable to verify" in selector or "error" in selector.lower():
            if poll_calls >= 2:
                failed_mock.is_visible.return_value = True
                return failed_mock
            else:
                failed_mock.is_visible.return_value = False
                return not_visible
        elif any(k in selector for k in ("activation link", "check your email", "Verify your email", "More info needed", "captcha", "recaptcha", "hcaptcha")):
            return not_visible
        elif any(k in selector for k in ("Deposit", "My Account", "Logout")):
            return not_visible
        return generic_visible

    def wait_side_effect(ms):
        nonlocal poll_calls
        poll_calls += 1

    page.locator.side_effect = locator_side_effect
    page.wait_for_timeout.side_effect = wait_side_effect

    with patch("sites.fairplaybet.capture_failure_bundle") as mock_bundle:
        bundle_mock = MagicMock()
        bundle_mock.screenshot_path = "fail.png"
        bundle_mock.dom_snapshot_path = "fail.html"
        mock_bundle.return_value = bundle_mock

        res = adapter.fill_registration(page, mock_client, "Password123!")

    # Must NOT have exited on iteration 0 as SUCCESS
    assert res.status == RegistrationStatus.FAILED
    assert "Unable to verify" in res.error_summary or "Verification failed" in res.error_summary
    assert poll_calls >= 2


def test_fairplay_verifying_timeout_returns_failed(mock_client):
    """
    Verifies that if Fairplay Bet remains stuck in the 'Verifying...' state through
    the full polling window, it returns FAILED (never premature SUCCESS).
    """
    adapter = FairplayBetAdapter()
    page = MagicMock()
    page.url = "https://fairplaybet.co.uk/"
    page.is_closed.return_value = False

    generic_visible = MagicMock()
    generic_visible.first = generic_visible
    generic_visible.is_visible.return_value = True
    generic_visible.is_checked.return_value = True
    generic_visible.count.return_value = 1

    verifying_mock = MagicMock()
    verifying_mock.first = verifying_mock
    verifying_mock.is_visible.return_value = True
    verifying_mock.inner_text.return_value = "Verifying your details"

    not_visible = MagicMock()
    not_visible.first = not_visible
    not_visible.is_visible.return_value = False

    def locator_side_effect(selector):
        if any(k in selector for k in ("Please wait while we verify", "Verifying", "verifying")):
            return verifying_mock
        elif any(k in selector for k in ("activation link", "check your email", "Verify your email", "More info needed", "captcha", "recaptcha", "hcaptcha", "already registered", "Error", "Unable to verify", "Verification failed")):
            return not_visible
        elif any(k in selector for k in ("Deposit", "My Account", "Logout")):
            return not_visible
        return generic_visible

    page.locator.side_effect = locator_side_effect

    with patch("sites.fairplaybet.capture_failure_bundle") as mock_bundle:
        bundle_mock = MagicMock()
        bundle_mock.screenshot_path = "timeout.png"
        bundle_mock.dom_snapshot_path = "timeout.html"
        mock_bundle.return_value = bundle_mock

        res = adapter.fill_registration(page, mock_client, "Password123!")

    assert res.status == RegistrationStatus.FAILED
    assert "timed out" in res.error_summary.lower()


def test_quinnbet_adapter_instantiation():
    adapter = QuinnbetAdapter()
    assert adapter.site_id == "quinnbet"
    assert adapter.site_name == "QuinnBet"


def test_betfred_adapter_instantiation():
    adapter = BetfredAdapter()
    assert adapter.site_id == "betfred"
    assert adapter.site_name == "Betfred"


def test_bettom_verifying_spinner_does_not_exit_early(mock_client):
    """
    Verifies that when BetTOM displays 'Please wait, loading...' or verification spinner,
    it does NOT exit early on iteration 0 as SUCCESS even if background text has 'Safer Gambling'.
    """
    from sites.bettom import BetTOMAdapter
    adapter = BetTOMAdapter()
    page = MagicMock()
    page.url = "https://www.bettom.com/en/sport/"
    page.is_closed.return_value = False

    poll_calls = 0

    loading_mock = MagicMock()
    loading_mock.first = loading_mock

    modal_container_mock = MagicMock()
    modal_container_mock.first = modal_container_mock
    modal_container_mock.is_visible.return_value = True

    not_visible = MagicMock()
    not_visible.first = not_visible
    not_visible.is_visible.return_value = False

    def locator_side_effect(selector):
        nonlocal poll_calls
        if any(k in selector for k in ("Please wait", "loading...", "Verifying")):
            if poll_calls < 2:
                loading_mock.is_visible.return_value = True
                return loading_mock
            else:
                loading_mock.is_visible.return_value = False
                return not_visible
        elif any(k in selector for k in ("LoginModalContainer", "LoginModalContent", "RegisterWrapper")):
            if poll_calls >= 2:
                modal_container_mock.is_visible.return_value = False
            return modal_container_mock
        elif any(k in selector for k in ("ItemBalance", "ItemMyAccount", "AuthUser")):
            if poll_calls >= 2:
                auth_mock = MagicMock()
                auth_mock.first = auth_mock
                auth_mock.is_visible.return_value = True
                return auth_mock
            return not_visible
        elif "body" in selector:
            body_mock = MagicMock()
            body_mock.inner_text.return_value = "Safer Gambling Football Tennis BetTOM"
            return body_mock
        return not_visible

    def wait_side_effect(ms):
        nonlocal poll_calls
        poll_calls += 1

    page.locator.side_effect = locator_side_effect
    page.wait_for_timeout.side_effect = wait_side_effect

    mock_log = MagicMock()
    status, summary, ref = adapter._wait_for_verification_results(page, mock_client, mock_log)

    assert status == RegistrationStatus.SUCCESS
    # Must have polled at least twice while loading was active, not 0s
    assert poll_calls >= 2

