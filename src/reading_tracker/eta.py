"""Baseline time-to-finish estimate for a book (see CLAUDE.md, "ML scope").

Two plain ratios, nothing learned:

- reading time left = remaining pages / recent median pace (pages per minute)
- days left = reading time left / recent minutes read per day

The date range comes from using the 75th and 25th percentile of recent pace
instead of the median. Books without a page count (audiobooks, percent-only
ebooks) use their own percent-per-minute pace instead.

The shrinkage/Bayesian model lives in ``notebooks/02_eta_model.ipynb``.
"""

import math

import pandas as pd

WINDOW_DAYS = 28


def _recent(prepared: pd.DataFrame, today: pd.Timestamp, days: int) -> pd.DataFrame:
    start = today - pd.Timedelta(days=days - 1)
    return prepared[(prepared["date"] >= start) & (prepared["date"] <= today)]


def minutes_per_day(
    prepared: pd.DataFrame, today: pd.Timestamp, window_days: int = WINDOW_DAYS
) -> float:
    """Average minutes read per day over the last ``window_days`` days.

    Days before the first session ever don't count, so a new history isn't
    diluted by days when nothing was being tracked yet.
    """
    if prepared.empty:
        return 0.0
    today = pd.Timestamp(today).normalize()
    first_day = max(prepared["date"].min(), today - pd.Timedelta(days=window_days - 1))
    days = (today - first_day).days + 1
    if days <= 0:
        return 0.0
    return float(_recent(prepared, today, days)["duration_min"].sum() / days)


def baseline_eta(
    book: pd.Series,
    prepared: pd.DataFrame,
    today: pd.Timestamp,
    window_days: int = WINDOW_DAYS,
) -> dict | None:
    """Estimate when ``book`` will be finished.

    Parameters
    ----------
    book
        One row of ``features.book_progress``.
    prepared
        Output of ``features.prepare_sessions`` for all books.
    today
        Reference day.
    window_days
        How far back "recent" reaches.

    Returns
    -------
    dict or None
        ``remaining``, ``unit`` ("pages" or "percent"), ``pace`` (median, per
        minute), ``minutes_per_day``, ``minutes_left``, ``days_left``, ``eta``,
        ``eta_early`` and ``eta_late`` (dates). ``None`` when there isn't enough
        history to estimate.
    """
    today = pd.Timestamp(today).normalize()
    position = 0.0 if pd.isna(book["position"]) else float(book["position"])
    uses_pages = book["format"] != "audio" and pd.notna(book["total_pages"])

    if uses_pages:
        unit = "pages"
        remaining = float(book["total_pages"]) * (1 - book["fraction_complete"])
        paces = _recent(prepared, today, window_days)["pace"].dropna()
        if paces.empty:  # nothing recent: fall back to all history
            paces = prepared["pace"].dropna()
    else:
        unit = "percent"
        remaining = 100.0 - position
        own = prepared[prepared["book_id"] == book["book_id"]]
        own = own[(own["progress"] > 0) & (own["duration_min"] > 0)]
        paces = own["progress"] / own["duration_min"]

    remaining = max(remaining, 0.0)
    per_day = minutes_per_day(prepared, today, window_days)
    if paces.empty or per_day <= 0:
        return None

    def finish_date(pace: float) -> pd.Timestamp | None:
        if pace <= 0:
            return None
        return today + pd.Timedelta(days=math.ceil(remaining / pace / per_day))

    pace = float(paces.median())
    minutes_left = remaining / pace if pace > 0 else math.inf
    return {
        "remaining": remaining,
        "unit": unit,
        "pace": pace,
        "minutes_per_day": per_day,
        "minutes_left": minutes_left,
        "days_left": minutes_left / per_day,
        "eta": finish_date(pace),
        "eta_early": finish_date(float(paces.quantile(0.75))),
        "eta_late": finish_date(float(paces.quantile(0.25))),
    }
