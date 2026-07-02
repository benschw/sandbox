"""
Re-fetches every series already in goodreads_series_index.json from Goodreads
and updates the index in place. Useful after adding new fields to add_series.py.

Usage:
  python scripts/sync_all_series.py
"""

import sys
import time
import os

# add scripts/ to path so we can reuse add_series helpers
sys.path.insert(0, os.path.dirname(__file__))
from add_series import fetch_page, parse_series_page, series_key, load_index, save_index, regenerate_unread


def main():
    debug = "--debug" in sys.argv
    index = load_index()
    series_list = index.get("series", [])

    if not series_list:
        print("No series in index yet. Run add_series.py first.")
        return

    print(f"Syncing {len(series_list)} series…\n")
    failed = []

    for i, entry in enumerate(series_list, 1):
        name = entry.get("name", "?")
        url  = entry.get("url", "")
        if not url:
            print(f"[{i}/{len(series_list)}] {name!r} — no URL, skipping")
            failed.append(name)
            continue

        print(f"[{i}/{len(series_list)}] {name!r}")
        try:
            body   = fetch_page(url)
            series = parse_series_page(body, url, debug=debug and i == 1)
            if not series["books"]:
                print(f"  ✗ no books parsed — skipping")
                failed.append(name)
                continue

            sk = series_key(series["name"])
            idx = next(
                (j for j, s in enumerate(index["series"]) if series_key(s["name"]) == sk),
                None,
            )
            if idx is not None:
                index["series"][idx] = series
            else:
                index["series"].append(series)

            save_index(index)
            print(f"  ✓ {len(series['books'])} books")
        except Exception as e:
            print(f"  ✗ {e}")
            failed.append(name)

        if i < len(series_list):
            time.sleep(2)

    print()
    regenerate_unread(index)

    if failed:
        print(f"\nFailed ({len(failed)}): {', '.join(failed)}")
    else:
        print("All series synced.")


if __name__ == "__main__":
    main()
