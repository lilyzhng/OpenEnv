"""Phased APEX environment — dynamic teaching environment with conditional info release.

This extends ApexEnvironment with phase-based progression:
- Information is released incrementally (not all at once)
- Environment gives intermediate feedback after each step
- Agent must demonstrate understanding before advancing

This is the "teaching coach" version of the environment, vs the "exam" version.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

try:
    from .bash_executor import BashExecutor
    from .reward import READABLE_SUFFIXES, collect_workspace_text
    from .demo_task import PHASES, BRIEF_CONTENT, CRITERIA, HF_FILE
except ImportError:
    from bash_executor import BashExecutor
    from reward import READABLE_SUFFIXES, collect_workspace_text
    from demo_task import PHASES, BRIEF_CONTENT, CRITERIA, HF_FILE


class PhasedEnvironment:
    """A dynamic teaching environment for the KatNip demo task.

    Unlike the flat ApexEnvironment (give task → run bash → score at end),
    this environment:
    1. Releases information in phases (brief first, then data, then instructions)
    2. Checks progress after every step
    3. Advances to the next phase when the agent demonstrates readiness
    4. Gives intermediate feedback throughout

    Lifecycle:
        env = PhasedEnvironment()
        obs = env.reset()           # Phase 1: brief only
        obs = env.step("cat brief.md")  # Agent reads brief → Phase 2 unlocks
        obs = env.step("python3 extract.py")  # Agent works with data
        ...
        obs = env.step("done")      # Final scoring
    """

    def __init__(self, use_sandbox: bool = False):
        if use_sandbox:
            from .sandbox.docker_executor import DockerBashExecutor
            self._executor = DockerBashExecutor()
        else:
            self._executor = BashExecutor()
        self._use_sandbox = use_sandbox
        self._workspace: Path | None = None
        self._current_phase: int = 0  # Index into PHASES
        self._actions: list[str] = []
        self._step_count: int = 0
        self._phase_history: list[dict] = []  # Track when phases were unlocked

    def reset(self) -> dict:
        """Start the episode — Phase 1: give the brief only."""
        if self._workspace and self._workspace.exists():
            if self._use_sandbox and hasattr(self._executor, 'cleanup'):
                self._executor.cleanup(self._workspace)
            shutil.rmtree(self._workspace, ignore_errors=True)

        self._workspace = Path(tempfile.mkdtemp(prefix="apex_demo_katnip_"))
        self._current_phase = 0
        self._actions = []
        self._step_count = 0
        self._phase_history = []

        # Phase 1: release brief.md
        (self._workspace / "brief.md").write_text(BRIEF_CONTENT)
        self._phase_history.append({"phase": 1, "step": 0})

        phase = PHASES[0]
        instruction = (
            f"# KatNip Co. Financial Analysis (Demo)\n"
            f"# Phase 1 of {len(PHASES)}: {phase['name']}\n\n"
            f"{phase['brief']}\n"
            f"Your workspace is: {self._workspace}\n"
            f"This task has {len(CRITERIA)} evaluation criteria across {len(PHASES)} phases.\n"
            f"The environment will guide you through each phase.\n"
        )

        return {
            "stdout": instruction,
            "stderr": "",
            "exit_code": 0,
            "done": False,
            "reward": None,
            "phase": 1,
            "phase_name": phase["name"],
            "criteria_met": 0,
            "criteria_total": len(CRITERIA),
        }

    def step(self, command: str) -> dict:
        """Execute command, check phase progression, give feedback."""
        self._step_count += 1
        self._actions.append(command)

        # Check done
        if command.strip().lower() == "done":
            return self._finish()

        # Execute command
        result = self._executor.run(command, cwd=self._workspace, timeout_s=30.0)

        # Check criteria progress
        criteria_met = self._count_criteria_met()

        # Check if we should advance phase
        phase_advanced = self._maybe_advance_phase(command, criteria_met)

        # Build feedback
        phase = PHASES[self._current_phase]
        feedback_parts = []

        if result.stdout:
            feedback_parts.append(result.stdout[:3000])

        # Phase advancement feedback
        if phase_advanced:
            feedback_parts.append(
                f"\n{'='*50}\n"
                f"Phase {phase['id']} of {len(PHASES)}: {phase['name']}\n"
                f"{'='*50}\n"
                f"{phase['brief']}"
            )
            # Release files for new phase
            self._release_phase_files(phase)

        # Progress feedback
        files_in_ws = [f.name for f in self._workspace.iterdir() if f.is_file()]
        feedback_parts.append(
            f"\n[Phase {phase['id']}/{len(PHASES)}: {phase['name']} | "
            f"Progress: {criteria_met}/{len(CRITERIA)} criteria met | "
            f"Files: {', '.join(files_in_ws)}]"
        )

        return {
            "stdout": "\n".join(feedback_parts),
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "done": False,
            "reward": None,
            "phase": phase["id"],
            "phase_name": phase["name"],
            "criteria_met": criteria_met,
            "criteria_total": len(CRITERIA),
            "step": self._step_count,
        }

    def _maybe_advance_phase(self, command: str, criteria_met: int) -> bool:
        """Check if we should advance to the next phase."""
        if self._current_phase >= len(PHASES) - 1:
            return False  # Already at last phase

        phase = PHASES[self._current_phase]

        # Phase 1→2: agent read the brief (ran cat/head/less on brief.md)
        if phase["id"] == 1:
            if any(kw in command.lower() for kw in ["cat brief", "head brief", "less brief", "more brief", "cat ./brief"]):
                self._current_phase = 1
                self._phase_history.append({"phase": 2, "step": self._step_count})
                return True

        # Phase 2→3: agent has interacted with the PDF (ran python/pdfplumber)
        elif phase["id"] == 2:
            if any(kw in command.lower() for kw in ["pdfplumber", "pdf", "python", "cat katnip"]):
                self._current_phase = 2
                self._phase_history.append({"phase": 3, "step": self._step_count})
                return True

        # Phase 3→4: IRR and MOIC criteria met
        elif phase["id"] == 3:
            if criteria_met >= 2:  # criteria 1 & 2
                self._current_phase = 3
                self._phase_history.append({"phase": 4, "step": self._step_count})
                return True

        # Phase 4→5: NPV criteria met
        elif phase["id"] == 4:
            if criteria_met >= 5:  # criteria 1-5
                self._current_phase = 4
                self._phase_history.append({"phase": 5, "step": self._step_count})
                return True

        return False

    def _release_phase_files(self, phase: dict) -> None:
        """Release files for the current phase."""
        for fname in phase.get("files_to_release", []):
            if fname == "brief.md":
                continue  # Already released
            if fname == "KatNip.pdf":
                # Download from HuggingFace
                try:
                    from huggingface_hub import hf_hub_download
                    local = hf_hub_download("mercor/APEX-v1-extended", HF_FILE, repo_type="dataset")
                    shutil.copy2(local, self._workspace / "KatNip.pdf")
                except Exception as e:
                    # Fallback: create a placeholder
                    (self._workspace / "KatNip.pdf").write_text(
                        f"[PDF download failed: {e}. Use the data from brief.md.]"
                    )

    def _count_criteria_met(self) -> int:
        """Count how many criteria are currently satisfied."""
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
        """End the episode and compute final score."""
        criteria_met = self._count_criteria_met()
        reward = criteria_met / len(CRITERIA) if CRITERIA else 0.0

        # Build final report
        report_lines = [
            f"Episode finished.",
            f"Final: {criteria_met}/{len(CRITERIA)} criteria met.",
            f"Reward: {reward:.3f}",
            f"Steps used: {self._step_count}",
            f"Phases reached: {self._current_phase + 1}/{len(PHASES)}",
            f"",
            f"Phase progression:",
        ]
        for ph in self._phase_history:
            report_lines.append(f"  Phase {ph['phase']} unlocked at step {ph['step']}")

        report_lines.append(f"\nCriteria breakdown:")
        agent_text = collect_workspace_text(self._workspace).lower() if self._workspace else ""
        for c in CRITERIA:
            met = any(kw.lower() in agent_text for kw in c["check_keywords"])
            status = "PASS" if met else "FAIL"
            report_lines.append(f"  [{status}] {c['description']}")

        return {
            "stdout": "\n".join(report_lines),
            "stderr": "",
            "exit_code": 0,
            "done": True,
            "reward": reward,
            "phase": self._current_phase + 1,
            "phase_name": PHASES[self._current_phase]["name"],
            "criteria_met": criteria_met,
            "criteria_total": len(CRITERIA),
            "step": self._step_count,
            "phase_history": self._phase_history,
        }

    def close(self):
        if self._workspace:
            if self._use_sandbox and hasattr(self._executor, 'cleanup'):
                self._executor.cleanup(self._workspace)
            if self._workspace.exists():
                shutil.rmtree(self._workspace, ignore_errors=True)
        self._workspace = None
