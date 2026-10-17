# Reading Tracker

[![CI](https://github.com/feitandodatascience/reading-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/feitandodatascience/reading-tracker/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
<!-- Uncomment once the dashboard is live on Streamlit Community Cloud:
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://<your-app>.streamlit.app)
-->

A personal reading tracker and a public dashboard of my reading habits, built as a
data science portfolio project.

## Overview

- **Log in seconds.** A small private Streamlit app starts and stops reading
  sessions with one click, so the habit (and the data) survives.
- **Show the journey.** A public dashboard turns those sessions into daily
  minutes, streaks, pace by genre and format, and a timeline of finished books.
- **Estimate the finish.** A baseline time-to-finish estimate for the current
  book, built from my own reading history.

## Screenshots

_Coming soon: dashboard screenshots will go here._

## How it works

```
tracker (Streamlit, local) ──> data/raw/reading.db      private, gitignored
                                       │
                                  export.py              drops notes, rounds times to the hour
                                       ▼
                               data/processed/*.parquet ──> dashboard (Streamlit, public)
                                                                ▲
synthetic.py ──> data/demo/demo.db ─────────────────────────────┘  "Demo data" mode
```

- **Raw events only.** SQLite stores books and sessions (start, stop, position).
  Duration, pace, and progress are derived in pandas, never stored.
- **Privacy by design.** The real database never leaves my machine. The public
  dashboard reads only a privacy-filtered export (notes removed, times rounded
  to the hour) or synthetic demo data, and always labels demo data as such.
- **Baseline ETA.** Remaining pages divided by recent median pace, and remaining
  minutes divided by recent minutes per day.

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/feitandodatascience/reading-tracker.git
cd reading-tracker
uv sync
uv run pytest
```

**Tracker (private).** Logs sessions to `data/raw/reading.db`, which is
gitignored, and only listens on this computer:

```bash
uv run streamlit run app/tracker.py --server.address localhost
```

On Windows you can skip the terminal: double-click `app/start_tracker.pyw` (or a
desktop shortcut to it). It starts the tracker in the background on
<http://localhost:8519> and opens it in your browser; double-click again to
reopen the tab.

To try it on a throwaway database first, set `READING_TRACKER_DB` to another
path (for example `data/raw/try.db`) before running the command above.

**Demo data and export.**

```bash
uv run python -m reading_tracker.synthetic  # rebuild data/demo/demo.db (seeded)
uv run python -m reading_tracker.export     # data/raw/reading.db -> data/processed/
```

The export keeps book details, start times rounded down to the hour, durations
and positions. Notes and exact times stay private.

_The dashboard command will be added in the next phase._

## Project structure

```
reading-tracker/
├── app/                    # Streamlit apps: tracker (private) and dashboard (public)
├── data/
│   ├── raw/                # real database (gitignored)
│   ├── demo/               # synthetic demo database
│   └── processed/          # exported public data (notes removed, times rounded)
├── notebooks/              # exploration and the ETA model
├── src/reading_tracker/
│   ├── db.py               # schema, connection, read/write helpers
│   ├── log.py              # session logging and validation
│   ├── features.py         # pace, daily minutes, streaks, progress
│   ├── eta.py              # baseline time-to-finish estimate
│   ├── synthetic.py        # seeded demo data generator
│   ├── export.py           # private db -> public parquet
│   └── brand.py            # colour palette and plotly template
└── tests/
```

## Roadmap

- [x] Project scaffold: uv, ruff, pytest, CI, SQLite schema
- [x] Tracker: start/stop sessions, add books, log past sessions
- [x] Features, synthetic demo data, privacy-safe export, baseline ETA
- [ ] Branded dashboard: progress, calendar heatmap, weekly goal, pace, timeline
- [ ] Deploy the dashboard to Streamlit Community Cloud
- [ ] Bayesian time-to-finish model with a backtest (notebook)

## License

The code is released under the [MIT License](LICENSE). My personal reading data
(`data/processed/`) and personal brand (`brand.md`, `assets/`) are not covered by
it.
