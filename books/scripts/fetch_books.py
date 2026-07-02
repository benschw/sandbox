"""
Fetches 'currently-reading' and 'read' shelves from Goodreads RSS
and writes books.json to the repo root.

Requires the GOODREADS_USER_ID environment variable to be set.
Your Goodreads user ID is the number in your profile URL:
  https://www.goodreads.com/user/show/12345678  →  12345678
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

USER_ID = os.environ.get("GOODREADS_USER_ID", "").strip()
if not USER_ID:
    print("Error: GOODREADS_USER_ID is not set.", file=sys.stderr)
    sys.exit(1)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "books.json")


def fetch_url(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; reading-tracker/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"  URL error for {url}: {e.reason}", file=sys.stderr)
        raise


def text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else ""


def parse_rss(xml_data: bytes) -> list[dict]:
    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    if channel is None:
        return []

    books = []
    for item in channel.findall("item"):
        title = text(item, "title")
        if not title:
            continue
        books.append(
            {
                "title": title,
                "author": text(item, "author_name"),
                "cover": text(item, "book_large_image_url") or text(item, "book_image_url"),
                "link": text(item, "link"),
                "rating": text(item, "user_rating"),
                "dateRead": text(item, "user_read_at"),
                "dateAdded": text(item, "user_date_added"),
                "isbn": text(item, "isbn"),
                "pages": text(item, "num_pages"),
                "avgRating": text(item, "average_rating"),
                "published": text(item, "book_published"),
            }
        )
    return books


def fetch_shelf(shelf: str, per_page: int = 200) -> list[dict]:
    all_books: list[dict] = []
    page = 1
    print(f"Fetching '{shelf}' shelf …")
    while True:
        url = (
            f"https://www.goodreads.com/review/list_rss/{USER_ID}"
            f"?shelf={shelf}&per_page={per_page}&page={page}&sort=date_read&order=d"
        )
        data = fetch_url(url)
        books = parse_rss(data)
        all_books.extend(books)
        print(f"  page {page}: {len(books)} book(s)")
        if len(books) < per_page:
            break
        page += 1
        time.sleep(1)
    return all_books


currently_reading = fetch_shelf("currently-reading", per_page=20)
time.sleep(1)  # be polite to Goodreads
read = fetch_shelf("read")

# Goodreads shelf caches update independently; a book just marked read can
# still appear in currently-reading for hours. Drop any overlap by title.
read_titles = {b["title"].lower() for b in read if b.get("title")}
currently_reading = [b for b in currently_reading
                     if b.get("title", "").lower() not in read_titles]

output = {
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
    "currentlyReading": currently_reading,
    "read": read,
}

out_path = os.path.normpath(OUTPUT_PATH)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n✓ Saved to {out_path}")
