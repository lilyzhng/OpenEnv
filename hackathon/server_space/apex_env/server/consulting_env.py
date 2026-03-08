"""Consulting building-block environment — market entry analysis.

Same design principles as BuildingBlockEnvironment (IB):
1. Provide building blocks (market data, tools, examples)
2. Tell agent if it's right (per-step criteria feedback)
3. Don't tell agent how to analyze (agent decides approach)
4. Don't tell agent where blocks are (agent discovers via bash)
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

try:
    from .bash_executor import BashExecutor
    from .reward import collect_workspace_text, check_criterion_hybrid
    from .demo_task_consulting import (
        CRITERIA, MARKET_DATA, BRIEF_CONTENT,
        EXAMPLE_BRIEF, EXAMPLE_CALC, EXAMPLE_STRATEGY,
        MARKET_SIZING_TOOL, DISTRACTOR_FILES,
    )
except ImportError:
    from bash_executor import BashExecutor
    from reward import collect_workspace_text, check_criterion_hybrid
    from demo_task_consulting import (
        CRITERIA, MARKET_DATA, BRIEF_CONTENT,
        EXAMPLE_BRIEF, EXAMPLE_CALC, EXAMPLE_STRATEGY,
        MARKET_SIZING_TOOL, DISTRACTOR_FILES,
    )


class ConsultingEnvironment:
    """Building-block environment for consulting tasks.

    Workspace layout:
        /work/
        ├── examples/                       ← completed simpler analysis
        │   ├── alpha_brief.md
        │   ├── alpha_calc.py
        │   └── alpha_strategy.txt
        ├── data/
        │   ├── latam_market.md             ← relevant market data
        │   ├── competitor_profiles.md      ← distractor
        │   ├── regulatory_overview.csv     ← distractor
        │   └── macroeconomic_forecast.json ← distractor
        ├── briefs/
        │   ├── novatech_brief.md           ← task brief
        │   └── internal_capabilities.md    ← distractor
        ├── tools/
        │   └── market_sizing.py            ← building block
        └── README.md
    """

    def __init__(self):
        self._executor = BashExecutor()
        self._workspace: Path | None = None
        self._actions: list[str] = []
        self._step_count: int = 0
        self._progress_history: list[int] = []
        self._scripts_written: set[str] = set()
        self._scripts_run: set[str] = set()
        self._has_read_data: bool = False
        self._has_explored_tools: bool = False
        self._has_explored_examples: bool = False
        self._last_hint: str | None = None

    def reset(self) -> dict:
        if self._workspace and self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)

        self._workspace = Path(tempfile.mkdtemp(prefix="apex_consult_"))
        self._actions = []
        self._step_count = 0
        self._progress_history = []
        self._scripts_written = set()
        self._scripts_run = set()
        self._has_read_data = False
        self._has_explored_tools = False
        self._has_explored_examples = False
        self._last_hint = None

        # Create directory structure
        for d in ["examples", "data", "briefs", "tools"]:
            (self._workspace / d).mkdir()

        # Example (completed simpler analysis)
        (self._workspace / "examples" / "alpha_brief.md").write_text(EXAMPLE_BRIEF)
        (self._workspace / "examples" / "alpha_calc.py").write_text(EXAMPLE_CALC)
        (self._workspace / "examples" / "alpha_strategy.txt").write_text(EXAMPLE_STRATEGY)

        # Market data
        (self._workspace / "data" / "latam_market.md").write_text(MARKET_DATA)
        (self._workspace / "briefs" / "novatech_brief.md").write_text(BRIEF_CONTENT)

        # Tool
        (self._workspace / "tools" / "market_sizing.py").write_text(MARKET_SIZING_TOOL)

        # Distractors
        (self._workspace / "data" / "competitor_profiles.md").write_text(
            DISTRACTOR_FILES["competitor_profiles.md"]
        )
        (self._workspace / "data" / "regulatory_overview.csv").write_text(
            DISTRACTOR_FILES["regulatory_overview.csv"]
        )
        (self._workspace / "briefs" / "internal_capabilities.md").write_text(
            DISTRACTOR_FILES["internal_capabilities.md"]
        )
        (self._workspace / "data" / "macroeconomic_forecast.json").write_text(
            DISTRACTOR_FILES["macroeconomic_forecast.json"]
        )

        # Minimal README
        (self._workspace / "README.md").write_text(
            "# Task: NovaTech — Latin America Market Entry Strategy\n\n"
            "You are a strategy consultant. Analyze the LatAm market opportunity "
            "and write your strategy to `strategy.txt`.\n"
            "Your workspace contains market data, frameworks, and tools. "
            "Figure out what you need.\n"
        )

        # Track original files so criteria only check agent-created files
        self._original_files = set()
        for f in self._workspace.rglob("*"):
            if f.is_file():
                self._original_files.add(str(f))

        instruction = (
            f"You are a strategy consultant. Your workspace is: {self._workspace}\n"
            f"Analyze the LatAm market opportunity for NovaTech. Write your strategy to strategy.txt.\n"
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
        self._step_count += 1
        self._actions.append(command)

        if command.strip().lower() == "done":
            return self._finish()

        self._track_behavior(command)

        result = self._executor.run(command, cwd=self._workspace, timeout_s=30.0)

        criteria_met = self._count_criteria_met()
        self._progress_history.append(criteria_met)

        parts = []
        if result.stdout:
            parts.append(result.stdout[:3000])
        if result.stderr:
            parts.append(f"STDERR: {result.stderr[:2000]}")
        if not result.stdout and not result.stderr:
            parts.append(f"(command executed, exit code {result.exit_code})")

        prev = self._progress_history[-2] if len(self._progress_history) >= 2 else 0
        delta = criteria_met - prev
        delta_str = f" (+{delta})" if delta > 0 else (f" ({delta})" if delta < 0 else "")
        parts.append(f"\n[Progress: {prev}→{criteria_met}/{len(CRITERIA)} criteria met{delta_str}]")

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
        import re
        cmd = command.strip().lower()

        write_match = re.search(r'>\s*(\S+\.py)', cmd)
        if write_match:
            self._scripts_written.add(write_match.group(1))
        run_match = re.search(r'python3?\s+(\S+\.py)', cmd)
        if run_match:
            self._scripts_run.add(run_match.group(1))

        if any(kw in cmd for kw in ["data/", "latam", "market", "novatech"]):
            self._has_read_data = True
        if any(kw in cmd for kw in ["tools/", "/tools", "ls tools"]):
            self._has_explored_tools = True
        if any(kw in cmd for kw in ["examples/", "/examples", "ls examples"]):
            self._has_explored_examples = True

    def _get_meta_feedback(self, command: str) -> str | None:
        import re
        hint = None

        unrun = self._scripts_written - self._scripts_run
        if unrun:
            hint = f"You wrote {', '.join(sorted(unrun))} but haven't executed it yet."
        elif (self._step_count >= 8
              and len(self._progress_history) >= 3
              and self._progress_history[-1] == 0
              and any("python" in a.lower() for a in self._actions[-5:])):
            hint = ("You're computing but 0 criteria met. "
                    "Are your inputs correct? Check the market data again.")
        elif len(self._progress_history) >= 4:
            recent = self._progress_history[-4:]
            if len(set(recent)) == 1:
                current = recent[0]
                total = len(CRITERIA)
                if current == 0:
                    hint = ("No criteria met after several attempts. "
                            "Have you read the market data and computed TAM/SAM/SOM?")
                elif current < total // 2:
                    hint = (f"{current}/{total} criteria met but stalled. "
                            "Check if you've calculated unit economics (LTV, LTV/CAC, payback).")
                else:
                    hint = (f"{current}/{total} met — close! "
                            "Review which criteria are still failing.")

        if hint is None and self._step_count >= 5:
            if not self._has_explored_examples:
                hint = ("Your workspace has an examples/ directory with a completed "
                        "market entry analysis you can study for the workflow pattern.")
            elif not self._has_read_data:
                hint = ("Your workspace has a data/ directory with market research "
                        "you need for the analysis.")
            elif not self._has_explored_tools and self._step_count >= 8:
                hint = ("Your workspace has a tools/ directory with a market sizing "
                        "calculator you haven't explored yet.")

        if hint and hint == self._last_hint:
            return None
        self._last_hint = hint
        return hint

    def _collect_agent_text(self) -> str:
        """Collect text only from files the agent created (not original workspace files)."""
        from reward import READABLE_SUFFIXES
        if not self._workspace or not self._workspace.exists():
            return ""
        parts = []
        for f in sorted(self._workspace.rglob("*")):
            if f.is_file() and f.suffix in READABLE_SUFFIXES:
                if str(f) not in self._original_files:
                    try:
                        parts.append(f.read_text(errors="replace"))
                    except Exception:
                        continue
        return " ".join(parts)

    def _count_criteria_met(self, use_llm: bool = False) -> int:
        if not self._workspace or not self._workspace.exists():
            return 0
        agent_text = self._collect_agent_text()
        if not agent_text:
            return 0
        count = 0
        for criterion in CRITERIA:
            if check_criterion_hybrid(criterion, agent_text, use_llm=use_llm):
                count += 1
        return count

    def _finish(self) -> dict:
        agent_text = self._collect_agent_text()
        criteria_results = []
        criteria_met = 0
        for c in CRITERIA:
            met = check_criterion_hybrid(c, agent_text, use_llm=True)
            criteria_results.append((c, met))
            if met:
                criteria_met += 1

        correctness = criteria_met / len(CRITERIA) if CRITERIA else 0.0

        # Process signals — reward meta-strategy, not just outcome
        discovery = self._has_read_data            # explored workspace, read market data
        reference = self._has_explored_examples    # found and studied example strategy
        building_block = self._has_explored_tools  # discovered and used market_sizing

        discovery_bonus = 0.1 if discovery else 0.0
        reference_bonus = 0.1 if reference else 0.0
        building_block_bonus = 0.2 if building_block else 0.0
        correctness_component = 0.6 * correctness

        reward = discovery_bonus + reference_bonus + building_block_bonus + correctness_component

        lines = [
            f"Episode finished.",
            f"Final: {criteria_met}/{len(CRITERIA)} criteria met.",
            f"Correctness: {correctness:.3f}",
            f"Process: discovery={'Y' if discovery else 'N'} "
            f"reference={'Y' if reference else 'N'} "
            f"building_block={'Y' if building_block else 'N'}",
            f"Reward: {reward:.3f} "
            f"(process {discovery_bonus + reference_bonus + building_block_bonus:.1f} "
            f"+ correctness {correctness_component:.3f})",
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
