import pytest
from unittest.mock import MagicMock, patch
from sites.base import (
    handle_playbook_safer_gambling_no_limit,
    human_type,
    human_pause
)
from sites.bresbet import BresbetAdapter
from sites.planetsportbet import PlanetSportBetAdapter
from sites.betstgeorge import BetStGeorgeAdapter
from sites.starsports import StarSportsAdapter
from data.models import Client, RegistrationStatus


def test_handle_playbook_safer_gambling_detected_and_handled():
    mock_page = MagicMock()
    
    # Modal selector visible
    mock_modal = MagicMock()
    mock_modal.is_visible.return_value = True
    
    # No limit option
    mock_no_limit = MagicMock()
    mock_no_limit.is_visible.return_value = True
    
    # Switch
    mock_switch = MagicMock()
    mock_switch.count.return_value = 1
    mock_switch.last.is_visible.return_value = True
    
    # Next button
    mock_btn = MagicMock()
    mock_btn.is_visible.return_value = True

    def locator_side_effect(selector):
        loc = MagicMock()
        if "SAFER GAMBLING" in selector:
            loc.first = mock_modal
            return loc
        elif "No limit" in selector or "No I don't want" in selector:
            loc.first = mock_no_limit
            return loc
        elif "switch" in selector:
            return mock_switch
        elif "Next" in selector or "Save" in selector:
            loc.first = mock_btn
            return loc
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            loc.count.return_value = 0
            return loc

    mock_page.locator.side_effect = locator_side_effect
    
    handled = handle_playbook_safer_gambling_no_limit(mock_page)
    assert handled is True
    assert mock_page.wait_for_timeout.called


def test_handle_playbook_explicit_no_deposit_limit_text():
    mock_page = MagicMock()
    mock_modal = MagicMock()
    mock_modal.is_visible.return_value = True

    mock_target = MagicMock()
    mock_target.is_visible.return_value = True

    mock_btn = MagicMock()
    mock_btn.is_visible.return_value = True

    def locator_side_effect(selector):
        loc = MagicMock()
        if "No I don't want" in selector:
            loc.first = mock_target
            return loc
        elif "deposit limit" in selector or "SAFER GAMBLING" in selector:
            loc.first = mock_modal
            return loc
        elif "Save & Continue" in selector or "Next" in selector:
            loc.first = mock_btn
            return loc
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            loc.count.return_value = 0
            return loc

    mock_page.locator.side_effect = locator_side_effect
    handled = handle_playbook_safer_gambling_no_limit(mock_page)
    assert handled is True
    assert mock_target.click.called


def test_handle_playbook_safer_gambling_not_present():
    mock_page = MagicMock()
    loc = MagicMock()
    loc.is_visible.return_value = False
    loc.first.is_visible.return_value = False
    loc.count.return_value = 0
    mock_page.locator.return_value = loc

    handled = handle_playbook_safer_gambling_no_limit(mock_page)
    assert handled is False


def test_human_type_and_pause():
    mock_page = MagicMock()
    mock_loc = MagicMock()
    
    human_pause(mock_page, 0.01, 0.02)
    assert mock_page.wait_for_timeout.called
    
    # Test typing without page
    human_type(mock_loc, "TestText", page=None, min_delay_ms=1, max_delay_ms=2)
    assert mock_loc.click.called
    assert mock_loc.press_sequentially.called



def test_playbook_adapters_instantiation():
    bresbet = BresbetAdapter()
    assert bresbet.site_id == "bresbet"
    
    planetsportbet = PlanetSportBetAdapter()
    assert planetsportbet.site_id == "planetsportbet"
    
    betstgeorge = BetStGeorgeAdapter()
    assert betstgeorge.site_id == "betstgeorge"
    
    starsports = StarSportsAdapter()
    assert starsports.site_id == "starsports"


def test_starsports_onboarding_form_toggle_and_next_progression():
    """
    Specifically tests that Star Sports does NOT exit prematurely on second 4,
    physically toggles the Safer Gambling switch / box ON, and clicks the Next button
    to complete onboarding before verifying the session.
    """
    adapter = StarSportsAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://www.starsports.bet/?account=signup"

    client = Client(
        client_id="CLI_VERIFY_SS",
        full_name="Star Sports Tester",
        first_name="Star",
        last_name="Tester",
        email="starsportstester99@gmail.com",
        phone="07700900123",
        dob="1990-05-15",
        address_line1="12 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    switch_clicked = False
    next_btn_clicked = False
    modal_dismissed = False

    # Mock inputs
    mock_input = MagicMock()
    mock_input.is_visible.return_value = True

    mock_btn = MagicMock()
    mock_btn.is_visible.return_value = True

    mock_switch = MagicMock()
    mock_switch.count.return_value = 1
    mock_switch_nth = MagicMock()
    mock_switch_nth.is_visible.return_value = True
    mock_switch_nth.get_attribute.return_value = "false"
    
    def on_switch_click(*args, **kwargs):
        nonlocal switch_clicked
        switch_clicked = True
    mock_switch_nth.click.side_effect = on_switch_click
    mock_switch.nth.return_value = mock_switch_nth

    mock_next_btn = MagicMock()
    mock_next_btn.is_visible.return_value = True
    def on_next_click(*args, **kwargs):
        nonlocal next_btn_clicked, modal_dismissed
        next_btn_clicked = True
        modal_dismissed = True
    mock_next_btn.click.side_effect = on_next_click

    mock_auth = MagicMock()
    mock_auth.is_visible.return_value = True

    mock_container = MagicMock()
    def container_visible(*args, **kwargs):
        return not modal_dismissed
    mock_container.is_visible.side_effect = container_visible

    mock_addr_item = MagicMock()
    mock_addr_item.is_visible.return_value = True
    mock_addr_item.count.return_value = 1
    mock_addr_item.first = mock_addr_item
    mock_addr_item.inner_text.return_value = "12 High Street, London"

    def locator_dispatcher(selector):
        loc = MagicMock()
        if "error" in selector.lower():
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            return loc
        elif "SignUpStepsContainer" in selector or "SAFER GAMBLING" in selector:
            loc.first = mock_container
            loc.is_visible = container_visible
            return loc
        elif "switch" in selector or "Switch" in selector:
            return mock_switch
        elif "next" in selector.lower() or "Save" in selector or "Next" in selector:
            loc.first = mock_next_btn
            loc.is_visible.return_value = True
            return loc
        elif "DEPOSIT" in selector or "Deposit" in selector or "My Account" in selector:
            loc.first = mock_auth
            loc.is_visible.return_value = True
            return loc
        elif "AddressesListItemWrapper" in selector:
            return mock_addr_item
        elif "input" in selector or "box" in selector:
            loc.first = mock_input
            loc.is_visible.return_value = True
            return loc
        elif "button" in selector or "link" in selector:
            loc.first = mock_btn
            loc.is_visible.return_value = True
            return loc
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            loc.count.return_value = 0
            return loc

    mock_page.locator.side_effect = locator_dispatcher

    with patch("sites.starsports.human_pause"), \
         patch("sites.starsports.human_type"), \
         patch("sites.starsports.capture_login_proof_screenshot", return_value="proof.png"), \
         patch("sites.starsports.capture_success_screenshot", return_value="success.png"):
        result = adapter.fill_registration(mock_page, client, "StrongPass123!@")

    assert switch_clicked is True, "Expected Safer Gambling switch box to be toggled ON"
    assert next_btn_clicked is True, "Expected Next progression button to be clicked"
    assert result.status == RegistrationStatus.SUCCESS
    assert result.login_verified is True
    assert "Active Session Verified" in result.account_reference


def test_planetsportbet_onboarding_form_toggle_and_next_progression():
    """
    Specifically tests that Planet Sport Bet toggles the Safer Gambling switch / box ON,
    and clicks Next to complete onboarding before verifying the session.
    """
    adapter = PlanetSportBetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://planetsportbet.com/?account=signup"

    client = Client(
        client_id="CLI_VERIFY_PSB",
        full_name="Planet Tester",
        first_name="Planet",
        last_name="Tester",
        email="planettester99@gmail.com",
        phone="07700900123",
        dob="1990-05-15",
        address_line1="12 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    switch_clicked = False
    next_btn_clicked = False
    modal_dismissed = False

    mock_input = MagicMock()
    mock_input.is_visible.return_value = True

    mock_btn = MagicMock()
    mock_btn.is_visible.return_value = True

    mock_switch = MagicMock()
    mock_switch.count.return_value = 1
    mock_switch_nth = MagicMock()
    mock_switch_nth.is_visible.return_value = True
    mock_switch_nth.get_attribute.return_value = "false"
    
    def on_switch_click(*args, **kwargs):
        nonlocal switch_clicked
        switch_clicked = True
    mock_switch_nth.click.side_effect = on_switch_click
    mock_switch.nth.return_value = mock_switch_nth

    mock_next_btn = MagicMock()
    mock_next_btn.is_visible.return_value = True
    def on_next_click(*args, **kwargs):
        nonlocal next_btn_clicked, modal_dismissed
        next_btn_clicked = True
        modal_dismissed = True
    mock_next_btn.click.side_effect = on_next_click

    mock_auth = MagicMock()
    mock_auth.is_visible.return_value = True

    mock_container = MagicMock()
    def container_visible(*args, **kwargs):
        return not modal_dismissed
    mock_container.is_visible.side_effect = container_visible

    mock_addr_item = MagicMock()
    mock_addr_item.is_visible.return_value = True
    mock_addr_item.count.return_value = 1
    mock_addr_item.first = mock_addr_item
    mock_addr_item.inner_text.return_value = "12 High Street, London"

    def locator_dispatcher(selector):
        loc = MagicMock()
        if "error" in selector.lower():
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            return loc
        elif "SignUpStepsContainer" in selector or "SAFER GAMBLING" in selector:
            loc.first = mock_container
            loc.is_visible = container_visible
            return loc
        elif "switch" in selector or "Switch" in selector:
            return mock_switch
        elif "next" in selector.lower() or "Save" in selector or "Next" in selector:
            loc.first = mock_next_btn
            loc.is_visible.return_value = True
            return loc
        elif "DEPOSIT" in selector or "Deposit" in selector or "My Account" in selector:
            loc.first = mock_auth
            loc.is_visible.return_value = True
            return loc
        elif "AddressesListItemWrapper" in selector:
            return mock_addr_item
        elif "input" in selector or "box" in selector:
            loc.first = mock_input
            loc.is_visible.return_value = True
            return loc
        elif "button" in selector or "link" in selector:
            loc.first = mock_btn
            loc.is_visible.return_value = True
            return loc
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            loc.count.return_value = 0
            return loc

    mock_page.locator.side_effect = locator_dispatcher

    with patch("sites.planetsportbet.human_pause"), \
         patch("sites.planetsportbet.human_type"), \
         patch("sites.planetsportbet.capture_login_proof_screenshot", return_value="proof.png"), \
         patch("sites.planetsportbet.capture_success_screenshot", return_value="success.png"):
        result = adapter.fill_registration(mock_page, client, "StrongPass123!@")

    assert switch_clicked is True, "Expected Safer Gambling switch box to be toggled ON on Planet Sport Bet"
    assert next_btn_clicked is True, "Expected Next progression button to be clicked on Planet Sport Bet"
    assert result.status == RegistrationStatus.SUCCESS
    assert result.login_verified is True
    assert "Active Session Verified" in result.account_reference


def test_bresbet_onboarding_form_toggle_and_next_progression():
    """
    Specifically tests that BresBet toggles the Safer Gambling switch / box ON,
    and clicks Next to complete onboarding before verifying the session.
    """
    adapter = BresbetAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://bresbet.com/?account=signup"

    client = Client(
        client_id="CLI_VERIFY_BB",
        full_name="Bres Tester",
        first_name="Bres",
        last_name="Tester",
        email="brestester99@gmail.com",
        phone="07700900123",
        dob="1990-05-15",
        address_line1="12 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    switch_clicked = False
    next_btn_clicked = False
    modal_dismissed = False

    mock_input = MagicMock()
    mock_input.is_visible.return_value = True

    mock_btn = MagicMock()
    mock_btn.is_visible.return_value = True

    mock_switch = MagicMock()
    mock_switch.count.return_value = 1
    mock_switch_nth = MagicMock()
    mock_switch_nth.is_visible.return_value = True
    mock_switch_nth.get_attribute.return_value = "false"
    
    def on_switch_click(*args, **kwargs):
        nonlocal switch_clicked
        switch_clicked = True
    mock_switch_nth.click.side_effect = on_switch_click
    mock_switch.nth.return_value = mock_switch_nth

    mock_next_btn = MagicMock()
    mock_next_btn.is_visible.return_value = True
    def on_next_click(*args, **kwargs):
        nonlocal next_btn_clicked, modal_dismissed
        next_btn_clicked = True
        modal_dismissed = True
    mock_next_btn.click.side_effect = on_next_click

    mock_auth = MagicMock()
    mock_auth.is_visible.return_value = True

    mock_container = MagicMock()
    def container_visible(*args, **kwargs):
        return not modal_dismissed
    mock_container.is_visible.side_effect = container_visible

    mock_addr_item = MagicMock()
    mock_addr_item.is_visible.return_value = True
    mock_addr_item.count.return_value = 1
    mock_addr_item.first = mock_addr_item
    mock_addr_item.inner_text.return_value = "12 High Street, London"

    def locator_dispatcher(selector):
        loc = MagicMock()
        if "error" in selector.lower():
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            return loc
        elif "SignUpStepsContainer" in selector or "SAFER GAMBLING" in selector:
            loc.first = mock_container
            loc.is_visible = container_visible
            return loc
        elif "switch" in selector or "Switch" in selector:
            return mock_switch
        elif "next" in selector.lower() or "Save" in selector or "Next" in selector:
            loc.first = mock_next_btn
            loc.is_visible.return_value = True
            return loc
        elif "DEPOSIT" in selector or "Deposit" in selector or "My Account" in selector:
            loc.first = mock_auth
            loc.is_visible.return_value = True
            return loc
        elif "AddressesListItemWrapper" in selector:
            return mock_addr_item
        elif "input" in selector or "box" in selector:
            loc.first = mock_input
            loc.is_visible.return_value = True
            return loc
        elif "button" in selector or "link" in selector:
            loc.first = mock_btn
            loc.is_visible.return_value = True
            return loc
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            loc.count.return_value = 0
            return loc

    mock_page.locator.side_effect = locator_dispatcher

    with patch("sites.bresbet.human_pause"), \
         patch("sites.bresbet.human_type"), \
         patch("sites.bresbet.capture_login_proof_screenshot", return_value="proof.png"), \
         patch("sites.bresbet.capture_success_screenshot", return_value="success.png"):
        result = adapter.fill_registration(mock_page, client, "StrongPass123!@")

    assert switch_clicked is True, "Expected Safer Gambling switch box to be toggled ON on BresBet"
    assert next_btn_clicked is True, "Expected Next progression button to be clicked on BresBet"
    assert result.status == RegistrationStatus.SUCCESS
    assert result.login_verified is True
    assert "Active Session Verified" in result.account_reference


def test_betstgeorge_onboarding_form_toggle_and_next_progression():
    """
    Specifically tests that Bet St George toggles the Safer Gambling switch / box ON,
    and clicks Next to complete onboarding before verifying the session.
    """
    adapter = BetStGeorgeAdapter()
    mock_page = MagicMock()
    mock_page.url = "https://betstgeorge.com/?promo=signup"

    client = Client(
        client_id="CLI_VERIFY_BSG",
        full_name="George Tester",
        first_name="George",
        last_name="Tester",
        email="georgetester99@gmail.com",
        phone="07700900123",
        dob="1990-05-15",
        address_line1="12 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )

    switch_clicked = False
    next_btn_clicked = False
    modal_dismissed = False

    mock_input = MagicMock()
    mock_input.is_visible.return_value = True

    mock_btn = MagicMock()
    mock_btn.is_visible.return_value = True

    mock_switch = MagicMock()
    mock_switch.count.return_value = 1
    mock_switch_nth = MagicMock()
    mock_switch_nth.is_visible.return_value = True
    mock_switch_nth.get_attribute.return_value = "false"
    
    def on_switch_click(*args, **kwargs):
        nonlocal switch_clicked
        switch_clicked = True
    mock_switch_nth.click.side_effect = on_switch_click
    mock_switch.nth.return_value = mock_switch_nth

    mock_next_btn = MagicMock()
    mock_next_btn.is_visible.return_value = True
    def on_next_click(*args, **kwargs):
        nonlocal next_btn_clicked, modal_dismissed
        next_btn_clicked = True
        modal_dismissed = True
    mock_next_btn.click.side_effect = on_next_click

    mock_auth = MagicMock()
    mock_auth.is_visible.return_value = True

    mock_container = MagicMock()
    def container_visible(*args, **kwargs):
        return not modal_dismissed
    mock_container.is_visible.side_effect = container_visible

    mock_addr_item = MagicMock()
    mock_addr_item.is_visible.return_value = True
    mock_addr_item.count.return_value = 1
    mock_addr_item.first = mock_addr_item
    mock_addr_item.inner_text.return_value = "12 High Street, London"

    def locator_dispatcher(selector):
        loc = MagicMock()
        if "error" in selector.lower():
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            return loc
        elif "SignUpStepsContainer" in selector or "SAFER GAMBLING" in selector:
            loc.first = mock_container
            loc.is_visible = container_visible
            return loc
        elif "switch" in selector or "Switch" in selector:
            return mock_switch
        elif "next" in selector.lower() or "Save" in selector or "Next" in selector:
            loc.first = mock_next_btn
            loc.is_visible.return_value = True
            return loc
        elif "DEPOSIT" in selector or "Deposit" in selector or "My Account" in selector:
            loc.first = mock_auth
            loc.is_visible.return_value = True
            return loc
        elif "AddressesListItemWrapper" in selector:
            return mock_addr_item
        elif "input" in selector or "box" in selector:
            loc.first = mock_input
            loc.is_visible.return_value = True
            return loc
        elif "button" in selector or "link" in selector:
            loc.first = mock_btn
            loc.is_visible.return_value = True
            return loc
        else:
            loc.is_visible.return_value = False
            loc.first.is_visible.return_value = False
            loc.count.return_value = 0
            return loc

    mock_page.locator.side_effect = locator_dispatcher

    with patch("sites.betstgeorge.human_pause"), \
         patch("sites.betstgeorge.human_type"), \
         patch("sites.betstgeorge.capture_login_proof_screenshot", return_value="proof.png"), \
         patch("sites.betstgeorge.capture_success_screenshot", return_value="success.png"):
        result = adapter.fill_registration(mock_page, client, "StrongPass123!@")

    assert switch_clicked is True, "Expected Safer Gambling switch box to be toggled ON on Bet St George"
    assert next_btn_clicked is True, "Expected Next progression button to be clicked on Bet St George"
    assert result.status == RegistrationStatus.SUCCESS
    assert result.login_verified is True
    assert "Active Session Verified" in result.account_reference

