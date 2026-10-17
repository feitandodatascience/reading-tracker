"""Tests for the baseline time-to-finish estimate."""

import math

import pandas as pd

from reading_tracker import eta, features
from tests.test_features import BOOKS, at, raw_sessions

TODAY = pd.Timestamp("2026-01-10")


def progress_and_prepared(*rows):
    sessions = raw_sessions(*rows)
    progress = features.book_progress(BOOKS, sessions).set_index("title")
    return progress, features.prepare_sessions(sessions, BOOKS)


def test_minutes_per_day_counts_days_since_first_session_only():
    _, prepared = progress_and_prepared(
        (1, at(9, "20:00:00"), at(9, "21:00:00"), 0, 60),  # 60 min on day 9
    )
    assert eta.minutes_per_day(prepared, TODAY) == 30.0  # over days 9 and 10


def test_baseline_eta_for_a_page_book():
    # 1 page per minute, 30 minutes per day over the last 10 days.
    rows = [
        (1, at(d, "20:00:00"), at(d, "20:30:00"), (d - 1) * 30, d * 30)
        for d in range(1, 11)
    ]
    progress, prepared = progress_and_prepared(*rows)
    result = eta.baseline_eta(progress.loc["Paper"], prepared, TODAY)
    assert result["unit"] == "pages"
    assert result["remaining"] == 0  # 300 of 300 pages
    assert result["eta"] == TODAY


def test_baseline_eta_date_range_comes_from_pace_quartiles():
    rows = [
        (1, at(1, "20:00:00"), at(1, "20:30:00"), 0, 15),  # 0.5 pages/min
        (1, at(2, "20:00:00"), at(2, "20:30:00"), 15, 45),  # 1.0
        (1, at(3, "20:00:00"), at(3, "20:30:00"), 45, 90),  # 1.5
    ]
    progress, prepared = progress_and_prepared(*rows)
    result = eta.baseline_eta(
        progress.loc["Paper"], prepared, pd.Timestamp("2026-01-03")
    )
    assert result["remaining"] == 210
    assert result["pace"] == 1.0
    assert result["minutes_per_day"] == 30
    assert result["days_left"] == 7
    assert result["eta"] == pd.Timestamp("2026-01-10")
    assert result["eta_early"] < result["eta"] < result["eta_late"]


def test_audiobook_uses_its_own_percent_pace():
    rows = [
        (3, at(d, "07:00:00"), at(d, "07:30:00"), (d - 1) * 5, d * 5) for d in (8, 9)
    ]
    progress, prepared = progress_and_prepared(*rows)
    result = eta.baseline_eta(
        progress.loc["Audio"], prepared, pd.Timestamp("2026-01-09")
    )
    assert result["unit"] == "percent"
    assert result["remaining"] == 55
    assert math.isclose(result["pace"], 5 / 30)


def test_no_estimate_without_history():
    progress, prepared = progress_and_prepared()
    assert eta.baseline_eta(progress.loc["Paper"], prepared, TODAY) is None


def test_no_estimate_when_nothing_read_recently():
    progress, prepared = progress_and_prepared(
        (1, at(1, "20:00:00"), at(1, "20:30:00"), 0, 30)
    )
    later = pd.Timestamp("2026-03-01")
    assert eta.baseline_eta(progress.loc["Paper"], prepared, later) is None
