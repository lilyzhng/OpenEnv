"""
APEX Environment Server — OpenEnv-compatible FastAPI app.

This is the "exam room" that the trainer connects to.
- POST /reset  → load a task, create workspace, return instruction
- POST /step   → execute bash command, return observation + reward
- GET  /state  → get current environment state

Trainer connects via:
    from apex_env.client import ApexEnv
    env = ApexEnv(base_url="https://lilyzhng-apex-env-server.hf.space")
    obs = env.reset()
    obs = env.step(BashAction(command="echo hello"))
"""

from apex_env.models import ApexObservation, BashAction
from apex_env.server.apex_environment import ApexEnvironment
from openenv.core.env_server import create_app

app = create_app(
    ApexEnvironment,
    BashAction,
    ApexObservation,
    env_name="apex_env",
)
