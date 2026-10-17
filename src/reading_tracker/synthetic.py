"""Seeded synthetic reading history for the public demo (``data/demo/demo.db``).

About six months and fifteen books read in English and Vietnamese (listed by
their English titles, as the brand font has no Vietnamese diacritics), mostly
physical with some ebooks and audiobooks, with streaks, gaps (a trip, a sick
week) and two abandoned books. Everything is written through ``log``, so the demo obeys
the same validation rules as real data.

The default end date is fixed, so the same seed always gives the same file:

    uv run python -m reading_tracker.synthetic
"""

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np

from reading_tracker import db, log

TZ = timezone(timedelta(hours=7))  # Vietnam
SEED = 10  # ends mid-way through a book, so the demo ETA has a range
END_DATE = date(2026, 10, 15)
DAYS = 182

# title, author, genre, language, format, total_pages (print), audio hours
CATALOG = [
    ("Project Hail Mary", "Andy Weir", "Science fiction", "English", "physical", 476, None),  # noqa: E501
    ("I See Yellow Flowers in the Green Grass", "Nguyen Nhat Anh", "Fiction", "Vietnamese", "physical", 378, None),  # noqa: E501
    ("Sapiens", "Yuval Noah Harari", "History", "English", "physical", 443, None),
    ("Atomic Habits", "James Clear", "Self-help", "English", "ebook", 320, None),
    ("Dreamy Eyes", "Nguyen Nhat Anh", "Fiction", "Vietnamese", "physical", 300, None),
    ("Thinking, Fast and Slow", "Daniel Kahneman", "Psychology", "English", "physical", 499, None),  # noqa: E501
    ("Dumb Luck", "Vu Trong Phung", "Classic", "Vietnamese", "ebook", 240, None),
    ("The Midnight Library", "Matt Haig", "Fiction", "English", "physical", 288, None),
    ("The Sorrow of War", "Bao Ninh", "Fiction", "Vietnamese", "physical", 320, None),  # noqa: E501
    ("Klara and the Sun", "Kazuo Ishiguro", "Fiction", "English", "ebook", 303, None),
    ("Diary of a Cricket", "To Hoai", "Classic", "Vietnamese", "physical", 144, None),
    ("The Pragmatic Programmer", "David Thomas, Andrew Hunt", "Technology", "English", "physical", 352, None),  # noqa: E501
    ("How to Win Friends and Influence People", "Dale Carnegie", "Self-help", "Vietnamese", "physical", 320, None),  # noqa: E501
    ("Norwegian Wood", "Haruki Murakami", "Fiction", "English", "physical", 296, None),
    ("The Alchemist", "Paulo Coelho", "Fiction", "Vietnamese", "physical", 228, None),
    ("The Design of Everyday Things", "Don Norman", "Technology", "English", "physical", 368, None),  # noqa: E501
    ("Homo Deus", "Yuval Noah Harari", "History", "English", "physical", 450, None),
    ("Dune", "Frank Herbert", "Science fiction", "English", "audio", None, 21.0),
    ("Educated", "Tara Westover", "Memoir", "English", "audio", None, 12.0),
]  # fmt: skip
ABANDON_AT = {"Thinking, Fast and Slow": 0.35, "The Sorrow of War": 0.4}
BASE_PACE = {"English": 0.75, "Vietnamese": 1.0}  # pages per minute
GENRE_PACE = {
    "Fiction": 1.1,
    "Science fiction": 1.05,
    "Classic": 0.95,
    "History": 0.7,
    "Psychology": 0.65,
    "Technology": 0.6,
    "Self-help": 0.9,
    "Memoir": 1.0,
}
NOTES = ["Great chapter", "So good", "Slow going tonight", "Couldn't put it down"]


def _reading_days(rng: np.random.Generator, days: int) -> np.ndarray:
    """Which days have reading: a sticky habit (streaks) plus two planned gaps."""
    read = np.zeros(days, dtype=bool)
    read[0] = True
    for day in range(1, days):
        keep_going = 0.86 if read[day - 1] else 0.45
        read[day] = rng.random() < keep_going
    read[days // 2 : days // 2 + 7] = False  # a week-long trip
    read[days - 40 : days - 36] = False  # sick for a few days
    return read


def _session(
    rng: np.random.Generator, day: date, start: time, median_min: float
) -> tuple[datetime, datetime]:
    """A session starting at ``start`` (plus random seconds) on ``day``."""
    started = datetime.combine(day, start, TZ) + timedelta(
        seconds=int(rng.integers(60))
    )
    minutes = float(np.clip(rng.lognormal(np.log(median_min), 0.45), 5, 150))
    return started, started + timedelta(seconds=round(minutes * 60))


def simulate(
    seed: int = SEED, end_date: date = END_DATE, days: int = DAYS
) -> tuple[list[dict], list[dict]]:
    """Simulate books and sessions in memory (no database involved).

    Returns
    -------
    tuple of list
        Books (catalog fields plus ``status`` and ``first_started``) and
        finished sessions (``book``, ``started_at``, ``ended_at``,
        ``start_pos``, ``end_pos``, ``note``), in time order.
    """
    rng = np.random.default_rng(seed)
    first_day = end_date - timedelta(days=days - 1)
    queue = [dict(zip(_FIELDS, entry, strict=True)) for entry in CATALOG]
    for book in queue:
        book.update(position=0.0, status=None, first_started=None)
    print_queue = [b for b in queue if b["format"] != "audio"]
    audio_queue = [b for b in queue if b["format"] == "audio"]
    sessions = []

    def read(book: dict, started: datetime, ended: datetime) -> None:
        minutes = (ended - started).total_seconds() / 60
        if book["format"] == "audio":  # percent of the audiobook per minute
            step = 100 / (book["audio_hours"] * 60) * 1.2 * rng.normal(1, 0.05)
            limit = 100.0
        else:
            pace = BASE_PACE[book["language"]] * GENRE_PACE[book["genre"]]
            step = pace * rng.lognormal(0, 0.2)
            limit = float(book["total_pages"])
        advance = step * minutes
        if book["format"] == "ebook":  # ebooks are tracked in percent
            advance, limit = advance / book["total_pages"] * 100, 100.0
        start_pos = book["position"]
        end_pos = min(start_pos + advance, limit)
        if end_pos == limit:  # finishing early: shorten the session to match
            ended = started + (ended - started) * ((limit - start_pos) / advance)
            ended = max(ended, started + timedelta(minutes=1))
        end_pos = round(end_pos, 1) if book["format"] != "physical" else int(end_pos)
        book["first_started"] = book["first_started"] or started
        sessions.append(
            {
                "book": book["title"],
                "started_at": started,
                "ended_at": ended,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "note": rng.choice(NOTES) if rng.random() < 0.08 else None,
            }
        )
        book["position"] = end_pos
        abandon_at = ABANDON_AT.get(book["title"])
        if end_pos >= limit:
            book["status"] = "finished"
        elif abandon_at and end_pos >= abandon_at * limit:
            book["status"] = "abandoned"

    for offset, reading in enumerate(_reading_days(rng, days)):
        day = first_day + timedelta(days=offset)
        print_queue = [b for b in print_queue if b["status"] is None]
        audio_queue = [b for b in audio_queue if b["status"] is None]
        if not reading:
            continue
        if audio_queue and rng.random() < 0.35:  # commute listening
            start = time(7, int(rng.integers(0, 50)))
            read(audio_queue[0], *_session(rng, day, start, 30))
        if print_queue and day.weekday() >= 5 and rng.random() < 0.4:
            start = time(14, int(rng.integers(0, 60)))
            read(print_queue[0], *_session(rng, day, start, 50))
        print_queue = [b for b in print_queue if b["status"] is None]
        if print_queue and rng.random() < 0.92:  # the main evening session
            start = time(int(rng.integers(20, 24)), int(rng.integers(0, 60)))
            read(print_queue[0], *_session(rng, day, start, 35))

    started_books = [b for b in queue if b["first_started"] is not None]
    for book in started_books:
        book["status"] = book["status"] or "reading"
    started_books.sort(key=lambda b: b["first_started"])
    return started_books, sessions


_FIELDS = (
    "title",
    "author",
    "genre",
    "language",
    "format",
    "total_pages",
    "audio_hours",
)


def generate(
    path: Path | str | None = None,
    seed: int = SEED,
    end_date: date = END_DATE,
    days: int = DAYS,
) -> Path:
    """Write a fresh synthetic database to ``path`` (default ``data/demo/demo.db``).

    Any existing file at ``path`` is replaced.
    """
    path = Path(db.DEMO_DB_PATH if path is None else path)
    path.unlink(missing_ok=True)
    books, sessions = simulate(seed, end_date, days)
    rng = np.random.default_rng(seed + 1)

    conn = db.connect(path)
    try:
        ids = {}
        for book in books:
            added = book["first_started"] - timedelta(
                days=int(rng.integers(1, 10)), hours=int(rng.integers(0, 6))
            )
            ids[book["title"]] = log.add_book(
                conn,
                book["title"],
                author=book["author"],
                genre=book["genre"],
                language=book["language"],
                format=book["format"],
                total_pages=book["total_pages"],
                added_at=added,
            )
        for session in sessions:
            log.add_manual_session(
                conn,
                ids[session["book"]],
                session["started_at"],
                session["ended_at"],
                session["start_pos"],
                session["end_pos"],
                note=session["note"],
            )
        for book in books:
            if book["status"] != "reading":
                log.mark_book_status(conn, ids[book["title"]], book["status"])
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    print(f"Wrote {generate()}")
