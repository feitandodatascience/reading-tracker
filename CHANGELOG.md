# Changelog

All notable changes to this project. Versions follow [Semantic Versioning](https://semver.org/).

## [1.1.1] - 2026-10-25

### Fixed

- Charts no longer zoom on a drag, a pinch or a swipe. The mode bar with its reset
  button is hidden, so a zoomed chart could not be reset; now a swipe over a chart
  scrolls, which matters where the dashboard is embedded on a phone.

## [1.1.0] - 2026-10-25

The dashboard now wears the Regent brand of the portfolio site, where it is embedded.

### Changed

- **Brand** (`brand.md`, `brand.py`, `.streamlit/config.toml`): deep regent green on
  pearl with one antique-gold accent, replacing the sand and olive palette. Headings in
  Libre Bodoni and text in Jost at weight 450, replacing Glacial Indifference. The theme
  stays light only.
- **Charts** follow the new palette: Regent green bars with the current week in gold, a
  green heatmap ramp, and Haze for abandoned books.
- **Tracker**: the big Start and Stop buttons are Regent green with Pearl text.

### Fixed

- Charts sat on the theme's sunken colour instead of the page colour, because Streamlit
  fills an unset `plot_bgcolor`. Each figure now sets it.

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
