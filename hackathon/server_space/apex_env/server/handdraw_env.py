"""Hand-draw composition environment — cross-domain building block proof.

Same four principles as IB environment, different domain:
1. Provide building blocks (Rough.js element snippets)
2. Tell if right (per-step criteria feedback)
3. Don't tell how to build (agent decides composition)
4. Don't tell where blocks are (agent discovers via bash)

Demo narrative: Act 1 of "If an agent can learn to compose illustrations,
it can learn to do your job."
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

try:
    from .bash_executor import BashExecutor
    from .reward import collect_workspace_text, check_criterion_hybrid
    from .demo_task_handdraw import (
        CRITERIA, ELEMENTS, EXAMPLES, TEMPLATE, DISTRACTORS, SPEC_CONTENT,
    )
except ImportError:
    from bash_executor import BashExecutor
    from reward import collect_workspace_text, check_criterion_hybrid
    from demo_task_handdraw import (
        CRITERIA, ELEMENTS, EXAMPLES, TEMPLATE, DISTRACTORS, SPEC_CONTENT,
    )


class HandDrawEnvironment:
    """Environment where agent composes SVG illustrations from basic elements.

    Workspace layout:
        /work/
        ├── elements/
        │   ├── triangle.js      ← basic element code snippet
        │   ├── circle.js
        │   ├── rectangle.js
        │   ├── line.js
        │   └── arc.js
        ├── examples/
        │   ├── diamond.html     ← composition reference
        │   └── seesaw.html
        ├── template.html        ← Rough.js boilerplate
        ├── notes/
        │   ├── color_theory.md  ← distractor
        │   └── animation_notes.md ← distractor
        └── specs.md             ← "Compose an HOURGLASS"
    """

    def __init__(self):
        self._executor = BashExecutor()
        self._workspace: Path | None = None
        self._actions: list[str] = []
        self._step_count: int = 0
        self._progress_history: list[int] = []
        self._scripts_written: set[str] = set()
        self._scripts_run: set[str] = set()
        self._has_read_specs: bool = False
        self._has_explored_elements: bool = False
        self._has_explored_examples: bool = False
        self._last_hint: str | None = None

    def reset(self) -> dict:
        """Create explorable workspace, return minimal instruction."""
        if self._workspace and self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)

        self._workspace = Path(tempfile.mkdtemp(prefix="apex_hd_"))
        self._actions = []
        self._step_count = 0
        self._progress_history = []
        self._scripts_written = set()
        self._scripts_run = set()
        self._has_read_specs = False
        self._has_explored_elements = False
        self._has_explored_examples = False
        self._last_hint = None

        # Create directory structure
        (self._workspace / "elements").mkdir()
        (self._workspace / "examples").mkdir()
        (self._workspace / "notes").mkdir()

        # Basic element code snippets
        for name, content in ELEMENTS.items():
            (self._workspace / "elements" / name).write_text(content)

        # Example compositions
        for name, content in EXAMPLES.items():
            (self._workspace / "examples" / name).write_text(content)

        # Template
        (self._workspace / "template.html").write_text(TEMPLATE)

        # Distractor files
        for name, content in DISTRACTORS.items():
            (self._workspace / "notes" / name).write_text(content)

        # Task spec
        (self._workspace / "specs.md").write_text(SPEC_CONTENT)

        instruction = (
            f"You are an illustrator. Your workspace is: {self._workspace}\n"
            f"Create a hand-drawn SVG illustration. Check specs.md for details.\n"
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

        self._track_behavior(command)

        result = self._executor.run(command, cwd=self._workspace, timeout_s=30.0)

        criteria_met = self._count_criteria_met()

        # Progress delta
        prev = self._progress_history[-1] if self._progress_history else 0
        self._progress_history.append(criteria_met)
        delta = criteria_met - prev
        delta_str = f" (+{delta})" if delta > 0 else (f" ({delta})" if delta < 0 else "")

        parts = []
        if result.stdout:
            parts.append(result.stdout[:3000])
        if result.stderr:
            parts.append(f"STDERR: {result.stderr[:2000]}")
        if not result.stdout and not result.stderr:
            parts.append(f"(command executed, exit code {result.exit_code})")

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

        write_match = re.search(r'>\s*(\S+\.html)', cmd)
        if write_match:
            self._scripts_written.add(write_match.group(1))

        if any(kw in cmd for kw in ["specs.md", "specs", "cat specs"]):
            self._has_read_specs = True
        if any(kw in cmd for kw in ["elements/", "/elements", "ls elements"]):
            self._has_explored_elements = True
        if any(kw in cmd for kw in ["examples/", "/examples", "ls examples"]):
            self._has_explored_examples = True

    def _get_meta_feedback(self, command: str) -> str | None:
        hint = None

        # Layer 2: Outcome diagnosis
        if (self._step_count >= 6
                and len(self._progress_history) >= 3
                and self._progress_history[-1] == 0):
            hint = ("0 criteria met. Have you created the output file yet? "
                    "Check specs.md for what's needed.")

        elif len(self._progress_history) >= 4:
            recent = self._progress_history[-4:]
            if len(set(recent)) == 1:
                current = recent[0]
                if current < len(CRITERIA) // 2:
                    hint = (f"{current}/{len(CRITERIA)} met but stalled. "
                            "Study the examples/ to see how compositions work.")

        # Layer 3: Behavior blind spots
        if hint is None and self._step_count >= 4:
            if not self._has_read_specs:
                hint = "Your workspace has a specs.md with task requirements."
            elif not self._has_explored_elements and self._step_count >= 6:
                hint = ("Your workspace has an elements/ directory with "
                        "code snippets for basic shapes.")
            elif not self._has_explored_examples and self._step_count >= 8:
                hint = ("Your workspace has an examples/ directory with "
                        "complete composition references.")

        if hint and hint == self._last_hint:
            return None
        self._last_hint = hint
        return hint

    def _count_criteria_met(self, use_llm: bool = False) -> int:
        if not self._workspace or not self._workspace.exists():
            return 0
        agent_text = collect_workspace_text(self._workspace)
        if not agent_text:
            return 0

        count = 0
        for criterion in CRITERIA:
            # Special check: file existence
            if criterion.get("check_type") == "file_exists":
                fname = criterion["file_name"]
                if (self._workspace / fname).exists():
                    count += 1
                continue
            if check_criterion_hybrid(criterion, agent_text, use_llm=use_llm):
                count += 1
        return count

    def _finish(self) -> dict:
        agent_text = collect_workspace_text(self._workspace) if self._workspace else ""
        criteria_results = []
        criteria_met = 0
        for c in CRITERIA:
            if c.get("check_type") == "file_exists":
                met = (self._workspace / c["file_name"]).exists()
            else:
                met = check_criterion_hybrid(c, agent_text, use_llm=True)
            criteria_results.append((c, met))
            if met:
                criteria_met += 1

        correctness = criteria_met / len(CRITERIA) if CRITERIA else 0.0

        # Efficiency (same formula as IB env)
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
