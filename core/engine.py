import time
from typing import List, Optional
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
        dry_run: bool = False
    ) -> dict:
        """Executes the signup pipeline for eligible clients across target websites."""
        logger.info(f"Starting automation run (Limit: {limit}, Dry-Run: {dry_run})")
        
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
                    finally:
                        self.browser_mgr.stop_trace(context, export_name=f"{client.client_id}_{site.site_id}")
                        try:
                            context.close()
                        except Exception:
                            pass

                stats["processed_clients"] += 1

        finally:
            self.browser_mgr.close()

        summary = self.state_mgr.get_summary()
        logger.info("\n=======================================================")
        logger.info(f"Batch Execution Finished. Summary: {summary}")
        logger.info(f"Run Stats: {stats}")
        logger.info(f"=======================================================")
        return {"stats": stats, "state_summary": summary}
