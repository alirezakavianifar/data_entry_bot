import tempfile
import os
from pathlib import Path
from core.state import StateManager
from data.models import RegistrationStatus, RegistrationResult


def test_state_manager_lifecycle():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # Close the OS file descriptor immediately
    db_path = Path(path)

    try:
        mgr = StateManager(db_path=db_path)
        assert mgr.get_status("CLI_001", "fairplaybet") == RegistrationStatus.PENDING
        assert mgr.is_complete("CLI_001", "fairplaybet") is False

        # Set status to IN_PROGRESS
        mgr.set_status("CLI_001", "fairplaybet", RegistrationStatus.IN_PROGRESS)
        assert mgr.get_status("CLI_001", "fairplaybet") == RegistrationStatus.IN_PROGRESS

        # Set status to SUCCESS
        res = RegistrationResult(
            client_id="CLI_001",
            client_name="Test User",
            site_id="fairplaybet",
            site_name="Fairplay Bet",
            status=RegistrationStatus.SUCCESS,
            email="test@example.com",
            password="SecurePass99#!"
        )
        mgr.record_result(res)
        assert mgr.get_status("CLI_001", "fairplaybet") == RegistrationStatus.SUCCESS
        assert mgr.is_complete("CLI_001", "fairplaybet") is True

        # Summary count
        summary = mgr.get_summary()
        assert summary[RegistrationStatus.SUCCESS.value] == 1

        # Test login verification update (Success)
        mgr.update_login_verification(
            client_id="CLI_001",
            site_id="fairplaybet",
            success=True,
            screenshot_path="/path/to/LOGIN_PROOF.png"
        )
        rec = mgr.get_record("CLI_001", "fairplaybet")
        assert rec is not None
        assert rec["login_verified"] == 1
        assert rec["login_screenshot_path"] == "/path/to/LOGIN_PROOF.png"
        assert rec["status"] == "SUCCESS"

        # Test login verification update (Pending Email / KYC Verification)
        mgr.update_login_verification(
            client_id="CLI_001",
            site_id="fairplaybet",
            success=False,
            screenshot_path="/path/to/PENDING_PROOF.png",
            error_summary="Pending Email Verification: Activation link sent",
            is_pending_verification=True
        )
        rec = mgr.get_record("CLI_001", "fairplaybet")
        assert rec["status"] == "SUCCESS"  # Status must remain SUCCESS
        assert rec["login_verified"] == 0
        assert rec["error_summary"] == "Pending Email Verification: Activation link sent"

        # Test is_processed
        assert mgr.is_processed("CLI_001", "fairplaybet") is True
        assert mgr.is_processed("CLI_002", "fairplaybet") is False

        # Set CLI_002 to FAILED
        mgr.set_status("CLI_002", "fairplaybet", RegistrationStatus.FAILED, error_summary="Bad address")
        assert mgr.is_complete("CLI_002", "fairplaybet") is False
        assert mgr.is_processed("CLI_002", "fairplaybet", include_failed=True) is True
        assert mgr.is_processed("CLI_002", "fairplaybet", include_failed=False) is False

        # Test has_pending_sites
        assert mgr.has_pending_sites("CLI_001", ["fairplaybet"], retry_failed=False) is False
        assert mgr.has_pending_sites("CLI_002", ["fairplaybet"], retry_failed=False) is False
        assert mgr.has_pending_sites("CLI_002", ["fairplaybet"], retry_failed=True) is True
        assert mgr.has_pending_sites("CLI_003", ["fairplaybet"], retry_failed=False) is True

        # Test reset_all_failed
        deleted = mgr.reset_all_failed()
        assert deleted == 1
        assert mgr.get_status("CLI_002", "fairplaybet") == RegistrationStatus.PENDING

    finally:
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

