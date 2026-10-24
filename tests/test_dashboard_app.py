"""Run the public dashboard with AppTest on demo and exported data."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from reading_tracker import brand, db, export

DASHBOARD = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"


def open_dashboard(processed_dir: Path, monkeypatch) -> AppTest:
    monkeypatch.setenv("READING_TRACKER_PROCESSED_DIR", str(processed_dir))
    app = AppTest.from_file(str(DASHBOARD), default_timeout=60)
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    return app


def texts(app: AppTest) -> str:
    parts = [*app.markdown, *app.caption, *app.subheader, *app.title]
    return " | ".join(element.value for element in parts)


@pytest.fixture
def exported(tmp_path) -> Path:
    """The demo database exported as if it were real data."""
    export.export(db.DEMO_DB_PATH, tmp_path / "processed")
    return tmp_path / "processed"


def test_without_exported_data_it_shows_labelled_demo_data(tmp_path, monkeypatch):
    app = open_dashboard(tmp_path / "nothing", monkeypatch)
    assert app.toggle[0].value is True
    assert app.toggle[0].disabled
    assert "Synthetic history, not real reading." in texts(app)
    assert len(app.get("plotly_chart")) == 4


def test_every_section_renders(tmp_path, monkeypatch):
    app = open_dashboard(tmp_path / "nothing", monkeypatch)
    page = texts(app)
    for heading in [
        "Daily reading",
        "Weekly minutes",
        "How fast I read",
        "Finished and abandoned",
    ]:
        assert heading in page
    labels = [metric.label for metric in app.metric]
    assert labels.count("Estimated finish") >= 1
    assert {"Current streak", "Longest streak"} <= set(labels)


def test_exported_data_is_the_default_and_unlabelled(exported, monkeypatch):
    app = open_dashboard(exported, monkeypatch)
    assert app.toggle[0].value is False
    assert "Synthetic history" not in texts(app)


def test_demo_toggle_switches_to_labelled_demo_data(exported, monkeypatch):
    app = open_dashboard(exported, monkeypatch)
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert "Synthetic history, not real reading." in texts(app)


def test_weekly_goal_and_pace_grouping_update(tmp_path, monkeypatch):
    app = open_dashboard(tmp_path / "nothing", monkeypatch)
    app.number_input[0].set_value(300).run()
    assert "of 300 minutes" in texts(app)
    for group in ["format", "language"]:
        app.button_group[0].set_value(group).run()
        assert not app.exception


def test_charts_sit_on_the_page_colour(tmp_path, monkeypatch):
    # Streamlit would fill an unset plot background with the theme's Mist.
    app = open_dashboard(tmp_path / "nothing", monkeypatch)
    for chart in app.get("plotly_chart"):
        layout = json.loads(chart.proto.spec)["layout"]
        assert layout["plot_bgcolor"] == brand.PEARL
        assert layout["template"]["layout"]["paper_bgcolor"] == brand.PEARL
