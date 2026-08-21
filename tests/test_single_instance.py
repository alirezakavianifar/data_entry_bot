import sys
import subprocess
from gui_app import ensure_single_instance


def test_duplicate_instance_exits():
    """Verify that launching a secondary instance when the app is active exits cleanly."""
    lock = ensure_single_instance()
    try:
        proc = subprocess.run([sys.executable, "gui_app.py"], capture_output=True, text=True, timeout=5)
        assert proc.returncode == 0
        assert "already running" in proc.stdout.lower()
    finally:
        pass


