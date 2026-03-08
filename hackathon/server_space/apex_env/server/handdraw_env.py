"""Hand-draw task family environment — transfer distance curriculum.

Tests analogical reasoning: can agent adapt a reference composition
(diamond) to create different illustrations?

Transfer distance = reasoning gap from reference to target:
- Zero (diamond): copy the example
- Near (hourglass): same elements, adapt arrangement
- Medium (seesaw): different elements, different composition
- Far (temple): example not applicable, build from scratch

Workspace layout:
    /work/
    ├── elements/          ← basic element code snippets
    │   ├── triangle.js
    │   ├── circle.js
    │   ├── rectangle.js
    │   ├── line.js
    │   └── arc.js
    ├── examples/
    │   └── diamond.html   ← ONE completed composition (reference)
    ├── template.html      ← Rough.js boilerplate
    ├── notes/             ← distractors
    └── specs.md           ← MINIMAL: just "Compose an X"
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

try:
    from .bash_executor import BashExecutor
    from .reward import (
        collect_workspace_text, check_criterion_hybrid,
        screenshot_html, vlm_visual_check,
    )
    from .demo_task_handdraw import (
        ELEMENTS, EXAMPLES, TEMPLATE, DISTRACTORS, TASK_FAMILY, DEFAULT_TASK,
    )
except ImportError:
    from bash_executor import BashExecutor
    from reward import (
        collect_workspace_text, check_criterion_hybrid,
        screenshot_html, vlm_visual_check,
    )
    from demo_task_handdraw import (
        ELEMENTS, EXAMPLES, TEMPLATE, DISTRACTORS, TASK_FAMILY, DEFAULT_TASK,
    )


class HandDrawEnvironment:
    """Task family environment for hand-drawn SVG illustrations.

    Accepts a task_id to select which task from the family:
    - "diamond" (zero distance — copy example)
    - "hourglass" (near — adapt arrangement)
    - "seesaw" (medium — different elements)
    - "temple" (far — build from scratch)
    """

    def __init__(self, task_id: str | None = None):
        self._task_id = task_id or DEFAULT_TASK
        if self._task_id not in TASK_FAMILY:
            raise ValueError(
                f"Unknown task '{self._task_id}'. "
                f"Available: {list(TASK_FAMILY.keys())}"
            )
        self._task = TASK_FAMILY[self._task_id]
        self._criteria = self._task["criteria"]

        self._executor = BashExecutor()
        self._workspace: Path | None = None
        self._actions: list[str] = []
        self._step_count: int = 0
        self._progress_history: list[int] = []
        self._scripts_written: set[str] = set()
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

        # Reference composition (diamond only)
        for name, content in EXAMPLES.items():
            (self._workspace / "examples" / name).write_text(content)

        # Template
        (self._workspace / "template.html").write_text(TEMPLATE)

        # Distractor files
        for name, content in DISTRACTORS.items():
            (self._workspace / "notes" / name).write_text(content)

        # Task spec — MINIMAL, no decomposition hints
        (self._workspace / "specs.md").write_text(self._task["spec"])

        concept = self._task["concept"]
        instruction = (
            f"You are an illustrator. Your workspace is: {self._workspace}\n"
            f"Create a hand-drawn SVG illustration. Check specs.md for details.\n"
            f"This task has {len(self._criteria)} evaluation criteria.\n"
            f"When finished, send: done"
        )

        return {
            "stdout": instruction,
            "stderr": "",
            "exit_code": 0,
            "done": False,
            "reward": None,
            "criteria_met": 0,
            "criteria_total": len(self._criteria),
            "task_id": self._task_id,
            "transfer_distance": self._task["transfer_distance"],
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

        parts.append(f"\n[Progress: {prev}→{criteria_met}/{len(self._criteria)} criteria met{delta_str}]")

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
            "criteria_total": len(self._criteria),
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

        # Outcome diagnosis: stuck at 0
        if (self._step_count >= 6
                and len(self._progress_history) >= 3
                and self._progress_history[-1] == 0):
            hint = ("0 criteria met. Have you created the output file yet? "
                    "Check specs.md for what's needed.")

        # Stalled progress
        elif len(self._progress_history) >= 4:
            recent = self._progress_history[-4:]
            if len(set(recent)) == 1:
                current = recent[0]
                if current < len(self._criteria) // 2:
                    hint = (f"{current}/{len(self._criteria)} met but stalled. "
                            "Study the examples/ to see how compositions work.")

        # Behavior blind spots — guide to unexplored areas
        if hint is None and self._step_count >= 4:
            if not self._has_read_specs:
                hint = "Your workspace has a specs.md with task requirements."
            elif not self._has_explored_elements and self._step_count >= 6:
                hint = ("Your workspace has an elements/ directory with "
                        "code snippets for basic shapes.")
            elif not self._has_explored_examples and self._step_count >= 8:
                hint = ("Your workspace has an examples/ directory with "
                        "a completed composition you can study.")

        if hint and hint == self._last_hint:
            return None
        self._last_hint = hint
        return hint

    def _check_criterion(self, criterion: dict, agent_text: str, use_llm: bool = False) -> bool:
        """Check a single criterion, dispatching by check_type."""
        check_type = criterion.get("check_type", "")

        if check_type == "file_exists":
            fname = criterion["file_name"]
            return (self._workspace / fname).exists()

        if check_type == "visual_check":
            # Only run VLM check when use_llm=True (final scoring)
            if not use_llm:
                return False
            fname = criterion["file_name"]
            html_path = self._workspace / fname
            if not html_path.exists():
                return False
            png_path = screenshot_html(html_path)
            if not png_path:
                return False
            concept = criterion.get("concept", "")
            return vlm_visual_check(png_path, concept)

        return check_criterion_hybrid(criterion, agent_text, use_llm=use_llm)

    def _count_criteria_met(self, use_llm: bool = False) -> int:
        if not self._workspace or not self._workspace.exists():
            return 0
        agent_text = collect_workspace_text(self._workspace)
        if not agent_text:
            return 0

        count = 0
        for criterion in self._criteria:
            if self._check_criterion(criterion, agent_text, use_llm=use_llm):
                count += 1
        return count

    def _finish(self) -> dict:
        agent_text = collect_workspace_text(self._workspace) if self._workspace else ""
        criteria_results = []
        criteria_met = 0
        for c in self._criteria:
            met = self._check_criterion(c, agent_text, use_llm=True)
            criteria_results.append((c, met))
            if met:
                criteria_met += 1

        correctness = criteria_met / len(self._criteria) if self._criteria else 0.0

        # Process signals — reward meta-strategy, not just outcome
        discovery = self._has_read_specs          # explored workspace, read task spec
        reference = self._has_explored_examples   # found and studied diamond.html
        building_block = self._has_explored_elements  # discovered element code snippets

        discovery_bonus = 0.1 if discovery else 0.0
        reference_bonus = 0.1 if reference else 0.0
        building_block_bonus = 0.2 if building_block else 0.0
        correctness_component = 0.6 * correctness

        reward = discovery_bonus + reference_bonus + building_block_bonus + correctness_component

        lines = [
            f"Episode finished.",
            f"Task: {self._task_id} (transfer distance: {self._task['transfer_distance']})",
            f"Final: {criteria_met}/{len(self._criteria)} criteria met.",
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
            "criteria_total": len(self._criteria),
            "step": self._step_count,
            "task_id": self._task_id,
            "transfer_distance": self._task["transfer_distance"],
        }

    def close(self):
        if self._workspace and self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)
        self._workspace = None
