# Changelog

All notable changes to this project. Versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-17

The first complete version: log reading privately, publish a branded dashboard.

### Added

- **Tracker** (`app/tracker.py`): big Start and Stop buttons with the start page
  prefilled, a live timer in hours, minutes and seconds, and expanders to add a
  book, log a past session, and finish or abandon a book. Runs on localhost only.
- **Validation** (`log.py`): one active session at a time, no overlapping or
  future sessions, positions within the book, timestamps stored to the second
  with their UTC offset, text stored in Unicode NFC.
- **Features** (`features.py`): session duration, pages read, pace, daily
  minutes, current and longest streak, and book progress.
- **Baseline ETA** (`eta.py`): pages left ÷ recent median pace ÷ recent minutes
  per day, with a date range from the pace quartiles.
- **Demo data** (`synthetic.py`): a seeded six-month history of about 15 books in
  English and Vietnamese, written through the same validation as real data.
- **Export** (`export.py`): private SQLite to public parquet, without notes or end
  times and with start times rounded down to the hour.
- **Dashboard** (`app/dashboard.py`): current book with finish estimate, calendar
  heatmap and streaks, weekly minutes against a goal, pace by genre, format or
  language, and a timeline of finished and abandoned books. Labelled demo mode.
- **Branding** (`brand.py`, `.streamlit/config.toml`): the brand.md palette and the
  self-hosted Glacial Indifference font.
- **Windows launchers**: double-click `.pyw` files and desktop icons for both apps.
- **Books have a language** (`books.language`), for pace by language.
- CI on GitHub Actions running ruff and pytest.
