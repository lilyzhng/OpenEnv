"""FastAPI app for the APEX environment."""

from apex_env.models import ApexObservation, BashAction
from apex_env.server.apex_environment import ApexEnvironment
from openenv.core.env_server import create_app

app = create_app(
    ApexEnvironment,
    BashAction,
    ApexObservation,
    env_name="apex_env",
)


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
