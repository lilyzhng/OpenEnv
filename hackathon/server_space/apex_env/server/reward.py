"""Rubric-based reward computation for APEX tasks."""

import json
import re
from pathlib import Path
from typing import Any


READABLE_SUFFIXES = {".txt", ".md", ".csv", ".json", ".py", ".sh", ".html", ".xml"}


def collect_workspace_text(workspace_dir: Path) -> str:
    """Read all readable files in the workspace and concatenate their text."""
    parts = []
    for f in sorted(workspace_dir.iterdir()):
        if f.is_file() and f.suffix in READABLE_SUFFIXES:
            try:
                parts.append(f.read_text(errors="replace"))
            except Exception:
                continue
    return " ".join(parts)


def extract_keywords_from_rubric(rubric: list[dict[str, Any]]) -> list[str]:
    """Extract checkable keywords directly from rubric criteria text.

    Instead of regex-guessing keywords, extract the parts that actually matter:
    numbers, percentages, proper nouns, and specific values that the rubric
    says should appear in the answer.
    """
    keywords = []
    for criterion in rubric:
        # Handle all known field names across datasets
        text = " ".join([
            criterion.get("criteria", ""),
            criterion.get("criterion", ""),
            criterion.get("description", ""),
        ]).strip()
        if not text:
            continue

        # Numbers with optional units/symbols (e.g., "24.9x", "$926", "243,275.56 MWh", "7.0%")
        numbers = re.findall(r"\$?[\d,]+\.?\d*[xX%]?\s*(?:million|billion|MWh|GWh)?", text)
        keywords.extend(n.strip() for n in numbers if len(n.strip()) > 1)

        # Hyphenated compound terms (e.g., "Germany-North")
        hyphenated = re.findall(r"\b[A-Z][a-z]+-[A-Z][a-z]+\b", text)
        keywords.extend(hyphenated)

        # Multi-word proper nouns (e.g., "Thermal Overload", "Voltage Violations")
        proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
        keywords.extend(proper_nouns)

        # Acronyms (e.g., "EBIT", "EBITDA", "FCF", "OpFCF", "LBO")
        acronyms = re.findall(r"\b[A-Z][A-Z0-9a-z]{1,10}\b", text)
        # Filter out common words that look like acronyms
        noise = {"States", "Yes", "No", "The", "Act", "Does"}
        keywords.extend(a for a in acronyms if a not in noise)

        # Quoted terms
        quoted = re.findall(r'"([^"]+)"', text)
        keywords.extend(quoted)

    # Deduplicate, keep only meaningful ones
    seen = set()
    result = []
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if kw_lower not in seen and len(kw_lower) > 1:
            seen.add(kw_lower)
            result.append(kw)
    return result


def compute_reward(task: dict[str, Any], workspace_dir: Path) -> float:
    """
    Compute reward from rubric criteria using keyword matching + file existence.

    Returns float in [0, 1].
    """
    score = 0.0

    # 1. Did agent create any output files? (0.3)
    output_files = [
        f
        for f in workspace_dir.iterdir()
        if f.is_file() and f.suffix in READABLE_SUFFIXES
    ]
    if output_files:
        score += 0.3

    # 2. Keyword coverage from rubric (0.7)
    rubric = task.get("rubric", [])
    if isinstance(rubric, str):
        try:
            rubric = json.loads(rubric)
        except (json.JSONDecodeError, TypeError):
            rubric = []

    if not rubric:
        # No rubric available — reward based on output existence only
        return min(score, 1.0)

    agent_text = collect_workspace_text(workspace_dir)
    keywords = extract_keywords_from_rubric(rubric)

    if keywords:
        matched = sum(1 for k in keywords if k.lower() in agent_text.lower())
        score += 0.7 * (matched / len(keywords))

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Action Efficiency — "Spend Less, Do More"
# ---------------------------------------------------------------------------

_TALK_PREFIXES = (
    "I ", "I'", "Let me", "Now ", "First", "Next", "The ", "This ",
    "Here", "Sure", "OK", "Okay", "Great", "Note", "Since ", "To ",
    "We ", "My ", "After", "Before", "Based", "Looking", "There ",
)


def is_talk_action(action: str) -> bool:
    """Return True if an action string is natural-language talk, not a bash command."""
    s = action.strip()
    if not s:
        return True
    if any(s.startswith(p) for p in _TALK_PREFIXES):
        return True
    if s.endswith(".") and not any(c in s for c in "|>&;$`"):
        return True
    return False


def compute_efficiency_reward(
    actions: list[str],
    task_reward: float,
    max_turns: int = 10,
) -> dict[str, float]:
    """Compute action efficiency metrics for "Spend Less, Do More" scoring.

    Components:
    - talk_penalty: up to -0.2 for high talk ratio (wasted tokens)
    - efficiency_bonus: up to +0.1 for completing in fewer turns (only if task_reward > 0)

    Returns dict with individual components and combined final reward.
    """
    if not actions:
        return {
            "talk_ratio": 0.0,
            "talk_penalty": 0.0,
            "efficiency_bonus": 0.0,
            "final_reward": max(task_reward, 0.0),
        }

    talk_count = sum(1 for a in actions if is_talk_action(a))
    talk_ratio = talk_count / len(actions)

    # Talk penalty: linearly scale, max -0.2 when 100% talk
    talk_penalty = -0.2 * talk_ratio

    # Efficiency bonus: only if the model actually produced useful output
    efficiency_bonus = 0.0
    if task_reward > 0:
        turns_used = len(actions)
        efficiency_bonus = 0.1 * max(0.0, 1.0 - turns_used / max_turns)

    final = max(0.0, min(1.0, task_reward + talk_penalty + efficiency_bonus))

    return {
        "talk_ratio": round(talk_ratio, 3),
        "talk_penalty": round(talk_penalty, 3),
        "efficiency_bonus": round(efficiency_bonus, 3),
        "final_reward": round(final, 3),
    }
