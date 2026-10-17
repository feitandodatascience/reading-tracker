"""Tests for the double-click launchers (app/launcher.py and the .pyw files)."""

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))  # the .pyw files import launcher from app/
import launcher  # noqa: E402


def load_pyw(name: str):
    loader = SourceFileLoader(name, str(APP_DIR / f"{name}.pyw"))
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader(name, loader)
    )
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("script", ["app/tracker.py", "app/dashboard.py"])
def test_server_listens_on_localhost_only_without_telemetry(script):
    command = launcher.server_command(script, 8519)
    assert all(isinstance(part, str) for part in command)
    assert script in command
    assert command[command.index("--server.address") + 1] == "localhost"
    assert command[command.index("--browser.gatherUsageStats") + 1] == "false"
    assert command[command.index("--server.port") + 1] == "8519"


def test_each_app_has_its_own_port():
    ports = {load_pyw("start_tracker").PORT, load_pyw("start_dashboard").PORT}
    assert len(ports) == 2
    assert 8501 not in ports  # Streamlit's default, used by manual runs


def test_is_running_is_false_when_nothing_listens():
    assert launcher.is_running(9) is False  # the discard port
