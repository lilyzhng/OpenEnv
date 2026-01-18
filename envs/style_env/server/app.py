"""
FastAPI application for the Style Consistency Environment.

This module creates an HTTP server that exposes the StyleEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    uv run --project . server
"""

# Support both in-repo and standalone imports
try:
    # In-repo imports (when running from OpenEnv repository)
    from openenv.core.env_server.http_server import create_app
    from ..models import StyleAction, StyleObservation
    from .style_environment import StyleEnvironment
except ImportError:
    # Standalone imports (when environment is standalone with openenv from pip)
    from openenv.core.env_server.http_server import create_app
    from models import StyleAction, StyleObservation
    from server.style_environment import StyleEnvironment

# Create the app with web interface and README integration
# Pass the class (factory) instead of an instance for WebSocket session support
app = create_app(StyleEnvironment, StyleAction, StyleObservation, env_name="style_env")


def main():
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        python -m envs.style_env.server.app
        openenv serve style_env

    """
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

