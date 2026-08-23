import pytest
from unittest.mock import MagicMock
from sites.base import is_already_registered_error, extract_clean_error_message
from sites.betfred import BetfredAdapter
from data.models import Client, RegistrationStatus


def test_betfred_already_registered_pattern():
    raw_msg = "It looks like you already have an account set up with this email address. Log In to your account."
    assert is_already_registered_error(raw_msg) is True
    clean = extract_clean_error_message(raw_msg)
    assert "looks like you already have an account" in clean.lower()


def test_betfred_step1_duplicate_email_mock():
    adapter = BetfredAdapter()
    client = Client(
        client_id="CLI_004",
        full_name="Lau Allen",
        first_name="Lau",
        last_name="Allen",
        email="lauallen76@gmail.com",
        phone="07700900077",
        dob="1995-06-15",
        address_line1="10 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    page = MagicMock()
    page.url = "https://www.betfred.com/registration"
    page.is_closed.return_value = False
    page.content.return_value = "<html><body>It looks like you already have an account set up with this email address.</body></html>"
    page.screenshot.return_value = b"screenshot"

    step1_err = MagicMock()
    step1_err.first = step1_err
    step1_err.is_visible.return_value = True
    step1_err.inner_text.return_value = "It looks like you already have an account set up with this email address. Log In to your account."

    generic_visible = MagicMock()
    generic_visible.first = generic_visible
    generic_visible.is_visible.return_value = True

    def locator_side_effect(selector):
        if "error" in selector or "already have an account" in selector:
            return step1_err
        elif any(k in selector for k in ("unavailable in your location", "Network Error", "previous operation was unsuccessful", "Alert")):
            m = MagicMock()
            m.first = m
            m.is_visible.return_value = False
            return m
        return generic_visible

    page.locator.side_effect = locator_side_effect

    res = adapter.fill_registration(page, client, "StrongPass123!@")
    assert res.status == RegistrationStatus.ALREADY_REGISTERED
    assert "Already registered" in res.error_summary
    assert "looks like you already have an account" in res.error_summary.lower()


def test_betfred_network_error_retry_recovery():
    adapter = BetfredAdapter()
    client = Client(
        client_id="CLI_005",
        full_name="Kiran Bokil",
        first_name="Kiran",
        last_name="Bokil",
        email="kiran.bokil.new@gmail.com",
        phone="07700900077",
        dob="1979-03-07",
        address_line1="10 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    page = MagicMock()
    page.url = "https://www.betfred.com/registration"
    page.is_closed.return_value = False
    page.content.return_value = "<html><body>Betfred Registration</body></html>"
    page.screenshot.return_value = b"screenshot"

    attempts = {"count": 0}

    def fn_inp_visible(timeout=0):
        # On attempt 1, simulate network error. On attempt 2, Step 2 appears.
        return attempts["count"] >= 2

    def net_err_visible(timeout=0):
        return attempts["count"] < 2

    cont1_btn = MagicMock()
    cont1_btn.first = cont1_btn
    cont1_btn.is_visible.return_value = True
    def cont1_click(**kwargs):
        attempts["count"] += 1
    cont1_btn.click.side_effect = cont1_click

    fn_inp = MagicMock()
    fn_inp.first = fn_inp
    fn_inp.is_visible.side_effect = fn_inp_visible

    net_err = MagicMock()
    net_err.first = net_err
    net_err.is_visible.side_effect = net_err_visible

    generic_visible = MagicMock()
    generic_visible.first = generic_visible
    generic_visible.is_visible.return_value = True

    def locator_side_effect(selector):
        if "PersonalSection.first_name" in selector or "firstName" in selector:
            return fn_inp
        elif "NavigationButtonsPage1.Continue" in selector:
            return cont1_btn
        elif "Network Error" in selector or "previous operation was unsuccessful" in selector:
            return net_err
        elif any(k in selector for k in ("unavailable in your location", "error", "already have an account")):
            m = MagicMock()
            m.first = m
            m.is_visible.return_value = False
            return m
        return generic_visible

    page.locator.side_effect = locator_side_effect

    res = adapter.fill_registration(page, client, "StrongPass123!@")
    # Verify retry happened (attempt count >= 2)
    assert attempts["count"] >= 2
    assert res.status == RegistrationStatus.SUCCESS


def test_betfred_step3_security_question_mock():
    adapter = BetfredAdapter()
    client = Client(
        client_id="CLI_003",
        full_name="Alexander Miller",
        first_name="Alexander",
        last_name="Miller",
        email="alexander.miller.bf123@gmail.com",
        phone="07700900077",
        dob="1995-06-15",
        address_line1="10 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    page = MagicMock()
    page.url = "https://www.betfred.com/registration"
    page.is_closed.return_value = False
    page.content.return_value = "<html><body>Betfred Registration</body></html>"
    page.screenshot.return_value = b"screenshot"

    # Locators
    area_code_select = MagicMock()
    area_code_select.first = area_code_select
    area_code_select.is_visible.return_value = True

    sq_select = MagicMock()
    sq_select.first = sq_select
    sq_select.is_visible.return_value = True

    ans_inp = MagicMock()
    ans_inp.first = ans_inp
    ans_inp.is_visible.return_value = True

    generic_visible = MagicMock()
    generic_visible.first = generic_visible
    generic_visible.is_visible.return_value = True

    def locator_side_effect(selector):
        if "securityQuestion" in selector or "Dropdown.securityQuestion" in selector:
            return sq_select
        elif "security_answer" in selector:
            return ans_inp
        elif "area_code" in selector:
            return area_code_select
        elif any(k in selector for k in ("unavailable in your location", "Network Error", "previous operation was unsuccessful", "Alert", "error", "already have an account")):
            m = MagicMock()
            m.first = m
            m.is_visible.return_value = False
            return m
        return generic_visible

    page.locator.side_effect = locator_side_effect

    res = adapter.fill_registration(page, client, "StrongPass123!@")
    sq_select.select_option.assert_called_once()
    ans_inp.fill.assert_called_with("London")


def test_betfred_self_exclusion_already_registered_mock():
    adapter = BetfredAdapter()
    client = Client(
        client_id="CLI_006",
        full_name="Edward Davies",
        first_name="Edward",
        last_name="Davies",
        email="edward.davies.test@gmail.com",
        phone="07700900077",
        dob="1985-08-20",
        address_line1="10 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    page = MagicMock()
    page.url = "https://www.betfred.com/registration"
    page.is_closed.return_value = False
    page.screenshot.return_value = b"screenshot"

    raw_msg = (
        "Already registered? "
        "You're unable to register due to an active Self-Exclusion agreement in place on your account. "
        "If you believe this to be incorrect, please Contact Us."
    )
    assert is_already_registered_error(raw_msg) is True
    clean = extract_clean_error_message(raw_msg)
    assert "self-exclusion" in clean.lower() or "unable to register" in clean.lower()

    # Locator mocks
    body_mock = MagicMock()
    body_mock.inner_text.return_value = raw_msg

    generic_visible = MagicMock()
    generic_visible.first = generic_visible
    generic_visible.is_visible.return_value = True

    def locator_side_effect(selector):
        if selector == "body":
            return body_mock
        elif any(k in selector for k in ("unavailable in your location", "Network Error", "error")):
            m = MagicMock()
            m.first = m
            m.is_visible.return_value = False
            return m
        return generic_visible

    page.locator.side_effect = locator_side_effect

    res = adapter.fill_registration(page, client, "StrongPass123!@")
    assert res.status == RegistrationStatus.ALREADY_REGISTERED
    assert "Already registered" in res.error_summary
