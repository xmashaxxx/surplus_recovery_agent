# Broward County Site Investigation

**Investigated:** 2026-06-27  
**Investigator:** Claude (automated fetch + search)  
**Status:** Complete — awaiting human decision before code is written

---

## Executive Summary

`broward.realforeclose.com` (the user-specified target) returns HTTP 403 Forbidden
to every programmatic request — including browser-mimicking User-Agent headers and
direct curl. The block is at the AWS Elastic Load Balancer layer and is almost
certainly IP-range based (cloud/datacenter IPs are rejected, residential browser
IPs are allowed). This is not a Cloudflare JS challenge — no cookie or JS execution
will help from a server.

Compounding this: **Broward County is actively transitioning off both of its auction
platforms right now.** `broward.realforeclose.com` and `broward.deedauction.net` are
both being retired in favor of a new RealAuction platform. The new platform went live
July 1, 2026 (yesterday), with the first actual auction on October 26, 2026.

A viable alternative — `broward.deedauction.net/reports/total_sales` — is publicly
accessible as static HTML and carries real historical sale data, but is missing owner
names on the public view. Details and options are below.

---

## Site 1: `broward.realforeclose.com` (Mortgage Foreclosure Auctions)

### What it is
The online bidding platform for Broward County **mortgage foreclosure** sales,
administered by the Broward County Clerk of Court. This is where investors register
and place bids on properties where the court has ordered a foreclosure sale.

### Accessibility
| Method | Result |
|---|---|
| `WebFetch` (default UA) | 403 Forbidden |
| `PowerShell Invoke-WebRequest` with Chrome UA | 403 Forbidden |
| `curl` with Chrome UA | 403 Forbidden |
| Browser on residential IP (Masha's laptop) | Almost certainly works |

The response headers show `Server: awselb/2.0`. The 403 is issued by the AWS load
balancer before the application server is even reached — no amount of header
manipulation will bypass it from a cloud IP. **Selenium or Playwright running on
Masha's local machine (home/office IP) would bypass the block entirely**, because
the IP would be residential.

### URL structure (inferred from platform documentation)
The platform is ColdFusion-based (`.cfm` URLs):
- **Auction calendar:** `index.cfm?zaction=user&zmethod=calendar`
- **Single date's listings:** `index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=MM/DD/YYYY`
- **Individual property:** `index.cfm?zaction=AUCTION&Zmethod=DETAIL&AAID={id}`

Whether the page is static HTML or JavaScript-rendered could not be confirmed —
no page loaded during investigation.

### Surplus data
`broward.realforeclose.com` is a **bidding platform**, not a surplus tracking
system. Mortgage foreclosure surplus (sale price minus amount owed) is held in
the Court Registry and administered by the Broward Clerk of Court. There is
**no publicly accessible surplus list** for mortgage foreclosure on any Broward
website — claimants must file "Owner's Civil Claim for Mortgage Foreclosure Surplus"
directly with the Civil Court Services Division.

**Court Registry contact:** (954) 831-5659

### Platform transition — CRITICAL
Broward is migrating mortgage foreclosure auctions from `realforeclose.com` to a
new RealAuction platform. Timeline:
- New platform live: **July 1, 2026** (yesterday)
- `realforeclose.com` retirement date: not yet announced, but imminent
- Building against `realforeclose.com` now means rebuilding again within weeks

---

## Site 2: `broward.deedauction.net` (Tax Deed Auctions)

### What it is
The online bidding platform for Broward County **tax deed** auctions (properties
sold for delinquent property taxes), administered by the Broward County Records,
Taxes and Treasury Division (RTT). Separate from mortgage foreclosure.

### Accessibility
| Page | Method | Result |
|---|---|---|
| `/reports/total_sales` | WebFetch | **200 OK — static HTML, real data returned** |
| `/auctions` | WebFetch | JS-rendered (template placeholders only) |
| Homepage | WebFetch | Static, accessible |

The prior sale results page is the only data-bearing page that works from a server.

### Data available without login — `/reports/total_sales`

Column headers (verbatim):  
`Tax Deed #` | `Parcel #` | `Homestead` | `Sale Date` | `Opening Bid` | `Winning Bid` | `Notes`

Sample rows (real live data, first 5):

| Tax Deed # | Parcel # | Homestead | Sale Date | Opening Bid | Winning Bid | Notes |
|---|---|---|---|---|---|---|
| 53630 | 484232-10-1265 | No | 9/17/2025 | $985.95 | — | No Bids |
| 53481 | 484123-17-0711 | No | 7/23/2025 | $1,884.94 | $1,884.94 | (none) |
| 53273 | 514107-AC-0450 | Yes | 6/25/2025 | $53,509.69 | $99,300.00 | (none) |
| 53221 | 514124-14-4160 | No | 5/21/2025 | $25,833.40 | $216,300.00 | (none) |
| 53242 | 504234-14-0010 | No | 5/21/2025 | $3,772.35 | $6,000.00 | (none) |

- **Pages:** 38 pages, ~24 records per page (~900 total records)
- **Filter:** Year filter available via `/reports/total_sales?year=YYYY`
- **Row links:** No clickable links on individual rows — plain text only
- **Surplus computation:** Not labeled, but implicit. Row 3 above: Opening $53,510 →
  Winning $99,300 = **~$45,790 surplus**. Row 4: Opening $25,833 → Winning $216,300
  = **~$190,467 surplus**. These are real money sitting in the RTT.

### What's NOT available without login
- **Owner names** — the most critical field for outreach
- Property street addresses (only parcel numbers)
- Contact information

Owner names *can* be retrieved by cross-referencing Parcel # against the
Broward County Property Appraiser database (`bcpa.net`), but that's a second
scraping step. `bcpa.net` could not be tested during investigation (connection
errors — possible temporary block or outage).

### Platform transition — CRITICAL
`broward.deedauction.net` is also shutting down. New RealAuction platform went
live July 1, 2026. First actual auction on new platform: October 26, 2026.
Historical results on `deedauction.net` will likely remain accessible for some
period but the site is in wind-down mode.

### Surplus claims process (tax deed)
- Surplus is held for **120 days** from the date of the Notice of Surplus
- Claim form: "Claim To Receive Surplus Proceeds of Tax Deed Sale" (PDF)
- Filed with Broward RTT at 115 S. Andrews Ave, Room 114, Fort Lauderdale

---

## Site 3: New RealAuction Platform (Going Live Now)

RealAuction (realauction.com) is the company Broward has contracted for both
its mortgage foreclosure and tax deed auctions going forward. The new platform
went live July 1, 2026. The Broward-specific URL is not yet in any public
documentation — it will be linked from
`broward.org/RecordsTaxesTreasury/Pages/Default.aspx` once published.

Targeting this platform is premature — no data exists yet (first auction
October 26, 2026) and the URL is unknown. However, RealAuction is used by
many Florida counties already, so if we can find one live county on their platform,
we can infer the URL pattern for Broward.

---

## Decision Matrix — Three Viable Paths

### Path A: `broward.deedauction.net` — Available now, no browser needed

**Architecture:** `requests.get()` → agentic parser — same as Miami-Dade pattern  
**What we get:** Tax Deed #, Parcel #, Sale Date, Opening Bid, Winning Bid, computed surplus  
**What we don't get:** Owner names (need BCPA cross-reference, untested)  
**Code complexity:** Low — static HTML, 38 pages of pagination  
**Longevity:** Site is winding down but historical data accessible for now  
**Demo quality:** Real live Broward data, real dollar amounts, computable surplus

**Open question for Masha:** Is computing surplus from (Winning Bid - Opening Bid)
accurate enough for the demo, and is a second BCPA lookup for owner names acceptable?

---

### Path B: `broward.realforeclose.com` with Selenium on Masha's local machine

**Architecture:** Playwright/Selenium (Chrome) → fetches page locally → passes HTML
to agentic parser  
**What we get:** Whatever the site shows — likely property address, case number, sale
date, possibly bid amounts (surplus amounts not confirmed)  
**What we don't get:** Can't confirm surplus is even displayed on this site — it may
only exist in court records  
**Code complexity:** Medium — requires Playwright running locally, IP must be residential  
**Longevity:** Platform transitioning (probably dead within weeks)  
**Demo quality:** Depends on whether the site actually shows surplus amounts

**Key question for Masha:** Can you open `broward.realforeclose.com` in your browser
right now? If yes — does any page show a dollar amount labeled "surplus" or "excess
proceeds," or does it only show bid amounts and property info for upcoming/past sales?

---

### Path C: Pivot to a Florida county with a public accessible surplus list

Several Florida counties publish mortgage foreclosure surplus fund lists as
accessible static HTML or downloadable files:

- **Lee County** (`leeclerk.org`) — known to publish surplus list as HTML table
- **Brevard County** (`brevardclerk.us/tax-deed-surplus`) — confirmed accessible,
  lists tax deed surplus
- **Volusia County** — static HTML surplus table
- **Hillsborough County** — already in the scraper (Selenium, complex)

**Architecture:** Same as Miami-Dade — `requests` + agentic parser  
**What we get:** Former owner name, property address, case number, surplus amount,
sale date — the full pipeline-ready record set  
**Longevity:** No transition risk  
**Demo quality:** Strongest — agentic parser extracts real named records with real
dollar amounts, same workflow as the outreach automation

**Downside:** Not Broward (Masha's home county), so she can't personally verify
individual records. But the data is real FL foreclosure surplus data.

---

## Recommendation

If the goal is **a working end-to-end demo by this week**, Path C (Lee or Brevard)
is the lowest-risk path: accessible today, stable URLs, returns the full record
set the outreach pipeline needs.

If **Broward specifically matters** (because Masha can verify data is real and the
business operates there), Path A (`deedauction.net`) is the quickest Broward option,
with the caveat that owner names require a second lookup step.

Path B (`realforeclose.com` with Selenium) is the highest-effort and shortest-lived
option given the July 1 transition.

---

## Questions for Masha Before Any Code is Written

1. **Can you open `broward.realforeclose.com` in your browser?** If yes, navigate to
   a past sale and tell us: does any page show a field called "surplus," "excess
   proceeds," or similar? Or does it only show bid history?

2. **Tax deed vs. mortgage foreclosure?** Are you targeting one type specifically,
   or both? (Different courts, different claim processes, different data sources.)

3. **Is `broward.deedauction.net` data good enough?** It's real Broward tax deed
   data with computable surplus amounts — just no owner names without a second BCPA
   lookup. Acceptable for the demo?

4. **Are you open to Brevard or Lee County** as an alternative if Broward's data
   sources don't expose what we need?

5. **Are you willing to run Selenium locally** on your machine? (Bypasses the IP
   block, but the scraper would only work from your home/office network, not a server.)
