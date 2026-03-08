"""Demo task: KatNip IRR/NPV analysis — phased dynamic environment.

This is a hand-crafted demo showing what a TEACHING environment looks like
vs an EVAL harness. The task is split into phases with conditional information
release and intermediate feedback.

Task 2287: KatNip Co. financial analysis (IRR, MOIC, NPV, sensitivity)
"""
from __future__ import annotations

TASK_ID = "2287_demo"
DOMAIN = "Finance"
HF_FILE = "documents/2287/KatNip.pdf"

# Phase definitions — each phase has a brief, unlock condition, and criteria group
PHASES = [
    {
        "id": 1,
        "name": "Understand the Brief",
        "brief": (
            "# KatNip Co. — Financial Analysis\n\n"
            "You are an IB analyst. Your MD has asked you to analyze\n"
            "KatNip Co., a company that was granted a patent for a unique\n"
            "animal feeding device.\n\n"
            "Before you begin, review the brief to understand what's required.\n"
            "The brief is in `brief.md` in your workspace.\n"
        ),
        "files_to_release": ["brief.md"],
        "unlock_hint": "Read the brief to understand what analysis is needed.",
        "criteria_range": [],  # No criteria to check yet
    },
    {
        "id": 2,
        "name": "Extract Financial Data",
        "brief": (
            "Good — you've reviewed the brief. Now you need the financial data.\n"
            "The company's financial details are in `KatNip.pdf`.\n"
            "Extract the cash flow schedule and key assumptions.\n"
        ),
        "files_to_release": ["KatNip.pdf"],
        "unlock_hint": "Extract the cash flows and investment amounts from the PDF.",
        "criteria_range": [],  # Data extraction, no final answers yet
    },
    {
        "id": 3,
        "name": "Calculate IRR and MOIC",
        "brief": (
            "You have the data. Now calculate:\n"
            "1. The IRR for KatNip\n"
            "2. The MOIC (Multiple on Invested Capital)\n\n"
            "Write your results to `analysis.txt`.\n"
            "Round IRR to nearest tenth of a percentage point, MOIC to nearest tenth.\n"
        ),
        "files_to_release": [],
        "unlock_hint": "Calculate IRR and MOIC from the cash flow schedule.",
        "criteria_range": [0, 1],  # criterion 1 (IRR) and 2 (MOIC)
    },
    {
        "id": 4,
        "name": "Calculate NPV at Multiple Discount Rates",
        "brief": (
            "IRR and MOIC look good. Now calculate NPV at three discount rates:\n"
            "- NPV at 10% discount\n"
            "- NPV at 15% discount\n"
            "- NPV at 20% discount\n\n"
            "Round NPV to nearest tenth of a million. Add results to `analysis.txt`.\n"
        ),
        "files_to_release": [],
        "unlock_hint": "Calculate NPV using XNPV with the cash flow dates.",
        "criteria_range": [2, 3, 4],  # criteria 3-5 (NPV at 10/15/20%)
    },
    {
        "id": 5,
        "name": "Sensitivity Analysis",
        "brief": (
            "NPV calculations complete. Final step — sensitivity analysis:\n"
            "1. Required Sale Value to achieve 15%, 20%, and 25% IRR\n"
            "2. Required Unit Profit Price to achieve 15%, 20%, and 25% IRR\n\n"
            "Round Sale Value to nearest tenth of a million, Unit Price to nearest cent.\n"
            "Add results to `analysis.txt`. When done, send: done\n"
        ),
        "files_to_release": [],
        "unlock_hint": "Back-solve required values using goal seek or optimization.",
        "criteria_range": [5, 6, 7, 8, 9, 10],  # criteria 6-11
    },
]

# The brief.md content — high-level task description without the full details
BRIEF_CONTENT = """# KatNip Co. — Analysis Brief

## Company
KatNip Co. ("KatNip") was granted a patent for a unique animal feeding device.

## Your Assignment
Using the financial data (which will be provided), determine:

1. **IRR and MOIC** for the Company
   - Round IRR to nearest tenth of a percentage point
   - Round MOIC to nearest tenth

2. **NPV** at 10%, 15%, and 20% discount rates
   - Round to nearest tenth of a million

3. **Required Sale Value** to achieve 15%, 20%, and 25% IRR
   - Round to nearest tenth of a million

4. **Required Unit Profit Price** to achieve 15%, 20%, and 25% IRR
   - Round to nearest cent

## Deliverable
Write all results to `analysis.txt` in your workspace.

## Note
You will receive the financial data after reviewing this brief.
Request it when you're ready.
"""

# Criteria list (extracted from rubric, in order)
CRITERIA = [
    {"id": 1, "description": "IRR = 17.9%", "check_keywords": ["17.9%", "17.9", "17.8%", "18.0%"]},
    {"id": 2, "description": "MOIC = 1.5x", "check_keywords": ["1.5x", "1.5X", "1.5 x"]},
    {"id": 3, "description": "NPV at 10% = $10.9MM", "check_keywords": ["10.9", "$10.9"]},
    {"id": 4, "description": "NPV at 15% = $3.7MM", "check_keywords": ["3.7", "$3.7"]},
    {"id": 5, "description": "NPV at 20% = -$2.3MM", "check_keywords": ["-2.3", "-$2.3", "($2.3"]},
    {"id": 6, "description": "Sale Value for 15% IRR = $2.9MM", "check_keywords": ["2.9", "$2.9"]},
    {"id": 7, "description": "Sale Value for 20% IRR = $15.7MM", "check_keywords": ["15.7", "$15.7"]},
    {"id": 8, "description": "Sale Value for 25% IRR = $31.6MM", "check_keywords": ["31.6", "$31.6"]},
    {"id": 9, "description": "Unit Price for 15% IRR = $140.15", "check_keywords": ["140.15", "$140.15"]},
    {"id": 10, "description": "Unit Price for 20% IRR = $157.05", "check_keywords": ["157.05", "$157.05"]},
    {"id": 11, "description": "Unit Price for 25% IRR = $174.45", "check_keywords": ["174.45", "$174.45"]},
]
