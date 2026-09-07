import time
import pytest
from gui.main_gui import DataEntryBotGUI
from sites import DEFAULT_PROMO_LINKS, load_promo_config


def test_gui_lifecycle_and_dry_run():
    """Validates GUI initialization, source switching, promo tabs, and dry run execution."""
    app = DataEntryBotGUI()
    try:
        assert "Data Entry Bot" in app.title()
        assert app.is_running is False
        assert len(app.site_checkbox_vars) > 0
        app.update()

        # Source switching
        app._on_source_changed("Google Sheets")
        app.update()
        assert not app.excel_frame.winfo_ismapped()

        app._on_source_changed("Excel (.xlsx)")
        app.update()
        assert app.excel_frame.winfo_ismapped()

        # Site selection
        app._clear_all_sites()
        assert all(not var.get() for var in app.site_checkbox_vars.values())
        app._select_stage1_only()
        assert app.site_checkbox_vars["fairplaybet"].get() is True

        # Phase 2 site selection test
        app._select_phase2_only()
        phase2_keys = ["bettom", "easybet", "247bet", "paddypower", "betfair", "dragonbet"]
        for p2 in phase2_keys:
            assert app.site_checkbox_vars[p2].get() is True
        assert app.site_checkbox_vars["fairplaybet"].get() is False

        # Promo Links tab validation
        assert hasattr(app, "tab_promos")
        assert len(app.promo_field_entries) > 0
        assert "fairplaybet" in app.promo_field_entries
        for p2 in phase2_keys:
            assert p2 in app.promo_field_entries
            assert app.promo_field_entries[p2]["url_var"].get().startswith("http")
        assert app.promo_field_entries["fairplaybet"]["url_var"].get().startswith("http")

        # Dry-Run execution from GUI
        app.limit_slider.set(2)
        app._start_dry_run()

        max_wait = 15
        start_t = time.time()
        while app.is_running and (time.time() - start_t) < max_wait:
            app.update()
            time.sleep(0.05)

        app.update()
        log_text = app.log_textbox.get("1.0", "end")
        assert "Starting automation run" in log_text or "Valid Client" in log_text
    finally:
        app.destroy()
