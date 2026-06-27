"""
Parser comparison test — miami_dade_synthetic.html

Runs both parsers against the synthetic fixture and prints a side-by-side
comparison of record counts and first-record field values.

Usage (from project root):
  python tests/test_html_parser.py

Modes:
  - ANTHROPIC_API_KEY set   : html_to_records() calls Claude Haiku; results are
                              compared against _legacy_parse_miami_dade() output.
  - ANTHROPIC_API_KEY unset : html_to_records() falls back to legacy automatically;
                              both sides will be identical (verifies fallback path).
"""

import os
import sys

# Ensure project root is on the path regardless of where the script is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from agentic_parser import html_to_records
from surplus_scraper import _legacy_parse_miami_dade

FIXTURE = Path(__file__).parent / "fixtures" / "miami_dade_synthetic.html"
TOLERANCE = 0.10   # record counts may differ by up to 10% (or 1 record)


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_html():
    if not FIXTURE.exists():
        raise FileNotFoundError(
            f"Fixture not found: {FIXTURE}\n"
            "Run save_snapshot.py to create a real snapshot, or check the path."
        )
    return FIXTURE.read_text(encoding="utf-8")


def _print_record(label, record, index=0):
    print(f"\n  [{label}] record[{index}]:")
    for key, val in record.items():
        print(f"    {key:<20} {val!r}")


def _counts_ok(n_legacy, n_agentic):
    delta = abs(n_legacy - n_agentic)
    threshold = max(1, int(n_legacy * TOLERANCE))
    return delta <= threshold, delta, threshold


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    html = _load_html()

    using_api = bool(os.environ.get("ANTHROPIC_API_KEY"))
    mode = "Claude Haiku (live API)" if using_api else "fallback (no ANTHROPIC_API_KEY set)"
    print(f"\nMode: html_to_records() will use {mode}")
    print(f"Fixture: {FIXTURE.name}  ({len(html):,} bytes)\n")

    # ── run legacy parser ──
    print("Running _legacy_parse_miami_dade()...")
    legacy_records = _legacy_parse_miami_dade(html)
    print(f"  -> {len(legacy_records)} records")

    # ── run agentic parser (may fall back) ──
    print("\nRunning html_to_records()...")
    agentic_records = html_to_records(
        html,
        county="Miami-Dade",
        state="FL",
        fallback_fn=_legacy_parse_miami_dade,
    )
    print(f"  -> {len(agentic_records)} records")

    # ── side-by-side summary ──
    print("\n" + "-" * 60)
    print(f"  {'':30} {'LEGACY':>10}  {'AGENTIC':>10}")
    print(f"  {'Record count':30} {len(legacy_records):>10}  {len(agentic_records):>10}")

    if legacy_records:
        _print_record("LEGACY",  legacy_records[0])
    if agentic_records:
        _print_record("AGENTIC", agentic_records[0])

    # ── pre-slice sanity: verify the agentic path sent only the largest table ──
    from agentic_parser import _largest_table_html
    from bs4 import BeautifulSoup
    table_html = _largest_table_html(html)
    soup_full  = BeautifulSoup(html, "html.parser")
    soup_slice = BeautifulSoup(table_html, "html.parser")
    full_tables  = len(soup_full.find_all("table"))
    slice_tables = len(soup_slice.find_all("table"))
    print(f"\n  Pre-slice check:")
    print(f"    Tables in full HTML : {full_tables}")
    print(f"    Tables in slice     : {slice_tables}  (should be 1)")

    # ── assertions ──
    print("\n" + "-" * 60)
    failures = []

    # 1. Both parsers must return at least one record.
    if not legacy_records:
        failures.append("FAIL: legacy parser returned 0 records")
    if not agentic_records:
        failures.append("FAIL: agentic parser returned 0 records")

    # 2. Record counts must be within tolerance.
    ok, delta, threshold = _counts_ok(len(legacy_records), len(agentic_records))
    if not ok:
        failures.append(
            f"FAIL: record count diverged by {delta} "
            f"(threshold {threshold}, legacy={len(legacy_records)}, agentic={len(agentic_records)})"
        )

    # 3. Key fields on the first record must be non-null in both parsers.
    required_fields = ("former_owner", "property_address", "case_number")
    for field in required_fields:
        for label, records in [("legacy", legacy_records), ("agentic", agentic_records)]:
            if records and records[0].get(field) is None:
                failures.append(f"FAIL: {label} record[0].{field} is None")

    # 4. Pre-slice must reduce to exactly one table.
    if slice_tables != 1:
        failures.append(
            f"FAIL: pre-slice returned {slice_tables} tables (expected 1)"
        )

    if failures:
        for msg in failures:
            print(f"  {msg}")
        sys.exit(1)
    else:
        print("  PASS — all checks passed")


if __name__ == "__main__":
    main()
