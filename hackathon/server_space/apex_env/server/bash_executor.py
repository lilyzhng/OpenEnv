"""Subprocess-based bash executor."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BashResult:
    stdout: str
    stderr: str
    exit_code: int


class BashExecutor:
    """Execute bash commands in a given working directory."""

    def run(
        self, command: str, cwd: Path, timeout_s: float = 30.0
    ) -> BashResult:
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=cwd,
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
