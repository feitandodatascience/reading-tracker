"""Derived reading metrics: pace, daily minutes, streaks, and book progress.

All functions are pure: they take DataFrames and return new ones. They accept the
public tables from ``export.to_public`` (``started_at`` + ``duration_s``) as
well as the raw tables from ``db`` (``started_at`` + ``ended_at``).

Conventions (CLAUDE.md):

- a session spanning midnight counts for its start date,
- audiobooks count towards minutes and streaks, but not towards page-based pace,
- percent-tracked books are converted to pages when their page count is known.
"""

import numpy as np
import pandas as pd

BOOK_COLUMNS = [
    "book_id",
    "title",
    "genre",
    "language",
    "format",
    "progress_unit",
    "total_pages",
    "status",
]


def local_date(timestamps: pd.Series) -> pd.Series:
    """Return the calendar date of each ISO timestamp in its own UTC offset.

    ``"2026-01-05T23:40:00+07:00"`` is 5 January, even though it is already
    6 January in some other time zone.
    """
    return pd.to_datetime(timestamps.str[:10], format="%Y-%m-%d")


def session_duration_min(sessions: pd.DataFrame) -> pd.Series:
    """Return each session's length in minutes (NaN while it is still active)."""
    if "duration_s" in sessions:
        return sessions["duration_s"].astype(float) / 60
    started = pd.to_datetime(sessions["started_at"], utc=True, format="ISO8601")
    ended = pd.to_datetime(sessions["ended_at"], utc=True, format="ISO8601")
    return (ended - started).dt.total_seconds() / 60


def pages_read(sessions: pd.DataFrame) -> pd.Series:
    """Return pages read per session; needs the book columns merged in.

    Page-tracked books: ``end_pos - start_pos``. Percent-tracked books: the
    percent read times ``total_pages / 100``. NaN for audiobooks and for
    percent books without a page count.
    """
    progress = sessions["end_pos"] - sessions["start_pos"]
    pages = np.where(
        sessions["progress_unit"] == "percent",
        progress * sessions["total_pages"] / 100,
        progress,
    )
    pages = pd.Series(pages, index=sessions.index, dtype=float)
    return pages.where(sessions["format"] != "audio")


def prepare_sessions(sessions: pd.DataFrame, books: pd.DataFrame) -> pd.DataFrame:
    """Return finished sessions with their book details and derived columns.

    Added columns: ``started_utc``, ``date`` (local start date),
    ``duration_min``, ``progress`` (in the book's own unit), ``pages_read`` and
    ``pace`` (pages per minute). Pace is NaN for audiobooks, for books without
    a page count, and for zero-page sessions, which usually mean the position
    wasn't updated; those sessions still count towards minutes and streaks.
    """
    out = sessions.merge(
        books[BOOK_COLUMNS], on="book_id", how="left", validate="many_to_one"
    )
    out["duration_min"] = session_duration_min(out)
    out = out[out["duration_min"].notna()].copy()
    out["started_utc"] = pd.to_datetime(out["started_at"], utc=True, format="ISO8601")
    out["date"] = local_date(out["started_at"])
    out["progress"] = out["end_pos"] - out["start_pos"]
    out["pages_read"] = pages_read(out)
    has_pages_and_time = (out["pages_read"] > 0) & (out["duration_min"] > 0)
    out["pace"] = (out["pages_read"] / out["duration_min"]).where(has_pages_and_time)
    return out.sort_values("started_utc").reset_index(drop=True)


def daily_minutes(
    prepared: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return minutes read per calendar day, with 0 for days without reading.

    Parameters
    ----------
    prepared
        Output of ``prepare_sessions``.
    start, end
        Date range to cover. Default: first to last day with a session.
    """
    minutes = prepared.groupby("date")["duration_min"].sum()
    if minutes.empty and (start is None or end is None):
        return pd.DataFrame({"date": pd.to_datetime([]), "minutes": []})
    start = pd.Timestamp(minutes.index.min() if start is None else start).normalize()
    end = pd.Timestamp(minutes.index.max() if end is None else end).normalize()
    days = pd.date_range(start, end, freq="D", name="date")
    return minutes.reindex(days, fill_value=0.0).rename("minutes").reset_index()


def streaks(daily: pd.DataFrame, today: pd.Timestamp) -> dict[str, int]:
    """Return the current and longest run of consecutive reading days.

    Parameters
    ----------
    daily
        Output of ``daily_minutes`` (one row per day).
    today
        Reference day. Not having read yet today doesn't break the current
        streak; a whole day without reading does.

    Returns
    -------
    dict
        ``{"current": int, "longest": int}``
    """
    read = daily.set_index("date")["minutes"] > 0
    if not read.any():
        return {"current": 0, "longest": 0}
    today = pd.Timestamp(today).normalize()
    read = read.reindex(pd.date_range(read.index.min(), today), fill_value=False)

    run_id = (~read).cumsum()  # every non-reading day starts a new run
    longest = int(read.groupby(run_id).sum().max())

    if not read.iloc[-1]:  # today isn't over yet
        read = read.iloc[:-1]
    current = int(read[::-1].cumprod().sum())
    return {"current": current, "longest": longest}


def book_progress(books: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    """Return one row per book with its latest position and fraction complete.

    Added columns: ``position`` (end of the latest session, in the book's
    unit), ``fraction_complete`` (0-1), ``minutes``, ``sessions``,
    ``first_read`` and ``last_read`` (local dates).
    """
    prepared = prepare_sessions(sessions, books)
    per_book = prepared.groupby("book_id").agg(
        position=("end_pos", "last"),
        minutes=("duration_min", "sum"),
        sessions=("session_id", "count"),
        first_read=("date", "min"),
        last_read=("date", "max"),
    )
    out = books.merge(per_book, on="book_id", how="left")
    out["sessions"] = out["sessions"].fillna(0).astype(int)
    out["minutes"] = out["minutes"].fillna(0.0)
    upper = np.where(out["progress_unit"] == "percent", 100.0, out["total_pages"])
    out["fraction_complete"] = (out["position"].fillna(0) / upper).clip(0, 1)
    return out
