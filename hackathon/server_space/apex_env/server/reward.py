"""Rubric-based reward computation for APEX tasks.

Uses OpenEnv's Rubric API (RFC 004) for composable, introspectable reward signals.
Each rubric is a leaf that scores one dimension; they compose via WeightedSum.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, List

import requests

try:
    from openenv.core.rubrics.base import Rubric
    from openenv.core.rubrics.containers import Gate, Sequential, WeightedSum
except ImportError:
    class Rubric:
        """Stub when OpenEnv not installed."""
        def __init__(self): pass
        def __call__(self, action, observation): return self.forward(action, observation)
    Gate = None
    Sequential = None
    WeightedSum = None


READABLE_SUFFIXES = {".txt", ".md", ".csv", ".json", ".py", ".sh", ".html", ".xml"}

_TALK_PREFIXES = (
    "I ", "I'", "Let me", "Now ", "First", "Next", "The ", "This ",
    "Here", "Sure", "OK", "Okay", "Great", "Note", "Since ", "To ",
    "We ", "My ", "After", "Before", "Based", "Looking", "There ",
)


# ---------------------------------------------------------------------------
# Helper functions (unchanged)
# ---------------------------------------------------------------------------

def collect_workspace_text(workspace_dir: Path) -> str:
    """Read all readable files in the workspace (recursively) and concatenate their text."""
    parts = []
    for f in sorted(workspace_dir.rglob("*")):
        if f.is_file() and f.suffix in READABLE_SUFFIXES:
            try:
                parts.append(f.read_text(errors="replace"))
            except Exception:
                continue
    return " ".join(parts)


def extract_keywords_from_rubric(rubric: list[dict[str, Any]]) -> list[str]:
    """Extract checkable keywords directly from rubric criteria text."""
    keywords = []
    for criterion in rubric:
        text = " ".join([
            criterion.get("criteria", ""),
            criterion.get("criterion", ""),
            criterion.get("description", ""),
        ]).strip()
        if not text:
            continue

        numbers = re.findall(r"\$?[\d,]+\.?\d*[xX%]?\s*(?:million|billion|MWh|GWh)?", text)
        keywords.extend(n.strip() for n in numbers if len(n.strip()) > 1)

        hyphenated = re.findall(r"\b[A-Z][a-z]+-[A-Z][a-z]+\b", text)
        keywords.extend(hyphenated)

        proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
        keywords.extend(proper_nouns)

        acronyms = re.findall(r"\b[A-Z][A-Z0-9a-z]{1,10}\b", text)
        noise = {"States", "Yes", "No", "The", "Act", "Does"}
        keywords.extend(a for a in acronyms if a not in noise)

        quoted = re.findall(r'"([^"]+)"', text)
        keywords.extend(quoted)

    seen = set()
    result = []
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if kw_lower not in seen and len(kw_lower) > 1:
            seen.add(kw_lower)
            result.append(kw)
    return result


def check_criteria_progress(task: dict[str, Any], workspace_dir: Path) -> dict[str, Any]:
    """Check how many rubric criteria are currently satisfied in the workspace.

    Returns a dict with progress info for per-step feedback:
        - criteria_total: total number of rubric criteria
        - criteria_met: how many are currently satisfied
        - has_output_files: whether any output files exist
        - files_created: list of files in workspace
    """
    rubric_data = task.get("rubric", task.get("Rubric JSON", "{}"))
    if isinstance(rubric_data, str):
        try:
            rubric_data = json.loads(rubric_data)
        except (json.JSONDecodeError, TypeError):
            rubric_data = {}

    # Normalize to list of criteria dicts
    if isinstance(rubric_data, dict):
        criteria_list = [
            {"description": v.get("description", ""), "criteria": v.get("description", "")}
            for v in rubric_data.values()
        ]
    elif isinstance(rubric_data, list):
        criteria_list = rubric_data
    else:
        criteria_list = []

    # Check files
    output_files = [
        f.name for f in workspace_dir.iterdir()
        if f.is_file() and f.suffix in READABLE_SUFFIXES
    ] if workspace_dir.exists() else []

    if not criteria_list:
        return {
            "criteria_total": 0,
            "criteria_met": 0,
            "has_output_files": len(output_files) > 0,
            "files_created": output_files,
        }

    # For each criterion, extract its keywords and check if ANY appear in workspace
    agent_text = collect_workspace_text(workspace_dir).lower() if output_files else ""
    criteria_met = 0

    for criterion in criteria_list:
        # Extract keywords for this single criterion
        kws = extract_keywords_from_rubric([criterion])
        if not kws:
            continue
        # Criterion is "met" if at least one keyword from it appears
        if any(k.lower() in agent_text for k in kws):
            criteria_met += 1

    return {
        "criteria_total": len(criteria_list),
        "criteria_met": criteria_met,
        "has_output_files": len(output_files) > 0,
        "files_created": output_files,
    }


def is_talk_action(action_str: str) -> bool:
    """Return True if an action string is natural-language talk, not a bash command."""
    s = action_str.strip()
    if not s:
        return True
    if any(s.startswith(p) for p in _TALK_PREFIXES):
        return True
    if s.endswith(".") and not any(c in s for c in "|>&;$`"):
        return True
    return False


# ---------------------------------------------------------------------------
# Hybrid criteria checking: fuzzy numbers + LLM judge
# ---------------------------------------------------------------------------

def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from text, handling $, %, MM, commas, negatives."""
    patterns = [
        r'[-−]?\$?[\d,]+\.?\d*\s*%',      # percentages like 17.9%, -$2.3%
        r'[-−]?\$?[\d,]+\.?\d*\s*[Mm]{2}', # millions like $10.9MM
        r'[-−]?\$?[\d,]+\.?\d*\s*x',       # multiples like 1.5x
        r'[-−]?\$?[\d,]+\.\d+',            # decimals like $140.15
        r'[-−]?\$?[\d,]{2,}',              # integers like 50,000
    ]
    results = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group()
            # Strip non-numeric chars except minus and decimal
            cleaned = re.sub(r'[^0-9.\-−]', '', raw.replace('−', '-'))
            try:
                results.append(float(cleaned))
            except ValueError:
                continue
    return results


def fuzzy_number_match(
    criterion_text: str,
    agent_text: str,
    rel_tolerance: float = 0.05,
    abs_tolerance: float = 0.15,
) -> bool:
    """Check if agent output contains numbers matching the criterion.

    Uses both relative tolerance (5%) and absolute tolerance (0.15) to handle
    rounding differences like 2.9 vs 2.8, 17.9% vs 17.94%.
    """
    expected_nums = _extract_numbers(criterion_text)
    if not expected_nums:
        return False

    agent_nums = _extract_numbers(agent_text)
    if not agent_nums:
        return False

    # All expected numbers must have a close match in agent output
    for expected in expected_nums:
        matched = False
        for actual in agent_nums:
            if expected == 0:
                if abs(actual) <= abs_tolerance:
                    matched = True
                    break
            else:
                rel_diff = abs(actual - expected) / abs(expected)
                abs_diff = abs(actual - expected)
                if rel_diff <= rel_tolerance or abs_diff <= abs_tolerance:
                    matched = True
                    break
        if not matched:
            return False
    return True


def _get_openrouter_key() -> str:
    """Get OpenRouter API key from env or .env.local files."""
    key = os.environ.get("OPENROUTER_APIKEY", "")
    if not key:
        for env_path in [
            Path.home() / "Documents" / "lilyzhng" / "2026" / ".env.local",
            Path.home() / ".env.local",
        ]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("OPENROUTER_APIKEY="):
                        key = line.split("=", 1)[1].strip()
                        break
            if key:
                break
    return key


def llm_criterion_check(
    criterion_desc: str,
    agent_text: str,
    model: str = "anthropic/claude-haiku:beta",
) -> bool:
    """Use a lightweight LLM to judge if a criterion is satisfied.

    Falls back to keyword matching if API is unavailable.
    """
    api_key = _get_openrouter_key()
    if not api_key:
        return False

    # Truncate agent text to keep cost minimal
    snippet = agent_text[:3000]

    prompt = (
        f"You are a strict grading judge. Determine if the agent's output satisfies this criterion.\n\n"
        f"Criterion: {criterion_desc}\n\n"
        f"Agent output (excerpt):\n{snippet}\n\n"
        f"Does the agent's output satisfy this criterion? "
        f"Consider approximate values acceptable (e.g. 17.94% satisfies '17.9%', "
        f"1.5 satisfies '1.5x'). Respond with ONLY 'PASS' or 'FAIL'."
    )

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 5,
                "temperature": 0.0,
            },
            timeout=10,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
        return "PASS" in answer
    except Exception:
        return False


def screenshot_html(html_path: str | Path, output_png: str | Path | None = None) -> str | None:
    """Render an HTML file to a PNG screenshot using Playwright.

    Returns the path to the PNG file, or None on failure.
    """
    import tempfile
    html_path = Path(html_path)
    if not html_path.exists():
        return None

    if output_png is None:
        output_png = Path(tempfile.mktemp(suffix=".png"))
    else:
        output_png = Path(output_png)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 400, "height": 400})
            page.goto(f"file://{html_path.resolve()}")
            page.wait_for_timeout(1000)  # let Rough.js render
            page.screenshot(path=str(output_png))
            browser.close()
        return str(output_png) if output_png.exists() else None
    except Exception:
        return None


def vlm_visual_check(
    image_path: str,
    concept: str,
    model: str = "google/gemini-2.5-flash",
) -> bool:
    """Use a VLM to check if a rendered image depicts the expected concept.

    Uses Claude Sonnet with chain-of-thought: first describe what you see,
    then classify. This gives much better accuracy than a direct PASS/FAIL.
    """
    import base64
    api_key = _get_openrouter_key()
    if not api_key:
        return False

    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Does this hand-drawn illustration depict a {concept}? "
                                    f"Briefly describe what you see, then answer PASS or FAIL on the last line."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}",
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 250,
                "temperature": 0.0,
            },
            timeout=20,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()
        # Check last line for PASS/FAIL
        last_line = answer.strip().split("\n")[-1].upper()
        return "PASS" in last_line
    except Exception:
        return False


def check_criterion_hybrid(
    criterion: dict[str, Any],
    agent_text: str,
    use_llm: bool = True,
) -> bool:
    """Hybrid criterion check: try fuzzy number match first, fall back to LLM.

    Strategy:
    - If criterion has numbers → fuzzy_number_match (deterministic, reliable)
    - If fuzzy match fails AND use_llm → ask Claude Haiku (handles semantic cases)
    - If no LLM → fall back to keyword matching (legacy behavior)
    """
    desc = criterion.get("description", "")
    check_keywords = criterion.get("check_keywords", [])

    # Step 1: Fuzzy number match (fast, deterministic, no API cost)
    if _extract_numbers(desc):
        if fuzzy_number_match(desc, agent_text):
            return True

    # Step 2: Legacy keyword match (fast fallback)
    if any(kw.lower() in agent_text.lower() for kw in check_keywords):
        return True

    # Step 3: LLM judge (semantic understanding, handles edge cases)
    if use_llm and desc:
        return llm_criterion_check(desc, agent_text)

    return False


# ---------------------------------------------------------------------------
# Leaf Rubrics
# ---------------------------------------------------------------------------

class FileExistenceRubric(Rubric):
    """Score 1.0 if the agent created any output files, 0.0 otherwise.

    This is a gate-style check: did the agent actually produce artifacts?
    """

    def forward(self, action: Any, observation: Any) -> float:
        workspace_dir = self._get_workspace(observation)
        if workspace_dir is None:
            return 0.0
        output_files = [
            f for f in workspace_dir.iterdir()
            if f.is_file() and f.suffix in READABLE_SUFFIXES
        ]
        return 1.0 if output_files else 0.0

    def _get_workspace(self, observation: Any) -> Path | None:
        metadata = getattr(observation, "metadata", {}) or {}
        ws = metadata.get("workspace")
        if ws:
            p = Path(ws)
            return p if p.exists() else None
        return None


class KeywordCoverageRubric(Rubric):
    """Score based on how many rubric keywords appear in the agent's output files.

    Extracts keywords from the task rubric (numbers, acronyms, proper nouns)
    and checks what fraction appear in the workspace files.
    """

    def forward(self, action: Any, observation: Any) -> float:
        metadata = getattr(observation, "metadata", {}) or {}
        task = metadata.get("task", {})
        workspace_dir = self._get_workspace(observation)
        if workspace_dir is None or not task:
            return 0.0

        rubric_data = task.get("rubric", [])
        if isinstance(rubric_data, str):
            try:
                rubric_data = json.loads(rubric_data)
            except (json.JSONDecodeError, TypeError):
                rubric_data = []

        if not rubric_data:
            return 0.0

        agent_text = collect_workspace_text(workspace_dir)
        keywords = extract_keywords_from_rubric(rubric_data)
        if not keywords:
            return 0.0

        matched = sum(1 for k in keywords if k.lower() in agent_text.lower())
        return matched / len(keywords)

    def _get_workspace(self, observation: Any) -> Path | None:
        metadata = getattr(observation, "metadata", {}) or {}
        ws = metadata.get("workspace")
        if ws:
            p = Path(ws)
            return p if p.exists() else None
        return None


class TalkPenaltyRubric(Rubric):
    """Penalize agents that waste turns with natural-language filler.

    Scores 1.0 for pure action (0% talk), linearly down to 0.0 at 100% talk.
    Used as a multiplier in the final composition.
    """

    def forward(self, action: Any, observation: Any) -> float:
        metadata = getattr(observation, "metadata", {}) or {}
        actions = metadata.get("actions", [])
        if not actions:
            return 1.0
        talk_count = sum(1 for a in actions if is_talk_action(a))
        talk_ratio = talk_count / len(actions)
        # 1.0 at 0% talk, 0.8 at 100% talk (max 20% penalty)
        return 1.0 - 0.2 * talk_ratio


class EfficiencyBonusRubric(Rubric):
    """Bonus for completing tasks in fewer turns.

    Scores 0.0-1.0 based on how few turns were used relative to max.
    Only meaningful when combined (weighted) with task reward.
    """

    def __init__(self, max_turns: int = 10):
        super().__init__()
        self._max_turns = max_turns

    def forward(self, action: Any, observation: Any) -> float:
        metadata = getattr(observation, "metadata", {}) or {}
        step_count = metadata.get("step", 0)
        return max(0.0, 1.0 - step_count / self._max_turns)


# ---------------------------------------------------------------------------
# Composite Rubric — the full APEX scoring pipeline
# ---------------------------------------------------------------------------

class ApexRubric(Rubric):
    """Full APEX reward: gate on file existence, then weighted keyword + efficiency.

    Architecture (following RFC 004 patterns):
        Sequential(
            Gate(FileExistence) → must create files or score = 0
            WeightedSum(
                KeywordCoverage (0.7),
                EfficiencyBonus (0.1),
            ) × TalkPenalty multiplier
        )

    Introspectable via named_rubrics():
        for name, r in apex_rubric.named_rubrics():
            print(f"{name}: {r.last_score}")
    """

    def __init__(self, max_turns: int = 10):
        super().__init__()
        self.file_existence = FileExistenceRubric()
        self.keyword_coverage = KeywordCoverageRubric()
        self.talk_penalty = TalkPenaltyRubric()
        self.efficiency_bonus = EfficiencyBonusRubric(max_turns=max_turns)

    def forward(self, action: Any, observation: Any) -> float:
        # Gate: must have created output files
        file_score = self.file_existence(action, observation)
        if file_score == 0.0:
            return 0.0

        # Core task score: keyword coverage (primary signal)
        keyword_score = self.keyword_coverage(action, observation)

        # Efficiency bonus (secondary signal)
        eff_score = self.efficiency_bonus(action, observation)

        # Weighted combination: 0.875 keyword + 0.125 efficiency (normalized from 0.7/0.1)
        task_score = 0.3 * file_score + 0.7 * keyword_score

        # Talk penalty as multiplier
        talk_mult = self.talk_penalty(action, observation)

        # Efficiency bonus additive (up to +0.1)
        final = task_score * talk_mult + 0.1 * eff_score

        return max(0.0, min(1.0, final))


# ---------------------------------------------------------------------------
# Backward-compatible function API (used by baseline_eval.py)
# ---------------------------------------------------------------------------

def compute_reward(task: dict[str, Any], workspace_dir: Path) -> float:
    """Compute reward from rubric criteria using keyword matching + file existence.

    Returns float in [0, 1].
    """
    score = 0.0

    output_files = [
        f for f in workspace_dir.iterdir()
        if f.is_file() and f.suffix in READABLE_SUFFIXES
    ]
    if output_files:
        score += 0.3

    rubric = task.get("rubric", [])
    if isinstance(rubric, str):
        try:
            rubric = json.loads(rubric)
        except (json.JSONDecodeError, TypeError):
            rubric = []

    if not rubric:
        return min(score, 1.0)

    agent_text = collect_workspace_text(workspace_dir)
    keywords = extract_keywords_from_rubric(rubric)

    if keywords:
        matched = sum(1 for k in keywords if k.lower() in agent_text.lower())
        score += 0.7 * (matched / len(keywords))

    return min(score, 1.0)


def compute_efficiency_reward(
    actions: list[str],
    task_reward: float,
    max_turns: int = 10,
) -> dict[str, float]:
    """Compute action efficiency metrics for "Spend Less, Do More" scoring.

    Backward-compatible function API. The Rubric-based equivalent is ApexRubric.
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
    talk_penalty = -0.2 * talk_ratio

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
