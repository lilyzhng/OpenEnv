"""
Refactor Environment Client.

This module provides the client for connecting to a Refactor Environment server
via WebSocket for persistent sessions.
"""

from typing import Dict

# Support both in-repo and standalone imports
try:
    # In-repo imports (when running from OpenEnv repository)
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient
    from .models import RefactorAction, RefactorObservation, RefactorState
except ImportError:
    # Standalone imports (when environment is standalone with openenv from pip)
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient
    from models import RefactorAction, RefactorObservation, RefactorState


class RefactorEnv(EnvClient[RefactorAction, RefactorObservation, RefactorState]):
    """
    Client for the Refactor Environment.

    This client maintains a persistent WebSocket connection to the environment
    server, enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with RefactorEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(f"Initial metrics: dup={result.observation.dup_score:.4f}")
        ...
        ...     # Read a file
        ...     result = client.step(RefactorAction(
        ...         action_type="READ_FILE",
        ...         path="utils/string_helpers.py"
        ...     ))
        ...     print(result.observation.output)
        ...
        ...     # Run tests
        ...     result = client.step(RefactorAction(
        ...         action_type="RUN",
        ...         cmd_id="TEST"
        ...     ))
        ...     print(f"Tests passed: {result.observation.tests_pass}")

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = RefactorEnv.from_docker_image("refactor-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(RefactorAction(action_type="RUN", cmd_id="METRICS"))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: RefactorAction) -> Dict:
        """
        Convert RefactorAction to JSON payload for step request.

        Args:
            action: RefactorAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        payload = {
            "action_type": action.action_type,
        }
        
        if action.path is not None:
            payload["path"] = action.path
        if action.pattern is not None:
            payload["pattern"] = action.pattern
        if action.diff is not None:
            payload["diff"] = action.diff
        if action.cmd_id is not None:
            payload["cmd_id"] = action.cmd_id
            
        return payload

    def _parse_result(self, payload: Dict) -> StepResult[RefactorObservation]:
        """
        Parse server response into StepResult[RefactorObservation].

        Args:
            payload: JSON response from server

        Returns:
            StepResult with RefactorObservation
        """
        obs_data = payload.get("observation", {})
        observation = RefactorObservation(
            output=obs_data.get("output", ""),
            tests_pass=obs_data.get("tests_pass"),
            api_pass=obs_data.get("api_pass"),
            dup_score=obs_data.get("dup_score", 0.0),
            complexity_score=obs_data.get("complexity_score", 0.0),
            loc=obs_data.get("loc", 0),
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

    def _parse_state(self, payload: Dict) -> RefactorState:
        """
        Parse server response into RefactorState object.

        Args:
            payload: JSON response from /state endpoint

        Returns:
            RefactorState object
        """
        return RefactorState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            tests_pass=payload.get("tests_pass"),
            api_pass=payload.get("api_pass"),
            baseline_dup=payload.get("baseline_dup", 0.0),
            baseline_complexity=payload.get("baseline_complexity", 0.0),
            baseline_loc=payload.get("baseline_loc", 0),
        )

