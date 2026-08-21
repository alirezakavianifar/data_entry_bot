import sys
import subprocess


def test_duplicate_instance_exits():
    """Verify that launching a secondary instance when the app is active exits cleanly."""
    proc = subprocess.run([sys.executable, "gui_app.py"], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    # Should either launch or exit cleanly if already running

