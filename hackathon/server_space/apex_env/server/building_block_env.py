"""Building-block environment — agent discovers, decomposes, recomposes.

Design principles:
1. Provide building blocks (tools, data, compute)
2. Tell agent if it's right (per-step criteria feedback)
3. Don't tell agent how to build (agent decides decomposition)
4. Don't tell agent where blocks are (agent discovers context via bash)

Inspired by /hand-draw skill: "basic elements → compositions"
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

try:
    from .bash_executor import BashExecutor
    from .reward import collect_workspace_text
    from .demo_task import CRITERIA, DATA_CONTENT, BRIEF_CONTENT
except ImportError:
    from bash_executor import BashExecutor
    from reward import collect_workspace_text
    from demo_task import CRITERIA, DATA_CONTENT, BRIEF_CONTENT


# Distractor files — agent must figure out which are relevant
# Building block: XIRR utility — agent must discover and use it
XIRR_TOOL = '''\
"""XIRR calculator — compute IRR for irregular cash flows with dates.

Usage (in your script):
    import sys; sys.path.insert(0, "tools")
    from xirr_tool import xirr, xnpv

    dates = ["03/03/2024", "12/31/2024", "06/30/2025"]
    cash_flows = [-50.0, 7.5, 8.25]
    rate = xirr(dates, cash_flows)
    print(f"IRR: {rate*100:.1f}%")

    npv = xnpv(0.10, dates, cash_flows)
    print(f"NPV at 10%: {npv:.1f}")
"""
from datetime import datetime

def _parse_date(s):
    """Parse MM/DD/YYYY date string."""
    return datetime.strptime(s.strip(), "%m/%d/%Y")

def xnpv(rate, dates, cash_flows):
    """Net present value for irregular cash flows.

    Args:
        rate: annual discount rate (e.g. 0.10 for 10%)
        dates: list of date strings "MM/DD/YYYY"
        cash_flows: list of cash flow amounts (negative = outflow)
    Returns:
        NPV as float
    """
    d0 = _parse_date(dates[0])
    total = 0.0
    for i, (d, cf) in enumerate(zip(dates, cash_flows)):
        dt = _parse_date(d)
        years = (dt - d0).days / 365.25
        total += cf / (1 + rate) ** years
    return total

def xirr(dates, cash_flows, guess=0.1, tol=1e-9, max_iter=1000):
    """Compute IRR using Newton\'s method for irregular cash flows.

    Args:
        dates: list of date strings "MM/DD/YYYY"
        cash_flows: list of cash flow amounts
        guess: initial rate guess (default 0.1 = 10%)
    Returns:
        IRR as decimal (e.g. 0.12 for 12%)
    """
    d0 = _parse_date(dates[0])
    year_fracs = [((_parse_date(d) - d0).days / 365.25) for d in dates]

    rate = guess
    for _ in range(max_iter):
        npv = sum(cf / (1 + rate) ** yf for cf, yf in zip(cash_flows, year_fracs))
        dnpv = sum(-yf * cf / (1 + rate) ** (yf + 1) for cf, yf in zip(cash_flows, year_fracs))
        if abs(dnpv) < 1e-15:
            break
        new_rate = rate - npv / dnpv
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate
    return rate

'''

DISTRACTOR_FILES = {
    "project_beta_summary.md": (
        "# Project Beta — Renewable Energy Fund\n\n"
        "This project involves a $200MM wind farm investment.\n"
        "Expected IRR: 12-15%. Not related to KatNip.\n"
    ),
    "market_comps.csv": (
        "company,ev_ebitda,pe_ratio,sector\n"
        "PetFeed Inc,8.2,15.3,Consumer\n"
        "AnimalTech Co,11.5,22.1,Technology\n"
        "FarmSupply LLC,6.8,12.7,Agriculture\n"
    ),
    "memo_template.md": (
        "# Investment Memo Template\n\n"
        "## Executive Summary\n[TODO]\n\n"
        "## Financial Analysis\n[TODO]\n\n"
        "## Recommendation\n[TODO]\n"
    ),
    "historical_rates.json": (
        '{"10yr_treasury": [3.5, 3.8, 4.1, 4.3, 4.0],\n'
        ' "fed_funds": [5.25, 5.50, 5.50, 5.25, 5.00],\n'
        ' "libor_6m": [5.1, 5.3, 5.4, 5.2, 4.9]}\n'
    ),
}


class BuildingBlockEnvironment:
    """Environment that provides building blocks, not instructions.

    Workspace layout (agent must discover what's relevant):
        /work/
        ├── briefs/
        │   ├── katnip_brief.md          ← relevant
        │   └── project_beta_summary.md  ← distractor
        ├── data/
        │   ├── katnip_financials.txt    ← relevant
        │   ├── market_comps.csv         ← distractor
        │   └── historical_rates.json    ← distractor
        ├── templates/
        │   └── memo_template.md         ← distractor
        └── README.md                    ← minimal: "analyze KatNip"

    Agent must:
    - Explore workspace to find relevant files
    - Read and understand the data
    - Write python scripts to compute answers
    - Write results to analysis.txt
    """

    def __init__(self):
        self._executor = BashExecutor()
        self._workspace: Path | None = None
        self._actions: list[str] = []
        self._step_count: int = 0
        self._progress_history: list[int] = []  # criteria_met per step
        self._scripts_written: set[str] = set()
        self._scripts_run: set[str] = set()
        self._last_hint: str | None = None  # avoid repeating same hint

    def reset(self) -> dict:
        """Create explorable workspace, return minimal instruction."""
        if self._workspace and self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)

        self._workspace = Path(tempfile.mkdtemp(prefix="apex_bb_"))
        self._actions = []
        self._step_count = 0
        self._progress_history = []
        self._scripts_written = set()
        self._scripts_run = set()
        self._last_hint = None

        # Create directory structure
        (self._workspace / "briefs").mkdir()
        (self._workspace / "data").mkdir()
        (self._workspace / "templates").mkdir()
        (self._workspace / "tools").mkdir()

        # Relevant files
        (self._workspace / "briefs" / "katnip_brief.md").write_text(BRIEF_CONTENT)
        (self._workspace / "data" / "katnip_financials.txt").write_text(DATA_CONTENT)

        # Building block: XIRR tool (agent must discover it)
        (self._workspace / "tools" / "xirr_tool.py").write_text(XIRR_TOOL)

        # Distractor files
        (self._workspace / "briefs" / "project_beta_summary.md").write_text(
            DISTRACTOR_FILES["project_beta_summary.md"]
        )
        (self._workspace / "data" / "market_comps.csv").write_text(
            DISTRACTOR_FILES["market_comps.csv"]
        )
        (self._workspace / "data" / "historical_rates.json").write_text(
            DISTRACTOR_FILES["historical_rates.json"]
        )
        (self._workspace / "templates" / "memo_template.md").write_text(
            DISTRACTOR_FILES["memo_template.md"]
        )

        # Minimal README — doesn't tell agent which files to read
        (self._workspace / "README.md").write_text(
            "# Task: KatNip Co. Financial Analysis\n\n"
            "You are an IB analyst. Analyze KatNip Co. and write results to `analysis.txt`.\n"
            "Your workspace contains briefs, data, and templates. Figure out what you need.\n"
        )

        # Minimal observation — principle 4: don't tell agent where blocks are
        instruction = (
            f"You are an IB analyst. Your workspace is: {self._workspace}\n"
            f"Analyze KatNip Co. Write your results to analysis.txt.\n"
            f"This task has {len(CRITERIA)} evaluation criteria.\n"
            f"When finished, send: done"
        )

        return {
            "stdout": instruction,
            "stderr": "",
            "exit_code": 0,
            "done": False,
            "reward": None,
            "criteria_met": 0,
            "criteria_total": len(CRITERIA),
        }

    def step(self, command: str) -> dict:
        """Execute command, return output + criteria feedback."""
        self._step_count += 1
        self._actions.append(command)

        if command.strip().lower() == "done":
            return self._finish()

        # Track behavior patterns
        self._track_behavior(command)

        # Execute
        result = self._executor.run(command, cwd=self._workspace, timeout_s=30.0)

        # Per-step criteria feedback (principle 2: tell if right)
        criteria_met = self._count_criteria_met()
        self._progress_history.append(criteria_met)

        # Build feedback
        parts = []
        if result.stdout:
            parts.append(result.stdout[:3000])
        if result.stderr:
            parts.append(f"STDERR: {result.stderr[:2000]}")
        if not result.stdout and not result.stderr:
            parts.append(f"(command executed, exit code {result.exit_code})")

        # Progress feedback — just the score, no hints
        parts.append(f"\n[Progress: {criteria_met}/{len(CRITERIA)} criteria met]")

        # Meta-feedback — coach behavior patterns, never give answers
        meta = self._get_meta_feedback(command)
        if meta:
            parts.append(f"[Hint: {meta}]")

        return {
            "stdout": "\n".join(parts),
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "done": False,
            "reward": None,
            "criteria_met": criteria_met,
            "criteria_total": len(CRITERIA),
            "step": self._step_count,
        }

    def _track_behavior(self, command: str):
        """Track observable behavior for meta-feedback."""
        import re
        cmd = command.strip()

        # Track scripts written (> foo.py) vs run (python3 foo.py)
        write_match = re.search(r'>\s*(\S+\.py)', cmd)
        if write_match:
            self._scripts_written.add(write_match.group(1))
        run_match = re.search(r'python3?\s+(\S+\.py)', cmd)
        if run_match:
            self._scripts_run.add(run_match.group(1))

    def _get_meta_feedback(self, command: str) -> str | None:
        """Outcome-driven coaching: diagnose from results, not behavior.

        A good coach doesn't track "did you open the textbook".
        She watches your performance and says "your input data looks wrong".

        Three layers: exposure → learning → application.
        We only have ground truth on application (criteria_met).
        So we coach based on outcomes + observable patterns.
        """
        import re
        hint = None

        # 1. Script written but not run — directly observable fact
        unrun = self._scripts_written - self._scripts_run
        if unrun:
            hint = f"You wrote {', '.join(sorted(unrun))} but haven't executed it yet."

        # 2. Computing but results don't match — outcome-driven
        #    "Your results don't match any criteria — check your inputs or method."
        elif (self._step_count >= 8
              and len(self._progress_history) >= 3
              and self._progress_history[-1] == 0
              and any("python" in a.lower() for a in self._actions[-5:])):
            hint = ("You're computing but 0 criteria met. "
                    "Are your inputs correct? Is your method right for this data?")

        # 3. Stalled: progress hasn't changed for 3+ turns
        #    Diagnose WHY based on context
        elif len(self._progress_history) >= 4:
            recent = self._progress_history[-4:]
            if len(set(recent)) == 1:  # same score 4 turns in a row
                current = recent[0]
                total = len(CRITERIA)
                if current == 0:
                    hint = ("No criteria met after several attempts. "
                            "Step back — have you read all the requirements for this task?")
                elif current < total // 2:
                    hint = (f"{current}/{total} met. You're making progress but stalled. "
                            "What criteria are you missing? Your workspace may have resources you haven't used.")
                else:
                    hint = (f"{current}/{total} met. Close! "
                            "Review which criteria are still failing and focus there.")

        # 4. Running python repeatedly with no progress — pattern detection
        elif len(self._actions) >= 3:
            last_3 = [a.lower() for a in self._actions[-3:]]
            if all("python" in a for a in last_3):
                # 3 consecutive python commands with same progress = spinning wheels
                if (len(self._progress_history) >= 3
                        and len(set(self._progress_history[-3:])) == 1):
                    hint = ("You've run 3 similar computations with no progress change. "
                            "Your workspace may have tools or docs you haven't explored yet.")

        # Don't repeat the same hint consecutively
        if hint and hint == self._last_hint:
            return None
        self._last_hint = hint
        return hint

    def _count_criteria_met(self) -> int:
        if not self._workspace or not self._workspace.exists():
            return 0
        agent_text = collect_workspace_text(self._workspace).lower()
        if not agent_text:
            return 0
        count = 0
        for criterion in CRITERIA:
            if any(kw.lower() in agent_text for kw in criterion["check_keywords"]):
                count += 1
        return count

    def _finish(self) -> dict:
        criteria_met = self._count_criteria_met()
        reward = criteria_met / len(CRITERIA) if CRITERIA else 0.0

        # Final report
        agent_text = collect_workspace_text(self._workspace).lower() if self._workspace else ""
        lines = [
            f"Episode finished.",
            f"Final: {criteria_met}/{len(CRITERIA)} criteria met.",
            f"Reward: {reward:.3f}",
            f"Steps used: {self._step_count}",
            f"",
            f"Criteria breakdown:",
        ]
        for c in CRITERIA:
            met = any(kw.lower() in agent_text for kw in c["check_keywords"])
            status = "PASS" if met else "FAIL"
            lines.append(f"  [{status}] {c['description']}")

        return {
            "stdout": "\n".join(lines),
            "stderr": "",
            "exit_code": 0,
            "done": True,
            "reward": reward,
            "criteria_met": criteria_met,
            "criteria_total": len(CRITERIA),
            "step": self._step_count,
        }

    def close(self):
        if self._workspace and self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)
        self._workspace = None
