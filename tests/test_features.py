"""Tests for derived metrics, built from small hand-made tables."""

import math

import pandas as pd
import pytest

from reading_tracker import features

BOOKS = pd.DataFrame(
    [
        # book_id, title, genre, language, format, unit, total_pages, status
        (1, "Paper", "Fiction", "English", "physical", "page", 300, "reading"),
        (2, "Ebook", "Fiction", "Vietnamese", "ebook", "percent", 200, "reading"),
        (3, "Audio", "Memoir", "English", "audio", "percent", None, "reading"),
        (4, "No pages", "Fiction", "English", "ebook", "percent", None, "reading"),
    ],
    columns=features.BOOK_COLUMNS,
)


def raw_sessions(*rows) -> pd.DataFrame:
    """Raw sessions: (book_id, started_at, ended_at, start_pos, end_pos)."""
    frame = pd.DataFrame(
        rows, columns=["book_id", "started_at", "ended_at", "start_pos", "end_pos"]
    )
    frame.insert(0, "session_id", range(1, len(frame) + 1))
    return frame


def prepare(*rows) -> pd.DataFrame:
    return features.prepare_sessions(raw_sessions(*rows), BOOKS)


def at(day: int, clock: str) -> str:
    return f"2026-01-{day:02d}T{clock}+07:00"


# --- durations, pages, pace ------------------------------------------------------


def test_duration_from_raw_timestamps_and_from_public_seconds():
    raw = raw_sessions((1, at(5, "20:00:00"), at(5, "20:30:30"), 0, 10))
    assert features.session_duration_min(raw).tolist() == [30.5]
    public = pd.DataFrame({"duration_s": [1830]})
    assert features.session_duration_min(public).tolist() == [30.5]


def test_active_sessions_are_left_out():
    prepared = prepare(
        (1, at(5, "20:00:00"), at(5, "20:30:00"), 0, 10),
        (1, at(6, "20:00:00"), None, 10, None),
    )
    assert len(prepared) == 1


def test_pace_is_pages_per_minute():
    prepared = prepare((1, at(5, "20:00:00"), at(5, "20:30:00"), 10, 40))
    assert prepared.loc[0, "pages_read"] == 30
    assert prepared.loc[0, "pace"] == 1.0


def test_percent_ebook_is_converted_to_pages():
    prepared = prepare((2, at(5, "20:00:00"), at(5, "20:20:00"), 10, 20))
    assert prepared.loc[0, "progress"] == 10  # percent
    assert prepared.loc[0, "pages_read"] == 20  # 10% of 200 pages
    assert prepared.loc[0, "pace"] == 1.0


def test_percent_ebook_without_page_count_has_no_pace():
    prepared = prepare((4, at(5, "20:00:00"), at(5, "20:20:00"), 10, 20))
    assert math.isnan(prepared.loc[0, "pages_read"])
    assert math.isnan(prepared.loc[0, "pace"])


def test_audiobooks_count_for_minutes_but_not_for_pace():
    prepared = prepare(
        (1, at(5, "07:00:00"), at(5, "07:30:00"), 0, 30),
        (3, at(5, "20:00:00"), at(5, "21:00:00"), 0, 10),
    )
    audio = prepared[prepared["format"] == "audio"].iloc[0]
    assert math.isnan(audio["pages_read"])
    assert math.isnan(audio["pace"])
    assert prepared["pace"].median() == 1.0  # only the paper session counts
    daily = features.daily_minutes(prepared)
    assert daily["minutes"].tolist() == [90.0]


def test_zero_page_session_counts_for_minutes_not_for_pace():
    prepared = prepare((1, at(5, "20:00:00"), at(5, "20:45:00"), 50, 50))
    assert prepared.loc[0, "pages_read"] == 0
    assert math.isnan(prepared.loc[0, "pace"])
    assert features.daily_minutes(prepared)["minutes"].tolist() == [45.0]


# --- daily minutes and midnight ---------------------------------------------------


def test_session_spanning_midnight_counts_for_its_start_date():
    prepared = prepare((1, at(5, "23:30:00"), at(6, "00:30:00"), 0, 40))
    daily = features.daily_minutes(prepared)
    assert daily["date"].tolist() == [pd.Timestamp("2026-01-05")]
    assert daily["minutes"].tolist() == [60.0]


def test_local_date_uses_each_timestamps_own_offset():
    stamps = pd.Series(["2026-01-05T23:30:00+07:00", "2026-01-05T23:30:00-05:00"])
    assert features.local_date(stamps).tolist() == [pd.Timestamp("2026-01-05")] * 2


def test_daily_minutes_fills_days_without_reading_with_zero():
    prepared = prepare(
        (1, at(5, "20:00:00"), at(5, "20:30:00"), 0, 10),
        (1, at(8, "20:00:00"), at(8, "20:10:00"), 10, 20),
    )
    daily = features.daily_minutes(prepared, end=pd.Timestamp("2026-01-09"))
    assert daily["minutes"].tolist() == [30.0, 0.0, 0.0, 10.0, 0.0]


def test_daily_minutes_of_no_sessions_is_empty():
    assert features.daily_minutes(prepare()).empty


# --- streaks ------------------------------------------------------------------------


def daily_from(days_read: list[int]) -> pd.DataFrame:
    rows = [(d, at(d, "20:00:00"), at(d, "20:20:00"), 0, 1) for d in days_read]
    return features.daily_minutes(prepare(*[(1, *row[1:]) for row in rows]))


def test_a_gap_breaks_the_streak():
    daily = daily_from([1, 2, 3, 5, 6])
    assert features.streaks(daily, today=pd.Timestamp("2026-01-06")) == {
        "current": 2,
        "longest": 3,
    }


def test_not_reading_yet_today_keeps_the_streak():
    daily = daily_from([4, 5, 6])
    result = features.streaks(daily, today=pd.Timestamp("2026-01-07"))
    assert result == {"current": 3, "longest": 3}


def test_a_full_day_without_reading_ends_the_current_streak():
    daily = daily_from([4, 5, 6])
    result = features.streaks(daily, today=pd.Timestamp("2026-01-08"))
    assert result == {"current": 0, "longest": 3}


def test_streaks_without_any_reading_are_zero():
    assert features.streaks(daily_from([]), today=pd.Timestamp("2026-01-08")) == {
        "current": 0,
        "longest": 0,
    }


# --- book progress ------------------------------------------------------------------


def test_book_progress_uses_latest_session_in_time():
    sessions = raw_sessions(
        (1, at(9, "20:00:00"), at(9, "20:30:00"), 100, 150),
        (1, at(5, "20:00:00"), at(5, "20:30:00"), 0, 100),  # logged later
        (2, at(6, "20:00:00"), at(6, "20:30:00"), 0, 25),
    )
    progress = features.book_progress(BOOKS, sessions).set_index("title")
    assert progress.loc["Paper", "position"] == 150
    assert progress.loc["Paper", "fraction_complete"] == 0.5
    assert progress.loc["Paper", "sessions"] == 2
    assert progress.loc["Ebook", "fraction_complete"] == 0.25
    assert progress.loc["Audio", "sessions"] == 0
    assert progress.loc["Audio", "fraction_complete"] == 0


@pytest.mark.parametrize("column", ["minutes", "first_read", "last_read"])
def test_book_progress_has_summary_columns(column):
    sessions = raw_sessions((1, at(5, "20:00:00"), at(5, "20:30:00"), 0, 10))
    assert column in features.book_progress(BOOKS, sessions)
