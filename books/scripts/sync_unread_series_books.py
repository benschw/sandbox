"""
Regenerates series_unread.json from books.json and goodreads_series_index.json.

Run by the daily GH Actions workflow to keep series_unread.json in sync
as new books are marked read. Add new series with add_series.py.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from add_series import norm_title, load_ignored

BOOKS_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "books.json")
INDEX_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "goodreads_series_index.json")
UNREAD_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "series_unread.json")


def main():
    with open(os.path.normpath(BOOKS_PATH), encoding="utf-8") as f:
        books_data = json.load(f)

    user_titles = {
        norm_title(b.get("title", ""))
        for shelf in ("read", "currentlyReading")
        for b in books_data.get(shelf, [])
        if b.get("title")
    }

    index_series = []
    index_path = os.path.normpath(INDEX_PATH)
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index_series = json.load(f).get("series", [])

    ignored = load_ignored()

    unread = []
    for series in index_series:
        for bk in series.get("books", []):
            bt = norm_title(bk.get("title", ""))
            if bt not in user_titles and bt not in ignored:
                unread.append({
                    "title":     bk["title"],
                    "series":    series.get("name", ""),
                    "published": bk.get("published", ""),
                })

    with open(os.path.normpath(UNREAD_PATH), "w", encoding="utf-8") as f:
        json.dump(
            {"lastUpdated": datetime.now(timezone.utc).isoformat(), "books": unread},
            f, indent=2, ensure_ascii=False,
        )

    print(f"✓ {len(unread)} unread books across {len(index_series)} indexed series → series_unread.json")


if __name__ == "__main__":
    main()
