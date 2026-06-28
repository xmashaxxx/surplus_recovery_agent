# surplus_recovery_agent

An agentic data extraction pipeline for foreclosure surplus recovery. It pulls
unclaimed-surplus records from county clerk websites, normalises them into a
single record schema, and feeds them into a downstream outreach workflow that
contacts former owners about funds they are legally entitled to claim. The
extraction layer is powered by Claude (Haiku 4.5) using the Anthropic tool-use
API, with a deterministic BeautifulSoup parser preserved as a fallback. The
technical thesis is straightforward: county clerk pages are inconsistently
maintained, frequently redesigned, and occasionally retired without notice, a
parser that *understands* a surplus table is more durable than one wired to a
specific DOM path, and pairing it with a deterministic fallback gives you the
resilience of an LLM with the floor of a hand-written scraper.

## Architecture

```
                    raw HTML
                       │
                       ▼
            ┌─────────────────────┐
            │ _largest_table_html │   pre-slice — keeps the biggest <table>,
            │  (noise reduction)  │   drops nav/chrome/scripts
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │   Claude Haiku 4.5  │   tool_choice forced to
            │  extract_surplus_   │   extract_surplus_records →
            │      records        │   schema-conformant dict, no json.loads()
            └──────────┬──────────┘
                       │
              success  │  any failure (no key, transport error,
                       │  unexpected shape, SDK not installed)
                       │           │
                       ▼           ▼
            ┌─────────────────────┐   ┌──────────────────────────┐
            │ normalised records  │   │ _legacy_parse_miami_dade │
            │ (county, state,     │◄──┤   (BeautifulSoup, the    │
            │  surplus_amount as  │   │    deterministic floor)  │
            │  float, etc.)       │   └──────────────────────────┘
            └─────────────────────┘
                       │
                       ▼
                downstream pipeline
              (outreach_automation.py)
```

**Key modules**

- `agentic_parser.py`: the LLM extraction layer. `html_to_records(html, county, state, fallback_fn=None)` is the single public entry point. Internally it pre-slices to the largest `<table>` block, defines an `extract_surplus_records` tool with a strict JSON schema (`former_owner`, `property_address`, `surplus_amount`, `sale_date`, `case_number`, `notes`: all nullable, all required), and pins `tool_choice` to that tool. Claude returns a `tool_use` block whose `input` already deserialises into a Python dict, no markdown stripping, no `json.loads()`, no format drift.
- `surplus_scraper.py`: fetch layer plus the legacy parser. `_legacy_parse_miami_dade()` is the BeautifulSoup implementation that previously did all of the extraction; it is now retained as the `fallback_fn` argument passed into `html_to_records()`. If the API key is missing, the SDK is not installed, or the API call fails for any reason, the agentic parser invokes this function and the pipeline keeps producing records.
- `tests/test_html_parser.py`: comparison harness. Runs both parsers against the same fixture and asserts they agree on record count (within a 10% tolerance), that the critical fields (`former_owner`, `property_address`, `case_number`) are populated on the first record from each side, and that the pre-slice step reduces multi-table HTML down to exactly one table before it ever reaches the model.
- `save_snapshot.py`: one-shot utility for refreshing the local HTML fixture against the live Miami-Dade page (when reachable from the environment).
- `outreach_automation.py`: the downstream consumer. It expects the record schema produced by `html_to_records()` and is intentionally decoupled from the extraction layer.

## The reality of building against real-world data

The demo was designed around three live target sites. Two of them no longer
behave the way they did when the project was scoped:

- **Miami-Dade Clerk surplus page**  the URL hardcoded into the original
  scraper now returns a 404 / silent redirect to a restructured clerk portal.
  The page that exists today is not the page the regex selectors were written
  against.
- **Fulton County, GA**  the comparable surplus listing has moved behind a
  third-party auction platform; the original public URL no longer serves
  surplus data.
- **Broward County (`broward.realforeclose.com`)**  investigated as a
  replacement. Found to be (a) returning HTTP 403 to every request from cloud
  / datacenter IP ranges (block sits at the AWS load balancer, IP-range based,
  not solvable from a server-side environment), and (b) structured as an
  *auction bidding platform* rather than a surplus listing, the data shape is
  different even if you do reach the page. On top of that, Broward is in the
  middle of migrating both of its auction platforms to a new RealAuction
  vendor (new platform went live 2026-07-01), so building against the current
  URLs would be throwaway work. The full investigation, including the three
  candidate paths forward and the questions still pending for the project
  owner, is in [`docs/BROWARD_INVESTIGATION.md`](docs/BROWARD_INVESTIGATION.md).

This is the actual point of the project. The original hand-written scraper
would have continued to "succeed" against 404 pages and silently produce empty
result sets in production. the kind of failure that is invisible until
someone notices the outreach queue has been empty for a month. The agentic
system was built to surface these failures (each layer logs why it fell back),
degrade gracefully (the legacy parser keeps the pipeline running even when the
API path can't), and remain valid against the *structure* of the data rather
than a specific URL that may not exist next quarter.

A second real-world constraint shaped the demo itself: is
operating from Russia, which means residential-IP access to US county clerk
sites isn't available from the development environment. Rather than faking live
access, the demo validates against a structurally-faithful synthetic fixture
(described below) and documents the live-data deployment plan explicitly.

## Validation

The demo is validated against
[`tests/fixtures/miami_dade_synthetic.html`](tests/fixtures/miami_dade_synthetic.html) — a
synthetic HTML file that mirrors the chrome and table structure of the
historical Miami-Dade surplus page (nav, header, breadcrumb, multiple tables,
one main data table) but contains entirely fabricated records. No real
individuals or properties are represented in the fixture.

`tests/test_html_parser.py` runs both parsers against this fixture and asserts:

1. Both parsers return at least one record.
2. Record counts agree within a 10% tolerance (or ±1 record on small fixtures).
3. `former_owner`, `property_address`, and `case_number` are non-null on the
   first record from each parser.
4. The pre-slice step reduces the full multi-table page down to exactly one
   `<table>` before sending it to the model.

The live run as of the last commit produced **10 records from both parsers
with no divergence**, no fallback warning, and the API path returning a
schema-conformant tool-use response on the first call.

**Fixture freshness.** The synthetic fixture date is **2026-06-28**. To refresh
it against the live Miami-Dade page once that URL is reachable again, run
`python save_snapshot.py` from a residential-IP environment — it will fetch
the live page, write `tests/fixtures/miami_dade_snapshot.html`, and print the
new snapshot date.

## Production deployment plan

The path from demo to live production has three steps, in order of effort:

1. **Swap the synthetic fixture for live HTTP.** From a US-based residential
   or proxied environment, `scrape_miami_dade()` (in `surplus_scraper.py`)
   already issues a `requests.get()` against the configured URL and passes the
   HTML straight into `html_to_records()`. No code change is required — the
   only thing the demo skips is the actual network call.
2. **Integrate a working Broward source.** Per
   [`docs/BROWARD_INVESTIGATION.md`](docs/BROWARD_INVESTIGATION.md), the lowest-friction
   live source is `broward.deedauction.net/reports/total_sales` (accessible as
   static HTML, real historical data, owner names require a secondary BCPA
   lookup). The mid-term target is the new RealAuction-vendored platform once
   its Broward-specific URL is published. Both fit the existing
   `requests.get()` → `html_to_records()` shape with no architectural change.
3. **Promote to a multi-agent orchestrator.** Counties fall into three
   distinct classes: static HTML (Miami-Dade, Brevard, Lee — handled by the
   current pattern), third-party auction platforms (RealAuction, GovEase —
   need session/cookie handling), and JS-rendered single-page apps
   (Hillsborough — already uses Selenium). The phased plan for routing each
   county to the right fetch strategy while keeping a single normalised record
   schema lives in [`docs/PLAN.md`](docs/PLAN.md).

## Running the demo

Requirements: Python 3.10+, an Anthropic API key.

```bash
pip install anthropic beautifulsoup4 requests
export ANTHROPIC_API_KEY=sk-ant-...
python tests/test_html_parser.py
```

On Windows PowerShell, set the key with `$env:ANTHROPIC_API_KEY = "sk-ant-..."`.

Expected output (abridged):

```
Mode: html_to_records() will use Claude Haiku (live API)
Fixture: miami_dade_synthetic.html  (... bytes)

Running _legacy_parse_miami_dade()...
  -> 10 records

Running html_to_records()...
  -> 10 records

------------------------------------------------------------
                                   LEGACY     AGENTIC
  Record count                         10          10

  [LEGACY] record[0]:
    former_owner         '...'
    property_address     '...'
    surplus_amount       12345.67
    ...

  [AGENTIC] record[0]:
    former_owner         '...'
    property_address     '...'
    surplus_amount       12345.67
    ...

  Pre-slice check:
    Tables in full HTML : 3
    Tables in slice     : 1  (should be 1)

------------------------------------------------------------
  PASS — all checks passed
```

Running the script without `ANTHROPIC_API_KEY` set is also useful: the
agentic parser detects the missing key, falls back to
`_legacy_parse_miami_dade`, and both sides of the comparison become identical.
That is the deliberate test of the fallback path.

## Built with Claude Code

This project was built in collaboration with
[Claude Code](https://claude.com/claude-code) as a visible co-author on each
commit — including the agentic-parser rewrite that this README documents.
Developed as part of the Claude Corps program.

## License

MIT. See [LICENSE](LICENSE).
