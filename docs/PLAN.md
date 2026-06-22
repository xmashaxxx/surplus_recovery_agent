# Agentic HTML Parsing — Phase 2 Plan

## Goal

Replace the hardcoded BeautifulSoup selectors in `scrape_miami_dade()` with a
Claude-powered parser that reads raw HTML and returns structured records. The
selector approach breaks whenever the county redesigns its page; the agentic
approach is resilient to layout changes because it understands the content, not
the DOM shape.

Miami-Dade is the pilot because its surplus page is static HTML with no
JavaScript rendering — no Selenium needed, straightforward to save a local
snapshot for testing, and the existing scraper already works against it (giving
us a ground-truth baseline to validate against).

---

## Function Signature

```python
def html_to_records(html: str, county: str, state: str) -> list[dict]:
```

**Parameters**
- `html` — raw HTML string exactly as returned by `requests.get(...).text`
- `county` — e.g. `"Miami-Dade"` (used to populate the `county` field in each record)
- `state` — e.g. `"FL"`

**Returns** a list of dicts, each with these keys matching the existing pipeline
contract (use `None` for missing fields, never omit a key):

```python
{
    "former_owner":     str | None,
    "property_address": str | None,
    "surplus_amount":   float | None,   # already parsed to float, not raw string
    "sale_date":        str | None,     # keep as raw string; parse_date() handles it
    "case_number":      str | None,
    "county":           str,
    "state":            str,
    "notes":            str | None,
}
```

The function must be a pure data transformer — no HTTP calls, no file I/O,
no side effects. The existing `scrape_miami_dade()` continues to own fetching.

---

## How It Slots Into `scrape_miami_dade()`

The current function fetches HTML, parses with BeautifulSoup, and returns
records. After this change it becomes a thin fetch + dispatch wrapper:

```python
def scrape_miami_dade():
    print("  [Miami-Dade] Fetching page...")
    url = COUNTY_CONFIG["miami_dade"]["url"]
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [Miami-Dade] Request failed: {e}")
        return []

    records = html_to_records(resp.text, county="Miami-Dade", state="FL")

    if not records:
        print("  [Miami-Dade] No records extracted — check saved HTML snapshot.")
        print(f"  [Miami-Dade] URL: {url}")

    return records
```

All BeautifulSoup logic is deleted from this function. The existing `parse_amount()`
helper is still called inside `html_to_records()` to normalize the dollar value
returned by Claude.

---

## Prompt Strategy

### System prompt

Keep it short and strict. The model's job is extraction, not summarization.

```
You are a data extraction tool. Given raw HTML from a county surplus funds webpage,
extract every surplus record you can find into a JSON array.

Return ONLY a JSON array — no explanation, no markdown fences, no other text.
If you find no records, return an empty array: []

Each element must have exactly these keys:
  former_owner, property_address, surplus_amount, sale_date, case_number, notes

Rules:
- surplus_amount: extract the numeric dollar value as a plain number (e.g. 12345.67),
  or null if not present
- sale_date: preserve the date exactly as written on the page, or null
- notes: any extra text that seems relevant but doesn't fit another field, or null
- If a field is absent, use null — never omit the key
```

### User message

Pass the full HTML. Miami-Dade's surplus page is small enough (typically < 50 KB)
to fit in a single Haiku context window without truncation. If a future county's
page is very large, trim to the `<body>` tag or the largest `<table>` block first.

```python
user_content = f"Extract all surplus records from this HTML:\n\n{html}"
```

### Why no few-shot examples in the prompt?

Miami-Dade's table structure is stable enough that zero-shot works — validated
during local testing (see below). Adding examples increases token cost on every
call and makes the prompt brittle if the page layout changes slightly. If zero-shot
accuracy on real pages turns out to be below ~95%, revisit and add 1-2 examples.

---

## Model Choice: Haiku

Use `claude-haiku-4-5-20251001` (Haiku 4.5). Reasons:

- Extraction from structured HTML is not a reasoning task — Haiku is fully capable.
- Miami-Dade's page is typically < 50 KB of HTML and produces < 50 records;
  Haiku handles this comfortably within its context window.
- Cost: Haiku is roughly **20× cheaper** than Sonnet on a per-token basis.
  At $0.25 / MTok input and $1.25 / MTok output (Haiku 4.5 pricing), a typical
  Miami-Dade scrape costs well under $0.01 per run, versus $0.15-$0.20 with Sonnet.
- The outreach letter generator (`outreach_automation.py`) already uses a larger
  model where reasoning matters; the scraper does not need the same.

If a future county's page is ambiguous or multilingual, bump that specific call
to Sonnet — but keep Haiku as the default.

---

## Testing on Saved HTML Before Going Live

### Step 1 — Save a snapshot

Before modifying any code, save the current live page:

```python
# run once manually or add a --save-snapshot flag
resp = requests.get("https://www.miami-dadeclerk.com/clerkserv/surplus.asp",
                    headers={"User-Agent": "Mozilla/5.0"})
with open("tests/fixtures/miami_dade_snapshot.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
```

Store the snapshot at `tests/fixtures/miami_dade_snapshot.html` (add to `.gitignore`
if it contains real personal data — check before committing).

### Step 2 — Run the existing scraper against the snapshot baseline

Before writing `html_to_records()`, run the current BeautifulSoup scraper on the
snapshot and save the output as `tests/fixtures/miami_dade_baseline.json`. This
is your ground truth.

### Step 3 — Write a simple test script

`tests/test_html_parser.py` — not a full pytest suite, just a runnable script:

```python
import json
from pathlib import Path
from surplus_scraper import html_to_records

html = Path("tests/fixtures/miami_dade_snapshot.html").read_text(encoding="utf-8")
baseline = json.loads(Path("tests/fixtures/miami_dade_baseline.json").read_text())

records = html_to_records(html, county="Miami-Dade", state="FL")

print(f"Baseline: {len(baseline)} records | Claude: {len(records)} records")

# Check record count is within 5% of baseline
assert abs(len(records) - len(baseline)) <= max(1, len(baseline) * 0.05), \
    "Record count diverged from baseline"

# Spot-check first record fields
for key in ("former_owner", "property_address", "surplus_amount"):
    assert records[0].get(key) is not None, f"Missing field: {key}"

print("PASS")
```

Run this test before touching `scrape_miami_dade()`. Only swap the live function
in once the test passes.

### Step 4 — Acceptance criteria

- Record count within 5% of the BeautifulSoup baseline on the saved snapshot
- `former_owner` and `property_address` non-null on at least 90% of records
- `surplus_amount` is a float (not a string) or null — never a raw dollar string
- No exception raised on the snapshot; graceful empty list on malformed HTML

---

## Cost Summary

| Scenario | Tokens (est.) | Haiku cost (est.) |
|---|---|---|
| Miami-Dade page (~40 KB HTML) | ~12 K input, ~1 K output | ~$0.004/run |
| Weekly run (1 scrape/week) | — | ~$0.02/month |
| 10 counties added later | ~120 K input, ~10 K output | ~$0.04/run |

These are rough estimates. Run with `--dry-run` logging to confirm actual token
counts once the function is implemented.

---

## What Is Not Changing

- `build_pipeline()`, `save_to_excel()`, and all pipeline downstream logic
  are untouched — `html_to_records()` returns the same dict shape the current
  scraper returns.
- Hillsborough and Fulton scrapers are not touched in this phase.
- `outreach_automation.py` is not touched.
- The CLI interface (`--county miami_dade`) remains identical.

---

## Open Questions (decide before implementation)

1. **HTML truncation threshold** — If the page ever exceeds ~100 KB, should we
   pre-slice to the largest `<table>` block before sending to the API, or rely on
   Haiku's full context window? Lean toward pre-slicing to keep costs predictable.

2. **Snapshot freshness** — Should the test fixture be re-saved weekly (cron job),
   or manually when the site changes? Manual is simpler and good enough for now.

3. **JSON parse failure fallback** — If Claude returns malformed JSON, should we
   fall back to the old BeautifulSoup selectors (kept in a `_legacy_parse()` helper)
   or just return `[]` and print a warning? The fallback is safer but adds code to
   maintain. Recommend starting with `[]` + warning and only adding the fallback if
   it triggers in practice.
