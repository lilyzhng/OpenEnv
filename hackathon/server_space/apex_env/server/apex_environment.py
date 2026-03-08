"""Core APEX environment — bash-based professional task solving."""

import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from openenv.core.env_server.interfaces import Action, Environment

from apex_env.models import ApexObservation, ApexState, BashAction

from .bash_executor import BashExecutor
from .reward import ApexRubric, check_criteria_progress
from .task_loader import TaskLoader


def _make_executor(use_sandbox: bool):
    """Create the appropriate bash executor."""
    if use_sandbox:
        from .sandbox.docker_executor import DockerBashExecutor
        return DockerBashExecutor()
    return BashExecutor()


class ApexEnvironment(Environment):
    """Environment for APEX professional tasks (law, IB, consulting).

    Each episode:
    1. reset() picks a task and creates an isolated workspace
    2. Agent executes bash commands via step()
    3. Episode ends at step limit or when agent sends "done"
    4. Reward computed via OpenEnv Rubric API (RFC 004) at episode end

    Sandbox mode (use_sandbox=True):
    - Commands run inside a Docker container (apex-sandbox:latest)
    - No network access, memory/CPU limited, non-root user
    - Workspace bind-mounted so output files are accessible for reward

    Rubric architecture:
        ApexRubric(
            Gate(FileExistence) → must create files or score = 0
            WeightedSum(KeywordCoverage, EfficiencyBonus) × TalkPenalty
        )

    Introspect rubric components:
        for name, r in env.rubric.named_rubrics():
            print(f"{name}: {r.last_score}")
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self, use_sandbox: bool = False):
        self._executor = _make_executor(use_sandbox)
        self._use_sandbox = use_sandbox
        self._task_loader = TaskLoader()
        self.rubric = ApexRubric()
        self._state = ApexState()
        self._current_task: dict | None = None
        self._workspace_dir: Path | None = None
        self._actions: list[str] = []

    def reset(self, seed=None, episode_id=None, **kwargs) -> ApexObservation:
        """Load a task, create workspace, return instruction."""
        # Clean up previous workspace
        self._cleanup_workspace()

        # Pick task (supports difficulty-based curriculum)
        task = self._task_loader.get_task(
            seed=seed,
            task_id=kwargs.get("task_id"),
            difficulty=kwargs.get("difficulty"),
        )
        self._current_task = task

        # Create isolated workspace
        self._workspace_dir = Path(
            tempfile.mkdtemp(prefix=f"apex_{task.get('task_id', 'unknown')}_")
        )

        # Reset state
        self._actions = []
        self.rubric.reset()
        self._state = ApexState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=str(task.get("task_id", "")),
            domain=task.get("domain", ""),
        )

        # Count rubric criteria for progress feedback
        progress = check_criteria_progress(task, self._workspace_dir)
        self._criteria_total = progress["criteria_total"]

        # Build instruction text
        prompt = task.get("prompt", task.get("instruction", ""))
        instruction = (
            f"# Task: {task.get('task_id', 'unknown')}\n"
            f"# Domain: {task.get('domain', 'unknown')}\n\n"
            f"{prompt}\n\n"
            f"Your workspace is: {self._workspace_dir}\n"
            f"This task has {self._criteria_total} evaluation criteria.\n"
            f"Create your output files in the workspace directory.\n"
            f"When finished, send the command: done"
        )

        return ApexObservation(
            stdout=instruction,
            stderr="",
            exit_code=0,
            done=False,
            reward=None,
            metadata={
                "task_id": task.get("task_id"),
                "domain": task.get("domain"),
                "workspace": str(self._workspace_dir),
            },
        )

    def step(self, action: Action, timeout_s=None, **kwargs) -> ApexObservation:
        """Execute bash command, return output, check termination."""
        if not isinstance(action, BashAction):
            raise ValueError(f"Expected BashAction, got {type(action)}")

        if self._workspace_dir is None:
            raise RuntimeError("Must call reset() before step()")

        self._state.step_count += 1
        self._actions.append(action.command)

        # Check if agent is signaling done
        agent_said_done = action.command.strip().lower() == "done"

        if agent_said_done:
            reward = self._compute_rubric_reward()
            progress = check_criteria_progress(self._current_task, self._workspace_dir)
            return ApexObservation(
                stdout=f"Episode finished. Final: {progress['criteria_met']}/{progress['criteria_total']} criteria met.",
                stderr="",
                exit_code=0,
                done=True,
                reward=reward,
                metadata={
                    "step": self._state.step_count,
                    "criteria_met": progress["criteria_met"],
                    "criteria_total": progress["criteria_total"],
                    "files_created": progress["files_created"],
                },
            )

        # Execute in workspace
        result = self._executor.run(
            action.command,
            cwd=self._workspace_dir,
            timeout_s=timeout_s or 30.0,
        )

        # Check step limit
        at_step_limit = self._state.step_count >= self._state.max_steps
        is_done = at_step_limit

        reward = None
        if is_done:
            reward = self._compute_rubric_reward()

        # Update file list
        self._state.files_in_workspace = [
            f.name
            for f in self._workspace_dir.iterdir()
            if f.is_file()
        ]

        # Per-step progress feedback — the environment responds to agent actions
        progress = check_criteria_progress(self._current_task, self._workspace_dir)
        criteria_met = progress["criteria_met"]
        criteria_total = progress["criteria_total"]
        files = progress["files_created"]

        progress_line = f"\n[Progress: {criteria_met}/{criteria_total} criteria met"
        if files:
            progress_line += f" | Files: {', '.join(files)}"
        progress_line += "]"

        # Append progress to stdout so agent sees it as environment feedback
        enriched_stdout = result.stdout + progress_line

        return ApexObservation(
            stdout=enriched_stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            done=is_done,
            reward=reward,
            metadata={
                "step": self._state.step_count,
                "criteria_met": criteria_met,
                "criteria_total": criteria_total,
                "files_created": files,
            },
        )

    def _compute_rubric_reward(self) -> float:
        """Compute reward using OpenEnv Rubric API."""
        if self._current_task is None or self._workspace_dir is None:
            return 0.0

        # Build observation with metadata the rubric needs
        obs = ApexObservation(
            stdout="", stderr="", exit_code=0, done=True, reward=None,
            metadata={
                "workspace": str(self._workspace_dir),
                "task": self._current_task,
                "actions": self._actions,
                "step": self._state.step_count,
            },
        )
        action = BashAction(command="done")
        return self.rubric(action, obs)

    @property
    def state(self) -> ApexState:
        return self._state

    def close(self):
        self._cleanup_workspace()

    def _cleanup_workspace(self):
        if self._workspace_dir:
            if self._use_sandbox and hasattr(self._executor, 'cleanup'):
                self._executor.cleanup(self._workspace_dir)
            if self._workspace_dir.exists():
                shutil.rmtree(self._workspace_dir, ignore_errors=True)
        self._workspace_dir = None
