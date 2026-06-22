=====================================================================
SURPLUS RECOVERY AUTOMATION TOOLKIT
=====================================================================
Two scripts that automate the two most time-consuming parts of your
surplus recovery business:

  surplus_scraper.py      → pulls surplus lists from county sites
  outreach_automation.py  → writes personalized letters for each claimant

---------------------------------------------------------------------
SETUP (do this once)
---------------------------------------------------------------------

1. INSTALL PYTHON PACKAGES
   Open your Anaconda terminal and run:

     pip install selenium openpyxl pandas requests beautifulsoup4 anthropic

2. INSTALL CHROME + CHROMEDRIVER (for JS-rendered county sites)
   Download ChromeDriver matching your Chrome version:
   https://chromedriver.chromium.org/downloads

   Place chromedriver.exe in the same folder as these scripts,
   or set the environment variable:
     set CHROMEDRIVER_PATH=C:\path\to\chromedriver.exe

3. SET YOUR ANTHROPIC API KEY (for AI-personalized letters)
   Get your key from: https://console.anthropic.com
   In your Anaconda terminal:
     set ANTHROPIC_API_KEY=sk-ant-...
   To make it permanent, add it to your Windows environment variables.

4. EDIT YOUR CONTACT INFO IN outreach_automation.py
   Open the file and fill in the block at the top:
     YOUR_NAME    = "Your Full Name"
     YOUR_COMPANY = "Your Company Name"
     YOUR_PHONE   = "(555) 000-0000"
     YOUR_EMAIL   = "you@yourcompany.com"
     YOUR_ADDRESS = "123 Main St, City, State ZIP"
     YOUR_FEE_PCT = 30

---------------------------------------------------------------------
STEP 1 — PULL SURPLUS LISTS
---------------------------------------------------------------------

Run all counties (Hillsborough FL, Miami-Dade FL, Fulton GA):
  python surplus_scraper.py

Run one county only:
  python surplus_scraper.py --county hillsborough
  python surplus_scraper.py --county miami_dade
  python surplus_scraper.py --county fulton

Watch Chrome browser work (useful for debugging):
  python surplus_scraper.py --county hillsborough --headless false

OUTPUT:
  Creates a file in the pipeline/ folder:
    pipeline/surplus_pipeline_2025-01-15.xlsx

  Open this in Excel. It has two sheets:
    Pipeline     — your working tracker (fill in skip trace data here)
    Instructions — how to use the tracker

PIPELINE COLUMNS:
  Former Owner        → the person you're trying to find
  Property Address    → the foreclosed property (old address)
  Surplus Amount      → how much is waiting (may be blank until you verify)
  Claim Deadline      → when the money expires
  Urgency             → URGENT = less than 6 months left; EXPIRED = gone
  Current Address     → YOU fill this in from skip trace
  Phone Number        → YOU fill this in from skip trace
  Status              → track progress: NEW → CONTACTED → SIGNED → FILED → PAID

---------------------------------------------------------------------
STEP 2 — SKIP TRACE (manual or API)
---------------------------------------------------------------------

For each record in your pipeline, find the current address and phone.

Free/cheap tools:
  spokeo.com, whitepages.com, intelius.com

Professional tools (more accurate):
  tlo.com, risk.lexisnexis.com (Accurint)

Fill in the "Current Address" and "Phone Number" columns in the Excel file.

---------------------------------------------------------------------
STEP 3 — GENERATE OUTREACH LETTERS
---------------------------------------------------------------------

Process all NEW records in your pipeline:
  python outreach_automation.py --pipeline pipeline/surplus_pipeline_2025-01-15.xlsx

Process only 10 records at a time:
  python outreach_automation.py --pipeline pipeline/surplus_pipeline_2025-01-15.xlsx --limit 10

Preview without writing files:
  python outreach_automation.py --pipeline pipeline/surplus_pipeline_2025-01-15.xlsx --dry-run

OUTPUT:
  Creates one .txt file per claimant in the outreach_letters/ folder:
    outreach_letters/John_Smith_Hillsborough_2025-01-15.txt

  Each letter has:
    - Personalized letter body (AI-generated if API key is set, template if not)
    - Placeholder for current address (fill in from skip trace)
    - Internal reference block at the bottom

  Your pipeline Status column is automatically updated to CONTACTED.
  All activity is logged to outreach_log.csv.

SENDING LETTERS:
  Option A — Print and mail (best for initial contact):
    Open each .txt file, fill in the current address, print, mail.

  Option B — Email:
    Copy the letter body into your email client.
    Keep the subject line simple: "Funds that may be owed to you"

  DO NOT auto-send without reviewing each letter. One wrong message
  to the wrong person creates legal exposure. Review is non-negotiable.

---------------------------------------------------------------------
ADDING NEW COUNTIES
---------------------------------------------------------------------

Open surplus_scraper.py and scroll to the COUNTY_CONFIG section.
Copy an existing scraper function (e.g. scrape_miami_dade) and adapt:

  1. Change the URL to your new county's surplus/excess proceeds page
  2. Update the CSS selectors to match the new page structure
  3. Add an entry to COUNTY_CONFIG
  4. Add the function to the SCRAPERS dict at the bottom

Each county site is different. Some post PDFs instead of web tables.
For PDF counties: download the PDF manually, extract the data, and
add it to your pipeline spreadsheet directly.

---------------------------------------------------------------------
TROUBLESHOOTING
---------------------------------------------------------------------

"ChromeDriver not found"
  → Download from https://chromedriver.chromium.org and set CHROMEDRIVER_PATH

"No records collected"
  → The county site structure may have changed. Visit the URL manually
    and check if the surplus data is still there. Update the scraper if needed.

"anthropic package not found"
  → Run: pip install anthropic

"Letter body is generic / not personalized"
  → Check that ANTHROPIC_API_KEY is set. Run: echo %ANTHROPIC_API_KEY%
    If blank, set it and run again.

"Urgency shows UNKNOWN"
  → The sale date wasn't parsed from the county page. Fill in the
    Sale Date column manually in the pipeline Excel file.

---------------------------------------------------------------------
WORKFLOW SUMMARY
---------------------------------------------------------------------

Weekly routine:
  1. python surplus_scraper.py          (Mon morning — pull new records)
  2. Open pipeline Excel, do skip trace  (fill in current addresses/phones)
  3. python outreach_automation.py       (generate personalized letters)
  4. Print and mail letters              (or email)
  5. Follow up by phone (5-7 days later)
  6. Update Status column as deals progress

That's it. The rest is contract signing, document gathering, and filing.
See the training manual for those steps.

=====================================================================
