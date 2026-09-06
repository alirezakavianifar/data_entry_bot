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


def test_betgoodwin_checkbox_targets_part_and_scrolls_to_done(sample_client):
    adapter = BetgoodwinAdapter()
    mock_page = MagicMock()
    mock_page.context.pages = [mock_page]

    part_box_mock = MagicMock()
    part_box_mock.is_visible.return_value = True
    part_box_mock.first = part_box_mock

    terms_cb_mock = MagicMock()
    terms_cb_mock.is_visible.return_value = True
    terms_cb_mock.first = terms_cb_mock
    terms_cb_mock.locator.return_value = part_box_mock
    terms_cb_mock.evaluate.return_value = True

    done_btn_mock = MagicMock()
    done_btn_mock.is_visible.return_value = True
    done_btn_mock.first = done_btn_mock

    def locator_side_effect(selector):
        loc = MagicMock()
        if "vaadin-checkbox" in selector:
            return terms_cb_mock
        elif "Done" in selector:
            return done_btn_mock
        elif "error" in selector or "invalid" in selector:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
        elif "Deposit" in selector or "My Account" in selector:
            loc.first.is_visible.return_value = True
        else:
            loc.first.is_visible.return_value = False
            loc.is_visible.return_value = False
        return loc

    mock_page.locator.side_effect = locator_side_effect

    with patch("sites.betgoodwin.human_click") as mock_human_click, \
         patch("sites.betgoodwin.human_scroll") as mock_human_scroll, \
         patch("sites.betgoodwin.capture_success_screenshot", return_value="success.png"):
        result = adapter.fill_registration(mock_page, sample_client, "Goodwin2026!a")

    # Verifies that human_click was invoked with part_box_mock, not the outer label
    mock_human_click.assert_any_call(part_box_mock, mock_page)
    # Verifies scroll to Done was executed
    mock_human_scroll.assert_called()
    done_btn_mock.scroll_into_view_if_needed.assert_called()
    assert result.status == RegistrationStatus.SUCCESS


def test_client_resolved_title_variations():
    # Male default
    c_male = Client(
        client_id="CLI_M",
        full_name="Daniel Buckley",
        first_name="Daniel",
        last_name="Buckley",
        email="d@example.com",
        phone="07700900111",
        address_line1="1 High St",
        town_city="London",
        postcode="SW1A 1AA"
    )
    assert c_male.resolved_title == "Mr."
    assert c_male.resolved_title_clean == "Mr"

    # Female heuristic
    c_female = Client(
        client_id="CLI_F",
        full_name="Holly Shaw",
        first_name="Holly",
        last_name="Shaw",
        email="h@example.com",
        phone="07700900222",
        address_line1="2 High St",
        town_city="Derby",
        postcode="DE1 1AA"
    )
    assert c_female.resolved_title == "Mrs."
    assert c_female.resolved_title_clean == "Mrs"

    # Explicit title
    c_explicit = Client(
        client_id="CLI_E",
        full_name="Courtney Weaver",
        first_name="Courtney",
        last_name="Weaver",
        title="Miss",
        email="c@example.com",
        phone="07700900333",
        address_line1="3 High St",
        town_city="Leeds",
        postcode="LS1 1AA"
    )
    assert c_explicit.resolved_title == "Miss"
    assert c_explicit.resolved_title_clean == "Miss"

    # Full name prefix
    c_prefix = Client(
        client_id="CLI_P",
        full_name="Ms Laura Allen",
        first_name="Laura",
        last_name="Allen",
        email="l@example.com",
        phone="07700900444",
        address_line1="4 High St",
        town_city="Bristol",
        postcode="BS1 1AA"
    )
    assert c_prefix.resolved_title == "Ms."
    assert c_prefix.resolved_title_clean == "Ms"


def test_betgoodwin_title_selection_executed_with_client_title():
    adapter = BetgoodwinAdapter()
    mock_page = MagicMock()

    client_female = Client(
        client_id="CLI_BG_FEMALE",
        full_name="Sarah Mennell",
        first_name="Sarah",
        last_name="Mennell",
        email="sarah.mennell.999@gmail.com",
        phone="07700900444",
        dob="1991-04-12",
        address_line1="12 Park Lane",
        town_city="Manchester",
        postcode="M1 1AA"
    )

    eval_calls = []
    def on_evaluate(script, *args):
        eval_calls.append((script, args))
        return True
    mock_page.evaluate.side_effect = on_evaluate

    def locator_side_effect(selector):
        loc = MagicMock()
        if "error" in selector:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
        elif "Deposit" in selector or "My Account" in selector:
            loc.first.is_visible.return_value = True
        else:
            loc.first.is_visible.return_value = False
            loc.is_visible.return_value = False
        return loc
    mock_page.locator.side_effect = locator_side_effect

    with patch("sites.betgoodwin.capture_success_screenshot", return_value="success.png"):
        result = adapter.fill_registration(mock_page, client_female, "Goodwin2026!a")

    # Check that evaluate was called with 'Mrs.' for Sarah
    title_eval = [args[0] for script, args in eval_calls if "VAADIN-SELECT" in script and "Title" in script and args]
    assert len(title_eval) > 0, "Expected Title selection evaluation to be called"
    assert title_eval[0] == "Mrs.", f"Expected 'Mrs.' for female client Sarah, got {title_eval[0]}"
    assert result.status == RegistrationStatus.SUCCESS
