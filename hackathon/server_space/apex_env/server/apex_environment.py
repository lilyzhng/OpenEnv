"""Core APEX environment — bash-based professional task solving."""

import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from openenv.core.env_server.interfaces import Action, Environment

from apex_env.models import ApexObservation, ApexState, BashAction

from .bash_executor import BashExecutor
from .reward import compute_reward
from .task_loader import TaskLoader


class ApexEnvironment(Environment):
    """Environment for APEX professional tasks (law, IB, consulting).

    Each episode:
    1. reset() picks a task and creates an isolated workspace
    2. Agent executes bash commands via step()
    3. Episode ends at step limit or when agent sends "done"
    4. Reward computed from rubric at episode end
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._executor = BashExecutor()
        self._task_loader = TaskLoader()
        self._state = ApexState()
        self._current_task: dict | None = None
        self._workspace_dir: Path | None = None

    def reset(self, seed=None, episode_id=None, **kwargs) -> ApexObservation:
        """Load a task, create workspace, return instruction."""
        # Clean up previous workspace
        self._cleanup_workspace()

        # Pick task
        task = self._task_loader.get_task(
            seed=seed, task_id=kwargs.get("task_id")
        )
        self._current_task = task

        # Create isolated workspace
        self._workspace_dir = Path(
            tempfile.mkdtemp(prefix=f"apex_{task.get('task_id', 'unknown')}_")
        )

        # Reset state
        self._state = ApexState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=str(task.get("task_id", "")),
            domain=task.get("domain", ""),
        )

        # Build instruction text
        prompt = task.get("prompt", task.get("instruction", ""))
        instruction = (
            f"# Task: {task.get('task_id', 'unknown')}\n"
            f"# Domain: {task.get('domain', 'unknown')}\n\n"
            f"{prompt}\n\n"
            f"Your workspace is: {self._workspace_dir}\n"
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

        # Check if agent is signaling done
        agent_said_done = action.command.strip().lower() == "done"

        if agent_said_done:
            reward = self._compute_reward()
            return ApexObservation(
                stdout="Episode finished.",
                stderr="",
                exit_code=0,
                done=True,
                reward=reward,
                metadata={"step": self._state.step_count},
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
            reward = self._compute_reward()

        # Update file list
        self._state.files_in_workspace = [
            f.name
            for f in self._workspace_dir.iterdir()
            if f.is_file()
        ]

        return ApexObservation(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            done=is_done,
            reward=reward,
            metadata={"step": self._state.step_count},
        )

    def _compute_reward(self) -> float:
        if self._current_task is None or self._workspace_dir is None:
            return 0.0
        return compute_reward(self._current_task, self._workspace_dir)

    @property
    def state(self) -> ApexState:
        return self._state

    def close(self):
        self._cleanup_workspace()

    def _cleanup_workspace(self):
        if self._workspace_dir and self._workspace_dir.exists():
            shutil.rmtree(self._workspace_dir, ignore_errors=True)
        self._workspace_dir = None
