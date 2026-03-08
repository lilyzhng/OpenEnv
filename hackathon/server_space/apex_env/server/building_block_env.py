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
    from .reward import collect_workspace_text, check_criterion_hybrid
    from .demo_task import (
        CRITERIA, DATA_CONTENT, BRIEF_CONTENT,
        EXAMPLE_BRIEF, EXAMPLE_CALC, EXAMPLE_ANALYSIS,
    )
except ImportError:
    from bash_executor import BashExecutor
    from reward import collect_workspace_text, check_criterion_hybrid
    from demo_task import (
        CRITERIA, DATA_CONTENT, BRIEF_CONTENT,
        EXAMPLE_BRIEF, EXAMPLE_CALC, EXAMPLE_ANALYSIS,
    )


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
        ├── examples/                       ← Layer 2: composition example
        │   ├── alpha_brief.md              ← completed simple analysis
        │   ├── alpha_calc.py               ← workflow: brief→data→tools→compute
        │   └── alpha_analysis.txt          ← final output
        ├── briefs/
        │   ├── katnip_brief.md             ← relevant
        │   └── project_beta_summary.md     ← distractor
        ├── data/
        │   ├── katnip_financials.txt       ← relevant
        │   ├── market_comps.csv            ← distractor
        │   └── historical_rates.json       ← distractor
        ├── tools/
        │   └── xirr_tool.py                ← building block
        ├── templates/
        │   └── memo_template.md            ← distractor
        └── README.md                       ← minimal: "analyze KatNip"

    Three-layer structure (inspired by hand-draw skill):
    - Layer 1: Building blocks (data, tools, briefs)
    - Layer 2: Composition example (examples/ — completed simple analysis)
    - Layer 3: Meta-strategy (agent learns recomposition from example)
    """

    def __init__(self):
        self._executor = BashExecutor()
        self._workspace: Path | None = None
        self._actions: list[str] = []
        self._step_count: int = 0
        self._progress_history: list[int] = []  # criteria_met per step
        self._scripts_written: set[str] = set()
        self._scripts_run: set[str] = set()
        self._has_read_briefs: bool = False   # Layer 3: behavior blind spots
        self._has_explored_tools: bool = False
        self._has_explored_examples: bool = False
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
        self._has_read_briefs = False
        self._has_explored_tools = False
        self._has_explored_examples = False
        self._last_hint = None

        # Create directory structure
        (self._workspace / "examples").mkdir()
        (self._workspace / "briefs").mkdir()
        (self._workspace / "data").mkdir()
        (self._workspace / "templates").mkdir()
        (self._workspace / "tools").mkdir()

        # Layer 2: Composition example — completed simple analysis
        # Shows the full workflow: brief → data → tools → compute → results
        (self._workspace / "examples" / "alpha_brief.md").write_text(EXAMPLE_BRIEF)
        (self._workspace / "examples" / "alpha_calc.py").write_text(EXAMPLE_CALC)
        (self._workspace / "examples" / "alpha_analysis.txt").write_text(EXAMPLE_ANALYSIS)

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

        # Progress feedback with delta signal
        prev = self._progress_history[-1] if self._progress_history else 0
        delta = criteria_met - prev
        delta_str = f" (+{delta})" if delta > 0 else (f" ({delta})" if delta < 0 else "")
        parts.append(f"\n[Progress: {prev}→{criteria_met}/{len(CRITERIA)} criteria met{delta_str}]")

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
        cmd = command.strip().lower()

        # Track scripts written (> foo.py) vs run (python3 foo.py)
        write_match = re.search(r'>\s*(\S+\.py)', cmd)
        if write_match:
            self._scripts_written.add(write_match.group(1))
        run_match = re.search(r'python3?\s+(\S+\.py)', cmd)
        if run_match:
            self._scripts_run.add(run_match.group(1))

        # Track resource category exploration (not specific files)
        if any(kw in cmd for kw in ["briefs/", "brief", "/briefs"]):
            self._has_read_briefs = True
        if any(kw in cmd for kw in ["tools/", "/tools", "ls tools"]):
            self._has_explored_tools = True
        if any(kw in cmd for kw in ["examples/", "/examples", "ls examples"]):
            self._has_explored_examples = True

    def _get_meta_feedback(self, command: str) -> str | None:
        """Hybrid coaching: outcome diagnosis + behavior blind spots.

        Layer 1: [Progress: N/M] — always present (in step() directly)
        Layer 2: Outcome diagnosis — "results wrong, check your method"
        Layer 3: Behavior blind spots — "briefs/ and tools/ exist, you haven't looked"

        Layer 2 tells you WHAT's wrong. Layer 3 tells you WHERE to look.
        Neither tells you the specific answer.
        """
        import re
        hint = None

        # --- Layer 2: Outcome diagnosis ---

        # Script written but not run — directly observable
        unrun = self._scripts_written - self._scripts_run
        if unrun:
            hint = f"You wrote {', '.join(sorted(unrun))} but haven't executed it yet."

        # Computing but 0 criteria — your method or inputs are wrong
        elif (self._step_count >= 8
              and len(self._progress_history) >= 3
              and self._progress_history[-1] == 0
              and any("python" in a.lower() for a in self._actions[-5:])):
            hint = ("You're computing but 0 criteria met. "
                    "Are your inputs correct? Is your method right for this data?")

        # Stalled: same score 4+ turns — diagnose based on level
        elif len(self._progress_history) >= 4:
            recent = self._progress_history[-4:]
            if len(set(recent)) == 1:
                current = recent[0]
                total = len(CRITERIA)
                if current == 0:
                    hint = ("No criteria met after several attempts. "
                            "Step back — have you read all the requirements for this task?")
                elif current < total // 2:
                    hint = (f"{current}/{total} criteria met but stalled. "
                            "What criteria are you missing? Check if your workspace has unused resources.")
                else:
                    hint = (f"{current}/{total} met — close! "
                            "Review which criteria are still failing and focus there.")

        # --- Layer 3: Behavior blind spots ---
        # Only fire these when agent is struggling (0 criteria or stalled)
        # and hasn't explored the resource category yet.
        # Says "this category exists" not "use this specific file".

        if hint is None and self._step_count >= 5:
            if not self._has_explored_examples:
                hint = ("Your workspace has an examples/ directory with a completed "
                        "analysis you can study for the workflow pattern.")
            elif not self._has_read_briefs:
                hint = ("Your workspace has a briefs/ directory with task requirements "
                        "you haven't looked at yet.")
            elif not self._has_explored_tools and self._step_count >= 8:
                hint = ("Your workspace has a tools/ directory with utility scripts "
                        "you haven't explored yet.")

        # Don't repeat the same hint consecutively
        if hint and hint == self._last_hint:
            return None
        self._last_hint = hint
        return hint

    def _count_criteria_met(self, use_llm: bool = False) -> int:
        """Count satisfied criteria. use_llm=False for per-step (fast), True for final."""
        if not self._workspace or not self._workspace.exists():
            return 0
        agent_text = collect_workspace_text(self._workspace)
        if not agent_text:
            return 0
        count = 0
        for criterion in CRITERIA:
            if check_criterion_hybrid(criterion, agent_text, use_llm=use_llm):
                count += 1
        return count

    def _finish(self) -> dict:
        # Final scoring uses LLM for semantic criteria
        agent_text = collect_workspace_text(self._workspace) if self._workspace else ""
        criteria_results = []
        criteria_met = 0
        for c in CRITERIA:
            met = check_criterion_hybrid(c, agent_text, use_llm=True)
            criteria_results.append((c, met))
            if met:
                criteria_met += 1

        correctness = criteria_met / len(CRITERIA) if CRITERIA else 0.0

        # Efficiency: penalize stuck-in-a-loop turns, not exploration.
        # A no-progress streak of ≤2 is normal exploration (grace period).
        # Only turns beyond the grace period in each streak count as wasted.
        grace = 3
        wasted = 0
        streak = 0
        for i in range(1, len(self._progress_history)):
            if self._progress_history[i] <= self._progress_history[i - 1]:
                streak += 1
                if streak > grace:
                    wasted += 1
            else:
                streak = 0
        efficiency_mult = max(0.5, 1.0 - 0.05 * wasted)
        reward = correctness * efficiency_mult

        lines = [
            f"Episode finished.",
            f"Final: {criteria_met}/{len(CRITERIA)} criteria met.",
            f"Correctness: {correctness:.3f}",
            f"Efficiency: {efficiency_mult:.3f} ({wasted} wasted turns out of {self._step_count})",
            f"Reward: {reward:.3f} (correctness × efficiency)",
            f"Steps used: {self._step_count}",
            f"",
            f"Criteria breakdown:",
        ]
        for c, met in criteria_results:
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
