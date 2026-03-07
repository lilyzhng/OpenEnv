"""APEX Environment models — Action, Observation, State."""

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field


class BashAction(Action):
    """A bash command to execute in the sandbox."""

    command: str = Field(..., description="Bash command to execute")


class ApexObservation(Observation):
    """Result of executing a bash command."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class ApexState(State):
    """Environment state tracking task progress."""

    task_id: str | None = None
    domain: str | None = None
    max_steps: int = 20
    files_in_workspace: list[str] = Field(default_factory=list)
