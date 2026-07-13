# sandbox

## Books scripts

Scripts live in `books/scripts/`. Run them from the repo root with `python books/scripts/<script>.py`.

### Prerequisites

- Python 3 (no third-party packages required)
- `GOODREADS_USER_ID` — the numeric ID from your Goodreads profile URL (`goodreads.com/user/show/12345678`)

### Automated workflow

The GitHub Actions cron (`fetch-books.yml`) runs daily at 6 AM UTC and executes these three steps in order:

1. **`fetch_books.py`** — Pulls your "read" and "currently-reading" shelves from the Goodreads RSS feed and writes `books/data/books.json`.
2. **`sync_all_series.py`** — Re-fetches every series in the index from Goodreads and updates `books/data/goodreads_series_index.json`.
3. **`sync_unread_series_books.py`** — Regenerates `books/data/series_unread.json` by diffing the series index against your read shelf.

### Adding a new series

Find the series page on Goodreads (e.g. `goodreads.com/series/49075-the-locked-tomb`) and run:

```sh
GOODREADS_USER_ID=<your-id> python books/scripts/fetch_books.py  # refresh read list first
python books/scripts/add_series.py https://www.goodreads.com/series/49075-the-locked-tomb
```

`add_series.py` scrapes the series page, upserts it into `goodreads_series_index.json`, and regenerates `series_unread.json`. Commit the updated data files to deploy.

### Manually re-syncing all series

```sh
python books/scripts/sync_all_series.py
```

Useful after Goodreads updates publication dates or after changes to the scraping logic. Fetches each series in the index sequentially (2 s delay between requests) and updates the index in place.

### Data files

| File | Written by | Contents |
|---|---|---|
| `books/data/books.json` | `fetch_books.py` | Read shelf + currently-reading shelf from Goodreads RSS |
| `books/data/goodreads_series_index.json` | `add_series.py` / `sync_all_series.py` | Series metadata and book lists scraped from Goodreads |
| `books/data/series_unread.json` | `sync_unread_series_books.py` | Series books not yet on your read shelf |
| `books/data/ignore.json` | manual | Titles to exclude from series views (e.g. companion novellas) |
