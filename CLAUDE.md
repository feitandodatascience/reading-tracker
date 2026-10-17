# CLAUDE.md — Reading Tracker

Persistent context for AI coding assistants working in this repo. Read this before every task.

## What this project is

A personal reading tracker and public dashboard, built by a data scientist as a portfolio project.

Three goals, in priority order:

1. **Habit**: logging a reading session must take under 10 seconds. Friction kills the habit and the data.
2. **Portfolio**: a clean, public GitHub repo with a Streamlit dashboard showing my reading journey.
3. **ML**: estimate time-to-finish for the current book from my own history (built later, mostly by me).

## Tech stack

- Python 3.12, managed with `uv` (`pyproject.toml`, `uv.lock` committed)
- `sqlite3` (stdlib) + `pandas` for data access. **No ORM.**
- `streamlit` for both the private tracker and the public dashboard
- `plotly` for charts
- `ruff` for linting and formatting, `pytest` for tests
- `numpy` / `scipy` only when actually needed

Do **not** add: FastAPI, Docker, SQLAlchemy, auth, Celery, config frameworks, or abstract base classes. This is a data science project, not a production service.

## Code conventions

- PEP 8, enforced by `ruff` (line length 88)
- Type hints on public functions; short NumPy-style docstrings
- Prefer plain functions over classes. Use a class only when state genuinely needs to be bundled.
- Keep functions small and testable. Pure functions in `features.py` and `eta.py`, with I/O kept in `db.py`.
- Use `pathlib` for paths, resolved relative to the project root, never hardcoded absolute paths
- Use `snake_case` for column names in every DataFrame and table
- No notebooks in `src/`. Notebooks go in `notebooks/`, numbered (`01_eda.ipynb`).

## Repo layout

```
reading-tracker/
├── README.md
├── CLAUDE.md
├── brand.md                # branding source of truth (colors, fonts, tone)
├── pyproject.toml
├── .streamlit/config.toml  # theme derived from brand.md
├── data/
│   ├── raw/                # gitignored: reading.db (real data)
│   ├── demo/               # demo.db (synthetic, committed)
│   └── processed/          # exported public data (committed)
├── notebooks/
├── src/reading_tracker/
│   ├── __init__.py
│   ├── db.py               # schema, connection, read/write helpers
│   ├── log.py              # start/stop/manual session logic + validation
│   ├── features.py         # pace, daily minutes, streaks, progress
│   ├── eta.py              # baseline ETA only (see "ML scope")
│   ├── synthetic.py        # seeded demo data generator
│   ├── export.py           # raw db -> data/processed/*.parquet
│   └── brand.py            # color palette + plotly template from brand.md
├── app/
│   ├── tracker.py          # private logging UI (run locally)
│   └── dashboard.py        # public dashboard
└── tests/
```

## Data model

```sql
books (
  book_id        INTEGER PRIMARY KEY,
  title          TEXT NOT NULL,
  author         TEXT,
  genre          TEXT,
  language       TEXT,      -- e.g. 'English', 'Vietnamese' (Unicode NFC)
  format         TEXT CHECK (format IN ('physical', 'ebook', 'audio')),
  progress_unit  TEXT CHECK (progress_unit IN ('page', 'percent')),
  total_pages    INTEGER,   -- print-equivalent page count, also for ebooks
  added_at       TEXT NOT NULL,
  status         TEXT CHECK (status IN ('reading', 'finished', 'abandoned'))
)

sessions (
  session_id  INTEGER PRIMARY KEY,
  book_id     INTEGER NOT NULL REFERENCES books(book_id),
  started_at  TEXT NOT NULL,
  ended_at    TEXT,           -- NULL means session is active
  start_pos   REAL NOT NULL,  -- page number or percent, per books.progress_unit
  end_pos     REAL,
  note        TEXT
)
```

Rules:

- Timestamps are ISO 8601 **with UTC offset** (`datetime.now().astimezone().isoformat()`).
- Store raw events only. Duration, pace, and fraction complete are derived in `features.py`, never stored.
- At most one active session (`ended_at IS NULL`) at a time.
- Validation: `ended_at > started_at`, `end_pos >= start_pos`, and positions within book bounds. Sessions never overlap and never end in the future.
- Text fields are stripped and stored in Unicode NFC, so Vietnamese diacritics typed on different keyboards group together.
- A session spanning midnight is attributed to its start date for daily aggregates.
- Audiobooks are tracked but excluded from page-based pace calculations.

## Privacy

- `data/raw/` is gitignored. The real database never gets committed.
- `export.py` drops `note` and rounds timestamps to the hour before writing to `data/processed/`.
- The dashboard reads only from `data/processed/` (real) or `data/demo/` (synthetic).
- Committed notebooks read only from `data/processed/` or `data/demo/`, never `data/raw/`, and are saved with all outputs cleared. `tests/test_notebooks.py` enforces both.

## Demo mode

- `synthetic.py` generates a seeded, realistic history (about 6 months, about 15 books, mixed formats and genres, realistic gaps and streaks).
- The dashboard shows a visible "Demo data" badge whenever it is in demo mode. Synthetic and real data must never be mixed silently.

## ML scope (important)

- `eta.py` contains only a **baseline**: remaining pages ÷ recent median pace, and remaining minutes ÷ recent minutes per day.
- The shrinkage/Bayesian ETA model and its backtest are written **by me** in `notebooks/02_eta_model.ipynb`. Do not implement them unless I explicitly ask. You may scaffold the notebook with section headers only.

## Branding

- `brand.md` is the single source of truth for colors, fonts, tone, and visual style.
- Encode it once in `src/reading_tracker/brand.py` (palette constants and a registered plotly template) and in `.streamlit/config.toml`. Everything else imports from there; no hex codes scattered across files.
- If `brand.md` doesn't specify something, choose a neutral default and list it under "assumptions" in your summary. Don't invent brand elements.

## Workflow

- Work one phase at a time. At the end of each phase, stop and summarize what changed, how to run it, and any assumptions.
- Before finishing a phase, run `uv run ruff check . && uv run ruff format --check . && uv run pytest`.
- Use small commits with conventional messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Ask before adding any dependency not listed above.
