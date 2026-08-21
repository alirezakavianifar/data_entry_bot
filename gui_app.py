import sys
import os
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


def ensure_single_instance():
    """Guarantees that only one instance of the desktop application runs at a time."""
    if sys.platform == "win32":
        import ctypes
        ERROR_ALREADY_EXISTS = 183
        mutex_name = "Local\\DataEntryBot_SingleInstance_Mutex"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            print("[INFO] Data Entry Bot Desktop App is already running.")
            sys.exit(0)
        return mutex
    else:
        import fcntl
        lock_file = Path(os.getenv("TEMP", "/tmp")) / "data_entry_bot.lock"
        try:
            f = open(lock_file, "w")
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except (IOError, BlockingIOError):
            print("[INFO] Data Entry Bot Desktop App is already running.")
            sys.exit(0)


from gui.main_gui import run_gui

if __name__ == "__main__":
    _instance_lock = ensure_single_instance()
    run_gui()


