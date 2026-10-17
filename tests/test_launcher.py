"""Tests for the double-click tracker launcher (app/start_tracker.pyw)."""

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "app" / "start_tracker.pyw"
_loader = SourceFileLoader("start_tracker", str(LAUNCHER_PATH))
launcher = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("start_tracker", _loader)
)
_loader.exec_module(launcher)


def test_server_listens_on_localhost_only_without_telemetry():
    command = launcher.server_command()
    assert all(isinstance(part, str) for part in command)
    assert "app/tracker.py" in command
    assert command[command.index("--server.address") + 1] == "localhost"
    assert command[command.index("--browser.gatherUsageStats") + 1] == "false"
    assert command[command.index("--server.port") + 1] == str(launcher.PORT)


def test_tracker_port_differs_from_streamlit_default():
    assert launcher.PORT != 8501


def test_is_running_is_false_when_nothing_listens(monkeypatch):
    monkeypatch.setattr(launcher, "URL", "http://localhost:9")  # discard port
    assert launcher.is_running() is False
