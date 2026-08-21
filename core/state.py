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
                    login_verified INTEGER DEFAULT 0,
                    login_screenshot_path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (client_id, site_id)
                )
            """)
            # Auto-migrate table if columns are missing
            for col, col_type in [
                ("email", "TEXT"),
                ("login_verified", "INTEGER DEFAULT 0"),
                ("login_screenshot_path", "TEXT")
            ]:
                try:
                    conn.execute(f"ALTER TABLE client_site_status ADD COLUMN {col} {col_type}")
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

    def get_record(self, client_id: str, site_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM client_site_status WHERE client_id = ? AND site_id = ?",
                (client_id, site_id)
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def is_complete(self, client_id: str, site_id: str) -> bool:
        """Returns True if the site signup is already completed, skipped, or already registered."""
        status = self.get_status(client_id, site_id)
        return status in (RegistrationStatus.SUCCESS, RegistrationStatus.SKIPPED, RegistrationStatus.ALREADY_REGISTERED)


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
        screenshot_path: Optional[str] = None,
        login_verified: Optional[bool] = None,
        login_screenshot_path: Optional[str] = None
    ):
        now = datetime.datetime.now().isoformat()
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO client_site_status (
                    client_id, site_id, client_name, site_name, status,
                    email, username, password, account_reference, error_summary,
                    screenshot_path, login_verified, login_screenshot_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    login_verified = COALESCE(excluded.login_verified, client_site_status.login_verified),
                    login_screenshot_path = COALESCE(excluded.login_screenshot_path, client_site_status.login_screenshot_path),
                    updated_at = excluded.updated_at
            """, (
                client_id, site_id, client_name, site_name, status.value,
                email, username, password, account_reference, error_summary,
                screenshot_path, 1 if login_verified is True else (0 if login_verified is False else None),
                login_screenshot_path, now
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
            screenshot_path=result.screenshot_path,
            login_verified=result.login_verified,
            login_screenshot_path=result.login_screenshot_path
        )

    def update_login_verification(
        self,
        client_id: str,
        site_id: str,
        success: bool,
        screenshot_path: Optional[str] = None,
        error_summary: Optional[str] = None
    ):
        """Updates login verification state and login proof screenshot. Downgrades status to FAILED if false."""
        now = datetime.datetime.now().isoformat()
        conn = self._get_connection()
        try:
            if success:
                conn.execute("""
                    UPDATE client_site_status
                    SET login_verified = 1,
                        status = 'SUCCESS',
                        login_screenshot_path = COALESCE(?, login_screenshot_path),
                        screenshot_path = COALESCE(?, screenshot_path),
                        updated_at = ?
                    WHERE client_id = ? AND site_id = ?
                """, (screenshot_path, screenshot_path, now, client_id, site_id))
            else:
                conn.execute("""
                    UPDATE client_site_status
                    SET login_verified = 0,
                        status = 'FAILED',
                        login_screenshot_path = COALESCE(?, login_screenshot_path),
                        error_summary = COALESCE(?, error_summary),
                        updated_at = ?
                    WHERE client_id = ? AND site_id = ?
                """, (screenshot_path, error_summary, now, client_id, site_id))
            conn.commit()
        finally:
            conn.close()

    def reset_record(self, client_id: str, site_id: str):
        """Resets a client-site status back to PENDING so fresh registration can be run."""
        conn = self._get_connection()
        try:
            conn.execute(
                "DELETE FROM client_site_status WHERE client_id = ? AND site_id = ?",
                (client_id, site_id)
            )
            conn.commit()
        finally:
            conn.close()



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
