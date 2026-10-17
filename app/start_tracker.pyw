"""Double-click launcher for the private reading tracker (Windows).

Starts the tracker in the background with no console window, reachable from
this computer only, waits until it answers, then opens it in the browser. If the
tracker is already running, it just opens the browser again.

Uses only the standard library, so any Python can run this file; the tracker
itself runs in the project's uv environment.
"""

import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8519  # its own port, so it never gets mixed up with the dashboard (8501)
URL = f"http://localhost:{PORT}"
REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "raw" / "tracker.log"  # gitignored
STARTUP_TIMEOUT_S = 60


def is_running() -> bool:
    """Return True if a Streamlit server already answers on ``PORT``."""
    try:
        with urllib.request.urlopen(f"{URL}/_stcore/health", timeout=1) as reply:
            return reply.read() == b"ok"
    except OSError:
        return False


def server_command() -> list[str]:
    """Command that serves the tracker on localhost only, without telemetry."""
    streamlit_args = [
        "run",
        "app/tracker.py",
        "--server.address",
        "localhost",
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "streamlit", *streamlit_args]
    venv_streamlit = REPO_ROOT / ".venv" / "Scripts" / "streamlit.exe"
    return [str(venv_streamlit), *streamlit_args]


def start_server() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log:
        subprocess.Popen(
            server_command(),
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def show_error(message: str) -> None:
    """Show a message box (there is no console to print to)."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Reading tracker", 0x10)
    else:
        print(message, file=sys.stderr)


def main() -> None:
    if not is_running():
        try:
            start_server()
        except OSError as error:
            show_error(f"Couldn't start the tracker:\n{error}")
            return
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while not is_running():
            if time.monotonic() > deadline:
                show_error(f"The tracker didn't start. See the log:\n{LOG_PATH}")
                return
            time.sleep(0.5)
    webbrowser.open(URL)


if __name__ == "__main__":
    main()
