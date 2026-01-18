"""
Lint Scorer for the Style Consistency Environment.

This scorer runs the build toolchain (pnpm build, lint, format:check)
and determines if the hard gates pass.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class LintResult:
    """Result from running lint checks."""

    build_passed: bool
    lint_passed: bool
    format_passed: bool
    build_output: str
    lint_output: str
    format_output: str

    @property
    def all_passed(self) -> bool:
        """Check if all hard gates passed."""
        return self.build_passed and self.lint_passed and self.format_passed


class LintScorer:
    """
    Scorer that runs the build toolchain to check hard gates.

    Hard gates:
    - pnpm build (TypeScript compilation + Vite build)
    - pnpm lint (ESLint)
    - pnpm format:check (Prettier)

    If any hard gate fails, the total score should be 0.
    """

    def __init__(self, work_dir: Path, timeout: int = 60):
        """
        Initialize the lint scorer.

        Args:
            work_dir: Path to the frontend template directory
            timeout: Timeout for each command in seconds
        """
        self.work_dir = work_dir
        self.timeout = timeout

    def _run_command(self, cmd: list[str]) -> tuple[bool, str]:
        """
        Run a command and return (success, output).

        Args:
            cmd: Command to run

        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.work_dir),
                timeout=self.timeout,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"

            return result.returncode == 0, output

        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {self.timeout} seconds"
        except FileNotFoundError as e:
            return False, f"Command not found: {e}"
        except Exception as e:
            return False, f"Error running command: {e}"

    def run_build(self) -> tuple[bool, str]:
        """Run pnpm build."""
        return self._run_command(["pnpm", "build"])

    def run_lint(self) -> tuple[bool, str]:
        """Run pnpm lint."""
        return self._run_command(["pnpm", "lint"])

    def run_format_check(self) -> tuple[bool, str]:
        """Run pnpm format:check."""
        return self._run_command(["pnpm", "format:check"])

    def score(self) -> LintResult:
        """
        Run all lint checks and return the result.

        Returns:
            LintResult with pass/fail status for each check
        """
        build_passed, build_output = self.run_build()
        lint_passed, lint_output = self.run_lint()
        format_passed, format_output = self.run_format_check()

        return LintResult(
            build_passed=build_passed,
            lint_passed=lint_passed,
            format_passed=format_passed,
            build_output=build_output,
            lint_output=lint_output,
            format_output=format_output,
        )

    def quick_check(self) -> Optional[str]:
        """
        Run a quick TypeScript check only (faster than full build).

        Returns:
            None if passed, error message if failed
        """
        success, output = self._run_command(["pnpm", "exec", "tsc", "--noEmit"])
        if success:
            return None
        return output

