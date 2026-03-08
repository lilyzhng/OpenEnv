"""Task: Royalty Dispute Analysis — TechLoom v. DataForge.

Building-block law task that tests the same meta-strategy as IB and hand-draw:
  Discover workspace → Find reference case → Decompose problem → Recompose → Adapt

Task: DataForge systematically underpaid royalties on TechLoom's patent license.
Agent must calculate owed amounts, interest, total damages, and characterize the breach.

Example case (Alpha Dynamics v. SoftCore) shows a completed simpler royalty analysis.
Tool: royalty_calc.py helps compute royalty amounts and interest.
"""
from __future__ import annotations

TASK_ID = "law_royalty_001"
DOMAIN = "Law"

# === Case Data ===

CASE_DATA = """\
# TechLoom Inc. v. DataForge Corp. — Case Facts

## License Agreement (executed 01/01/2024)
- Licensor: TechLoom Inc. ("TechLoom")
- Licensee: DataForge Corp. ("DataForge")
- Licensed IP: TechLoom Data Analytics Patent Portfolio (US Pat. 11,234,567 et al.)
- License term: 5 years (01/01/2024 – 12/31/2028)
- Royalty rate: 8% of net revenue from licensed products
- Minimum annual royalty guarantee: $1,200,000
- Late payment interest: 10% per annum, simple interest from due date
- Payment due: within 30 days of quarter end
- Audit rights: TechLoom may audit DataForge's books with 30 days notice
- Termination clause: Material breach allows termination after 60-day cure period

## Dispute Period: Calendar Year 2025

DataForge reported the following net revenue and made the following payments:

| Quarter  | Quarter End | Net Revenue   | Royalty Paid  |
|----------|-------------|---------------|---------------|
| Q1 2025  | 03/31/2025  | $5,500,000    | $350,000      |
| Q2 2025  | 06/30/2025  | $6,200,000    | $380,000      |
| Q3 2025  | 09/30/2025  | $7,100,000    | $400,000      |
| Q4 2025  | 12/31/2025  | $7,800,000    | $420,000      |

## TechLoom's Claim
TechLoom alleges DataForge systematically underpaid royalties throughout 2025.
TechLoom seeks unpaid royalties, interest, and declaration of material breach.

## DataForge's Defense
DataForge claims certain revenue was from non-licensed products and disputes
the net revenue figures. DataForge has not provided supporting documentation.

## Applicable Law
- Uniform Commercial Code (UCC) Article 2A (Leases) by analogy
- Contract law: breach, material breach, remedies
- Interest calculation per contract terms
- Damages must be proven with reasonable certainty

## Your Assignment
Analyze the case and write a legal memorandum to `memo.txt` with:
1. Royalty calculations (owed vs. paid per quarter)
2. Interest calculations on underpayment
3. Total damages computation
4. Breach characterization (material vs. minor)
5. Recommended remedies

Use python3 for calculations. Write scripts to .py files, then run them.
"""

BRIEF_CONTENT = """\
# TechLoom v. DataForge — Analysis Brief

## Matter
Royalty underpayment dispute under patent license agreement.

## Your Assignment
Using the case data (which will be provided), determine:

1. **Per-quarter royalty owed** (8% of net revenue)
   - Round to nearest dollar

2. **Per-quarter shortfall** (owed minus paid)

3. **Total unpaid royalties** across all 4 quarters

4. **Interest on each quarter's shortfall**
   - 10% per annum, simple interest
   - Accrued from payment due date to analysis date (12/31/2025)
   - Q1 due 04/30/2025 → 8 months to 12/31/2025
   - Q2 due 07/30/2025 → 5 months to 12/31/2025
   - Q3 due 10/30/2025 → 2 months to 12/31/2025
   - Q4 due 01/30/2026 → 0 months (not yet due)

5. **Total damages** (shortfall + interest)

6. **Breach characterization** — is this a material breach?

7. **Recommended remedies**

## Deliverable
Write all results to `memo.txt` in your workspace.

## Next Step
Review the case data in `cases/techloom_v_dataforge.md`.
Check the tools/ directory for calculation utilities.
Study the examples/ directory for a completed analysis pattern.
"""

# === Example Case (completed) — Agent can study this workflow ===

EXAMPLE_BRIEF = """\
# Alpha Dynamics v. SoftCore — Analysis Brief

## Matter
Royalty underpayment dispute. SoftCore licensed Alpha's ML framework
and underpaid royalties for 2 quarters.

## License Terms
- Royalty rate: 5% of net revenue
- Late interest: 8% per annum
- Minimum annual guarantee: $500,000

## Revenue Data
| Quarter  | Net Revenue  | Paid     |
|----------|-------------|----------|
| Q3 2024  | $4,000,000  | $160,000 |
| Q4 2024  | $4,500,000  | $180,000 |
"""

EXAMPLE_CALC = """\
#!/usr/bin/env python3
\"\"\"Alpha Dynamics v. SoftCore — Royalty dispute calculation.

Workflow:
1. Read the case brief to understand the dispute
2. Use royalty_calc from tools/ to compute amounts
3. Calculate interest on shortfalls
4. Write legal memo with findings
\"\"\"
import sys
sys.path.insert(0, "tools")
from royalty_calc import compute_royalty, compute_interest

# Data from case brief
quarters = [
    {"quarter": "Q3 2024", "revenue": 4_000_000, "paid": 160_000, "due_date": "07/30/2024"},
    {"quarter": "Q4 2024", "revenue": 4_500_000, "paid": 180_000, "due_date": "10/30/2024"},
]
rate = 0.05
interest_rate = 0.08
analysis_date = "12/31/2024"

total_owed = 0
total_paid = 0
total_shortfall = 0
total_interest = 0

for q in quarters:
    owed = compute_royalty(q["revenue"], rate)
    shortfall = owed - q["paid"]
    interest = compute_interest(shortfall, interest_rate, q["due_date"], analysis_date)
    total_owed += owed
    total_paid += q["paid"]
    total_shortfall += shortfall
    total_interest += interest
    print(f"{q['quarter']}: Owed ${owed:,.0f}, Paid ${q['paid']:,.0f}, "
          f"Shortfall ${shortfall:,.0f}, Interest ${interest:,.0f}")

print(f"\\nTotal Owed: ${total_owed:,.0f}")
print(f"Total Paid: ${total_paid:,.0f}")
print(f"Total Shortfall: ${total_shortfall:,.0f}")
print(f"Total Interest: ${total_interest:,.0f}")
print(f"Total Damages: ${total_shortfall + total_interest:,.0f}")

# Write memo
with open("alpha_memo.txt", "w") as f:
    f.write("LEGAL MEMORANDUM — Alpha Dynamics v. SoftCore\\n")
    f.write("=" * 50 + "\\n\\n")
    f.write(f"Total Unpaid Royalties: ${total_shortfall:,.0f}\\n")
    f.write(f"Accrued Interest: ${total_interest:,.0f}\\n")
    f.write(f"Total Damages: ${total_shortfall + total_interest:,.0f}\\n")
    f.write(f"\\nBreach Type: Material breach (systematic underpayment)\\n")
    f.write(f"Remedy: Monetary damages + specific performance\\n")
"""

EXAMPLE_MEMO = """\
LEGAL MEMORANDUM — Alpha Dynamics v. SoftCore
==================================================

Total Unpaid Royalties: $60,000
Accrued Interest: $2,600
Total Damages: $62,600

Breach Type: Material breach (systematic underpayment)
Remedy: Monetary damages + specific performance
"""

# === Tool: Royalty Calculator ===

ROYALTY_CALC_TOOL = '''\
"""Royalty and interest calculator — compute royalties and simple interest.

Usage (in your script):
    import sys; sys.path.insert(0, "tools")
    from royalty_calc import compute_royalty, compute_interest

    owed = compute_royalty(revenue=5_500_000, rate=0.08)
    print(f"Royalty owed: ${owed:,.0f}")

    interest = compute_interest(
        principal=90_000,
        annual_rate=0.10,
        from_date="04/30/2025",
        to_date="12/31/2025",
    )
    print(f"Interest: ${interest:,.0f}")
"""
from datetime import datetime

def compute_royalty(revenue: float, rate: float) -> float:
    """Compute royalty amount.

    Args:
        revenue: net revenue for the period
        rate: royalty rate (e.g. 0.08 for 8%)
    Returns:
        Royalty amount as float
    """
    return revenue * rate


def compute_interest(
    principal: float,
    annual_rate: float,
    from_date: str,
    to_date: str,
) -> float:
    """Compute simple interest between two dates.

    Args:
        principal: amount owed
        annual_rate: annual interest rate (e.g. 0.10 for 10%)
        from_date: start date "MM/DD/YYYY"
        to_date: end date "MM/DD/YYYY"
    Returns:
        Interest amount as float
    """
    d1 = datetime.strptime(from_date.strip(), "%m/%d/%Y")
    d2 = datetime.strptime(to_date.strip(), "%m/%d/%Y")
    days = (d2 - d1).days
    if days <= 0:
        return 0.0
    return principal * annual_rate * (days / 365.0)


def check_minimum_guarantee(total_owed: float, minimum: float) -> dict:
    """Check if total royalties meet the minimum annual guarantee.

    Args:
        total_owed: total royalty amount owed for the year
        minimum: minimum annual guarantee amount
    Returns:
        dict with exceeded (bool), shortfall or surplus amount
    """
    if total_owed >= minimum:
        return {"exceeded": True, "surplus": total_owed - minimum}
    else:
        return {"exceeded": False, "shortfall": minimum - total_owed}
'''

# === Distractor Files ===

DISTRACTOR_FILES = {
    "prior_art_analysis.md": (
        "# Prior Art Analysis — TechLoom Patents\n\n"
        "US Patent 11,234,567: Data Analytics Pipeline\n"
        "Filed: 03/15/2020, Granted: 08/22/2022\n"
        "Prior art search revealed 3 relevant references.\n"
        "Conclusion: Patent is valid and enforceable.\n"
        "Not relevant to the royalty dispute.\n"
    ),
    "market_survey.csv": (
        "competitor,market_share,revenue_2025\n"
        "DataForge Corp,12.3%,$26.6MM\n"
        "AnalytiQ Inc,8.7%,$18.8MM\n"
        "ByteInsight,15.1%,$32.6MM\n"
        "InfoStream Ltd,6.2%,$13.4MM\n"
    ),
    "settlement_template.md": (
        "# Settlement Agreement Template\n\n"
        "## Parties\n[Licensor] and [Licensee]\n\n"
        "## Terms\n"
        "1. Payment of $[AMOUNT] within [DAYS] days\n"
        "2. Future compliance with license terms\n"
        "3. Audit rights for [PERIOD]\n"
        "4. Release of all related claims\n"
    ),
    "jurisdiction_notes.md": (
        "# Jurisdiction Notes\n\n"
        "Contract specifies Delaware state court.\n"
        "Delaware statute of limitations for contract: 3 years.\n"
        "UCC applies to goods transactions only, not pure IP licenses.\n"
        "Federal Circuit may have jurisdiction over patent disputes.\n"
    ),
}

# === Criteria (checkable answers) ===
# Agent must compute these numbers from the case data using the royalty_calc tool.
#
# Royalties owed:
#   Q1: 8% × $5,500,000 = $440,000
#   Q2: 8% × $6,200,000 = $496,000
#   Q3: 8% × $7,100,000 = $568,000
#   Q4: 8% × $7,800,000 = $624,000
#   Total owed: $2,128,000
#
# Shortfalls:
#   Q1: $440,000 - $350,000 = $90,000
#   Q2: $496,000 - $380,000 = $116,000
#   Q3: $568,000 - $400,000 = $168,000
#   Q4: $624,000 - $420,000 = $204,000
#   Total shortfall: $578,000
#
# Interest (10% annual simple, from due date to 12/31/2025):
#   Q1: $90,000 × 10% × (245/365) = $6,041  (04/30 to 12/31 = 245 days)
#   Q2: $116,000 × 10% × (154/365) = $4,893  (07/30 to 12/31 = 154 days)
#   Q3: $168,000 × 10% × (62/365) = $2,852   (10/30 to 12/31 = 62 days)
#   Q4: $204,000 × 10% × (0/365) = $0         (01/30/2026, not yet due)
#   Total interest: $13,786
#
# Total damages: $578,000 + $13,786 = $591,786
#
# Minimum guarantee: $1,200,000. Total owed: $2,128,000 > minimum → exceeded.
# Breach: Material (systematic underpayment, 27.2% overall shortfall)

CRITERIA = [
    {"id": 1, "description": "Total royalties owed = $2,128,000",
     "check_keywords": ["2,128,000", "2128000", "2,128"]},
    {"id": 2, "description": "Total royalties paid = $1,550,000",
     "check_keywords": ["1,550,000", "1550000", "1,550"]},
    {"id": 3, "description": "Total shortfall = $578,000",
     "check_keywords": ["578,000", "578000", "578"]},
    {"id": 4, "description": "Q1 shortfall = $90,000",
     "check_keywords": ["90,000", "90000"]},
    {"id": 5, "description": "Q2 shortfall = $116,000",
     "check_keywords": ["116,000", "116000"]},
    {"id": 6, "description": "Q3 shortfall = $168,000",
     "check_keywords": ["168,000", "168000"]},
    {"id": 7, "description": "Q4 shortfall = $204,000",
     "check_keywords": ["204,000", "204000"]},
    {"id": 8, "description": "Total interest on shortfalls approximately $13,786",
     "check_keywords": ["13,786", "13786", "13,7"]},
    {"id": 9, "description": "Total damages approximately $591,786",
     "check_keywords": ["591,786", "591786", "591,7", "591"]},
    {"id": 10, "description": "Breach characterized as material breach",
     "check_keywords": ["material breach", "Material Breach", "MATERIAL BREACH"]},
]
