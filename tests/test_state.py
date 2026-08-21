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

    finally:
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass
