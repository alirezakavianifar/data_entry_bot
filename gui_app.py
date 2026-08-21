import sys
import socket
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


def ensure_single_instance():
    """Guarantees that only one instance of the desktop application runs at a time."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 49832))
        return s
    except socket.error:
        print("[INFO] Data Entry Bot Desktop App is already running. Focusing existing instance...")
        sys.exit(0)


_instance_lock = ensure_single_instance()

from gui.main_gui import run_gui

if __name__ == "__main__":
    run_gui()

