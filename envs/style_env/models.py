"""
Data models for the Style Consistency Environment.

The Style environment evaluates frontend code for adherence to product-specific
design systems, penalizing "AI slop" aesthetics like purple gradients, neon colors,
and inconsistent styling.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Support both in-repo and standalone imports
try:
    from openenv.core.env_server.types import Action, Observation, State
except ImportError:
    from openenv.core.env_server.types import Action, Observation, State


class StyleAction(Action):
    """
    Action for the Style Consistency environment.

    Supports 5 action types:
    - READ_FILE: Read contents of a file
    - CREATE_FILE: Create a new file with specified content
    - APPLY_PATCH: Apply a unified diff patch
    - RUN: Run a command (BUILD, LINT, SCORE)
    - GET_PROFILE: Get current product profile rules
    """

    action_type: Literal["READ_FILE", "CREATE_FILE", "APPLY_PATCH", "RUN", "GET_PROFILE"] = Field(
        ..., description="Type of action to perform"
    )
    path: Optional[str] = Field(
        default=None, description="File path for READ_FILE/CREATE_FILE actions"
    )
    content: Optional[str] = Field(
        default=None, description="File content for CREATE_FILE action"
    )
    diff: Optional[str] = Field(
        default=None, description="Unified diff text for APPLY_PATCH action"
    )
    cmd_id: Optional[Literal["BUILD", "LINT", "SCORE"]] = Field(
        default=None, description="Command ID for RUN action"
    )


class RuleViolation(BaseModel):
    """A single rule violation detected by the scorer."""

    rule: str = Field(..., description="Rule ID (e.g., R1, R2)")
    file: str = Field(..., description="File where violation occurred")
    line: int = Field(..., ge=1, description="Line number of violation")
    snippet: str = Field(..., description="Code snippet showing the violation")
    penalty: int = Field(..., le=0, description="Penalty points (negative)")


class ScoreBreakdown(BaseModel):
    """Detailed scoring breakdown from the style evaluation."""

    total_score: int = Field(ge=0, le=100, description="Total score (0-100)")
    max_score: int = Field(default=100, description="Maximum possible score")
    hard_gates: Dict[str, bool] = Field(
        default_factory=dict,
        description="Hard gate results (build, lint, format)"
    )
    rule_violations: List[RuleViolation] = Field(
        default_factory=list,
        description="List of rule violations"
    )
    penalties_total: int = Field(
        default=0, le=0,
        description="Total penalty points (negative or zero)"
    )


class StyleObservation(Observation):
    """
    Observation from the Style Consistency environment.

    Contains the output of the last action plus current scoring state.
    """

    output: str = Field(
        default="",
        description="Output from the last action (file contents, command output, etc.)"
    )
    current_profile: str = Field(
        default="",
        description="Active product profile name (enterprise, consumer, fintech)"
    )
    task_description: str = Field(
        default="",
        description="Current task description"
    )
    build_passed: Optional[bool] = Field(
        default=None,
        description="Whether build is passing (None if not yet run)"
    )
    lint_passed: Optional[bool] = Field(
        default=None,
        description="Whether lint is passing (None if not yet run)"
    )
    format_passed: Optional[bool] = Field(
        default=None,
        description="Whether format check is passing (None if not yet run)"
    )
    score_breakdown: Optional[ScoreBreakdown] = Field(
        default=None,
        description="Detailed scoring breakdown (None if SCORE not yet run)"
    )
    steps_remaining: int = Field(
        default=0, ge=0,
        description="Number of steps remaining in episode"
    )


class StyleState(State):
    """State for the Style Consistency environment."""

    current_profile: str = Field(default="", description="Active product profile")
    task_id: str = Field(default="", description="Current task ID")
    build_passed: Optional[bool] = Field(default=None)
    lint_passed: Optional[bool] = Field(default=None)
    format_passed: Optional[bool] = Field(default=None)
    last_score: Optional[int] = Field(default=None, ge=0, le=100)

