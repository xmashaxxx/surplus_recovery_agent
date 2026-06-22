"""
Downloads the Miami-Dade surplus page and saves it as a local HTML snapshot
for offline testing of the agentic parser.

Run this whenever you suspect the county site structure has changed.
After saving, update the snapshot date in README.md so future runs know
how fresh the fixture is.

Usage:
  python save_snapshot.py
"""

import os
from datetime import date

import requests

URL      = "https://www.miami-dadeclerk.com/clerkserv/surplus.asp"
OUT_DIR  = os.path.join(os.path.dirname(__file__), "tests", "fixtures")
OUT_FILE = os.path.join(OUT_DIR, "miami_dade_snapshot.html")


def main():
    today = date.today().isoformat()
    print(f"Fetching Miami-Dade surplus page...")

    try:
        resp = requests.get(URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(resp.text)

    print(f"Snapshot saved : {OUT_FILE}")
    print(f"Snapshot date  : {today}")
    print(f"Size           : {len(resp.content):,} bytes")
    print()
    print(f"Next step: update README.md — set snapshot date to {today}")


if __name__ == "__main__":
    main()
