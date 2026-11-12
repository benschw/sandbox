# Books data pipeline. Run from the repo root; `make all` runs every step in order.
PYTHON ?= python3
SCRIPTS := books/scripts

.PHONY: all books series unread

all: books series unread

# Build books/data/books.json from books/data/goodreads_library_export.csv
books:
	$(PYTHON) $(SCRIPTS)/fetch_books.py

# Re-scrape every series in books/data/goodreads_series_index.json
series:
	$(PYTHON) $(SCRIPTS)/sync_all_series.py

# Regenerate books/data/series_unread.json
unread:
	$(PYTHON) $(SCRIPTS)/sync_unread_series_books.py
