"""Export the private database to public parquet files for the dashboard.

Privacy rules (CLAUDE.md): notes are dropped and timestamps are rounded down to
the hour. Rounding both ends of a session would destroy its duration (20:10-20:40
becomes 20:00-20:00), so the public sessions keep the start hour and a derived
``duration_s`` (whole seconds) instead of ``ended_at``. Flooring (not rounding)
keeps every session on its real start date. Active sessions are left out until
they end.

Run from the repo root:

    uv run python -m reading_tracker.export
"""

from pathlib import Path

import pandas as pd

from reading_tracker import db

PUBLIC_BOOK_COLUMNS = [
    "book_id",
    "title",
    "author",
    "genre",
    "language",
    "format",
    "progress_unit",
    "total_pages",
    "added_at",
    "status",
]
PUBLIC_SESSION_COLUMNS = [
    "session_id",
    "book_id",
    "started_at",
    "duration_s",
    "start_pos",
    "end_pos",
]


def floor_to_hour(timestamps: pd.Series) -> pd.Series:
    """Round ISO 8601 timestamps down to the hour, keeping each one's UTC offset.

    ``"2026-01-05T20:47:13+07:00"`` becomes ``"2026-01-05T20:00:00+07:00"``.
    Works on the text, so mixed offsets are never converted to another zone.
    """
    return timestamps.str.replace(
        r"^(\d{4}-\d\d-\d\dT\d\d):\d\d:\d\d(\.\d+)?", r"\1:00:00", regex=True
    )


def to_public(
    books: pd.DataFrame, sessions: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Turn raw ``books``/``sessions`` tables into their privacy-safe public form.

    Parameters
    ----------
    books, sessions
        Tables as returned by ``db.read_books`` and ``db.read_sessions``.

    Returns
    -------
    tuple of DataFrame
        Public books (``added_at`` floored to the hour) and public finished
        sessions (no ``note``, no ``ended_at``, ``started_at`` floored to the
        hour, plus ``duration_s``: the exact length in whole seconds).
    """
    public_books = books[PUBLIC_BOOK_COLUMNS].copy()
    public_books["added_at"] = floor_to_hour(public_books["added_at"])

    finished = sessions[sessions["ended_at"].notna()].copy()
    started = pd.to_datetime(finished["started_at"], utc=True, format="ISO8601")
    ended = pd.to_datetime(finished["ended_at"], utc=True, format="ISO8601")
    finished["duration_s"] = (ended - started).dt.total_seconds().round().astype(int)
    finished["started_at"] = floor_to_hour(finished["started_at"])
    public_sessions = finished[PUBLIC_SESSION_COLUMNS].reset_index(drop=True)
    return public_books, public_sessions


def export(
    db_path: Path | str | None = None, out_dir: Path | str | None = None
) -> dict[str, Path]:
    """Write ``books.parquet`` and ``sessions.parquet`` from the private database.

    Parameters
    ----------
    db_path
        Private database, by default ``data/raw/reading.db``.
    out_dir
        Output folder, by default ``data/processed/``.

    Returns
    -------
    dict
        Table name -> written file.
    """
    db_path = Path(db.RAW_DB_PATH if db_path is None else db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"No database at {db_path}. Log some reading first.")
    out_dir = Path(db.PROCESSED_DIR if out_dir is None else out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = db.connect(db_path)
    try:
        books, sessions = to_public(db.read_books(conn), db.read_sessions(conn))
    finally:
        conn.close()

    paths = {
        "books": out_dir / "books.parquet",
        "sessions": out_dir / "sessions.parquet",
    }
    books.to_parquet(paths["books"], index=False)
    sessions.to_parquet(paths["sessions"], index=False)
    return paths


if __name__ == "__main__":
    for name, path in export().items():
        print(f"Wrote {name}: {path}")
