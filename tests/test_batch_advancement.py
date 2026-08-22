import tempfile
import os
from pathlib import Path
from typing import List
from data.base_provider import BaseDataProvider
from data.models import Client, RegistrationResult, RegistrationStatus
from core.state import StateManager
from core.engine import AutomationEngine


class MockDataProvider(BaseDataProvider):
    def __init__(self, clients: List[Client]):
        self.clients = clients
        self.successes = []
        self.failures = []

    def get_all_clients(self) -> List[Client]:
        return self.clients

    def record_success(self, result: RegistrationResult) -> bool:
        self.successes.append(result)
        return True

    def record_failure(self, result: RegistrationResult) -> bool:
        self.failures.append(result)
        return True

    def remove_success(self, client_name: str, site_name: str, email: str = "") -> int:
        return 0


def test_batch_advancement_and_failed_skipping():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_path = Path(path)

    try:
        state_mgr = StateManager(db_path=db_path)

        # Create 5 sample clients
        clients = [
            Client(
                client_id=f"CLI_{i:03d}",
                full_name=f"User {i}",
                first_name=f"User",
                last_name=f"{i}",
                dob="1990-01-01",
                email=f"user{i}@example.com",
                phone="07123456789",
                address_line1="1 High St",
                town_city="London",
                postcode="SW1A 1AA"
            )
            for i in range(1, 6)
        ]

        provider = MockDataProvider(clients)
        engine = AutomationEngine(provider=provider, state_mgr=state_mgr)

        # Pre-populate state:
        # Client 1: SUCCESS on fairplaybet
        state_mgr.set_status("CLI_001", "fairplaybet", RegistrationStatus.SUCCESS)
        # Client 2: FAILED on fairplaybet
        state_mgr.set_status("CLI_002", "fairplaybet", RegistrationStatus.FAILED, error_summary="Postcode error")

        # Run dry run with limit 2 and retry_failed=False
        # Since Client 1 is SUCCESS and Client 2 is FAILED, it should advance directly to Client 3 & 4!
        res1 = engine.run(limit=2, site_filters=["fairplaybet"], dry_run=True, retry_failed=False)
        assert res1["clients_validated"] == 2

        # Verify pending clients when retry_failed=False
        active_site_ids = ["fairplaybet"]
        pending_no_retry = [
            c for c in clients if state_mgr.has_pending_sites(c.client_id, active_site_ids, retry_failed=False)
        ]
        assert [c.client_id for c in pending_no_retry] == ["CLI_003", "CLI_004", "CLI_005"]

        # Verify pending clients when retry_failed=True (includes Client 2)
        pending_with_retry = [
            c for c in clients if state_mgr.has_pending_sites(c.client_id, active_site_ids, retry_failed=True)
        ]
        assert [c.client_id for c in pending_with_retry] == ["CLI_002", "CLI_003", "CLI_004", "CLI_005"]

    finally:
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass
