"""Task: Market Entry Analysis — NovaTech Latin America Expansion.

Building-block consulting task that tests the same meta-strategy:
  Discover workspace → Find reference case → Decompose problem → Recompose → Adapt

Task: NovaTech wants to expand its SCM SaaS platform into Latin America.
Agent must size the market (TAM/SAM/SOM), analyze unit economics,
recommend entry mode and target markets.

Example case (Alpha Corp → Southeast Asia) shows a completed simpler analysis.
Tool: market_sizing.py helps compute TAM/SAM/SOM and unit economics.
"""
from __future__ import annotations

TASK_ID = "consulting_market_001"
DOMAIN = "Management Consulting"

# === Market Data ===

MARKET_DATA = """\
# NovaTech — Latin America Market Data

## Company Background
NovaTech is a US-based B2B SaaS company specializing in supply chain management (SCM)
software for mid-market companies (100-2,000 employees). Annual revenue: $42MM.
NovaTech wants to expand into Latin America.

## Regional Market Data (2025)

### Total IT Spending
- Latin America total IT spending: $85.0 billion
- Growth rate: 9.2% CAGR (2025-2030)

### B2B SaaS Segment
- B2B SaaS share of total IT spending: 18%
- B2B SaaS market size: $15.3 billion

### Supply Chain Management (SCM) Software
- SCM share of B2B SaaS market: 12%
- SCM market size: calculate from above

### Addressable Segment
- Mid-market companies (100-2,000 employees) represent 45% of SCM market
- This is NovaTech's target segment

## Country-Level Data

| Country    | IT Spend Share | IT Spend ($B) | SaaS Maturity | Regulatory Ease | Score |
|------------|---------------|---------------|---------------|-----------------|-------|
| Brazil     | 45%           | $38.25        | High          | Medium          | 8.5   |
| Mexico     | 20%           | $17.00        | High          | High            | 8.0   |
| Colombia   | 8%            | $6.80         | Medium        | High            | 7.2   |
| Chile      | 6%            | $5.10         | High          | High            | 7.0   |
| Argentina  | 5%            | $4.25         | Medium        | Low             | 4.5   |
| Peru       | 4%            | $3.40         | Low           | Medium          | 5.0   |

## Competitive Landscape
- SAP (dominant in enterprise, weak in mid-market)
- Oracle NetSuite (growing, strong brand)
- TOTVS (Brazilian local champion, 30% mid-market share in Brazil)
- Local players in each country

## Pricing & Unit Economics Benchmarks (LatAm B2B SaaS)
- Average Contract Value (ACV): $48,000/year for mid-market SCM
- Customer Acquisition Cost (CAC): $12,000
- Average customer lifespan: 3.0 years
- Gross margin: 72%

## Market Penetration Benchmarks (new entrant in LatAm)
- Year 1: 2% of SAM (conservative, building brand)
- Year 3: 5% of SAM (established presence)
- Year 5: 8% of SAM (mature operations)

## Entry Mode Options

| Mode           | Investment ($MM) | Time to Revenue | Control | Risk |
|----------------|-----------------|-----------------|---------|------|
| Direct (own)   | $8-12           | 12-18 months    | High    | High |
| Joint Venture   | $3-5            | 6-9 months      | Medium  | Med  |
| Channel Partner | $1-2            | 3-6 months      | Low     | Low  |
"""

BRIEF_CONTENT = """\
# NovaTech — Market Entry Strategy Brief

## Client
NovaTech (US B2B SaaS, SCM platform, $42MM revenue)

## Assignment
Evaluate Latin America as an expansion market and recommend a go-to-market strategy.

Using the market data (in the data/ directory), determine:

1. **Market Sizing**
   - TAM (Total Addressable Market) for SCM SaaS in LatAm
   - SAM (Serviceable Addressable Market) for mid-market segment
   - SOM (Serviceable Obtainable Market) for Year 1, Year 3, Year 5
   - Round to nearest $0.1MM

2. **Unit Economics**
   - LTV (Lifetime Value) per customer
   - LTV/CAC ratio
   - CAC payback period in months
   - Round LTV to nearest $1K, payback to nearest 0.1 month

3. **Entry Mode Recommendation**
   - Recommend one of: Direct, Joint Venture, Channel Partner
   - Justify based on NovaTech's size and market conditions

4. **Target Market Ranking**
   - Rank top 3 countries by attractiveness
   - Justify rankings

## Deliverable
Write all results to `strategy.txt` in your workspace.

## Next Step
Review the market data in `data/latam_market.md`.
Check tools/ directory for market sizing utilities.
Study examples/ directory for a completed analysis pattern.
"""

# === Example Case (completed) — Alpha Corp → Southeast Asia ===

EXAMPLE_BRIEF = """\
# Alpha Corp — Southeast Asia Expansion Brief

## Client
Alpha Corp (US B2B SaaS, HR platform, $28MM revenue)

## Market Data
- SEA total IT spending: $50.0 billion
- B2B SaaS share: 15% → $7.5 billion
- HR software share of B2B SaaS: 10% → TAM = $750MM
- Mid-market segment (target): 40% of TAM → SAM = $300MM
- Penetration: Year 1: 3% → SOM = $9.0MM

## Unit Economics
- ACV: $36,000/year
- CAC: $9,000
- Customer lifespan: 3 years
- LTV: $108,000
- LTV/CAC: 12.0x

## Recommendation
- Entry mode: Joint Venture (balanced risk/control for first international expansion)
- Priority market: Singapore (highest SaaS maturity, English-speaking, regional hub)
"""

EXAMPLE_CALC = """\
#!/usr/bin/env python3
\"\"\"Alpha Corp — Market sizing calculation for SEA expansion.

Workflow:
1. Read the brief to understand the client and market
2. Use market_sizing tool from tools/ to compute TAM/SAM/SOM
3. Calculate unit economics (LTV, LTV/CAC, payback)
4. Write strategy with findings
\"\"\"
import sys
sys.path.insert(0, "tools")
from market_sizing import compute_tam, compute_sam, compute_som, compute_unit_economics

# Data from market brief
total_it_spend = 50_000  # $MM
saas_share = 0.15
segment_share = 0.10
target_share = 0.40

# Market sizing
tam = compute_tam(total_it_spend, saas_share, segment_share)
sam = compute_sam(tam, target_share)
som_y1 = compute_som(sam, penetration=0.03)

print(f"TAM: ${tam:,.1f}MM")
print(f"SAM: ${sam:,.1f}MM")
print(f"Year 1 SOM: ${som_y1:,.1f}MM")

# Unit economics
econ = compute_unit_economics(acv=36_000, cac=9_000, lifespan_years=3.0)
print(f"\\nLTV: ${econ['ltv']:,.0f}")
print(f"LTV/CAC: {econ['ltv_cac_ratio']:.1f}x")
print(f"CAC Payback: {econ['cac_payback_months']:.1f} months")

# Write strategy
with open("alpha_strategy.txt", "w") as f:
    f.write("STRATEGY MEMO — Alpha Corp SEA Expansion\\n")
    f.write("=" * 50 + "\\n\\n")
    f.write(f"TAM: ${tam:,.1f}MM\\n")
    f.write(f"SAM: ${sam:,.1f}MM\\n")
    f.write(f"Year 1 SOM: ${som_y1:,.1f}MM\\n\\n")
    f.write(f"LTV: ${econ['ltv']:,.0f}\\n")
    f.write(f"LTV/CAC Ratio: {econ['ltv_cac_ratio']:.1f}x\\n")
    f.write(f"CAC Payback: {econ['cac_payback_months']:.1f} months\\n\\n")
    f.write(f"Entry Mode: Joint Venture\\n")
    f.write(f"Priority Market: Singapore\\n")
"""

EXAMPLE_STRATEGY = """\
STRATEGY MEMO — Alpha Corp SEA Expansion
==================================================

TAM: $750.0MM
SAM: $300.0MM
Year 1 SOM: $9.0MM

LTV: $108,000
LTV/CAC Ratio: 12.0x
CAC Payback: 3.0 months

Entry Mode: Joint Venture
Priority Market: Singapore
"""

# === Tool: Market Sizing Calculator ===

MARKET_SIZING_TOOL = '''\
"""Market sizing and unit economics calculator.

Usage (in your script):
    import sys; sys.path.insert(0, "tools")
    from market_sizing import compute_tam, compute_sam, compute_som, compute_unit_economics

    tam = compute_tam(total_it_spend=85_000, saas_share=0.18, segment_share=0.12)
    print(f"TAM: ${tam:,.1f}MM")

    sam = compute_sam(tam, target_share=0.45)
    print(f"SAM: ${sam:,.1f}MM")

    som = compute_som(sam, penetration=0.02)
    print(f"Year 1 SOM: ${som:,.1f}MM")

    econ = compute_unit_economics(acv=48_000, cac=12_000, lifespan_years=3.0)
    print(f"LTV: ${econ['ltv']:,.0f}")
    print(f"LTV/CAC: {econ['ltv_cac_ratio']:.1f}x")
"""

def compute_tam(
    total_it_spend: float,
    saas_share: float,
    segment_share: float,
) -> float:
    """Compute Total Addressable Market (TAM).

    Args:
        total_it_spend: total regional IT spending in $MM
        saas_share: B2B SaaS share of IT spending (e.g. 0.18 for 18%)
        segment_share: vertical segment share of SaaS (e.g. 0.12 for 12%)
    Returns:
        TAM in $MM
    """
    return total_it_spend * saas_share * segment_share


def compute_sam(tam: float, target_share: float) -> float:
    """Compute Serviceable Addressable Market (SAM).

    Args:
        tam: Total Addressable Market in $MM
        target_share: target customer segment share (e.g. 0.45 for 45%)
    Returns:
        SAM in $MM
    """
    return tam * target_share


def compute_som(sam: float, penetration: float) -> float:
    """Compute Serviceable Obtainable Market (SOM).

    Args:
        sam: Serviceable Addressable Market in $MM
        penetration: expected market penetration rate (e.g. 0.02 for 2%)
    Returns:
        SOM in $MM
    """
    return sam * penetration


def compute_unit_economics(
    acv: float,
    cac: float,
    lifespan_years: float,
) -> dict:
    """Compute SaaS unit economics.

    Args:
        acv: Average Contract Value (annual) in $
        cac: Customer Acquisition Cost in $
        lifespan_years: average customer lifespan in years
    Returns:
        dict with ltv, ltv_cac_ratio, cac_payback_months
    """
    ltv = acv * lifespan_years
    ltv_cac_ratio = ltv / cac if cac > 0 else 0
    monthly_revenue = acv / 12.0
    cac_payback_months = cac / monthly_revenue if monthly_revenue > 0 else 0

    return {
        "ltv": ltv,
        "ltv_cac_ratio": ltv_cac_ratio,
        "cac_payback_months": cac_payback_months,
    }
'''

# === Distractor Files ===

DISTRACTOR_FILES = {
    "competitor_profiles.md": (
        "# Competitor Deep Dives\n\n"
        "## SAP S/4HANA\n"
        "Revenue: $35B (total), strong in enterprise, weak mid-market.\n"
        "LatAm presence: 15 years, 200+ enterprise clients.\n\n"
        "## Oracle NetSuite\n"
        "Revenue: $2.5B, growing in mid-market.\n"
        "LatAm: Recent expansion into Brazil and Mexico.\n\n"
        "Not directly relevant to NovaTech's market sizing.\n"
    ),
    "regulatory_overview.csv": (
        "country,data_privacy_law,tax_complexity,foreign_ownership_limit\n"
        "Brazil,LGPD (strict),High,100%\n"
        "Mexico,LFPDPPP (moderate),Medium,100%\n"
        "Colombia,Law 1581 (moderate),Medium,100%\n"
        "Chile,Law 19628 (basic),Low,100%\n"
        "Argentina,PDPA (strict),Very High,100%\n"
    ),
    "internal_capabilities.md": (
        "# NovaTech Internal Assessment\n\n"
        "## Engineering\n"
        "- 85 engineers (US-based)\n"
        "- Multi-tenant architecture, supports localization\n"
        "- Spanish/Portuguese UI not yet available\n\n"
        "## Sales\n"
        "- No LatAm sales team\n"
        "- No Spanish/Portuguese-speaking reps\n\n"
        "## Finance\n"
        "- $18MM cash on hand\n"
        "- Could fund $3-5MM international expansion\n"
    ),
    "macroeconomic_forecast.json": (
        '{"region": "Latin America",\n'
        ' "gdp_growth_2025": 2.8,\n'
        ' "inflation_avg": 6.2,\n'
        ' "fx_risk": "moderate",\n'
        ' "note": "Background context only"}\n'
    ),
}

# === Criteria (checkable answers) ===
# Agent must compute these from the market data using market_sizing tool.
#
# TAM = $85,000MM × 18% × 12% = $85,000 × 0.18 × 0.12 = $1,836.0MM
# SAM = $1,836.0MM × 45% = $826.2MM
# Year 1 SOM = $826.2MM × 2% = $16.524MM ≈ $16.5MM
# Year 3 SOM = $826.2MM × 5% = $41.31MM ≈ $41.3MM
# Year 5 SOM = $826.2MM × 8% = $66.096MM ≈ $66.1MM
#
# LTV = $48,000 × 3.0 = $144,000
# LTV/CAC = $144,000 / $12,000 = 12.0x
# CAC Payback = $12,000 / ($48,000/12) = $12,000 / $4,000 = 3.0 months
#
# Entry mode: Joint Venture (best fit for $42MM company, first intl expansion)
# Top market: Brazil (highest score 8.5, largest market 45%)

CRITERIA = [
    {"id": 1, "description": "TAM = $1,836.0MM",
     "check_keywords": ["1,836", "1836", "1.836"]},
    {"id": 2, "description": "SAM = $826.2MM",
     "check_keywords": ["826.2", "826"]},
    {"id": 3, "description": "Year 1 SOM = $16.5MM",
     "check_keywords": ["16.5"]},
    {"id": 4, "description": "Year 3 SOM = $41.3MM",
     "check_keywords": ["41.3"]},
    {"id": 5, "description": "Year 5 SOM = $66.1MM",
     "check_keywords": ["66.1"]},
    {"id": 6, "description": "LTV = $144,000",
     "check_keywords": ["144,000", "144000", "144K", "$144"]},
    {"id": 7, "description": "LTV/CAC ratio = 12.0x",
     "check_keywords": ["12.0x", "12x", "12.0"]},
    {"id": 8, "description": "CAC payback = 3.0 months",
     "check_keywords": ["3.0 month", "3 month"]},
    {"id": 9, "description": "Entry mode recommendation: Joint Venture",
     "check_keywords": ["Joint Venture", "joint venture", "JV"]},
    {"id": 10, "description": "Top target market: Brazil",
     "check_keywords": ["Brazil"]},
]
