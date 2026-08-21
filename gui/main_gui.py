import os
import sys
import queue
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import customtkinter as ctk
from tkinter import filedialog, messagebox
from loguru import logger

from config.settings import (
    BASE_DIR,
    DATA_SOURCE,
    EXCEL_INPUT_PATH,
    GOOGLE_SHEET_URL,
    DAILY_CLIENT_LIMIT,
    BROWSER_HEADLESS,
    LOGS_DIR,
    ARTIFACTS_DIR
)
from data.factory import get_data_provider
from data.models import RegistrationStatus
from core.browser import BrowserManager
from core.state import StateManager
from core.engine import AutomationEngine
from sites import get_site_adapters, load_promo_config

# Set appearance mode and theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class GuiLogSink:
    """Thread-safe sink redirecting loguru records into a Queue for GUI display."""

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def write(self, message: str):
        self.log_queue.put(message)


class DataEntryBotGUI(ctk.CTk):
    """Modern Desktop GUI Application for Data Entry Client Signup Automation."""

    def __init__(self):
        super().__init__()

        self.title("Data Entry Bot — Automated Client Registration")
        self.geometry("1280x800")
        self.minsize(980, 680)

        # Maximize to full screen on startup
        try:
            self.state("zoomed")
        except Exception:
            self.after(50, lambda: self.state("zoomed"))

        # State & Threading
        self.log_queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.stop_requested = False

        # Register Loguru GUI sink
        self.gui_sink = GuiLogSink(self.log_queue)
        logger.add(
            self.gui_sink.write,
            level="INFO",
            format="{time:HH:mm:ss} | {level: <7} | {message}\n"
        )

        # Build UI
        self._create_layout()
        self._load_site_checkboxes()
        self._update_stats_display()

        # Start Log Polling Loop
        self.after(100, self._poll_log_queue)

    def _create_layout(self):
        # Configure Grid Layout (2 columns: Sidebar & Main Area)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==========================================
        # 1. LEFT SIDEBAR (Configuration Panel)
        # ==========================================
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_rowconfigure(12, weight=1)

        # App Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="⚡ DataEntryBot",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar,
            text="Client Registration Automation",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Section: Data Source
        self.src_label = ctk.CTkLabel(self.sidebar, text="Data Source:", font=ctk.CTkFont(weight="bold"))
        self.src_label.grid(row=2, column=0, padx=20, pady=(5, 2), sticky="w")

        self.src_selector = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Excel (.xlsx)", "Google Sheets"],
            command=self._on_source_changed
        )
        self.src_selector.set("Excel (.xlsx)" if DATA_SOURCE == "excel" else "Google Sheets")
        self.src_selector.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Excel File Picker Frame
        self.excel_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.excel_frame.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.excel_path_var = ctk.StringVar(value=str(EXCEL_INPUT_PATH))
        self.excel_entry = ctk.CTkEntry(self.excel_frame, textvariable=self.excel_path_var, width=180)
        self.excel_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.browse_btn = ctk.CTkButton(self.excel_frame, text="Browse", width=60, command=self._browse_excel_file)
        self.browse_btn.pack(side="right")

        # Google Sheets URL Frame (Hidden by default if Excel selected)
        self.sheets_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sheets_frame.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.sheets_url_var = ctk.StringVar(value=GOOGLE_SHEET_URL)
        self.sheets_entry = ctk.CTkEntry(self.sheets_frame, textvariable=self.sheets_url_var, placeholder_text="Google Sheet URL")
        self.sheets_entry.pack(fill="x", expand=True)
        if DATA_SOURCE == "excel":
            self.sheets_frame.grid_remove()

        # Browser Mode Section (Visible vs Headless)
        self.mode_label = ctk.CTkLabel(self.sidebar, text="Browser Execution Mode:", font=ctk.CTkFont(weight="bold"))
        self.mode_label.grid(row=6, column=0, padx=20, pady=(10, 2), sticky="w")

        self.browser_mode_selector = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["🖥️ Visible (Headed)", "⚡ Silent (Headless)"]
        )
        self.browser_mode_selector.set("🖥️ Visible (Headed)" if not BROWSER_HEADLESS else "⚡ Silent (Headless)")
        self.browser_mode_selector.grid(row=7, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Client Batch Limit
        self.limit_label = ctk.CTkLabel(
            self.sidebar,
            text=f"Batch Client Limit: {DAILY_CLIENT_LIMIT}",
            font=ctk.CTkFont(weight="bold")
        )
        self.limit_label.grid(row=8, column=0, padx=20, pady=(10, 2), sticky="w")

        self.limit_slider = ctk.CTkSlider(
            self.sidebar,
            from_=1,
            to=50,
            number_of_steps=49,
            command=self._on_limit_slider_changed
        )
        self.limit_slider.set(DAILY_CLIENT_LIMIT)
        self.limit_slider.grid(row=9, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Specific Client Search Filter
        self.filter_label = ctk.CTkLabel(self.sidebar, text="Filter Client Name (Optional):")
        self.filter_label.grid(row=10, column=0, padx=20, pady=(5, 2), sticky="w")
        self.filter_entry = ctk.CTkEntry(self.sidebar, placeholder_text="e.g. Courtney Weaver")
        self.filter_entry.grid(row=11, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Open Artifacts Button
        self.open_logs_btn = ctk.CTkButton(
            self.sidebar,
            text="📂 Open Logs & Artifacts",
            fg_color="#2b2b2b",
            hover_color="#3b3b3b",
            command=self._open_artifacts_folder
        )
        self.open_logs_btn.grid(row=13, column=0, padx=20, pady=15, sticky="ew")

        # ==========================================
        # 2. MAIN CONTENT AREA (Right Panel)
        # ==========================================
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # TOP CARD: Website Selection Matrix
        self.sites_card = ctk.CTkFrame(self.main_frame)
        self.sites_card.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))

        self.sites_header_frame = ctk.CTkFrame(self.sites_card, fg_color="transparent")
        self.sites_header_frame.pack(fill="x", padx=15, pady=(10, 5))

        self.sites_title = ctk.CTkLabel(
            self.sites_header_frame,
            text="🎯 Target Websites Matrix",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.sites_title.pack(side="left")

        self.btn_select_all = ctk.CTkButton(
            self.sites_header_frame, text="Select All", width=70, height=24, command=self._select_all_sites
        )
        self.btn_select_all.pack(side="right", padx=(5, 0))

        self.btn_clear_sites = ctk.CTkButton(
            self.sites_header_frame, text="Clear All", width=70, height=24, fg_color="#444", hover_color="#555", command=self._clear_all_sites
        )
        self.btn_clear_sites.pack(side="right", padx=(5, 0))

        self.btn_local_only = ctk.CTkButton(
            self.sites_header_frame, text="Stage 1 (Fairplay)", width=110, height=24, fg_color="#1f538d", command=self._select_stage1_only
        )
        self.btn_local_only.pack(side="right")

        # Sites Checkbox Grid
        self.sites_grid_frame = ctk.CTkFrame(self.sites_card, fg_color="transparent")
        self.sites_grid_frame.pack(fill="x", padx=15, pady=(5, 12))
        self.site_checkbox_vars: Dict[str, ctk.BooleanVar] = {}

        # MIDDLE CARD: Stats & Execution Actions
        self.dashboard_card = ctk.CTkFrame(self.main_frame)
        self.dashboard_card.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, 10))

        self.dashboard_inner = ctk.CTkFrame(self.dashboard_card, fg_color="transparent")
        self.dashboard_inner.pack(fill="x", padx=15, pady=12)

        # Action Buttons
        self.btn_start = ctk.CTkButton(
            self.dashboard_inner,
            text="▶ Start Automation",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            height=36,
            command=self._start_automation
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_dry_run = ctk.CTkButton(
            self.dashboard_inner,
            text="⚡ Dry-Run Test",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#e65100",
            hover_color="#bf360c",
            height=36,
            command=self._start_dry_run
        )
        self.btn_dry_run.pack(side="left", padx=(0, 10))

        self.btn_stop = ctk.CTkButton(
            self.dashboard_inner,
            text="⏹ Stop",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c62828",
            hover_color="#8e0000",
            height=36,
            state="disabled",
            command=self._stop_automation
        )
        self.btn_stop.pack(side="left")

        # Status & Stats Counters (Right Side)
        self.stats_frame = ctk.CTkFrame(self.dashboard_inner, fg_color="transparent")
        self.stats_frame.pack(side="right")

        self.status_badge = ctk.CTkLabel(
            self.stats_frame,
            text="● IDLE",
            font=ctk.CTkFont(weight="bold"),
            text_color="#81c784"
        )
        self.status_badge.pack(side="right", padx=(10, 0))

        self.stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="Success: 0 | Failed: 0 | Total: 0",
            font=ctk.CTkFont(size=13)
        )
        self.stats_label.pack(side="right")

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self.dashboard_card)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 10))
        self.progress_bar.set(0)

        # BOTTOM AREA: Tabview (Live Log, Registered Accounts, Failures)
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self.tabview.grid_columnconfigure(0, weight=1)
        self.tabview.grid_rowconfigure(0, weight=1)

        # Tab 1: Live Console Log
        self.tab_log = self.tabview.add("📜 Live Execution Log")
        self.tab_log.grid_columnconfigure(0, weight=1)
        self.tab_log.grid_rowconfigure(1, weight=1)

        self.log_header = ctk.CTkFrame(self.tab_log, fg_color="transparent")
        self.log_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))

        self.log_title = ctk.CTkLabel(
            self.log_header,
            text="Real-time Automation Feed & Diagnostics",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.log_title.pack(side="left")

        self.btn_clear_log = ctk.CTkButton(
            self.log_header, text="Clear Log", width=70, height=22, fg_color="#333", command=self._clear_log
        )
        self.btn_clear_log.pack(side="right")

        self.log_textbox = ctk.CTkTextbox(
            self.tab_log,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word"
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Tab 2: Registered Accounts Table
        self.tab_accounts = self.tabview.add("✅ Registered Accounts")
        self.tab_accounts.grid_columnconfigure(0, weight=1)
        self.tab_accounts.grid_rowconfigure(1, weight=1)

        # Accounts Header Bar
        self.acc_header = ctk.CTkFrame(self.tab_accounts, fg_color="transparent")
        self.acc_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))

        self.acc_search_var = ctk.StringVar()
        self.acc_search_var.trace_add("write", lambda *_: self._populate_registered_accounts())
        self.acc_search_entry = ctk.CTkEntry(
            self.acc_header,
            textvariable=self.acc_search_var,
            placeholder_text="Search client name, email, or site...",
            width=260
        )
        self.acc_search_entry.pack(side="left", padx=(0, 10))

        self.btn_refresh_accs = ctk.CTkButton(
            self.acc_header, text="🔄 Refresh", width=80, height=24, command=self._populate_registered_accounts
        )
        self.btn_refresh_accs.pack(side="left", padx=(0, 10))

        self.btn_open_shots = ctk.CTkButton(
            self.acc_header, text="📂 Open Screenshots", width=140, height=24, fg_color="#1b5e20", hover_color="#2e7d32", command=self._open_artifacts_folder
        )
        self.btn_open_shots.pack(side="left")

        self.acc_count_label = ctk.CTkLabel(
            self.acc_header, text="Total: 0 accounts", font=ctk.CTkFont(weight="bold")
        )
        self.acc_count_label.pack(side="right")

        # Accounts Scrollable List
        self.acc_scroll_frame = ctk.CTkScrollableFrame(self.tab_accounts, fg_color="#1e1e1e")
        self.acc_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.acc_scroll_frame.grid_columnconfigure(0, weight=1)

        # Tab 3: Failures & Review
        self.tab_failures = self.tabview.add("⚠️ Failures & Review")
        self.tab_failures.grid_columnconfigure(0, weight=1)
        self.tab_failures.grid_rowconfigure(1, weight=1)

        self.fail_header = ctk.CTkFrame(self.tab_failures, fg_color="transparent")
        self.fail_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))
        self.fail_title = ctk.CTkLabel(self.fail_header, text="Registration Exceptions & Diagnostic Bundles", font=ctk.CTkFont(weight="bold"))
        self.fail_title.pack(side="left")
        self.btn_refresh_fails = ctk.CTkButton(self.fail_header, text="🔄 Refresh", width=80, height=24, command=self._populate_failures)
        self.btn_refresh_fails.pack(side="right")

        self.fail_scroll_frame = ctk.CTkScrollableFrame(self.tab_failures, fg_color="#1e1e1e")
        self.fail_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.fail_scroll_frame.grid_columnconfigure(0, weight=1)

    def _load_site_checkboxes(self):
        promo_cfg = load_promo_config()
        cols = 3
        r, c = 0, 0
        for site_id, cfg in promo_cfg.items():
            name = cfg.get("name", site_id)
            req_uk = cfg.get("requires_uk_ip", True)
            badge = "(Any IP)" if not req_uk else "(UK IP)"
            
            var = ctk.BooleanVar(value=True if site_id == "fairplaybet" else False)
            self.site_checkbox_vars[site_id] = var

            chk = ctk.CTkCheckBox(
                self.sites_grid_frame,
                text=f"{name} {badge}",
                variable=var,
                font=ctk.CTkFont(size=12)
            )
            chk.grid(row=r, column=c, padx=10, pady=6, sticky="w")
            c += 1
            if c >= cols:
                c = 0
                r += 1

    def _on_source_changed(self, value):
        if value == "Excel (.xlsx)":
            self.excel_frame.grid()
            self.sheets_frame.grid_remove()
        else:
            self.excel_frame.grid_remove()
            self.sheets_frame.grid()

    def _browse_excel_file(self):
        filename = filedialog.askopenfilename(
            title="Select Client Excel Workbook",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.excel_path_var.set(filename)

    def _on_limit_slider_changed(self, value):
        val = int(value)
        self.limit_label.configure(text=f"Batch Client Limit: {val}")

    def _select_all_sites(self):
        for var in self.site_checkbox_vars.values():
            var.set(True)

    def _clear_all_sites(self):
        for var in self.site_checkbox_vars.values():
            var.set(False)

    def _select_stage1_only(self):
        for site_id, var in self.site_checkbox_vars.items():
            var.set(True if site_id == "fairplaybet" else False)

    def _open_artifacts_folder(self):
        if ARTIFACTS_DIR.exists():
            subprocess.Popen(f'explorer "{ARTIFACTS_DIR}"')
        else:
            messagebox.showinfo("Logs", f"Logs folder: {LOGS_DIR}")

    def _clear_log(self):
        self.log_textbox.delete("1.0", "end")

    def _update_stats_display(self):
        try:
            state_mgr = StateManager()
            summary = state_mgr.get_summary()
            succ = summary.get("SUCCESS", 0)
            fail = summary.get("FAILED", 0)
            rev = summary.get("MANUAL_REVIEW", 0)
            self.stats_label.configure(text=f"Success: {succ} | Failed: {fail} | Manual: {rev}")
            self._populate_registered_accounts()
            self._populate_failures()
        except Exception:
            pass

    def _populate_registered_accounts(self):
        for widget in self.acc_scroll_frame.winfo_children():
            widget.destroy()

        try:
            state_mgr = StateManager()
            records = state_mgr.get_all_records(RegistrationStatus.SUCCESS)
            search_query = self.acc_search_var.get().strip().lower()

            if search_query:
                records = [
                    r for r in records
                    if search_query in (r.get("client_name") or "").lower()
                    or search_query in (r.get("email") or "").lower()
                    or search_query in (r.get("site_name") or "").lower()
                    or search_query in (r.get("username") or "").lower()
                ]

            self.acc_count_label.configure(text=f"Total: {len(records)} accounts")

            if not records:
                empty_lbl = ctk.CTkLabel(
                    self.acc_scroll_frame,
                    text="No successful registrations found matching search query.",
                    font=ctk.CTkFont(size=13),
                    text_color="gray"
                )
                empty_lbl.pack(pady=30)
                return

            for idx, r in enumerate(records):
                row_frame = ctk.CTkFrame(self.acc_scroll_frame, fg_color="#262626" if idx % 2 == 0 else "#2d2d2d", corner_radius=6)
                row_frame.pack(fill="x", padx=5, pady=3)

                # 1. Pack Action Buttons on the RIGHT FIRST (Guarantees they never get pushed off screen)
                def make_copy_cmd(pwd):
                    return lambda: self._copy_to_clipboard(pwd)

                def make_view_shot_cmd(shot):
                    if shot and Path(shot).exists():
                        return lambda: subprocess.Popen(f'explorer "{shot}"')
                    return lambda: subprocess.Popen(f'explorer "{ARTIFACTS_DIR}"')

                copy_btn = ctk.CTkButton(
                    row_frame,
                    text="📋 Copy",
                    width=55,
                    height=26,
                    fg_color="#37474f",
                    hover_color="#455a64",
                    command=make_copy_cmd(r.get("password") or "")
                )
                copy_btn.pack(side="right", padx=(4, 10), pady=6)

                shot_path = r.get("screenshot_path")
                shot_btn = ctk.CTkButton(
                    row_frame,
                    text="🖼️ Proof",
                    width=65,
                    height=26,
                    fg_color="#2e7d32",
                    hover_color="#1b5e20",
                    command=make_view_shot_cmd(shot_path)
                )
                shot_btn.pack(side="right", padx=(4, 4), pady=6)

                # 2. Pack Info Labels on the LEFT
                name_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"👤 {r.get('client_name', 'Unknown')}",
                    font=ctk.CTkFont(weight="bold", size=13),
                    anchor="w",
                    width=135
                )
                name_lbl.pack(side="left", padx=8, pady=6)

                site_badge = ctk.CTkLabel(
                    row_frame,
                    text=f"🎯 {r.get('site_name', r.get('site_id', 'Site'))}",
                    font=ctk.CTkFont(size=12),
                    text_color="#64b5f6",
                    anchor="w",
                    width=100
                )
                site_badge.pack(side="left", padx=4, pady=6)

                email_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"✉️ {r.get('email', '')}",
                    font=ctk.CTkFont(size=12),
                    text_color="#cfd8dc",
                    anchor="w",
                    width=180
                )
                email_lbl.pack(side="left", padx=4, pady=6)

                pwd_val = r.get("password") or ""
                pwd_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"🔑 {pwd_val}",
                    font=ctk.CTkFont(family="Consolas", size=12),
                    text_color="#aed581",
                    anchor="w",
                    width=120
                )
                pwd_lbl.pack(side="left", padx=4, pady=6)

        except Exception as e:
            logger.error(f"Failed to populate registered accounts: {e}")

    def _populate_failures(self):
        for widget in self.fail_scroll_frame.winfo_children():
            widget.destroy()

        try:
            state_mgr = StateManager()
            all_recs = state_mgr.get_all_records()
            fails = [r for r in all_recs if r.get("status") in ("FAILED", "MANUAL_REVIEW")]

            if not fails:
                empty_lbl = ctk.CTkLabel(
                    self.fail_scroll_frame,
                    text="🎉 No failed registrations or exceptions recorded!",
                    font=ctk.CTkFont(size=13),
                    text_color="#81c784"
                )
                empty_lbl.pack(pady=30)
                return

            for idx, r in enumerate(fails):
                row_frame = ctk.CTkFrame(self.fail_scroll_frame, fg_color="#2d1f1f", corner_radius=6)
                row_frame.pack(fill="x", padx=5, pady=3)

                info_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"⚠️ {r.get('client_name')} - {r.get('site_name')}: {r.get('error_summary', 'Unknown error')}",
                    font=ctk.CTkFont(size=12),
                    text_color="#ef9a9a",
                    anchor="w"
                )
                info_lbl.pack(side="left", padx=10, pady=8, fill="x", expand=True)

                shot_path = r.get("screenshot_path")
                if shot_path and Path(shot_path).exists():
                    def make_view_cmd(p):
                        return lambda: subprocess.Popen(f'explorer "{p}"')
                    view_btn = ctk.CTkButton(
                        row_frame, text="🖼️ Screenshot", width=90, height=24, fg_color="#b71c1c", command=make_view_cmd(shot_path)
                    )
                    view_btn.pack(side="right", padx=10, pady=8)
        except Exception as e:
            logger.error(f"Failed to populate failures: {e}")

    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Password copied to clipboard!")

    def _poll_log_queue(self):
        """Drains the log queue and appends entries to the textbox."""
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.log_textbox.insert("end", msg)
                self.log_textbox.see("end")
            except queue.Empty:
                break
        self.after(100, self._poll_log_queue)

    def _start_automation(self):
        self._run_task(dry_run=False)

    def _start_dry_run(self):
        self._run_task(dry_run=True)

    def _run_task(self, dry_run: bool = False):
        if self.is_running:
            return

        selected_sites = [site_id for site_id, var in self.site_checkbox_vars.items() if var.get()]
        if not selected_sites:
            messagebox.showwarning("No Sites Selected", "Please select at least one website to process.")
            return

        source = "excel" if self.src_selector.get() == "Excel (.xlsx)" else "sheets"
        excel_path = Path(self.excel_path_var.get())
        sheet_url = self.sheets_url_var.get()
        headed = "Visible" in self.browser_mode_selector.get()
        limit = int(self.limit_slider.get())
        client_filter = self.filter_entry.get().strip() or None

        self.is_running = True
        self.btn_start.configure(state="disabled")
        self.btn_dry_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_badge.configure(text="● RUNNING", text_color="#ffa726")
        self.progress_bar.set(0.1)

        def worker():
            try:
                provider = get_data_provider(
                    source=source,
                    excel_path=excel_path,
                    sheet_url=sheet_url
                )
                browser_mgr = BrowserManager(headless=not headed)
                state_mgr = StateManager()
                adapters = get_site_adapters(filter_sites=selected_sites)

                engine = AutomationEngine(
                    provider=provider,
                    state_mgr=state_mgr,
                    browser_mgr=browser_mgr,
                    site_adapters=adapters
                )

                engine.run(
                    limit=limit,
                    client_id_filter=client_filter,
                    site_filters=selected_sites,
                    dry_run=dry_run
                )

            except Exception as e:
                logger.error(f"Error in automation engine: {e}")
            finally:
                self.is_running = False
                self.after(0, self._on_task_finished)

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _stop_automation(self):
        self.status_badge.configure(text="● STOPPING...", text_color="#ef5350")
        logger.warning("Stop requested by user. Cleaning up after current step...")
        self.btn_stop.configure(state="disabled")

    def _on_task_finished(self):
        self.btn_start.configure(state="normal")
        self.btn_dry_run.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_badge.configure(text="● COMPLETED", text_color="#81c784")
        self.progress_bar.set(1.0)
        self._update_stats_display()


def run_gui():
    app = DataEntryBotGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
