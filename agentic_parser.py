"""
Agentic HTML parser — uses Claude Haiku with tool-use to extract surplus records
from raw HTML.

Entry point: html_to_records(html, county, state, fallback_fn=None)

Strategy:
  1. Pre-slice the HTML to the largest <table> block to reduce noise and tokens.
  2. Call Claude Haiku with a tool definition (extract_surplus_records) and
     tool_choice forced to that tool, guaranteeing a schema-conformant structured
     response. Tool-use is used instead of free-text JSON because it eliminates
     markdown fence wrapping and guarantees the output matches our field schema —
     no json.loads(), no format-coercion, no "please return only JSON" gymnastics.
  3. If the API key is missing, the package isn't installed, or the API call
     fails for any reason, call fallback_fn(html) when provided. Return [] otherwise.
"""

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
You are a data extraction tool. Given HTML from a county surplus funds webpage,
call the extract_surplus_records tool with every surplus record you find.

Rules for field values:
- surplus_amount: extract the numeric dollar value as a plain number (e.g. 12345.67),
  or null if not present
- sale_date: preserve the date exactly as written on the page, or null
- notes: any extra text that doesn't fit another field, or null
- Use null for any absent field"""

_EXTRACT_TOOL = {
    "name": "extract_surplus_records",
    "description": (
        "Return all surplus fund records found in the HTML. "
        "Call this once with the complete list — do not call it per record."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "records": {
                "type": "array",
                "description": "All surplus records extracted from the HTML.",
                "items": {
                    "type": "object",
                    "properties": {
                        "former_owner":     {"type": ["string", "null"]},
                        "property_address": {"type": ["string", "null"]},
                        "surplus_amount":   {"type": ["number", "null"]},
                        "sale_date":        {"type": ["string", "null"]},
                        "case_number":      {"type": ["string", "null"]},
                        "notes":            {"type": ["string", "null"]},
                    },
                    "required": [
                        "former_owner", "property_address", "surplus_amount",
                        "sale_date", "case_number", "notes",
                    ],
                },
            }
        },
        "required": ["records"],
    },
}


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
    Extract surplus records from raw HTML using Claude Haiku with tool-use.

    Tool-use (tool_choice forced to extract_surplus_records) guarantees
    schema-conformant structured output: the SDK deserialises the response
    directly into a Python dict, bypassing all JSON-parsing and prompt-
    engineering workarounds needed with free-text responses.

    Parameters
    ----------
    html        : raw HTML string (e.g. requests.get(...).text)
    county      : county name for the 'county' field in each record
    state       : two-letter state abbreviation
    fallback_fn : optional callable fallback_fn(html) -> list[dict]
                  called if the API is unavailable or the call fails for any reason

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
            tools=[_EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "extract_surplus_records"},
            messages=[
                {
                    "role": "user",
                    "content": f"Extract all surplus records from this HTML:\n\n{table_html}",
                }
            ],
        )
        block = msg.content[0]
        if block.type != "tool_use":
            raise ValueError(f"Expected tool_use block, got {block.type!r}")
        raw_records = block.input.get("records", [])
        if not isinstance(raw_records, list):
            raise ValueError(f"Expected 'records' list, got {type(raw_records).__name__}")
    except ValueError as e:
        print(f"  [agentic_parser] Unexpected response shape ({e}) — falling back.")
        return _call_fallback(html, fallback_fn)
    except Exception as e:
        print(f"  [agentic_parser] API error ({e}) — falling back.")
        return _call_fallback(html, fallback_fn)

    return [_normalize(item, county, state) for item in raw_records if isinstance(item, dict)]
