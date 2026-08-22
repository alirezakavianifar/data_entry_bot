import time
import threading
from typing import List, Optional, Tuple, Callable
from config.settings import AUTO_VERIFY_LOGIN
from data.base_provider import BaseDataProvider
from data.models import Client, RegistrationResult, RegistrationStatus
from core.state import StateManager
from core.browser import BrowserManager
from core.password_gen import generate_password
from sites.base import BaseSiteAdapter, is_pending_verification_error
from sites import get_site_adapters
from core.logger import get_logger

logger = get_logger(step="Engine")


class AutomationEngine:
    """Core orchestration engine coordinating client data, browser execution, state tracking, and output."""

    def __init__(
        self,
        provider: BaseDataProvider,
        state_mgr: Optional[StateManager] = None,
        browser_mgr: Optional[BrowserManager] = None,
        site_adapters: Optional[List[BaseSiteAdapter]] = None,
        stop_event: Optional[threading.Event] = None
    ):
        self.provider = provider
        self.state_mgr = state_mgr or StateManager()
        self.browser_mgr = browser_mgr or BrowserManager()
        self.site_adapters = site_adapters or get_site_adapters()
        self.stop_event = stop_event or threading.Event()

    def request_stop(self):
        """Requests a graceful stop of the automation engine."""
        logger.warning("Stop requested on AutomationEngine.")
        self.stop_event.set()

    def is_stop_requested(self) -> bool:
        """Returns True if a stop has been requested."""
        return self.stop_event.is_set()

    def run(
        self,
        limit: int = 20,
        client_id_filter: Optional[str] = None,
        site_filters: Optional[List[str]] = None,
        dry_run: bool = False,
        verify_login: bool = AUTO_VERIFY_LOGIN,
        retry_failed: bool = False,
        on_progress: Optional[Callable[[RegistrationResult, dict], None]] = None
    ) -> dict:
        """Executes the signup pipeline for eligible clients across target websites."""
        logger.info(f"Starting automation run (Limit: {limit}, Dry-Run: {dry_run}, Verify-Login: {verify_login}, Retry-Failed: {retry_failed})")
        
        if self.is_stop_requested():
            logger.warning("Stop requested before starting batch execution.")
            return {"status": "stopped", "stats": {}, "state_summary": self.state_mgr.get_summary()}

        # 1. Fetch eligible clients
        clients = self.provider.get_valid_clients()
        logger.info(f"Retrieved {len(clients)} valid client records from data source")

        # 2. Filter site adapters if specified
        active_adapters = self.site_adapters
        if site_filters:
            active_adapters = [a for a in self.site_adapters if a.site_id in site_filters or a.site_name.lower() in [s.lower() for s in site_filters]]
        active_site_ids = [a.site_id for a in active_adapters]
        logger.info(f"Active site adapters ({len(active_adapters)}): {[a.site_name for a in active_adapters]}")

        # 3. Select batch clients (advancing past clients with no pending work)
        if client_id_filter:
            selected_clients = [c for c in clients if client_id_filter.lower() in c.client_id.lower() or client_id_filter.lower() in c.full_name.lower()][:limit]
            logger.info(f"Targeting {len(selected_clients)} client(s) matching '{client_id_filter}'")
        else:
            pending_clients = [
                c for c in clients
                if self.state_mgr.has_pending_sites(c.client_id, active_site_ids, retry_failed=retry_failed)
            ]
            already_handled = len(clients) - len(pending_clients)
            if already_handled > 0:
                logger.info(f"Advancing past {already_handled} client(s) with no pending sites (Retry-Failed: {retry_failed})")
            selected_clients = pending_clients[:limit]
            logger.info(f"Processing batch of {len(selected_clients)} pending clients")

        if dry_run:
            logger.info("=== DRY RUN MODE: Validating client data only ===")
            for idx, client in enumerate(selected_clients, start=1):
                if self.is_stop_requested():
                    logger.warning("Dry-run stopped by user request.")
                    break
                logger.info(
                    f"[{idx}/{len(selected_clients)}] Valid Client: {client.full_name} | "
                    f"Email: {client.email} | Phone: {client.phone} | Postcode: {client.postcode} | DOB: {client.dob_day}/{client.dob_month}/{client.dob_year}"
                )
            return {
                "status": "stopped" if self.is_stop_requested() else "dry_run_complete",
                "clients_validated": len(selected_clients)
            }

        # 4. Main Execution Loop
        stats = {"processed_clients": 0, "success_count": 0, "already_registered_count": 0, "failed_count": 0, "skipped_count": 0}
        
        try:
            self.browser_mgr.start()

            for client_idx, client in enumerate(selected_clients, start=1):
                if self.is_stop_requested():
                    logger.warning(f"Stop requested by user. Halting execution before Client [{client_idx}/{len(selected_clients)}].")
                    break

                logger.info(f"\n=======================================================")
                logger.info(f"Processing Client [{client_idx}/{len(selected_clients)}]: {client.full_name} ({client.email})")
                logger.info(f"=======================================================")

                for site in active_adapters:
                    if self.is_stop_requested():
                        logger.warning(f"Stop requested by user. Skipping remaining sites for {client.full_name}.")
                        break

                    # Check if already completed / already registered
                    if self.state_mgr.is_complete(client.client_id, site.site_id):
                        logger.info(f"Skipping {site.site_name} for {client.full_name} (Already Completed or Registered)")
                        stats["skipped_count"] += 1
                        continue

                    # Check if previously failed and retry_failed is False
                    curr_status = self.state_mgr.get_status(client.client_id, site.site_id)
                    if curr_status in (RegistrationStatus.FAILED, RegistrationStatus.MANUAL_REVIEW) and not retry_failed:
                        logger.info(f"Skipping {site.site_name} for {client.full_name} (Previously Failed - retry_failed is False)")
                        stats["skipped_count"] += 1
                        continue

                    # Generate compliant password
                    password = generate_password()
                    
                    # Update state -> IN_PROGRESS
                    self.state_mgr.set_status(
                        client_id=client.client_id,
                        site_id=site.site_id,
                        status=RegistrationStatus.IN_PROGRESS,
                        client_name=client.full_name,
                        site_name=site.site_name
                    )

                    # Create browser context & page
                    context = self.browser_mgr.new_context(trace_name=f"{client.client_id}_{site.site_id}")
                    page = context.new_page()

                    try:
                        result = site.execute(page=page, client=client, password=password)

                        # Close signup context prior to login verification
                        self.browser_mgr.stop_trace(context, export_name=f"{client.client_id}_{site.site_id}")
                        try:
                            context.close()
                        except Exception:
                            pass

                        # Post-Registration Login Verification (if desired & signup succeeded)
                        if result.status == RegistrationStatus.SUCCESS and verify_login:
                            if self.is_stop_requested():
                                logger.warning(f"Stop requested by user: skipping login verification for {client.full_name} on {site.site_name}.")
                            else:
                                logger.info(f"🔐 Verifying account creation via login for {client.full_name} on {site.site_name}...")
                                login_ctx = self.browser_mgr.new_context(trace_name=f"{client.client_id}_{site.site_id}_login")
                                login_page = login_ctx.new_page()
                                try:
                                    login_ok, login_proof, login_err = site.login(
                                        page=login_page,
                                        username_or_email=client.email,
                                        password=password,
                                        client_id=client.client_id
                                    )
                                    if login_ok and login_proof:
                                        result.login_verified = True
                                        result.login_screenshot_path = login_proof
                                        result.screenshot_path = login_proof
                                        logger.info(f"✅ Login verified with visual proof: {login_proof}")
                                    elif is_pending_verification_error(login_err or ""):
                                        # Account was created successfully with valid credentials, but user email/KYC is pending
                                        result.login_verified = False
                                        result.login_screenshot_path = login_proof
                                        result.screenshot_path = login_proof
                                        result.error_summary = login_err
                                        result.account_reference = f"{site.site_name} (Pending Activation)"
                                        logger.info(f"ℹ️ Account created with valid credentials for {client.full_name}, but activation is pending ({login_err}). Preserving credentials.")
                                        # Keep status as SUCCESS and DO NOT remove from spreadsheet
                                    else:
                                        # Conclusive proof that registration was not successful / credentials rejected
                                        result.status = RegistrationStatus.FAILED
                                        result.login_verified = False
                                        result.login_error = login_err
                                        result.error_summary = f"Login verification failed: {login_err or 'Invalid credentials'}"
                                        logger.warning(f"❌ Login verification rejected ({login_err}). Registration marked as FAILED.")
                                        self.provider.remove_success(client_name=client.full_name, site_name=site.site_name, email=client.email)
                                except Exception as le:
                                    logger.error(f"Error during login verification step: {le}")
                                    result.status = RegistrationStatus.FAILED
                                    result.login_verified = False
                                    result.error_summary = f"Login verification error: {le}"
                                    self.provider.remove_success(client_name=client.full_name, site_name=site.site_name, email=client.email)
                                finally:
                                    try:
                                        login_ctx.close()
                                    except Exception:
                                        pass

                        # Record in persistent state
                        self.state_mgr.record_result(result)

                        # Write to output destination (Excel or Google Sheets)
                        if result.status == RegistrationStatus.SUCCESS:
                            self.provider.record_success(result)
                            stats["success_count"] += 1
                        elif result.status == RegistrationStatus.ALREADY_REGISTERED:
                            logger.info(f"ℹ️ {client.full_name} recorded as ALREADY_REGISTERED on {site.site_name}")
                            stats["already_registered_count"] += 1
                        else:
                            self.provider.record_failure(result)
                            stats["failed_count"] += 1

                        if on_progress:
                            try:
                                on_progress(result, stats)
                            except Exception:
                                pass

                    except Exception as e:
                        logger.error(f"Execution error on {site.site_name} for {client.full_name}: {e}")
                        stats["failed_count"] += 1

                stats["processed_clients"] += 1

        finally:
            if self.is_stop_requested():
                self.state_mgr.reset_in_progress()
            self.browser_mgr.close()

        summary = self.state_mgr.get_summary()
        logger.info("\n=======================================================")
        logger.info(f"Batch Execution {'Stopped Early by User' if self.is_stop_requested() else 'Finished'}. Summary: {summary}")
        logger.info(f"Run Stats: {stats}")
        logger.info(f"=======================================================")
        return {
            "status": "stopped" if self.is_stop_requested() else "completed",
            "stats": stats,
            "state_summary": summary
        }


def verify_single_account(
    client_id: str,
    site_id: str,
    email: str,
    password: str,
    client_name: str = "",
    site_name: str = "",
    headed: bool = True,
    provider: Optional[BaseDataProvider] = None
) -> Tuple[bool, Optional[str], Optional[str]]:

    """
    On-demand single account login verification utility.
    Launches browser, attempts login, captures proof screenshot, and updates StateManager.
    If login fails (e.g. invalid credentials), removes false positive row from provider and updates state to FAILED.
    Returns (success, proof_path, error_message).
    """
    state_mgr = StateManager()
    browser_mgr = BrowserManager(headless=not headed)
    adapters = get_site_adapters(filter_sites=[site_id])
    if not adapters:
        return False, None, f"No adapter found for site '{site_id}'"

    adapter = adapters[0]
    logger.info(f"Starting on-demand login verification: Client '{client_id}', Site '{site_id}', Headed={headed}")

    try:
        browser_mgr.start()
        context = browser_mgr.new_context()
        page = context.new_page()

        success, proof_path, error_msg = adapter.login(
            page=page,
            username_or_email=email,
            password=password,
            client_id=client_id
        )

        is_pending = is_pending_verification_error(error_msg or "")

        state_mgr.update_login_verification(
            client_id=client_id,
            site_id=site_id,
            success=success,
            screenshot_path=proof_path,
            error_summary=error_msg,
            is_pending_verification=is_pending
        )

        if not success and not is_pending:
            # Only remove false positive record from spreadsheet if credentials are truly invalid
            if provider:
                c_name = client_name
                s_name = site_name or adapter.site_name
                deleted = provider.remove_success(client_name=c_name, site_name=s_name, email=email)
                logger.info(f"Removed {deleted} false positive row(s) from provider for {client_id}")
        elif is_pending:
            logger.info(f"Account for {client_id} on {site_id} is valid but requires activation ({error_msg}). Preserving in spreadsheet.")

        try:
            context.close()
        except Exception:
            pass

        return success, proof_path, error_msg

    except Exception as e:
        logger.error(f"Error in verify_single_account for {client_id} on {site_id}: {e}")
        return False, None, str(e)
    finally:
        browser_mgr.close()


def register_single_account(
    client: Client,
    site_id: str,
    provider: BaseDataProvider,
    headed: bool = False,
    verify_login: bool = True
) -> RegistrationResult:
    """
    Executes a fresh registration for a single client on a specific site.
    """
    state_mgr = StateManager()
    browser_mgr = BrowserManager(headless=not headed)
    adapters = get_site_adapters(filter_sites=[site_id])
    if not adapters:
        raise ValueError(f"No adapter found for site '{site_id}'")

    site = adapters[0]
    password = generate_password()

    # Reset any previous failed/false state
    state_mgr.reset_record(client.client_id, site_id)
    state_mgr.set_status(
        client_id=client.client_id,
        site_id=site.site_id,
        status=RegistrationStatus.IN_PROGRESS,
        client_name=client.full_name,
        site_name=site.site_name
    )

    try:
        browser_mgr.start()
        context = browser_mgr.new_context(trace_name=f"{client.client_id}_{site.site_id}_fresh")
        page = context.new_page()

        result = site.execute(page=page, client=client, password=password)

        try:
            context.close()
        except Exception:
            pass

        # Post-Registration Login Verification
        if result.status == RegistrationStatus.SUCCESS and verify_login:
            login_ctx = browser_mgr.new_context(trace_name=f"{client.client_id}_{site.site_id}_login")
            login_page = login_ctx.new_page()
            try:
                login_ok, login_proof, login_err = site.login(
                    page=login_page,
                    username_or_email=client.email,
                    password=password,
                    client_id=client.client_id
                )
                if login_ok and login_proof:
                    result.login_verified = True
                    result.login_screenshot_path = login_proof
                    result.screenshot_path = login_proof
                else:
                    result.status = RegistrationStatus.FAILED
                    result.login_verified = False
                    result.login_error = login_err
                    result.error_summary = f"Login verification rejected: {login_err}"
            finally:
                try:
                    login_ctx.close()
                except Exception:
                    pass

        state_mgr.record_result(result)

        if result.status == RegistrationStatus.SUCCESS:
            provider.record_success(result)
        else:
            provider.record_failure(result)

        return result

    finally:
        browser_mgr.close()


