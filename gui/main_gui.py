import os
import sys
import queue
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import customtkinter as ctk
from tkinter import filedialog, messagebox
from loguru import logger

from config.settings import (
    BASE_DIR,
    DATA_SOURCE,
    EXCEL_INPUT_PATH,
    GOOGLE_SHEET_URL,
    DAILY_CLIENT_LIMIT,
    AUTO_VERIFY_LOGIN,
    BROWSER_HEADLESS,
    LOGS_DIR,
    ARTIFACTS_DIR
)
from data.factory import get_data_provider
from data.models import RegistrationStatus
import webbrowser
from core.browser import BrowserManager
from core.state import StateManager
from core.engine import AutomationEngine, verify_single_account, register_single_account
from sites import (
    get_site_adapters,
    load_promo_config,
    save_promo_config,
    reset_promo_to_default,
    add_or_update_promo_link,
    delete_custom_promo_link,
    is_valid_url,
    DEFAULT_PROMO_LINKS
)
from sites.base import is_pending_verification_error

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

        # Schedule maximization to avoid DPI/scaling conflict
        self.after(150, self._maximize_window)

        # State & Threading
        self.log_queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.current_engine: Optional[AutomationEngine] = None
        self.is_running = False
        self.stop_requested = False
        self.promo_field_entries: Dict[str, dict] = {}
        self.failure_checkbox_vars: Dict[Tuple[str, str], Tuple[ctk.BooleanVar, dict]] = {}

        # Register Loguru GUI sink
        self.gui_sink = GuiLogSink(self.log_queue)
        self.gui_sink_id = logger.add(
            self.gui_sink.write,
            level="INFO",
            format="{time:HH:mm:ss} | {level: <7} | {message}\n"
        )

        # Handle window closing gracefully
        self.protocol("WM_DELETE_WINDOW", self._on_window_closing)

        # Build UI
        self._create_layout()
        self._load_site_checkboxes()
        self._populate_promo_links_tab()
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
        self.sidebar.grid_rowconfigure(14, weight=1)

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
        self.filter_entry.grid(row=11, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Post-Registration Login Verification Switch
        self.auto_verify_var = ctk.BooleanVar(value=AUTO_VERIFY_LOGIN)
        self.auto_verify_switch = ctk.CTkSwitch(
            self.sidebar,
            text="🔐 Auto-Verify via Login",
            variable=self.auto_verify_var,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.auto_verify_switch.grid(row=12, column=0, padx=20, pady=(0, 10), sticky="w")

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

        # Top row of failure header
        self.fail_top_frame = ctk.CTkFrame(self.fail_header, fg_color="transparent")
        self.fail_top_frame.pack(fill="x", pady=(0, 4))

        self.fail_title = ctk.CTkLabel(self.fail_top_frame, text="Registration Exceptions & Diagnostic Bundles", font=ctk.CTkFont(weight="bold"))
        self.fail_title.pack(side="left")

        self.fail_count_label = ctk.CTkLabel(self.fail_top_frame, text="Total: 0 failures", font=ctk.CTkFont(weight="bold"))
        self.fail_count_label.pack(side="right", padx=(10, 0))

        self.btn_clear_fails = ctk.CTkButton(self.fail_top_frame, text="🧹 Clear All Failures", width=120, height=24, fg_color="#444", hover_color="#555", command=self._clear_all_failures_action)
        self.btn_clear_fails.pack(side="right", padx=(5, 0))

        self.btn_refresh_fails = ctk.CTkButton(self.fail_top_frame, text="🔄 Refresh", width=80, height=24, command=self._populate_failures)
        self.btn_refresh_fails.pack(side="right")

        # Batch Selection & Actions Toolbar Row
        self.fail_toolbar_frame = ctk.CTkFrame(self.fail_header, fg_color="#252525", corner_radius=6)
        self.fail_toolbar_frame.pack(fill="x", pady=(2, 0))

        self.select_all_fails_var = ctk.BooleanVar(value=False)
        self.select_all_fails_chk = ctk.CTkCheckBox(
            self.fail_toolbar_frame,
            text="Select All",
            variable=self.select_all_fails_var,
            command=self._toggle_select_all_failures,
            width=80,
            height=20,
            checkbox_width=18,
            checkbox_height=18
        )
        self.select_all_fails_chk.pack(side="left", padx=(10, 6), pady=5)

        self.fail_selected_label = ctk.CTkLabel(
            self.fail_toolbar_frame,
            text="(0 selected)",
            font=ctk.CTkFont(size=12),
            text_color="#9e9e9e"
        )
        self.fail_selected_label.pack(side="left", padx=(0, 10), pady=5)

        self.fail_search_var = ctk.StringVar()
        self.fail_search_var.trace_add("write", lambda *_: self._populate_failures())
        self.fail_search_entry = ctk.CTkEntry(
            self.fail_toolbar_frame,
            textvariable=self.fail_search_var,
            placeholder_text="🔍 Search site, client, or error...",
            width=220,
            height=24
        )
        self.fail_search_entry.pack(side="left", padx=(0, 8), pady=5)

        self.fail_site_filter_var = ctk.StringVar(value="All Websites")
        self.fail_site_filter = ctk.CTkOptionMenu(
            self.fail_toolbar_frame,
            variable=self.fail_site_filter_var,
            values=["All Websites"],
            command=lambda *_: self._populate_failures(),
            width=135,
            height=24,
            dynamic_resizing=False
        )
        self.fail_site_filter.pack(side="left", padx=(0, 12), pady=5)

        self.btn_retry_selected_fails = ctk.CTkButton(
            self.fail_toolbar_frame,
            text="🔁 Retry Selected (0)",
            width=140,
            height=24,
            fg_color="#1565c0",
            hover_color="#0d47a1",
            state="disabled",
            command=self._retry_selected_failures_action
        )
        self.btn_retry_selected_fails.pack(side="left", padx=(0, 8), pady=5)

        self.btn_dismiss_selected_fails = ctk.CTkButton(
            self.fail_toolbar_frame,
            text="🗑️ Dismiss Selected (0)",
            width=145,
            height=24,
            fg_color="#444",
            hover_color="#c62828",
            state="disabled",
            command=self._dismiss_selected_failures_action
        )
        self.btn_dismiss_selected_fails.pack(side="left", padx=(0, 8), pady=5)

        self.fail_scroll_frame = ctk.CTkScrollableFrame(self.tab_failures, fg_color="#1e1e1e")
        self.fail_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.fail_scroll_frame.grid_columnconfigure(0, weight=1)

        # Tab 4: Promo Links & Sites Settings
        self.tab_promos = self.tabview.add("🔗 Promo Links & Sites")
        self.tab_promos.grid_columnconfigure(0, weight=1)
        self.tab_promos.grid_rowconfigure(1, weight=1)

        self.promo_header = ctk.CTkFrame(self.tab_promos, fg_color="transparent")
        self.promo_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))

        self.promo_search_var = ctk.StringVar()
        self.promo_search_var.trace_add("write", lambda *_: self._populate_promo_links_tab())
        self.promo_search_entry = ctk.CTkEntry(
            self.promo_header,
            textvariable=self.promo_search_var,
            placeholder_text="Search promo site or URL...",
            width=240
        )
        self.promo_search_entry.pack(side="left", padx=(0, 10))

        self.btn_add_promo = ctk.CTkButton(
            self.promo_header,
            text="➕ Add Custom Link",
            width=140,
            height=24,
            fg_color="#1f538d",
            hover_color="#163f6e",
            command=self._open_add_promo_dialog
        )
        self.btn_add_promo.pack(side="left", padx=(0, 8))

        self.btn_reset_all_promos = ctk.CTkButton(
            self.promo_header,
            text="🔄 Reset All Defaults",
            width=140,
            height=24,
            fg_color="#444",
            hover_color="#555",
            command=self._reset_all_promos_action
        )
        self.btn_reset_all_promos.pack(side="left", padx=(0, 8))

        self.btn_save_promos = ctk.CTkButton(
            self.promo_header,
            text="💾 Save All Changes",
            width=140,
            height=24,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._save_all_promo_changes
        )
        self.btn_save_promos.pack(side="right")

        self.promo_scroll_frame = ctk.CTkScrollableFrame(self.tab_promos, fg_color="#1e1e1e")
        self.promo_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.promo_scroll_frame.grid_columnconfigure(0, weight=1)

    def _load_site_checkboxes(self):
        # Clear existing widgets from matrix frame
        for widget in self.sites_grid_frame.winfo_children():
            widget.destroy()

        promo_cfg = load_promo_config()
        cols = 3
        r, c = 0, 0
        old_vars = {k: v.get() for k, v in self.site_checkbox_vars.items()}
        self.site_checkbox_vars.clear()

        for site_id, cfg in promo_cfg.items():
            if not cfg.get("enabled", True):
                continue
            name = cfg.get("name", site_id)
            req_uk = cfg.get("requires_uk_ip", True)
            badge = "(Any IP)" if not req_uk else "(UK IP)"
            
            # Default to previous selected state if available, else True for fairplaybet
            init_val = old_vars.get(site_id, True if site_id == "fairplaybet" else False)
            var = ctk.BooleanVar(value=init_val)
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
            already = summary.get("ALREADY_REGISTERED", 0)
            total_processed = succ + fail + rev + already

            self.stats_label.configure(
                text=f"Total Processed: {total_processed} | ✅ Success: {succ} | ⚠️ Failed: {fail} | ⏳ KYC: {rev} | ℹ️ Existing: {already}"
            )
            self._populate_registered_accounts()
            self._populate_failures()
        except Exception:
            pass

    def _populate_registered_accounts(self):
        for widget in self.acc_scroll_frame.winfo_children():
            widget.destroy()
        try:
            state_mgr = StateManager()

            all_recs = state_mgr.get_all_records()
            records = [r for r in all_recs if r.get("status") in ("SUCCESS", "ALREADY_REGISTERED")]
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
                    text="No registered accounts found matching search query.",
                    font=ctk.CTkFont(size=13),
                    text_color="gray"
                )
                empty_lbl.pack(pady=30)
                return

            for idx, r in enumerate(records):
                status_val = r.get("status")
                is_already = (status_val == "ALREADY_REGISTERED")
                is_verified = bool(r.get("login_verified"))

                row_frame = ctk.CTkFrame(self.acc_scroll_frame, fg_color="#262626" if idx % 2 == 0 else "#2d2d2d", corner_radius=6)
                row_frame.pack(fill="x", padx=5, pady=3)

                client_id = r.get("client_id", "")
                site_id = r.get("site_id", "")
                email = r.get("email", "")
                password = r.get("password") or ""
                display_pwd = password if password else ("[Existing Account]" if is_already else "")
                shot_path = r.get("login_screenshot_path") or r.get("screenshot_path")

                # 1. Pack Action Buttons on the RIGHT FIRST (Guarantees they never get pushed off screen)
                def make_copy_cmd(pwd):
                    return lambda: self._copy_to_clipboard(pwd)

                def make_view_shot_cmd(shot):
                    if shot and Path(shot).exists():
                        try:
                            if sys.platform == "win32":
                                return lambda: os.startfile(str(shot))
                            return lambda: subprocess.Popen(f'explorer "{shot}"')
                        except Exception:
                            return lambda: subprocess.Popen(f'explorer "{shot}"')
                    return lambda: subprocess.Popen(f'explorer "{ARTIFACTS_DIR}"')

                copy_btn = ctk.CTkButton(
                    row_frame,
                    text="📋 Copy",
                    width=55,
                    height=26,
                    fg_color="#37474f",
                    hover_color="#455a64",
                    command=make_copy_cmd(display_pwd)
                )
                copy_btn.pack(side="right", padx=(4, 8), pady=6)

                shot_btn = ctk.CTkButton(
                    row_frame,
                    text="🖼️ Proof",
                    width=65,
                    height=26,
                    fg_color="#2e7d32" if is_verified else ("#e65100" if is_already else "#388e3c"),
                    hover_color="#1b5e20",
                    command=make_view_shot_cmd(shot_path)
                )
                shot_btn.pack(side="right", padx=(4, 4), pady=6)

                verify_btn = ctk.CTkButton(
                    row_frame,
                    text="🔑 Verify",
                    width=75,
                    height=26,
                    fg_color="#0277bd",
                    hover_color="#01579b"
                )
                c_name = r.get('client_name', '')
                s_name = r.get('site_name', '')
                verify_btn.configure(
                    command=lambda cid=client_id, sid=site_id, em=email, pw=password, cn=c_name, sn=s_name, btn=verify_btn: self._verify_single_account_action(cid, sid, em, pw, cn, sn, btn)
                )
                verify_btn.pack(side="right", padx=(4, 4), pady=6)

                # 2. Pack Status Badge and Info Labels on the LEFT
                err_summary = (r.get("error_summary") or "").lower()
                is_email_pending = any(k in err_summary for k in ["email", "activation", "inbox", "verify your email"])
                is_kyc_pending = any(k in err_summary for k in ["kyc", "more info", "proof of id", "document", "proof of address"])

                if is_already:
                    badge_text = "ℹ️ Existing"
                    badge_color = "#ffb74d"
                elif is_verified:
                    badge_text = "🔐 Verified"
                    badge_color = "#81c784"
                elif is_email_pending:
                    badge_text = "✉️ Email Pending"
                    badge_color = "#64b5f6"
                elif is_kyc_pending:
                    badge_text = "⚠️ KYC Pending"
                    badge_color = "#ffa726"
                else:
                    badge_text = "⏳ Unverified"
                    badge_color = "#ffa726"

                status_lbl = ctk.CTkLabel(
                    row_frame,
                    text=badge_text,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=badge_color,
                    width=95
                )
                status_lbl.pack(side="right", padx=(4, 8), pady=6)

                name_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"👤 {r.get('client_name', 'Unknown')}",
                    font=ctk.CTkFont(weight="bold", size=13),
                    anchor="w",
                    width=130
                )
                name_lbl.pack(side="left", padx=8, pady=6)

                site_badge = ctk.CTkLabel(
                    row_frame,
                    text=f"🎯 {r.get('site_name', r.get('site_id', 'Site'))}",
                    font=ctk.CTkFont(size=12),
                    text_color="#64b5f6",
                    anchor="w",
                    width=95
                )
                site_badge.pack(side="left", padx=4, pady=6)

                email_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"✉️ {email}",
                    font=ctk.CTkFont(size=12),
                    text_color="#cfd8dc",
                    anchor="w",
                    width=175
                )
                email_lbl.pack(side="left", padx=4, pady=6)

                pwd_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"🔑 {display_pwd}",
                    font=ctk.CTkFont(family="Consolas", size=12),
                    text_color="#aed581" if password else "#b0bec5",
                    anchor="w",
                    width=115
                )
                pwd_lbl.pack(side="left", padx=4, pady=6)

        except Exception as e:
            logger.error(f"Failed to populate registered accounts: {e}")

    def _populate_failures(self):
        for widget in self.fail_scroll_frame.winfo_children():
            widget.destroy()

        self.failure_checkbox_vars.clear()

        try:
            state_mgr = StateManager()
            all_recs = state_mgr.get_all_records()
            all_fails = [r for r in all_recs if r.get("status") in ("FAILED", "MANUAL_REVIEW")]

            # Dynamically update website filter dropdown values
            unique_sites = sorted(list({(r.get("site_name") or r.get("site_id") or "") for r in all_fails if (r.get("site_name") or r.get("site_id"))}))
            site_options = ["All Websites"] + unique_sites
            if hasattr(self, "fail_site_filter"):
                self.fail_site_filter.configure(values=site_options)
                if self.fail_site_filter_var.get() not in site_options:
                    self.fail_site_filter_var.set("All Websites")

            selected_site = self.fail_site_filter_var.get().strip() if hasattr(self, "fail_site_filter_var") else "All Websites"
            search_query = self.fail_search_var.get().strip().lower() if hasattr(self, "fail_search_var") else ""

            fails = all_fails

            # Filter by selected website dropdown
            if selected_site and selected_site != "All Websites":
                fails = [
                    r for r in fails
                    if (r.get("site_name") or "").lower() == selected_site.lower()
                    or (r.get("site_id") or "").lower() == selected_site.lower()
                ]

            # Filter by search text query
            if search_query:
                fails = [
                    r for r in fails
                    if search_query in (r.get("site_name") or "").lower()
                    or search_query in (r.get("site_id") or "").lower()
                    or search_query in (r.get("client_name") or "").lower()
                    or search_query in (r.get("client_id") or "").lower()
                    or search_query in (r.get("email") or "").lower()
                    or search_query in (r.get("error_summary") or "").lower()
                ]

            if len(fails) < len(all_fails):
                self.fail_count_label.configure(text=f"Total: {len(all_fails)} failures ({len(fails)} matching)")
            else:
                self.fail_count_label.configure(text=f"Total: {len(all_fails)} failures")

            if not all_fails:
                self.select_all_fails_var.set(False)
                self._on_failure_selection_change()
                empty_lbl = ctk.CTkLabel(
                    self.fail_scroll_frame,
                    text="🎉 No failed registrations or exceptions recorded!",
                    font=ctk.CTkFont(size=13),
                    text_color="#81c784"
                )
                empty_lbl.pack(pady=30)
                return

            if not fails:
                self.select_all_fails_var.set(False)
                self._on_failure_selection_change()
                empty_lbl = ctk.CTkLabel(
                    self.fail_scroll_frame,
                    text="🔍 No failure records match the current website / search filter.",
                    font=ctk.CTkFont(size=13),
                    text_color="#ffa726"
                )
                empty_lbl.pack(pady=30)
                return

            for idx, r in enumerate(fails):
                status_val = r.get("status")
                is_review = (status_val == "MANUAL_REVIEW")
                row_frame = ctk.CTkFrame(
                    self.fail_scroll_frame,
                    fg_color="#33241b" if is_review else "#2d1f1f",
                    corner_radius=6
                )
                row_frame.pack(fill="x", padx=5, pady=3)

                client_id = r.get("client_id", "")
                site_id = r.get("site_id", "")
                client_name = r.get("client_name", "")
                site_name = r.get("site_name", "")
                password = r.get("password") or ""
                email = r.get("email") or ""

                # Register checkbox variable for this row
                chk_var = ctk.BooleanVar(value=False)
                self.failure_checkbox_vars[(client_id, site_id)] = (chk_var, dict(r))

                # Action buttons packed to right first
                dismiss_btn = ctk.CTkButton(
                    row_frame,
                    text="🗑️ Dismiss",
                    width=70,
                    height=24,
                    fg_color="#444",
                    hover_color="#555",
                    command=lambda cid=client_id, sid=site_id: self._dismiss_single_failure_action(cid, sid)
                )
                dismiss_btn.pack(side="right", padx=(4, 8), pady=8)

                if password:
                    copy_btn = ctk.CTkButton(
                        row_frame,
                        text="📋 Copy Pwd",
                        width=80,
                        height=24,
                        fg_color="#37474f",
                        hover_color="#455a64",
                        command=lambda p=password: self._copy_to_clipboard(p)
                    )
                    copy_btn.pack(side="right", padx=(4, 4), pady=8)

                retry_btn = ctk.CTkButton(
                    row_frame,
                    text="🔁 Retry",
                    width=65,
                    height=24,
                    fg_color="#1565c0",
                    hover_color="#0d47a1"
                )
                retry_btn.configure(
                    command=lambda cid=client_id, sid=site_id, cn=client_name, sn=site_name, btn=retry_btn: self._retry_single_failed_action(cid, sid, cn, sn, btn)
                )
                retry_btn.pack(side="right", padx=(4, 4), pady=8)

                shot_path = r.get("screenshot_path")
                if shot_path and Path(shot_path).exists():
                    def make_view_cmd(p):
                        return lambda: subprocess.Popen(f'explorer "{p}"')
                    view_btn = ctk.CTkButton(
                        row_frame, text="🖼️ Proof", width=65, height=24, fg_color="#b71c1c" if not is_review else "#e65100", command=make_view_cmd(shot_path)
                    )
                    view_btn.pack(side="right", padx=(4, 4), pady=8)

                # Selection checkbox on the left
                chk = ctk.CTkCheckBox(
                    row_frame,
                    text="",
                    variable=chk_var,
                    width=22,
                    height=22,
                    checkbox_width=18,
                    checkbox_height=18,
                    command=self._on_failure_selection_change
                )
                chk.pack(side="left", padx=(8, 4), pady=8)

                # Badge label
                badge_lbl = ctk.CTkLabel(
                    row_frame,
                    text="⚠️ KYC Review" if is_review else "❌ Failed",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#ffa726" if is_review else "#ef5350",
                    width=85
                )
                badge_lbl.pack(side="left", padx=(4, 4), pady=8)

                info_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f"{client_name} ({site_name}): {r.get('error_summary', 'Unknown error')}",
                    font=ctk.CTkFont(size=12),
                    text_color="#ffe0b2" if is_review else "#ef9a9a",
                    anchor="w"
                )
                info_lbl.pack(side="left", padx=4, pady=8, fill="x", expand=True)

            self.select_all_fails_var.set(False)
            self._on_failure_selection_change()

        except Exception as e:
            logger.error(f"Failed to populate failures: {e}")

    def _on_failure_selection_change(self):
        """Updates selection label and enables/disables batch action buttons based on checked items."""
        selected_count = sum(1 for var, _ in self.failure_checkbox_vars.values() if var.get())
        total_count = len(self.failure_checkbox_vars)

        self.fail_selected_label.configure(text=f"({selected_count} selected)")

        # Sync Select All checkbox state without recursive feedback
        if total_count > 0 and selected_count == total_count:
            self.select_all_fails_var.set(True)
        else:
            self.select_all_fails_var.set(False)

        # Update button states
        is_active = not self.is_running
        if selected_count > 0 and is_active:
            self.btn_retry_selected_fails.configure(
                text=f"🔁 Retry Selected ({selected_count})",
                state="normal"
            )
            self.btn_dismiss_selected_fails.configure(
                text=f"🗑️ Dismiss Selected ({selected_count})",
                state="normal",
                fg_color="#8e0000",
                hover_color="#c62828"
            )
        else:
            self.btn_retry_selected_fails.configure(
                text=f"🔁 Retry Selected ({selected_count})",
                state="disabled"
            )
            self.btn_dismiss_selected_fails.configure(
                text=f"🗑️ Dismiss Selected ({selected_count})",
                state="disabled",
                fg_color="#444",
                hover_color="#555"
            )

    def _toggle_select_all_failures(self):
        """Toggles all failure item checkboxes based on the master checkbox."""
        new_val = self.select_all_fails_var.get()
        for var, _ in self.failure_checkbox_vars.values():
            var.set(new_val)
        self._on_failure_selection_change()

    def _dismiss_selected_failures_action(self):
        """Dismisses and deletes all currently selected failure records from the state database."""
        selected_keys = [k for k, (var, _) in self.failure_checkbox_vars.items() if var.get()]
        if not selected_keys:
            return

        confirm = messagebox.askyesno(
            "Dismiss Selected Failures",
            f"Are you sure you want to dismiss {len(selected_keys)} selected failure record(s)?\n\n"
            f"This will remove them from the failure list and reset their status to pending."
        )
        if confirm:
            try:
                state_mgr = StateManager()
                deleted = state_mgr.reset_records(selected_keys)
                logger.info(f"Dismissed {deleted} selected failed record(s) from state database.")
                self._populate_failures()
                self._update_stats_display()
                messagebox.showinfo("Failures Dismissed", f"Successfully dismissed {deleted} failure record(s).")
            except Exception as e:
                logger.error(f"Failed to dismiss selected failures: {e}")
                messagebox.showerror("Error", f"Failed to dismiss failures: {e}")

    def _retry_selected_failures_action(self):
        """Executes fresh registration for all selected failed client-site pairs in sequence."""
        selected_items = [
            (k[0], k[1], meta)
            for k, (var, meta) in self.failure_checkbox_vars.items()
            if var.get()
        ]
        if not selected_items:
            return

        if self.is_running:
            messagebox.showwarning("Process Running", "An automation or retry process is already running. Please wait or stop it first.")
            return

        confirm = messagebox.askyesno(
            "Retry Selected Failures",
            f"Are you sure you want to run fresh registration for {len(selected_items)} selected record(s)?"
        )
        if not confirm:
            return

        source = "excel" if self.src_selector.get() == "Excel (.xlsx)" else "sheets"
        excel_path = Path(self.excel_path_var.get())
        sheet_url = self.sheets_url_var.get()
        headed = "Visible" in self.browser_mode_selector.get()
        verify_login = self.auto_verify_var.get()

        self.is_running = True
        self.stop_requested = False
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_dry_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_retry_selected_fails.configure(state="disabled")
        self.btn_dismiss_selected_fails.configure(state="disabled")
        self.status_badge.configure(text=f"● RETRYING (0/{len(selected_items)})", text_color="#ffa726")
        self.progress_bar.set(0.05)

        def worker():
            total = len(selected_items)
            succeeded = 0
            failed = 0
            try:
                provider = get_data_provider(source=source, excel_path=excel_path, sheet_url=sheet_url)
                clients = provider.get_valid_clients()
                client_map = {c.client_id: c for c in clients}
                name_map = {c.full_name.lower(): c for c in clients}

                logger.info(f"🚀 Starting batch fresh retry for {total} selected failed record(s)...")

                for idx, (cid, sid, meta) in enumerate(selected_items, 1):
                    if self.stop_event.is_set() or self.stop_requested:
                        logger.warning(f"⏹ Batch retry stopped by user after {idx - 1}/{total} records.")
                        break

                    cname = meta.get("client_name", cid)
                    sname = meta.get("site_name", sid)

                    self.after(0, lambda i=idx, t=total: [
                        self.status_badge.configure(text=f"● RETRYING ({i}/{t})", text_color="#ffa726"),
                        self.progress_bar.set(i / t)
                    ])

                    target_client = client_map.get(cid) or name_map.get(cname.lower())
                    if not target_client:
                        logger.error(f"[{idx}/{total}] Could not locate client '{cname}' ({cid}) in data provider source.")
                        failed += 1
                        continue

                    logger.info(f"[{idx}/{total}] Fresh re-registration: {cname} on {sname} ({sid})")
                    try:
                        result = register_single_account(
                            client=target_client,
                            site_id=sid,
                            provider=provider,
                            headed=headed,
                            verify_login=verify_login
                        )
                        if result.status == RegistrationStatus.SUCCESS:
                            succeeded += 1
                            logger.info(f"[{idx}/{total}] ✅ Successfully registered {cname} on {sname}!")
                        else:
                            failed += 1
                            logger.warning(f"[{idx}/{total}] ❌ Retry failed for {cname} on {sname}: {result.error_summary}")
                    except Exception as ex:
                        failed += 1
                        logger.error(f"[{idx}/{total}] Exception during retry for {cname} on {sname}: {ex}")

                summary_msg = (
                    f"Batch Fresh Retry Finished!\n\n"
                    f"Total Processed: {succeeded + failed}/{total}\n"
                    f"✅ Succeeded: {succeeded}\n"
                    f"❌ Failed: {failed}"
                )
                if self.stop_event.is_set() or self.stop_requested:
                    summary_msg += "\n\n⚠️ Process was stopped before completing all records."

                self.after(0, lambda: messagebox.showinfo("Batch Retry Complete", summary_msg))

            except Exception as e:
                logger.error(f"Batch retry worker encountered error: {e}")
                self.after(0, lambda err_s=str(e): messagebox.showerror("Batch Retry Error", f"Error during batch retry: {err_s}"))
            finally:
                self.is_running = False
                self.stop_requested = False
                self.after(0, lambda: [
                    self.btn_start.configure(state="normal"),
                    self.btn_dry_run.configure(state="normal"),
                    self.btn_stop.configure(state="disabled"),
                    self.status_badge.configure(text="● READY", text_color="#81c784"),
                    self.progress_bar.set(0),
                    self._populate_registered_accounts(),
                    self._populate_failures(),
                    self._update_stats_display()
                ])

        threading.Thread(target=worker, daemon=True).start()

    def _retry_single_failed_action(self, client_id: str, site_id: str, client_name: str, site_name: str, btn: ctk.CTkButton):
        """Retries registration for a single failed client/site combination."""
        btn.configure(state="disabled", text="⏳ Retrying...")
        source = "excel" if self.src_selector.get() == "Excel (.xlsx)" else "sheets"
        excel_path = Path(self.excel_path_var.get())
        sheet_url = self.sheets_url_var.get()
        provider = get_data_provider(source=source, excel_path=excel_path, sheet_url=sheet_url)
        headed = "Visible" in self.browser_mode_selector.get()
        verify_login = self.auto_verify_var.get()

        def worker():
            try:
                logger.info(f"Retrying single failed registration for {client_name} ({client_id}) on {site_name} ({site_id})")
                clients = provider.get_valid_clients()
                target_client = next((c for c in clients if c.client_id == client_id), None)
                if not target_client:
                    target_client = next((c for c in clients if c.full_name.lower() == client_name.lower()), None)

                if not target_client:
                    logger.error(f"Could not locate client '{client_name}' ({client_id}) in data provider source.")
                    self.after(0, lambda: messagebox.showerror("Client Not Found", f"Could not locate '{client_name}' in the data source to retry."))
                    return

                result = register_single_account(
                    client=target_client,
                    site_id=site_id,
                    provider=provider,
                    headed=headed,
                    verify_login=verify_login
                )

                if result.status == RegistrationStatus.SUCCESS:
                    logger.info(f"🎉 Retry successful for {client_name} on {site_name}!")
                    self.after(0, lambda: messagebox.showinfo("Registration Successful", f"Account successfully created for {client_name} on {site_name}!"))
                else:
                    logger.warning(f"❌ Retry failed for {client_name} on {site_name}: {result.error_summary}")
                    self.after(0, lambda: messagebox.showwarning("Registration Failed", f"Retry registration failed for {client_name} on {site_name}:\n\n{result.error_summary}"))
            except Exception as e:
                logger.error(f"Error retrying registration for {client_id}: {e}")
                self.after(0, lambda err_s=str(e): messagebox.showerror("Retry Error", f"Error during retry registration: {err_s}"))
            finally:
                self.after(0, lambda: self._populate_registered_accounts())
                self.after(0, lambda: self._populate_failures())
                self.after(0, lambda: self._update_stats_display())

        threading.Thread(target=worker, daemon=True).start()

    def _dismiss_single_failure_action(self, client_id: str, site_id: str):
        try:
            state_mgr = StateManager()
            state_mgr.reset_record(client_id, site_id)
            self._populate_failures()
            self._update_stats_display()
        except Exception as e:
            logger.error(f"Failed to dismiss failure record: {e}")

    def _clear_all_failures_action(self):
        confirm = messagebox.askyesno(
            "Clear All Failures",
            "Are you sure you want to clear all recorded failures?\n\nThis will reset their status to pending so they can be re-evaluated."
        )
        if confirm:
            try:
                state_mgr = StateManager()
                deleted = state_mgr.reset_all_failed()
                logger.info(f"Cleared {deleted} failed record(s) from state database.")
                self._populate_failures()
                self._update_stats_display()
                messagebox.showinfo("Failures Cleared", f"Successfully cleared {deleted} failure record(s).")
            except Exception as e:
                logger.error(f"Failed to clear failures: {e}")
                messagebox.showerror("Error", f"Failed to clear failures: {e}")

    def _verify_single_account_action(self, client_id: str, site_id: str, email: str, password: str, client_name: str, site_name: str, btn: ctk.CTkButton):
        """Launches on-demand visible login verification for a single registered account."""
        btn.configure(state="disabled", text="⏳ Testing...")

        # Build a fresh provider from current GUI settings (self.provider is never stored on the instance)
        source = "excel" if self.src_selector.get() == "Excel (.xlsx)" else "sheets"
        excel_path = Path(self.excel_path_var.get())
        sheet_url = self.sheets_url_var.get()
        provider = get_data_provider(source=source, excel_path=excel_path, sheet_url=sheet_url)

        def worker():
            try:
                logger.info(f"Starting visible login verification for {client_id} ({email}) on {site_id}")
                success, proof_path, err = verify_single_account(
                    client_id=client_id,
                    site_id=site_id,
                    email=email,
                    password=password,
                    client_name=client_name,
                    site_name=site_name,
                    headed=True,
                    provider=provider
                )
                if success:
                    logger.info(f"🎉 Login verified successfully for {email}! Proof: {proof_path}")
                    self.after(0, lambda: messagebox.showinfo("Login Verified", f"Account successfully logged in!\n\nProof saved:\n{proof_path}"))
                elif is_pending_verification_error(err or ""):
                    logger.info(f"ℹ️ Account credentials valid for {email}, but pending user activation: {err}")
                    self.after(0, lambda: messagebox.showinfo(
                        "Account Created — Activation Required",
                        f"Account credentials are valid for {client_name or email} on {site_name or site_id}!\n\n"
                        f"Status: {err}\n\n"
                        f"The credentials remain safely saved in your spreadsheet. The user needs to verify their email or upload documents before logging in."
                    ))
                else:
                    logger.warning(f"❌ Login verification rejected for {email}: {err}")
                    self.after(0, lambda: messagebox.showwarning(
                        "Login Verification Failed",
                        f"Login verification failed for {client_name or email} on {site_name or site_id}:\n\n{err}\n\nFalse positive record was removed from the spreadsheet."
                    ))
            except Exception as e:
                logger.error(f"Exception during manual verification: {e}")
                self.after(0, lambda err_s=str(e): messagebox.showerror("Verification Error", f"Error during verification: {err_s}"))
            finally:
                self.after(0, lambda: self._update_stats_display())

        threading.Thread(target=worker, daemon=True).start()



    def _copy_to_clipboard(self, text: str):

        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Password copied to clipboard!")

    def _poll_log_queue(self):
        """Drains the log queue and appends entries to the textbox."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.log_textbox.insert("end", msg)
                self.log_textbox.see("end")
            except Exception:
                break

        try:
            if self.winfo_exists():
                self.after(100, self._poll_log_queue)
        except Exception:
            pass

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
        verify_login = self.auto_verify_var.get()
        retry_failed = False

        self.is_running = True
        self.stop_requested = False
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_dry_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_retry_selected_fails.configure(state="disabled")
        self.btn_dismiss_selected_fails.configure(state="disabled")
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
                    site_adapters=adapters,
                    stop_event=self.stop_event
                )
                self.current_engine = engine

                engine.run(
                    limit=limit,
                    client_id_filter=client_filter,
                    site_filters=selected_sites,
                    dry_run=dry_run,
                    verify_login=verify_login,
                    retry_failed=retry_failed,
                    on_progress=lambda res, st: self.after(0, self._on_single_record_progress)
                )

            except Exception as e:
                logger.error(f"Error in automation engine: {e}")
            finally:
                self.is_running = False
                self.current_engine = None
                try:
                    self.after(0, self._on_task_finished)
                except Exception:
                    pass

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _on_single_record_progress(self):
        """Called live in real-time on GUI main thread as each record completes."""
        self._update_stats_display()

    def _stop_automation(self):
        if not self.is_running:
            return
        self.stop_requested = True
        self.stop_event.set()
        if self.current_engine:
            self.current_engine.request_stop()
        self.status_badge.configure(text="● STOPPING...", text_color="#ef5350")
        logger.warning("Stop requested by user. Terminating process cleanly after current step...")
        self.btn_stop.configure(state="disabled")

    def _on_task_finished(self):
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_dry_run.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        if self.stop_requested:
            self.status_badge.configure(text="● STOPPED", text_color="#ef5350")
            logger.info("Automation stopped by user.")
        else:
            self.status_badge.configure(text="● COMPLETED", text_color="#81c784")
            self.progress_bar.set(1.0)
        self.stop_requested = False
        self._update_stats_display()
        self._on_failure_selection_change()

    def _on_window_closing(self):
        """Cleanly shuts down worker threads and browsers when closing the application."""
        if self.is_running:
            self.stop_requested = True
            self.stop_event.set()
            if self.current_engine:
                try:
                    self.current_engine.request_stop()
                except Exception:
                    pass
        self.destroy()

    def destroy(self):
        try:
            if hasattr(self, "gui_sink_id"):
                logger.remove(self.gui_sink_id)
        except Exception:
            pass
        super().destroy()

    def _populate_promo_links_tab(self):
        """Populates the Promo Links & Sites settings tab with interactive editable cards."""
        for widget in self.promo_scroll_frame.winfo_children():
            widget.destroy()

        self.promo_field_entries: Dict[str, dict] = {}
        promo_cfg = load_promo_config()
        search = self.promo_search_var.get().strip().lower()

        for site_id, cfg in promo_cfg.items():
            name = cfg.get("name", site_id)
            url = cfg.get("url", "")
            link_type = cfg.get("link_type", "direct_promo")
            req_uk = cfg.get("requires_uk_ip", True)
            enabled = cfg.get("enabled", True)
            notes = cfg.get("notes", "")

            if search and search not in name.lower() and search not in url.lower() and search not in site_id.lower():
                continue

            card = ctk.CTkFrame(self.promo_scroll_frame, fg_color="#262626", corner_radius=8)
            card.pack(fill="x", padx=5, pady=6)

            # --- Row 0: Site Title, Badges, and Enabled Switch ---
            top_bar = ctk.CTkFrame(card, fg_color="transparent")
            top_bar.pack(fill="x", padx=12, pady=(10, 4))

            title_lbl = ctk.CTkLabel(
                top_bar,
                text=f"🎯 {name}",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            title_lbl.pack(side="left", padx=(0, 10))

            id_badge = ctk.CTkLabel(
                top_bar,
                text=f"id: {site_id}",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            id_badge.pack(side="left", padx=(0, 10))

            ip_badge_text = "🇬🇧 UK IP" if req_uk else "🌐 Any IP"
            ip_badge_color = "#3949ab" if req_uk else "#00897b"
            ip_lbl = ctk.CTkLabel(
                top_bar,
                text=ip_badge_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=ip_badge_color
            )
            ip_lbl.pack(side="left", padx=(0, 10))

            type_lbl = ctk.CTkLabel(
                top_bar,
                text=f"[{link_type.replace('_', ' ').title()}]",
                font=ctk.CTkFont(size=11),
                text_color="#90a4ae"
            )
            type_lbl.pack(side="left")

            enabled_var = ctk.BooleanVar(value=enabled)
            enable_switch = ctk.CTkSwitch(
                top_bar,
                text="Active" if enabled else "Inactive",
                variable=enabled_var,
                font=ctk.CTkFont(size=12)
            )
            enable_switch.pack(side="right")

            # --- Row 1: URL Input Field & Actions ---
            url_frame = ctk.CTkFrame(card, fg_color="transparent")
            url_frame.pack(fill="x", padx=12, pady=(4, 6))

            url_lbl = ctk.CTkLabel(url_frame, text="Promo URL:", font=ctk.CTkFont(weight="bold", size=12), width=80, anchor="w")
            url_lbl.pack(side="left", padx=(0, 5))

            url_var = ctk.StringVar(value=url)
            url_entry = ctk.CTkEntry(url_frame, textvariable=url_var, font=ctk.CTkFont(family="Consolas", size=12))
            url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

            # Store references
            self.promo_field_entries[site_id] = {
                "name": name,
                "url_var": url_var,
                "url_entry": url_entry,
                "enabled_var": enabled_var,
                "requires_uk_ip": req_uk,
                "link_type": link_type,
                "notes": notes
            }

            # Action Buttons
            btn_test = ctk.CTkButton(
                url_frame,
                text="🌐 Test",
                width=65,
                height=26,
                fg_color="#0277bd",
                hover_color="#01579b",
                command=lambda v=url_var: self._test_url_in_browser(v.get())
            )
            btn_test.pack(side="right", padx=(3, 0))

            btn_copy = ctk.CTkButton(
                url_frame,
                text="📋 Copy",
                width=65,
                height=26,
                fg_color="#37474f",
                hover_color="#455a64",
                command=lambda v=url_var: self._copy_to_clipboard(v.get())
            )
            btn_copy.pack(side="right", padx=(3, 0))

            if site_id in DEFAULT_PROMO_LINKS:
                btn_reset = ctk.CTkButton(
                    url_frame,
                    text="🔄 Reset",
                    width=65,
                    height=26,
                    fg_color="#455a64",
                    hover_color="#546e7a",
                    command=lambda s=site_id, v=url_var: self._reset_single_promo_ui(s, v)
                )
                btn_reset.pack(side="right", padx=(3, 0))
            else:
                btn_del = ctk.CTkButton(
                    url_frame,
                    text="🗑️ Delete",
                    width=65,
                    height=26,
                    fg_color="#b71c1c",
                    hover_color="#d32f2f",
                    command=lambda s=site_id: self._delete_promo_action(s)
                )
                btn_del.pack(side="right", padx=(3, 0))

            # --- Row 2: Notes / Warning info if applicable ---
            if notes:
                notes_frame = ctk.CTkFrame(card, fg_color="transparent")
                notes_frame.pack(fill="x", padx=12, pady=(0, 8))
                notes_lbl = ctk.CTkLabel(
                    notes_frame,
                    text=f"ℹ️ Note: {notes}",
                    font=ctk.CTkFont(size=11),
                    text_color="#ffa726",
                    anchor="w"
                )
                notes_lbl.pack(side="left")

    def _test_url_in_browser(self, url: str):
        if not url or not is_valid_url(url):
            messagebox.showwarning("Invalid URL", f"The URL '{url}' is not a valid HTTP/HTTPS URL.")
            return
        logger.info(f"Opening promo URL in default web browser: {url}")
        webbrowser.open(url)

    def _reset_single_promo_ui(self, site_id: str, url_var: ctk.StringVar):
        if site_id in DEFAULT_PROMO_LINKS:
            default_url = DEFAULT_PROMO_LINKS[site_id]["url"]
            url_var.set(default_url)
            logger.info(f"Reverted URL for '{site_id}' to factory default in UI.")

    def _save_all_promo_changes(self):
        new_config: Dict[str, dict] = {}
        for site_id, field in self.promo_field_entries.items():
            name = field["name"]
            url = field["url_var"].get().strip()
            enabled = field["enabled_var"].get()
            requires_uk_ip = field["requires_uk_ip"]
            link_type = field["link_type"]
            notes = field["notes"]

            if not url or not is_valid_url(url):
                messagebox.showerror(
                    "Invalid URL Detected",
                    f"The URL for '{name}' ({site_id}) is invalid:\n\n'{url}'\n\nPlease ensure it starts with http:// or https://"
                )
                field["url_entry"].focus()
                return

            new_config[site_id] = {
                "name": name,
                "url": url,
                "link_type": link_type,
                "enabled": enabled,
                "requires_uk_ip": requires_uk_ip
            }
            if notes:
                new_config[site_id]["notes"] = notes

        if save_promo_config(new_config):
            self._load_site_checkboxes()
            self._populate_promo_links_tab()
            logger.info("Saved all promo links and site settings successfully.")
            messagebox.showinfo("Saved", "All promo link changes have been saved successfully!")
        else:
            messagebox.showerror("Save Error", "Failed to write changes to promo_links.json.")

    def _reset_all_promos_action(self):
        confirm = messagebox.askyesno(
            "Reset All Promo Links",
            "Are you sure you want to reset ALL promo URLs and site configurations to factory defaults?\n\nThis will restore all official tested URLs."
        )
        if confirm:
            reset_promo_to_default(None)
            self._load_site_checkboxes()
            self._populate_promo_links_tab()
            logger.info("Reset all promo URLs to factory defaults.")
            messagebox.showinfo("Reset Complete", "All promo links have been reset to factory defaults.")

    def _delete_promo_action(self, site_id: str):
        confirm = messagebox.askyesno(
            "Delete Link",
            f"Are you sure you want to delete custom link '{site_id}'?"
        )
        if confirm:
            delete_custom_promo_link(site_id)
            self._load_site_checkboxes()
            self._populate_promo_links_tab()

    def _open_add_promo_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Promo / Affiliate Link")
        dialog.geometry("520x470")
        dialog.resizable(False, False)
        dialog.grab_set()

        title_lbl = ctk.CTkLabel(
            dialog,
            text="➕ Add New Bookmaker / Promo Link",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_lbl.pack(padx=20, pady=(20, 15), anchor="w")

        id_lbl = ctk.CTkLabel(dialog, text="Site Identifier (Unique, e.g. 'bettinglounge_3'):", font=ctk.CTkFont(size=12, weight="bold"))
        id_lbl.pack(padx=20, pady=(5, 2), anchor="w")
        id_entry = ctk.CTkEntry(dialog, placeholder_text="e.g. bettinglounge_3")
        id_entry.pack(fill="x", padx=20, pady=(0, 10))

        name_lbl = ctk.CTkLabel(dialog, text="Display Name (e.g. 'Betting Lounge #3'):", font=ctk.CTkFont(size=12, weight="bold"))
        name_lbl.pack(padx=20, pady=(5, 2), anchor="w")
        name_entry = ctk.CTkEntry(dialog, placeholder_text="e.g. Betting Lounge #3")
        name_entry.pack(fill="x", padx=20, pady=(0, 10))

        url_lbl = ctk.CTkLabel(dialog, text="Target / Promo URL:", font=ctk.CTkFont(size=12, weight="bold"))
        url_lbl.pack(padx=20, pady=(5, 2), anchor="w")
        url_entry = ctk.CTkEntry(dialog, placeholder_text="https://...")
        url_entry.pack(fill="x", padx=20, pady=(0, 10))

        options_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        options_frame.pack(fill="x", padx=20, pady=(5, 10))

        type_lbl = ctk.CTkLabel(options_frame, text="Link Type:", font=ctk.CTkFont(size=12, weight="bold"))
        type_lbl.pack(side="left", padx=(0, 10))
        type_opt = ctk.CTkOptionMenu(
            options_frame,
            values=["affiliate_redirect", "direct_promo", "direct"]
        )
        type_opt.set("affiliate_redirect")
        type_opt.pack(side="left", padx=(0, 20))

        uk_ip_var = ctk.BooleanVar(value=True)
        uk_ip_switch = ctk.CTkSwitch(options_frame, text="Requires UK IP", variable=uk_ip_var)
        uk_ip_switch.pack(side="left")

        notes_lbl = ctk.CTkLabel(dialog, text="Notes (Optional):", font=ctk.CTkFont(size=12))
        notes_lbl.pack(padx=20, pady=(5, 2), anchor="w")
        notes_entry = ctk.CTkEntry(dialog, placeholder_text="e.g. Campaign expires Dec 2026")
        notes_entry.pack(fill="x", padx=20, pady=(0, 15))

        def save_new():
            site_id = id_entry.get().strip().lower().replace(" ", "_")
            site_name = name_entry.get().strip()
            url = url_entry.get().strip()
            link_type = type_opt.get()
            req_uk = uk_ip_var.get()
            notes = notes_entry.get().strip()

            if not site_id:
                messagebox.showwarning("Missing Site ID", "Please enter a unique Site Identifier.", parent=dialog)
                return
            if not site_name:
                messagebox.showwarning("Missing Name", "Please enter a Display Name.", parent=dialog)
                return
            if not url or not is_valid_url(url):
                messagebox.showwarning("Invalid URL", "Please enter a valid HTTP or HTTPS URL.", parent=dialog)
                return

            ok = add_or_update_promo_link(
                site_id=site_id,
                name=site_name,
                url=url,
                enabled=True,
                requires_uk_ip=req_uk,
                link_type=link_type,
                notes=notes
            )
            if ok:
                self._load_site_checkboxes()
                self._populate_promo_links_tab()
                dialog.destroy()
                messagebox.showinfo("Success", f"Promo link '{site_name}' added successfully!")
            else:
                messagebox.showerror("Error", "Failed to add promo link.", parent=dialog)

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(5, 15))

        btn_cancel = ctk.CTkButton(btn_row, text="Cancel", fg_color="#444", hover_color="#555", command=dialog.destroy, width=100)
        btn_cancel.pack(side="right", padx=(10, 0))

        btn_save = ctk.CTkButton(btn_row, text="Add Link", fg_color="#2e7d32", hover_color="#1b5e20", command=save_new, width=120)
        btn_save.pack(side="right")

    def _maximize_window(self):
        try:
            self.state("zoomed")
        except Exception:
            pass


def run_gui():
    app = DataEntryBotGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()

