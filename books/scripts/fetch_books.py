"""
Builds books/data/books.json from a Goodreads library CSV export.

Goodreads retired its shelf RSS feeds, so the source of truth is now the
export file committed at books/data/goodreads_library_export.csv.
To refresh it: Goodreads → My Books → Import and export → Export Library,
then replace that file and commit.

Covers and links aren't in the export, so they're carried over from the
previous books.json (or the series index) when the book is already known,
otherwise looked up on Open Library by ISBN.

Usage:
  python books/scripts/fetch_books.py [path/to/export.csv]
"""

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime

sys.path.insert(0, os.path.dirname(__file__))
from add_series import norm_title

DATA_DIR    = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
CSV_PATH    = os.path.join(DATA_DIR, "goodreads_library_export.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "books.json")
INDEX_PATH  = os.path.join(DATA_DIR, "goodreads_series_index.json")


def clean(value: str | None) -> str:
    """Strip whitespace and the ="..." wrapper Goodreads puts around ISBNs."""
    v = (value or "").strip()
    if v.startswith('="') and v.endswith('"'):
        v = v[2:-1]
    return v.strip()


def rfc822(date_str: str) -> str:
    """'2026/10/26' → 'Mon, 26 Oct 2026 00:00:00 +0000' (the format the RSS feed used)."""
    if not date_str:
        return ""
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            d = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            return format_datetime(d)
        except ValueError:
            pass
    return ""


def match_keys(title: str, author: str, isbn: str) -> list[tuple]:
    """Lookup keys, most specific first. Goodreads titles don't always agree
    between sources (the series suffix comes and goes), so also try ISBN and
    the title with the series suffix stripped."""
    a = author.strip().lower()
    keys: list[tuple] = []
    if isbn:
        keys.append(("isbn", isbn))
    keys.append(("title", title.strip().lower(), a))
    keys.append(("norm", norm_title(title), a))
    return keys


def load_known() -> dict[tuple, dict]:
    """Covers/links/avg ratings from the previous books.json and the series index."""
    known: dict[tuple, dict] = {}

    def add(b: dict) -> None:
        for k in match_keys(b.get("title", ""), b.get("author", ""), b.get("isbn", "")):
            known[k] = b

    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            for s in json.load(f).get("series", []):
                for b in s.get("books", []):
                    add(b)
    # previous books.json last, so it wins over the series index
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            prev = json.load(f)
        for shelf in ("read", "currentlyReading"):
            for b in prev.get(shelf, []):
                add(b)
    return known


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


_no_redirect_opener = urllib.request.build_opener(_NoRedirect)


def openlibrary_cover(isbn: str) -> str:
    """Open Library cover URL for an ISBN, or '' if it has none.

    With ?default=false it answers 404 for unknown ISBNs and 200/302 (redirect
    to archive.org storage) for known ones, so don't follow the redirect.
    """
    if not isbn:
        return ""
    url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
    req = urllib.request.Request(url + "?default=false", method="HEAD",
                                 headers={"User-Agent": "reading-tracker/1.0"})
    # Open Library intermittently 502s; retry those. A miss is retried on the
    # next run anyway, since books without a cover get looked up again.
    for attempt in range(4):
        try:
            with _no_redirect_opener.open(req, timeout=15) as resp:
                return url if resp.status == 200 else ""
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                return url
            if e.code < 500:
                return ""
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(2 ** attempt)
    return ""


def to_book(row: dict, known: dict) -> dict:
    title  = clean(row.get("Title"))
    author = clean(row.get("Author"))
    isbn   = clean(row.get("ISBN")) or clean(row.get("ISBN13"))
    prev   = next((known[k] for k in match_keys(title, author, isbn) if k in known), {})

    cover = prev.get("cover", "")
    if not cover:
        cover = openlibrary_cover(isbn)
        print(f"  cover lookup for {title!r}: {'found' if cover else 'none'}")

    book_id = clean(row.get("Book Id"))
    link = prev.get("link") or (f"https://www.goodreads.com/book/show/{book_id}" if book_id else "")

    return {
        "title": title,
        "author": author,
        "cover": cover,
        "link": link,
        "rating": clean(row.get("My Rating")) or "0",
        "dateRead": rfc822(clean(row.get("Date Read"))),
        "dateAdded": rfc822(clean(row.get("Date Added"))),
        "isbn": isbn,
        "pages": clean(row.get("Number of Pages")),
        # newer exports dropped the Average Rating column
        "avgRating": clean(row.get("Average Rating")) or prev.get("avgRating", ""),
        "published": clean(row.get("Original Publication Year")) or clean(row.get("Year Published")),
    }


def sort_key(row: dict) -> str:
    # 'YYYY/MM/DD' sorts lexically; fall back to date added like the RSS feed did
    return clean(row.get("Date Read")) or clean(row.get("Date Added"))


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else CSV_PATH
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Export your library from Goodreads "
              "(My Books → Import and export) and save it there.", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    shelves: dict[str, list[dict]] = {"read": [], "currently-reading": []}
    for row in rows:
        shelf = clean(row.get("Exclusive Shelf"))
        if shelf in shelves and clean(row.get("Title")):
            shelves[shelf].append(row)

    known = load_known()
    output = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "currentlyReading": [to_book(r, known) for r in
                             sorted(shelves["currently-reading"], key=sort_key, reverse=True)],
        "read": [to_book(r, known) for r in
                 sorted(shelves["read"], key=sort_key, reverse=True)],
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✓ {len(output['read'])} read, {len(output['currentlyReading'])} currently reading "
          f"→ {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
