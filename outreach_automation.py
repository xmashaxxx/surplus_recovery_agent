"""
=====================================================================
OUTREACH AUTOMATION
=====================================================================
Takes your pipeline spreadsheet (from surplus_scraper.py) and:

  1. Reads all NEW or CONTACTED records
  2. Uses the Claude API to personalize each outreach letter
  3. Saves one .txt file per claimant (ready to print or email)
  4. Updates the pipeline Status to CONTACTED
  5. Logs everything to outreach_log.csv

THIS SCRIPT NEVER AUTO-SENDS EMAIL.
You review and send each letter yourself. That is intentional —
auto-sending outreach creates legal exposure. The script does the
writing and organizing; you do the sending.

REQUIREMENTS:
  pip install anthropic openpyxl pandas
  Set ANTHROPIC_API_KEY environment variable:
    Windows:  set ANTHROPIC_API_KEY=sk-ant-...
    Mac/Linux: export ANTHROPIC_API_KEY=sk-ant-...

USAGE:
  python outreach_automation.py --pipeline pipeline/surplus_pipeline_2025-01-15.xlsx
  python outreach_automation.py --pipeline pipeline/surplus_pipeline_2025-01-15.xlsx --limit 10
  python outreach_automation.py --pipeline pipeline/surplus_pipeline_2025-01-15.xlsx --status CONTACTED
  python outreach_automation.py --pipeline pipeline/surplus_pipeline_2025-01-15.xlsx --dry-run

YOUR INFO (edit these before running):
=====================================================================
"""

import argparse
import csv
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

# ─── YOUR INFORMATION ─────────────────────────────────────────────
# Edit these before running. These go into every letter.

YOUR_NAME    = "Your Full Name"
YOUR_COMPANY = "Your Company Name"
YOUR_PHONE   = "(555) 000-0000"
YOUR_EMAIL   = "you@yourcompany.com"
YOUR_ADDRESS = "123 Main St, City, State ZIP"
YOUR_FEE_PCT = 30   # your contingency fee percentage

# ─── PATHS ────────────────────────────────────────────────────────
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "outreach_letters")
LOG_FILE    = os.path.join(os.path.dirname(__file__), "outreach_log.csv")


# ═══════════════════════════════════════════════════════════════════
#  LETTER TEMPLATES
#  Claude personalizes these — you can also edit them directly.
# ═══════════════════════════════════════════════════════════════════

LETTER_SYSTEM_PROMPT = """
You are writing a professional, warm, and clear outreach letter on behalf of 
a surplus funds recovery specialist. Your job is to inform a former homeowner 
that money may be owed to them by the county, and that we can help them claim it.

TONE RULES:
- Professional but human. Not corporate-stiff.
- Lead with the money. Don't bury the main point.
- Never make guarantees. Say "may be owed" not "is owed."
- Never mention our fee until the end — and frame it as risk-free.
- Keep it to one page (under 350 words).
- No legal jargon.
- No pressure tactics.

FORMAT: Return only the letter body text, starting with "Dear [Name],"
No subject line, no letterhead instructions — just the body.
""".strip()


def build_letter_prompt(record):
    """Build the user-facing prompt that goes to Claude."""
    amt = record.get("Surplus Amount ($)", "")
    amount_str = (f"approximately ${float(amt):,.0f}" if amt and str(amt).replace(".","").isdigit()
                  else "a significant amount")

    urgency = str(record.get("Urgency", ""))
    deadline_str = ""
    if record.get("Claim Deadline"):
        deadline_str = f"The deadline to claim these funds is {record['Claim Deadline']}."
        if "URGENT" in urgency:
            deadline_str += " This deadline is approaching soon."

    return f"""
Write a letter to inform this person about surplus funds they may be owed.

Former owner name: {record.get('Former Owner', 'the former owner')}
Property address: {record.get('Property Address', 'their former property')}
County and state: {record.get('County', '')}, {record.get('State', '')}
Estimated surplus amount: {amount_str}
{deadline_str}

Our company: {YOUR_COMPANY}
Our contact: {YOUR_NAME}, {YOUR_PHONE}, {YOUR_EMAIL}
Our fee: {YOUR_FEE_PCT}% contingency — no upfront cost, only paid on success

Write a warm, direct letter that:
1. Opens by telling them money may be owed to them
2. Briefly explains why (foreclosure surplus process — keep it simple)
3. Tells them the approximate amount (if known)
4. Explains we help them file the paperwork at no upfront cost
5. Tells them how to contact us
6. Closes warmly
""".strip()


# ═══════════════════════════════════════════════════════════════════
#  CLAUDE API CALL
# ═══════════════════════════════════════════════════════════════════

def generate_letter_claude(record):
    """Calls the Claude API to generate a personalized letter."""
    try:
        import anthropic
    except ImportError:
        print("  anthropic package not installed. Run: pip install anthropic")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set. Using template fallback.")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=LETTER_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_letter_prompt(record)}
            ],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"  Claude API error: {e}")
        return None


def generate_letter_template(record):
    """Fallback template if Claude API is unavailable."""
    name = record.get("Former Owner", "Former Resident")
    address = record.get("Property Address", "your former property")
    county  = record.get("County", "your county")
    state   = record.get("State", "")
    amt     = record.get("Surplus Amount ($)", "")

    amount_str = (f"approximately ${float(amt):,.0f}" if amt and str(amt).replace(".","").isdigit()
                  else "funds that may be significant")
    deadline = record.get("Claim Deadline", "")
    deadline_line = (f"\nImportantly, these funds must be claimed before {deadline}. "
                     "After that date, they are permanently transferred to the state.\n"
                     if deadline else "")

    return f"""Dear {name},

I am writing to let you know that money may be owed to you by {county} County, {state}, as a result of the foreclosure sale of your former property at {address}.

When a foreclosed property sells for more than the amount owed on it, the difference — called "surplus funds" or "excess proceeds" — legally belongs to the former owner. Based on public records, {amount_str} may be sitting in a county account under your name right now.
{deadline_line}
Most people in your situation never hear about this money because the county sends notice to the foreclosed address — which is no longer where you live.

My name is {YOUR_NAME}, and I specialize in helping former homeowners claim these funds. My fee is a simple contingency: {YOUR_FEE_PCT}% of what we recover together. If we don't recover anything, you owe nothing.

To find out exactly what may be available and start the process, please call or email me:

  {YOUR_NAME}
  {YOUR_COMPANY}
  {YOUR_PHONE}
  {YOUR_EMAIL}

There is no obligation, no upfront cost, and no risk to you.

Sincerely,

{YOUR_NAME}
{YOUR_COMPANY}
{YOUR_ADDRESS}"""


# ═══════════════════════════════════════════════════════════════════
#  FULL LETTER (with letterhead block)
# ═══════════════════════════════════════════════════════════════════

def format_full_letter(body, record):
    today = date.today().strftime("%B %d, %Y")
    name  = record.get("Former Owner", "")

    letterhead = f"""{"=" * 65}
{YOUR_COMPANY.upper()}
{YOUR_NAME}
{YOUR_PHONE}  |  {YOUR_EMAIL}
{YOUR_ADDRESS}
{"=" * 65}

{today}

{name}
[CURRENT ADDRESS — fill in from skip trace]
[CITY, STATE ZIP]

"""
    footer = f"""

---
INTERNAL REFERENCE:
  County:       {record.get('County', '')} County, {record.get('State', '')}
  Case #:       {record.get('Case Number', 'N/A')}
  Property:     {record.get('Property Address', '')}
  Sale Date:    {record.get('Sale Date', 'N/A')}
  Surplus Amt:  ${record.get('Surplus Amount ($)', 'Unknown')}
  Urgency:      {record.get('Urgency', '')}
  Generated:    {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    return letterhead + body + footer


# ═══════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════

def log_outreach(record, letter_path, method):
    """Append a row to the CSV outreach log."""
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Date", "Former Owner", "Property Address", "County", "State",
                "Surplus Amount", "Method", "Letter File", "Status"
            ])
        writer.writerow([
            date.today().isoformat(),
            record.get("Former Owner", ""),
            record.get("Property Address", ""),
            record.get("County", ""),
            record.get("State", ""),
            record.get("Surplus Amount ($)", ""),
            method,
            letter_path,
            "LETTER_GENERATED",
        ])


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Surplus outreach letter generator")
    parser.add_argument("--pipeline", required=True,
                        help="Path to pipeline Excel file from surplus_scraper.py")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of letters to generate this run")
    parser.add_argument("--status", default="NEW",
                        help="Which records to process: NEW | CONTACTED | all")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be generated without writing files")
    args = parser.parse_args()

    # ── Load pipeline ──
    if not os.path.exists(args.pipeline):
        print(f"Pipeline file not found: {args.pipeline}")
        sys.exit(1)

    df = pd.read_excel(args.pipeline, sheet_name="Pipeline")
    print(f"Loaded {len(df)} records from pipeline.")

    # ── Filter ──
    if args.status.lower() != "all":
        statuses = [s.strip().upper() for s in args.status.split(",")]
        work_df = df[df["Status"].str.upper().isin(statuses)].copy()
    else:
        work_df = df.copy()

    # Skip expired
    work_df = work_df[~work_df["Urgency"].str.contains("EXPIRED", na=False)]

    # Skip records without an owner name
    work_df = work_df[work_df["Former Owner"].notna() &
                      (work_df["Former Owner"].str.strip() != "") &
                      (work_df["Former Owner"].str.upper() != "SEE DOWNLOAD")]

    if args.limit:
        work_df = work_df.head(args.limit)

    print(f"Records to process: {len(work_df)}")

    if len(work_df) == 0:
        print("Nothing to do — no matching records.")
        sys.exit(0)

    # ── Check API key ──
    use_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    method = "claude_api" if use_claude else "template"
    if not use_claude:
        print("\n[NOTE] ANTHROPIC_API_KEY not found.")
        print("  Using built-in templates. To enable AI personalization:")
        print("  set ANTHROPIC_API_KEY=sk-ant-... (Windows)")
        print("  export ANTHROPIC_API_KEY=sk-ant-... (Mac/Linux)\n")

    # ── Generate letters ──
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generated = 0

    for idx, (_, record) in enumerate(work_df.iterrows(), 1):
        name    = str(record.get("Former Owner", "Unknown")).strip()
        county  = str(record.get("County", "")).strip()
        safe_name = re.sub(r"[^\w\s-]", "", name).replace(" ", "_")[:40]
        filename  = f"{safe_name}_{county}_{date.today().isoformat()}.txt"
        filepath  = os.path.join(OUTPUT_DIR, filename)

        print(f"\n[{idx}/{len(work_df)}] {name} — {county}")

        if args.dry_run:
            print(f"  DRY RUN: would write → {filepath}")
            continue

        # Generate body
        if use_claude:
            print("  Generating personalized letter with Claude...")
            body = generate_letter_claude(record)
            if not body:
                print("  Falling back to template.")
                body = generate_letter_template(record)
                method = "template"
            else:
                method = "claude_api"
            time.sleep(0.5)  # be polite to the API
        else:
            body = generate_letter_template(record)

        # Format full letter
        full_letter = format_full_letter(body, record)

        # Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_letter)

        print(f"  Saved: {filepath}")

        # Log it
        log_outreach(record, filepath, method)

        # Update status in dataframe
        df.loc[record.name, "Status"] = "CONTACTED"
        generated += 1

    # ── Save updated pipeline ──
    if not args.dry_run and generated > 0:
        df.to_excel(args.pipeline, index=False, sheet_name="Pipeline")
        print(f"\nUpdated pipeline: {generated} records marked CONTACTED.")
        print(f"Letters folder: {OUTPUT_DIR}")
        print(f"Log: {LOG_FILE}")

    print(f"\nDone. {generated} letters generated.")
    print("\nNEXT STEPS:")
    print("  1. Fill in [CURRENT ADDRESS] in each letter (from your skip trace)")
    print("  2. Review each letter for accuracy")
    print("  3. Print and mail, or copy into email")
    print("  4. Follow up by phone 5-7 days after mailing")


# ── Fix missing import ──
import re

if __name__ == "__main__":
    main()
