"""
Style Consistency Environment Client.

This module provides the client for connecting to a Style Environment server
via WebSocket for persistent sessions.
"""

from typing import Dict

# Support both in-repo and standalone imports
try:
    # In-repo imports (when running from OpenEnv repository)
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient
    from .models import (
        StyleAction,
        StyleObservation,
        StyleState,
        ScoreBreakdown,
        RuleViolation,
    )
except ImportError:
    # Standalone imports (when environment is standalone with openenv from pip)
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient
    from models import (
        StyleAction,
        StyleObservation,
        StyleState,
        ScoreBreakdown,
        RuleViolation,
    )


class StyleEnv(EnvClient[StyleAction, StyleObservation, StyleState]):
    """
    Client for the Style Consistency Environment.

    This client maintains a persistent WebSocket connection to the environment
    server, enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    The environment evaluates frontend code for adherence to product-specific
    design systems, penalizing "AI slop" aesthetics.

    Example:
        >>> # Connect to a running server
        >>> with StyleEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(f"Profile: {result.observation.current_profile}")
        ...     print(f"Task: {result.observation.task_description}")
        ...
        ...     # Read a file
        ...     result = client.step(StyleAction(
        ...         action_type="READ_FILE",
        ...         path="src/components/ui/Button.tsx"
        ...     ))
        ...     print(result.observation.output)
        ...
        ...     # Create a new page
        ...     result = client.step(StyleAction(
        ...         action_type="CREATE_FILE",
        ...         path="src/pages/Settings.tsx",
        ...         content="export default function Settings() { ... }"
        ...     ))
        ...
        ...     # Run scoring
        ...     result = client.step(StyleAction(action_type="RUN", cmd_id="SCORE"))
        ...     print(f"Score: {result.observation.score_breakdown.total_score}")

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = StyleEnv.from_docker_image("style-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(StyleAction(action_type="GET_PROFILE"))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: StyleAction) -> Dict:
        """
        Convert StyleAction to JSON payload for step request.

        Args:
            action: StyleAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        payload = {
            "action_type": action.action_type,
        }

        if action.path is not None:
            payload["path"] = action.path
        if action.content is not None:
            payload["content"] = action.content
        if action.diff is not None:
            payload["diff"] = action.diff
        if action.cmd_id is not None:
            payload["cmd_id"] = action.cmd_id

        return payload

    def _parse_result(self, payload: Dict) -> StepResult[StyleObservation]:
        """
        Parse server response into StepResult[StyleObservation].

        Args:
            payload: JSON response from server

        Returns:
            StepResult with StyleObservation
        """
        obs_data = payload.get("observation", {})

        # Parse score breakdown if present
        score_breakdown = None
        if obs_data.get("score_breakdown"):
            sb_data = obs_data["score_breakdown"]
            rule_violations = [
                RuleViolation(**rv) for rv in sb_data.get("rule_violations", [])
            ]
            score_breakdown = ScoreBreakdown(
                total_score=sb_data.get("total_score", 0),
                max_score=sb_data.get("max_score", 100),
                hard_gates=sb_data.get("hard_gates", {}),
                rule_violations=rule_violations,
                penalties_total=sb_data.get("penalties_total", 0),
            )

        observation = StyleObservation(
            output=obs_data.get("output", ""),
            current_profile=obs_data.get("current_profile", ""),
            task_description=obs_data.get("task_description", ""),
            build_passed=obs_data.get("build_passed"),
            lint_passed=obs_data.get("lint_passed"),
            format_passed=obs_data.get("format_passed"),
            score_breakdown=score_breakdown,
            steps_remaining=obs_data.get("steps_remaining", 0),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> StyleState:
        """
        Parse server response into StyleState object.

        Args:
            payload: JSON response from /state endpoint

        Returns:
            StyleState object
        """
        return StyleState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            current_profile=payload.get("current_profile", ""),
            task_id=payload.get("task_id", ""),
            build_passed=payload.get("build_passed"),
            lint_passed=payload.get("lint_passed"),
            format_passed=payload.get("format_passed"),
            last_score=payload.get("last_score"),
        )

