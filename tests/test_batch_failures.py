import pytest
import sqlite3
from pathlib import Path
from core.state import StateManager
from data.models import RegistrationStatus, RegistrationResult


def test_state_manager_reset_records(tmp_path: Path):
    db_file = tmp_path / "test_state.db"
    mgr = StateManager(db_path=db_file)

    # Insert several records
    mgr.set_status("CLI_001", "fairplaybet", RegistrationStatus.FAILED, client_name="Alice", site_name="FairPlay", error_summary="Timeout")
    mgr.set_status("CLI_002", "bresbet", RegistrationStatus.FAILED, client_name="Bob", site_name="BresBet", error_summary="Selector error")
    mgr.set_status("CLI_003", "betgoodwin", RegistrationStatus.MANUAL_REVIEW, client_name="Charlie", site_name="BetGoodwin", error_summary="KYC required")
    mgr.set_status("CLI_004", "fairplaybet", RegistrationStatus.SUCCESS, client_name="David", site_name="FairPlay", email="david@test.com")

    all_recs = mgr.get_all_records()
    assert len(all_recs) == 4

    # Batch reset empty list
    assert mgr.reset_records([]) == 0

    # Batch reset CLI_001 on fairplaybet and CLI_003 on betgoodwin
    deleted = mgr.reset_records([("CLI_001", "fairplaybet"), ("CLI_003", "betgoodwin")])
    assert deleted == 2

    # Verify CLI_001 and CLI_003 are removed (reset to PENDING)
    assert mgr.get_status("CLI_001", "fairplaybet") == RegistrationStatus.PENDING
    assert mgr.get_status("CLI_003", "betgoodwin") == RegistrationStatus.PENDING

    # Verify CLI_002 and CLI_004 remain intact
    assert mgr.get_status("CLI_002", "bresbet") == RegistrationStatus.FAILED
    assert mgr.get_status("CLI_004", "fairplaybet") == RegistrationStatus.SUCCESS

    remaining = mgr.get_all_records()
    assert len(remaining) == 2
    assert {r["client_id"] for r in remaining} == {"CLI_002", "CLI_004"}


def test_batch_failure_filtering_and_selection(tmp_path: Path):
    db_file = tmp_path / "test_state_filter.db"
    mgr = StateManager(db_path=db_file)

    mgr.set_status("CLI_A", "fairplaybet", RegistrationStatus.FAILED, client_name="User A", site_name="FairPlay")
    mgr.set_status("CLI_B", "bresbet", RegistrationStatus.MANUAL_REVIEW, client_name="User B", site_name="BresBet")
    mgr.set_status("CLI_C", "betgoodwin", RegistrationStatus.SUCCESS, client_name="User C", site_name="BetGoodwin")

    all_recs = mgr.get_all_records()
    fails = [r for r in all_recs if r.get("status") in ("FAILED", "MANUAL_REVIEW")]
    assert len(fails) == 2

    # Simulate batch dismiss of all fails
    keys_to_dismiss = [(r["client_id"], r["site_id"]) for r in fails]
    deleted = mgr.reset_records(keys_to_dismiss)
    assert deleted == 2

    remaining_fails = [r for r in mgr.get_all_records() if r.get("status") in ("FAILED", "MANUAL_REVIEW")]
    assert len(remaining_fails) == 0

    # Success record is unaffected
    assert mgr.get_status("CLI_C", "betgoodwin") == RegistrationStatus.SUCCESS


def test_failure_site_specific_search_and_batch_selection(tmp_path: Path):
    db_file = tmp_path / "test_site_filter.db"
    mgr = StateManager(db_path=db_file)

    # 3 failures on BresBet, 2 failures on FairPlayBet, 1 on BetGoodwin
    mgr.set_status("CLI_1", "bresbet", RegistrationStatus.FAILED, client_name="Leoni Samuda", site_name="BresBet", error_summary="EXECUTION_ERROR Step: fill_reg")
    mgr.set_status("CLI_2", "bresbet", RegistrationStatus.FAILED, client_name="Daniel Buckley", site_name="BresBet", error_summary="SELECTOR_TIMEOUT")
    mgr.set_status("CLI_3", "bresbet", RegistrationStatus.MANUAL_REVIEW, client_name="Chloe Adams", site_name="BresBet", error_summary="KYC verification pending")
    mgr.set_status("CLI_4", "fairplaybet", RegistrationStatus.FAILED, client_name="George Smith", site_name="FairPlayBet", error_summary="Connection reset")
    mgr.set_status("CLI_5", "fairplaybet", RegistrationStatus.FAILED, client_name="Emily Davis", site_name="FairPlayBet", error_summary="Timeout")
    mgr.set_status("CLI_6", "betgoodwin", RegistrationStatus.FAILED, client_name="Daniel Buckley", site_name="Betgoodwin", error_summary="Login verification failed")

    all_fails = [r for r in mgr.get_all_records() if r.get("status") in ("FAILED", "MANUAL_REVIEW")]
    assert len(all_fails) == 6

    # 1. Test filtering by specific site dropdown ("BresBet")
    bresbet_fails = [r for r in all_fails if (r.get("site_name") or "").lower() == "bresbet"]
    assert len(bresbet_fails) == 3

    # Dismiss only BresBet failures
    keys = [(r["client_id"], r["site_id"]) for r in bresbet_fails]
    deleted = mgr.reset_records(keys)
    assert deleted == 3

    # Verify BresBet failures are reset to PENDING
    assert mgr.get_status("CLI_1", "bresbet") == RegistrationStatus.PENDING
    assert mgr.get_status("CLI_2", "bresbet") == RegistrationStatus.PENDING
    assert mgr.get_status("CLI_3", "bresbet") == RegistrationStatus.PENDING

    # Verify FairPlayBet and BetGoodwin failures are still intact
    remaining = [r for r in mgr.get_all_records() if r.get("status") in ("FAILED", "MANUAL_REVIEW")]
    assert len(remaining) == 3
    assert {r["client_id"] for r in remaining} == {"CLI_4", "CLI_5", "CLI_6"}

    # 2. Test search query filtering by client name ("Daniel")
    daniel_fails = [r for r in remaining if "daniel" in (r.get("client_name") or "").lower()]
    assert len(daniel_fails) == 1
    assert daniel_fails[0]["client_id"] == "CLI_6"

