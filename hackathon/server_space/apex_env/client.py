"""Client-side wrapper for the APEX environment."""

from typing import Dict

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult

from .models import ApexObservation, ApexState, BashAction


class ApexEnv(EnvClient[BashAction, ApexObservation, ApexState]):
    """Client for interacting with the APEX environment server."""

    def _step_payload(self, action: BashAction) -> Dict:
        return {"command": action.command}

    def _parse_result(self, payload: Dict) -> StepResult[ApexObservation]:
        obs_data = payload.get("observation", {})
        observation = ApexObservation(
            stdout=obs_data.get("stdout", ""),
            stderr=obs_data.get("stderr", ""),
            exit_code=obs_data.get("exit_code", 0),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=bool(payload.get("done", False)),
        )

    def _parse_state(self, payload: Dict) -> ApexState:
        return ApexState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id"),
            domain=payload.get("domain"),
            max_steps=payload.get("max_steps", 20),
            files_in_workspace=payload.get("files_in_workspace", []),
        )
