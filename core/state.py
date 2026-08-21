import sqlite3
import datetime
from pathlib import Path
from typing import Optional, Dict
from data.models import RegistrationStatus, RegistrationResult
from config.settings import STATE_DB_PATH
from core.logger import get_logger

logger = get_logger(step="StateManager")


class StateManager:
    """Persistent SQLite-backed state manager for client registration progress."""

    def __init__(self, db_path: Path = STATE_DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS client_site_status (
                    client_id TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    client_name TEXT,
                    site_name TEXT,
                    status TEXT NOT NULL,
                    email TEXT,
                    username TEXT,
                    password TEXT,
                    account_reference TEXT,
                    error_summary TEXT,
                    screenshot_path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (client_id, site_id)
                )
            """)
            # Auto-migrate table if email column is missing
            try:
                conn.execute("ALTER TABLE client_site_status ADD COLUMN email TEXT")
            except Exception:
                pass
            conn.commit()
        finally:
            conn.close()

    def get_status(self, client_id: str, site_id: str) -> RegistrationStatus:
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT status FROM client_site_status WHERE client_id = ? AND site_id = ?",
                (client_id, site_id)
            )
            row = cur.fetchone()
            if row:
                try:
                    return RegistrationStatus(row["status"])
                except ValueError:
                    return RegistrationStatus.PENDING
            return RegistrationStatus.PENDING
        finally:
            conn.close()

    def is_complete(self, client_id: str, site_id: str) -> bool:
        """Returns True if the site signup is already completed or skipped."""
        status = self.get_status(client_id, site_id)
        return status in (RegistrationStatus.SUCCESS, RegistrationStatus.SKIPPED)

    def set_status(
        self,
        client_id: str,
        site_id: str,
        status: RegistrationStatus,
        client_name: str = "",
        site_name: str = "",
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        account_reference: Optional[str] = None,
        error_summary: Optional[str] = None,
        screenshot_path: Optional[str] = None
    ):
        now = datetime.datetime.now().isoformat()
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO client_site_status (
                    client_id, site_id, client_name, site_name, status,
                    email, username, password, account_reference, error_summary,
                    screenshot_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id, site_id) DO UPDATE SET
                    status = excluded.status,
                    client_name = COALESCE(NULLIF(excluded.client_name, ''), client_site_status.client_name),
                    site_name = COALESCE(NULLIF(excluded.site_name, ''), client_site_status.site_name),
                    email = COALESCE(excluded.email, client_site_status.email),
                    username = COALESCE(excluded.username, client_site_status.username),
                    password = COALESCE(excluded.password, client_site_status.password),
                    account_reference = COALESCE(excluded.account_reference, client_site_status.account_reference),
                    error_summary = COALESCE(excluded.error_summary, client_site_status.error_summary),
                    screenshot_path = COALESCE(excluded.screenshot_path, client_site_status.screenshot_path),
                    updated_at = excluded.updated_at
            """, (
                client_id, site_id, client_name, site_name, status.value,
                email, username, password, account_reference, error_summary,
                screenshot_path, now
            ))
            conn.commit()
        finally:
            conn.close()

    def record_result(self, result: RegistrationResult):
        self.set_status(
            client_id=result.client_id,
            site_id=result.site_id,
            status=result.status,
            client_name=result.client_name,
            site_name=result.site_name,
            email=result.email,
            username=result.username,
            password=result.password,
            account_reference=result.account_reference,
            error_summary=result.error_summary,
            screenshot_path=result.screenshot_path
        )

    def get_all_records(self, status: Optional[RegistrationStatus] = None) -> List[Dict]:
        """Returns all records sorted by updated_at descending, optionally filtered by status."""
        conn = self._get_connection()
        try:
            if status:
                cur = conn.execute(
                    "SELECT * FROM client_site_status WHERE status = ? ORDER BY updated_at DESC",
                    (status.value,)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM client_site_status ORDER BY updated_at DESC"
                )
            records = []
            for row in cur.fetchall():
                records.append(dict(row))
            return records
        finally:
            conn.close()

    def get_summary(self) -> Dict[str, int]:
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT status, COUNT(*) as cnt FROM client_site_status GROUP BY status")
            summary = {status.value: 0 for status in RegistrationStatus}
            for row in cur.fetchall():
                summary[row["status"]] = row["cnt"]
            return summary
        finally:
            conn.close()
