"""
Agentic HTML parser — uses Claude Haiku to extract surplus records from raw HTML.

Entry point: html_to_records(html, county, state, fallback_fn=None)

Strategy:
  1. Pre-slice the HTML to the largest <table> block to reduce noise and tokens.
  2. Send to Claude Haiku with a strict JSON-only extraction prompt.
  3. If the API key is missing, the package isn't installed, or the response
     is not valid JSON, call fallback_fn(html) when provided. Return [] otherwise.
"""

import json
import os
import re

try:
    import anthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

from bs4 import BeautifulSoup

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """\
You are a data extraction tool. Given raw HTML from a county surplus funds webpage,
extract every surplus record you can find into a JSON array.

Return ONLY a JSON array — no explanation, no markdown fences, no other text.
If you find no records, return an empty array: []

Each element must have exactly these keys:
  former_owner, property_address, surplus_amount, sale_date, case_number, notes

Rules:
- surplus_amount: the dollar value as a plain number (e.g. 12345.67), or null
- sale_date: preserve the date exactly as written on the page, or null
- notes: any extra text that doesn't fit another field, or null
- If a field is absent, use null — never omit the key"""


def _largest_table_html(html):
    """Return the HTML string of the largest <table> block, or full HTML if none."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return html
    return str(max(tables, key=lambda t: len(str(t))))


def _parse_amount(value):
    """Normalize a surplus_amount value from the model response to float or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize(raw, county, state):
    return {
        "former_owner":     raw.get("former_owner"),
        "property_address": raw.get("property_address"),
        "surplus_amount":   _parse_amount(raw.get("surplus_amount")),
        "sale_date":        raw.get("sale_date"),
        "case_number":      raw.get("case_number"),
        "county":           county,
        "state":            state,
        "notes":            raw.get("notes"),
    }


def _call_fallback(html, fallback_fn):
    if fallback_fn is None:
        return []
    try:
        return fallback_fn(html)
    except Exception as e:
        print(f"  [agentic_parser] Fallback parser also failed: {e}")
        return []


def html_to_records(html, county, state, fallback_fn=None):
    """
    Extract surplus records from raw HTML using Claude Haiku.

    Parameters
    ----------
    html        : raw HTML string (e.g. requests.get(...).text)
    county      : county name for the 'county' field in each record
    state       : two-letter state abbreviation
    fallback_fn : optional callable fallback_fn(html) -> list[dict]
                  called if the API is unavailable or returns bad JSON

    Returns a list of dicts with keys:
      former_owner, property_address, surplus_amount (float|None),
      sale_date, case_number, county, state, notes
    """
    if not _ANTHROPIC_OK:
        print("  [agentic_parser] anthropic package not installed — using fallback.")
        print("                   Run: pip install anthropic")
        return _call_fallback(html, fallback_fn)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [agentic_parser] ANTHROPIC_API_KEY not set — using fallback parser.")
        return _call_fallback(html, fallback_fn)

    table_html = _largest_table_html(html)
    client = anthropic.Anthropic(api_key=api_key)

    try:
        msg = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Extract all surplus records from this HTML:\n\n{table_html}",
                }
            ],
        )
        raw_text = msg.content[0].text.strip()
        parsed = json.loads(raw_text)
        if not isinstance(parsed, list):
            raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")
    except json.JSONDecodeError as e:
        print(f"  [agentic_parser] Claude returned malformed JSON ({e}) — falling back.")
        return _call_fallback(html, fallback_fn)
    except ValueError as e:
        print(f"  [agentic_parser] Unexpected response shape ({e}) — falling back.")
        return _call_fallback(html, fallback_fn)
    except Exception as e:
        print(f"  [agentic_parser] API error ({e}) — falling back.")
        return _call_fallback(html, fallback_fn)

    return [_normalize(item, county, state) for item in parsed if isinstance(item, dict)]
