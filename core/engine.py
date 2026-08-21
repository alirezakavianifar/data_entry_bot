import time
from typing import List, Optional, Tuple
from config.settings import AUTO_VERIFY_LOGIN
from data.base_provider import BaseDataProvider
from data.models import Client, RegistrationResult, RegistrationStatus
from core.state import StateManager
from core.browser import BrowserManager
from core.password_gen import generate_password
from sites.base import BaseSiteAdapter
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
        site_adapters: Optional[List[BaseSiteAdapter]] = None
    ):
        self.provider = provider
        self.state_mgr = state_mgr or StateManager()
        self.browser_mgr = browser_mgr or BrowserManager()
        self.site_adapters = site_adapters or get_site_adapters()

    def run(
        self,
        limit: int = 20,
        client_id_filter: Optional[str] = None,
        site_filters: Optional[List[str]] = None,
        dry_run: bool = False,
        verify_login: bool = AUTO_VERIFY_LOGIN
    ) -> dict:
        """Executes the signup pipeline for eligible clients across target websites."""
        logger.info(f"Starting automation run (Limit: {limit}, Dry-Run: {dry_run}, Verify-Login: {verify_login})")
        
        # 1. Fetch eligible clients
        clients = self.provider.get_valid_clients()
        logger.info(f"Retrieved {len(clients)} valid client records from data source")

        if client_id_filter:
            clients = [c for c in clients if client_id_filter.lower() in c.client_id.lower() or client_id_filter.lower() in c.full_name.lower()]
            logger.info(f"Filtered to {len(clients)} clients matching '{client_id_filter}'")

        selected_clients = clients[:limit]
        logger.info(f"Processing batch of {len(selected_clients)} clients")

        # 2. Filter site adapters if specified
        active_adapters = self.site_adapters
        if site_filters:
            active_adapters = [a for a in self.site_adapters if a.site_id in site_filters or a.site_name.lower() in [s.lower() for s in site_filters]]

        logger.info(f"Active site adapters ({len(active_adapters)}): {[a.site_name for a in active_adapters]}")

        if dry_run:
            logger.info("=== DRY RUN MODE: Validating client data only ===")
            for idx, client in enumerate(selected_clients, start=1):
                logger.info(
                    f"[{idx}/{len(selected_clients)}] Valid Client: {client.full_name} | "
                    f"Email: {client.email} | Phone: {client.phone} | Postcode: {client.postcode} | DOB: {client.dob_day}/{client.dob_month}/{client.dob_year}"
                )
            return {"status": "dry_run_complete", "clients_validated": len(selected_clients)}

        # 3. Main Execution Loop
        stats = {"processed_clients": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0}
        
        try:
            self.browser_mgr.start()

            for client_idx, client in enumerate(selected_clients, start=1):
                logger.info(f"\n=======================================================")
                logger.info(f"Processing Client [{client_idx}/{len(selected_clients)}]: {client.full_name} ({client.email})")
                logger.info(f"=======================================================")

                for site in active_adapters:
                    # Check if already completed
                    if self.state_mgr.is_complete(client.client_id, site.site_id):
                        logger.info(f"Skipping {site.site_name} for {client.full_name} (Already Completed/Skipped)")
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
                                else:
                                    result.login_verified = False
                                    result.login_error = login_err
                                    logger.warning(f"⚠️ Login verification unconfirmed: {login_err}")
                            except Exception as le:
                                logger.error(f"Error during login verification step: {le}")
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
                        else:
                            self.provider.record_failure(result)
                            stats["failed_count"] += 1

                    except Exception as e:
                        logger.error(f"Execution error on {site.site_name} for {client.full_name}: {e}")
                        stats["failed_count"] += 1

                stats["processed_clients"] += 1

        finally:
            self.browser_mgr.close()

        summary = self.state_mgr.get_summary()
        logger.info("\n=======================================================")
        logger.info(f"Batch Execution Finished. Summary: {summary}")
        logger.info(f"Run Stats: {stats}")
        logger.info(f"=======================================================")
        return {"stats": stats, "state_summary": summary}


def verify_single_account(
    client_id: str,
    site_id: str,
    email: str,
    password: str,
    headed: bool = False
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    On-demand single account login verification utility.
    Launches browser, attempts login, captures proof screenshot, and updates StateManager.
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

        state_mgr.update_login_verification(
            client_id=client_id,
            site_id=site_id,
            success=success,
            screenshot_path=proof_path,
            error_summary=error_msg
        )

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

