import time
import pytest
from gui.main_gui import DataEntryBotGUI


def test_gui_initialization():
    app = DataEntryBotGUI()
    assert "Data Entry Bot" in app.title()
    assert app.is_running is False
    assert len(app.site_checkbox_vars) > 0
    app.update()
    app.destroy()


def test_gui_source_switching_and_dry_run():
    app = DataEntryBotGUI()
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

    app.destroy()
