"""
Fetches a Goodreads series page and adds it to goodreads_series_index.json.
Also regenerates series_unread.json.

Usage:
  python scripts/add_series.py https://www.goodreads.com/series/229503-the-locked-tomb
"""

import html as html_module
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

_SERIES_PAREN = re.compile(r'^(.+?)\s+\([^)]+?,?\s*#[\d.]+[^)]*\)\s*$')
_VOLUME_RE    = re.compile(r',?\s+volume\s+\d+', re.IGNORECASE)

def base_title(t: str) -> str:
    m = _SERIES_PAREN.match(t or "")
    return m.group(1).strip().lower() if m else (t or "").strip().lower()

def norm_title(t: str) -> str:
    """base_title + strip ', Volume N' for cross-source title matching."""
    return _VOLUME_RE.sub("", base_title(t)).strip()

BOOKS_PATH      = os.path.join(os.path.dirname(__file__), "..", "data", "books.json")
INDEX_PATH      = os.path.join(os.path.dirname(__file__), "..", "data", "goodreads_series_index.json")
UNREAD_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "series_unread.json")
IGNORE_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "ignore.json")


def load_ignored() -> set[str]:
    """Return a set of base-title-normalised titles to filter out."""
    path = os.path.normpath(IGNORE_PATH)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {norm_title(t) for t in json.load(f).get("titles", [])}

GOODREADS_SERIES_RE = re.compile(
    r'^(?P<title>.+?)\s+\((?P<series>[^)]+?)\s*,?\s*#(?P<pos>[\d.]+)[^)]*\)\s*$'
)
GR_BASE = "https://www.goodreads.com"


def series_key(name: str) -> str:
    n = name.lower().strip()
    return n[4:] if n.startswith("the ") else n


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_series_page(body: str, url: str, debug: bool = False) -> dict:
    """Extract series name and full book list from a Goodreads series page."""
    # Series name from SeriesHeader
    header_match = re.search(
        r'data-react-class="ReactComponents\.SeriesHeader"\s+data-react-props="([^"]+)"',
        body,
    )
    series_name = ""
    if header_match:
        header = json.loads(html_module.unescape(header_match.group(1)))
        series_name = header.get("title", "").removesuffix(" Series").strip()

    # Books from SeriesList (two components: primary + other works)
    series_lists = re.findall(
        r'data-react-class="ReactComponents\.SeriesList"\s+data-react-props="([^"]+)"',
        body,
    )
    books = []
    seen_positions = set()
    _debug_printed = False
    for props_enc in series_lists:
        props = json.loads(html_module.unescape(props_enc))
        for entry in props.get("series", []):
            bk = entry.get("book") or {}
            full_title = bk.get("title", "").strip()
            if not full_title:
                continue
            if debug and not _debug_printed:
                print("  [debug] entry keys:", sorted(entry.keys()))
                print("  [debug] book keys: ", sorted(bk.keys()))
                _debug_printed = True
            m = GOODREADS_SERIES_RE.match(full_title)
            position = m.group("pos") if m else ""
            if position in seen_positions:
                continue
            seen_positions.add(position)
            author_obj = bk.get("author") or {}
            book_url = bk.get("bookUrl", "")
            pub_date = bk.get("publicationDate") or entry.get("publicationDate") or ""
            books.append({
                "title": full_title,
                "position": position,
                "author": author_obj.get("name", ""),
                "cover": bk.get("imageUrl", ""),
                "link": GR_BASE + book_url if book_url else "",
                "pages": str(bk.get("numPages") or ""),
                "avgRating": str(round(bk.get("avgRating", 0), 2)) if bk.get("avgRating") else "",
                "published": str(pub_date).strip() if pub_date else "",
            })

    books.sort(key=lambda b: float(b["position"]) if b["position"] else 9999)
    return {"name": series_name, "url": url, "books": books}


def load_index() -> dict:
    path = os.path.normpath(INDEX_PATH)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"series": []}


def save_index(index: dict) -> None:
    index["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    with open(os.path.normpath(INDEX_PATH), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def regenerate_unread(index: dict) -> None:
    """Write series_unread.json: books in the index not in books.json."""
    books_path = os.path.normpath(BOOKS_PATH)
    with open(books_path, encoding="utf-8") as f:
        books_data = json.load(f)

    user_titles = {
        norm_title(b.get("title", ""))
        for shelf in ("read", "currentlyReading")
        for b in books_data.get(shelf, [])
        if b.get("title")
    }
    ignored = load_ignored()

    unread = []
    for series in index.get("series", []):
        for bk in series.get("books", []):
            nt = norm_title(bk.get("title", ""))
            if nt not in user_titles and nt not in ignored:
                unread.append({
                    "title":     bk["title"],
                    "series":    series.get("name", ""),
                    "published": bk.get("published", ""),
                })

    output = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "books": unread,
    }
    with open(os.path.normpath(UNREAD_PATH), "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  → {len(unread)} unread books across all indexed series → series_unread.json")


def main():
    if len(sys.argv) < 2 or not sys.argv[1].startswith("http"):
        print(f"Usage: python {os.path.basename(__file__)} <goodreads-series-url>")
        sys.exit(1)

    url = sys.argv[1].split("?")[0].rstrip("/")
    print(f"Fetching {url} …")
    body = fetch_page(url)

    series = parse_series_page(body, url)
    if not series["books"]:
        print("No books found — page structure may have changed.")
        sys.exit(1)

    print(f"Series: {series['name']!r}  ({len(series['books'])} books)")
    for bk in series["books"]:
        print(f"  #{bk['position']:>4}  {bk['title']!r}")

    # Load index and upsert this series
    index = load_index()
    sk = series_key(series["name"])
    existing = next(
        (i for i, s in enumerate(index["series"]) if series_key(s["name"]) == sk),
        None,
    )
    if existing is not None:
        old_count = len(index["series"][existing]["books"])
        index["series"][existing] = series
        print(f"\nUpdated existing entry ({old_count} → {len(series['books'])} books)")
    else:
        index["series"].append(series)
        print(f"\nAdded new series to index")

    save_index(index)
    print(f"✓ goodreads_series_index.json updated")

    regenerate_unread(index)


if __name__ == "__main__":
    main()
