import datetime
import threading
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from core.engine import AutomationEngine
from core.state import StateManager
from data.models import Client, RegistrationResult, RegistrationStatus
from data.base_provider import BaseDataProvider
from gui.main_gui import DataEntryBotGUI


class MockDataProvider(BaseDataProvider):
    def __init__(self, clients):
        self.clients = clients
        self.successes = []
        self.failures = []

    def get_all_clients(self):
        return self.clients

    def get_valid_clients(self):
        return self.clients

    def record_success(self, result: RegistrationResult):
        self.successes.append(result)
        return True

    def record_failure(self, result: RegistrationResult):
        self.failures.append(result)
        return True

    def remove_success(self, client_name: str, site_name: str, email: str = ""):
        self.successes = [s for s in self.successes if s.client_name != client_name or s.site_name != site_name]
        return 1


def make_client(client_id: str, name: str, email: str):
    parts = name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else "Smith"
    return Client(
        client_id=client_id,
        full_name=name,
        first_name=first_name,
        last_name=last_name,
        dob=datetime.date(1992, 5, 15),
        email=email,
        phone="07123456789",
        address_line1="1 High Street",
        town_city="London",
        postcode="SW1A 1AA"
    )


def test_state_manager_reset_in_progress(tmp_path):
    db_path = tmp_path / "test_state.db"
    state_mgr = StateManager(db_path=db_path)

    # Set some in-progress and completed records
    state_mgr.set_status("C1", "site1", RegistrationStatus.IN_PROGRESS, client_name="Alice")
    state_mgr.set_status("C2", "site1", RegistrationStatus.IN_PROGRESS, client_name="Bob")
    state_mgr.set_status("C3", "site1", RegistrationStatus.SUCCESS, client_name="Charlie")

    assert state_mgr.get_status("C1", "site1") == RegistrationStatus.IN_PROGRESS
    assert state_mgr.get_status("C2", "site1") == RegistrationStatus.IN_PROGRESS
    assert state_mgr.get_status("C3", "site1") == RegistrationStatus.SUCCESS

    # Reset single in-progress record
    deleted = state_mgr.reset_in_progress(client_id="C1", site_id="site1")
    assert deleted == 1
    assert state_mgr.get_status("C1", "site1") == RegistrationStatus.PENDING

    # Reset all remaining in-progress records
    deleted_all = state_mgr.reset_in_progress()
    assert deleted_all == 1
    assert state_mgr.get_status("C2", "site1") == RegistrationStatus.PENDING
    assert state_mgr.get_status("C3", "site1") == RegistrationStatus.SUCCESS


def test_engine_stop_dry_run(tmp_path):
    clients = [
        make_client("C1", "Alice Smith", "alice@test.com"),
        make_client("C2", "Bob Jones", "bob@test.com"),
        make_client("C3", "Charlie Brown", "charlie@test.com"),
    ]
    provider = MockDataProvider(clients)
    state_mgr = StateManager(db_path=tmp_path / "test_engine_state.db")
    stop_event = threading.Event()

    engine = AutomationEngine(provider=provider, state_mgr=state_mgr, stop_event=stop_event)
    
    # Request stop before running
    engine.request_stop()
    assert engine.is_stop_requested() is True

    result = engine.run(dry_run=True)
    assert result["status"] == "stopped"


def test_engine_stop_during_batch_execution(tmp_path):
    clients = [
        make_client("C1", "Alice Smith", "alice@test.com"),
        make_client("C2", "Bob Jones", "bob@test.com"),
    ]
    provider = MockDataProvider(clients)
    state_mgr = StateManager(db_path=tmp_path / "test_engine_state2.db")
    browser_mgr = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    browser_mgr.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    mock_adapter1 = MagicMock()
    mock_adapter1.site_id = "site1"
    mock_adapter1.site_name = "Site One"
    
    stop_event = threading.Event()

    # When first client executes, signal stop
    def fake_execute(page, client, password):
        stop_event.set()
        return RegistrationResult(
            client_id=client.client_id,
            client_name=client.full_name,
            site_id="site1",
            site_name="Site One",
            status=RegistrationStatus.SUCCESS,
            email=client.email
        )

    mock_adapter1.execute.side_effect = fake_execute

    engine = AutomationEngine(
        provider=provider,
        state_mgr=state_mgr,
        browser_mgr=browser_mgr,
        site_adapters=[mock_adapter1],
        stop_event=stop_event
    )

    res = engine.run(dry_run=False, verify_login=False)

    assert res["status"] == "stopped"
    # First client was processed before stop signal
    assert res["stats"]["processed_clients"] == 1
    # Second client C2 was skipped due to stop!
    assert state_mgr.get_status("C1", "site1") == RegistrationStatus.SUCCESS
    assert state_mgr.get_status("C2", "site1") == RegistrationStatus.PENDING


def test_gui_stop_action(tmp_path):
    try:
        with patch.object(DataEntryBotGUI, "_maximize_window"), \
             patch.object(DataEntryBotGUI, "_poll_log_queue"), \
             patch.object(DataEntryBotGUI, "_populate_registered_accounts"), \
             patch.object(DataEntryBotGUI, "_populate_failures"):
            app = DataEntryBotGUI()
            try:
                assert app.is_running is False
                assert app.stop_requested is False
                assert app.stop_event.is_set() is False

                # Simulate running task state
                app.is_running = True
                mock_engine = MagicMock()
                app.current_engine = mock_engine

                # Click Stop
                app._stop_automation()

                assert app.stop_requested is True
                assert app.stop_event.is_set() is True
                mock_engine.request_stop.assert_called_once()
                assert "STOPPING" in app.status_badge.cget("text")

                # Simulate task finished callback
                app._on_task_finished()
                assert app.is_running is False
                assert "STOPPED" in app.status_badge.cget("text")
                assert app.stop_requested is False
                assert app.btn_start.cget("state") == "normal"
                assert app.btn_stop.cget("state") == "disabled"
            finally:
                try:
                    app.destroy()
                except Exception:
                    pass
    except Exception as e:
        if "TclError" in type(e).__name__ or "tcl_findLibrary" in str(e):
            pytest.skip(f"Skipping GUI Tk instantiation due to environment Tcl interpreter lock: {e}")
        raise
