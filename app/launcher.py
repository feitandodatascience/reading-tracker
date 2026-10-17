"""Shared logic for the double-click launchers (start_tracker.pyw, start_dashboard.pyw).

Starts a Streamlit app in the background with no console window, reachable from
this computer only and without usage telemetry, waits until it answers, then
opens it in the browser. If the app is already running, it just reopens the tab.

Uses only the standard library, so any Python can run the launchers; the apps
themselves run in the project's uv environment.
"""

import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "data" / "raw"  # gitignored
STARTUP_TIMEOUT_S = 60


def url(port: int) -> str:
    return f"http://localhost:{port}"


def is_running(port: int) -> bool:
    """Return True if a Streamlit server already answers on ``port``."""
    try:
        with urllib.request.urlopen(f"{url(port)}/_stcore/health", timeout=1) as r:
            return r.read() == b"ok"
    except OSError:
        return False


def server_command(script: str, port: int) -> list[str]:
    """Command that serves ``script`` on localhost only, without telemetry."""
    streamlit_args = [
        "run",
        script,
        "--server.address",
        "localhost",
        "--server.port",
        str(port),
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


def start_server(script: str, port: int, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        subprocess.Popen(
            server_command(script, port),
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def show_error(message: str, title: str) -> None:
    """Show a message box (there is no console to print to)."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    else:
        print(message, file=sys.stderr)


def launch(script: str, port: int, name: str) -> None:
    """Start ``script`` on ``port`` unless it already runs, then open the browser."""
    log_path = LOG_DIR / f"{name}.log"
    title = f"Reading {name}"
    if not is_running(port):
        try:
            start_server(script, port, log_path)
        except OSError as error:
            show_error(f"Couldn't start the {name}:\n{error}", title)
            return
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while not is_running(port):
            if time.monotonic() > deadline:
                show_error(f"The {name} didn't start. See the log:\n{log_path}", title)
                return
            time.sleep(0.5)
    webbrowser.open(url(port))
