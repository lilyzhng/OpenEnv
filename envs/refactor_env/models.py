"""
Data models for the Refactor Environment.

The Refactor environment allows agents to refactor code while maintaining
tests and API contracts.
"""

from typing import Literal, Optional

from pydantic import Field

# Support both in-repo and standalone imports
try:
    from openenv.core.env_server.types import Action, Observation, State
except ImportError:
    from openenv.core.env_server.types import Action, Observation, State


class RefactorAction(Action):
    """
    Action for the Refactor environment.
    
    Supports 4 action types:
    - READ_FILE: Read contents of a file
    - SEARCH: Search for a pattern in the codebase
    - APPLY_PATCH: Apply a unified diff patch
    - RUN: Run a command (TEST, API_CHECK, or METRICS)
    """

    action_type: Literal["READ_FILE", "SEARCH", "APPLY_PATCH", "RUN"] = Field(
        ..., description="Type of action to perform"
    )
    path: Optional[str] = Field(
        default=None, description="File path for READ_FILE action"
    )
    pattern: Optional[str] = Field(
        default=None, description="Search pattern for SEARCH action"
    )
    diff: Optional[str] = Field(
        default=None, description="Unified diff text for APPLY_PATCH action"
    )
    cmd_id: Optional[Literal["TEST", "API_CHECK", "METRICS"]] = Field(
        default=None, description="Command ID for RUN action"
    )


class RefactorObservation(Observation):
    """
    Observation from the Refactor environment.
    
    Contains the output of the last action plus current metrics.
    """

    output: str = Field(
        default="", description="Output from the last action (file contents, search results, command output)"
    )
    tests_pass: Optional[bool] = Field(
        default=None, description="Whether tests are passing (None if not yet run)"
    )
    api_pass: Optional[bool] = Field(
        default=None, description="Whether API check is passing (None if not yet run)"
    )
    dup_score: float = Field(
        default=0.0, ge=0.0, description="Duplication score (lower is better)"
    )
    complexity_score: float = Field(
        default=0.0, ge=0.0, description="Cyclomatic complexity score (lower is better)"
    )
    loc: int = Field(
        default=0, ge=0, description="Lines of code"
    )
    steps_remaining: int = Field(
        default=0, ge=0, description="Number of steps remaining in episode"
    )


class RefactorState(State):
    """State for the Refactor environment."""

    tests_pass: Optional[bool] = None
    api_pass: Optional[bool] = None
    baseline_dup: float = 0.0
    baseline_complexity: float = 0.0
    baseline_loc: int = 0

