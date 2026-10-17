"""Tests for the demo data generator and the privacy-safe export."""

import re
import sqlite3

import pandas as pd
import pytest

from reading_tracker import db, export, features, synthetic


@pytest.fixture(scope="module")
def demo_path(tmp_path_factory):
    return synthetic.generate(tmp_path_factory.mktemp("demo") / "demo.db")


@pytest.fixture(scope="module")
def demo(demo_path):
    conn = db.connect(demo_path)
    try:
        return db.read_books(conn), db.read_sessions(conn)
    finally:
        conn.close()


# --- synthetic ------------------------------------------------------------------------


def test_demo_is_reproducible(demo, tmp_path):
    conn = db.connect(synthetic.generate(tmp_path / "again.db"))
    books, sessions = db.read_books(conn), db.read_sessions(conn)
    conn.close()
    pd.testing.assert_frame_equal(books, demo[0])
    pd.testing.assert_frame_equal(sessions, demo[1])


def test_demo_looks_like_six_months_of_about_fifteen_books(demo):
    books, sessions = demo
    assert 12 <= len(books) <= 18
    days = features.local_date(sessions["started_at"])
    assert 150 <= (days.max() - days.min()).days <= 182
    assert set(books["format"]) == {"physical", "ebook", "audio"}
    assert set(books["language"]) == {"English", "Vietnamese"}
    assert books["genre"].nunique() >= 5
    assert set(books["status"]) == {"reading", "finished", "abandoned"}


def test_demo_has_streaks_and_gaps(demo):
    books, sessions = demo
    prepared = features.prepare_sessions(sessions, books)
    daily = features.daily_minutes(prepared)
    gaps = (daily["minutes"] == 0).astype(int)
    longest_gap = int(gaps.groupby((gaps == 0).cumsum()).sum().max())
    assert longest_gap >= 7  # the trip
    assert features.streaks(daily, daily["date"].max())["longest"] >= 10


def test_demo_obeys_the_session_rules(demo):
    books, sessions = demo
    assert sessions["ended_at"].notna().all()  # no active session left behind
    started = pd.to_datetime(sessions["started_at"], utc=True, format="ISO8601")
    ended = pd.to_datetime(sessions["ended_at"], utc=True, format="ISO8601")
    assert (ended > started).all()
    assert (sessions["end_pos"] >= sessions["start_pos"]).all()
    order = started.argsort()
    assert (
        started.iloc[order].iloc[1:].values >= ended.iloc[order].iloc[:-1].values
    ).all()


def test_demo_has_a_current_book_for_the_eta(demo):
    books, sessions = demo
    progress = features.book_progress(books, sessions)
    current = progress[
        (progress["status"] == "reading") & (progress["format"] != "audio")
    ]
    assert len(current) == 1
    assert 0.2 < current["fraction_complete"].iloc[0] < 0.8


# --- export ---------------------------------------------------------------------------


def test_floor_to_hour_keeps_offset_and_date():
    stamps = pd.Series(["2026-01-05T23:59:59+07:00", "2026-01-05T08:15:00.5-05:00"])
    assert export.floor_to_hour(stamps).tolist() == [
        "2026-01-05T23:00:00+07:00",
        "2026-01-05T08:00:00-05:00",
    ]


def test_export_writes_privacy_safe_parquet(demo_path, tmp_path):
    paths = export.export(demo_path, tmp_path / "processed")
    books = pd.read_parquet(paths["books"])
    sessions = pd.read_parquet(paths["sessions"])

    assert "note" not in sessions and "ended_at" not in sessions
    on_the_hour = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:00:00[+-]\d\d:\d\d$")
    assert sessions["started_at"].str.match(on_the_hour).all()
    assert books["added_at"].str.match(on_the_hour).all()
    assert list(sessions.columns) == export.PUBLIC_SESSION_COLUMNS


def test_export_keeps_exact_durations_and_start_dates(demo, demo_path, tmp_path):
    raw_books, raw_sessions = demo
    sessions = pd.read_parquet(export.export(demo_path, tmp_path)["sessions"])
    raw = features.prepare_sessions(raw_sessions, raw_books)
    public = features.prepare_sessions(sessions, raw_books)
    assert (public["duration_min"] - raw["duration_min"]).abs().max() < 1 / 60
    assert public["date"].tolist() == raw["date"].tolist()


def test_export_leaves_out_active_sessions(tmp_path):
    path = tmp_path / "raw.db"
    conn = db.connect(path)
    with conn:
        conn.execute(
            "INSERT INTO books (title, progress_unit, total_pages, added_at, status)"
            " VALUES ('Dune', 'page', 400, '2026-01-01T09:30:00+07:00', 'reading')"
        )
        conn.executemany(
            "INSERT INTO sessions (book_id, started_at, ended_at, start_pos, end_pos,"
            " note) VALUES (1, ?, ?, ?, ?, 'private thought')",
            [
                ("2026-01-05T20:10:00+07:00", "2026-01-05T20:40:00+07:00", 0, 20),
                ("2026-01-06T20:10:00+07:00", None, 20, None),
            ],
        )
    conn.close()
    sessions = pd.read_parquet(export.export(path, tmp_path / "out")["sessions"])
    assert sessions[["started_at", "duration_s"]].to_dict("records") == [
        {"started_at": "2026-01-05T20:00:00+07:00", "duration_s": 1800}
    ]


def test_export_without_a_database_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="No database"):
        export.export(tmp_path / "missing.db", tmp_path / "out")
    assert not (tmp_path / "missing.db").exists()


def test_demo_database_file_is_a_real_sqlite_db(demo_path):
    with sqlite3.connect(demo_path) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
