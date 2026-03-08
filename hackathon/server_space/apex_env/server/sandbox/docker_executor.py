"""Docker-based bash executor — runs agent commands in an isolated container."""
from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from bash_executor import BashResult


SANDBOX_IMAGE = "apex-sandbox:latest"
CONTAINER_WORKSPACE = "/home/agent/workspace"


class DockerBashExecutor:
    """Execute bash commands inside a Docker container.

    Drop-in replacement for BashExecutor. Each episode gets its own container
    (started on first command, removed on cleanup). The host workspace directory
    is bind-mounted into the container so output files are accessible for reward
    computation.

    Security constraints:
    - No network access (--network none)
    - No privileged escalation (--security-opt no-new-privileges)
    - Memory limit (512MB)
    - CPU limit (1 core)
    - Non-root user inside container
    """

    def __init__(self, image: str = SANDBOX_IMAGE):
        self._image = image
        self._containers: dict[str, str] = {}  # workspace_path -> container_id

    def _ensure_container(self, cwd: Path) -> str:
        """Start a container for this workspace if not already running."""
        key = str(cwd)
        if key in self._containers:
            # Check if container is still running
            check = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self._containers[key]],
                capture_output=True, text=True,
            )
            if check.returncode == 0 and "true" in check.stdout.strip():
                return self._containers[key]
            # Container died, remove reference
            del self._containers[key]

        # Start new container with workspace mounted
        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", f"apex-{cwd.name}",
                "--network", "none",
                "--security-opt", "no-new-privileges",
                "--memory", "512m",
                "--cpus", "1",
                "-v", f"{cwd}:{CONTAINER_WORKSPACE}",
                "-w", CONTAINER_WORKSPACE,
                self._image,
                "sleep", "3600",  # Keep alive for 1 hour
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start sandbox container: {result.stderr}")

        container_id = result.stdout.strip()
        self._containers[key] = container_id
        return container_id

    def run(self, command: str, cwd: Path, timeout_s: float = 30.0) -> BashResult:
        """Execute a bash command inside the sandbox container."""
        try:
            container_id = self._ensure_container(cwd)
        except RuntimeError as e:
            return BashResult(stdout="", stderr=f"Sandbox error: {e}", exit_code=1)

        try:
            result = subprocess.run(
                ["docker", "exec", container_id, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return BashResult(
                stdout=result.stdout[:10000],
                stderr=result.stderr[:5000],
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return BashResult(stdout="", stderr="Command timed out", exit_code=124)
        except Exception as e:
            return BashResult(stdout="", stderr=str(e), exit_code=1)

    def cleanup(self, cwd: Path) -> None:
        """Stop and remove the container for this workspace."""
        key = str(cwd)
        container_id = self._containers.pop(key, None)
        if container_id:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True, timeout=10,
            )

    def cleanup_all(self) -> None:
        """Stop and remove all containers managed by this executor."""
        for key in list(self._containers.keys()):
            self.cleanup(Path(key))
