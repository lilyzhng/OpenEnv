"""
Refactor Environment Implementation.

An RL environment for code refactoring tasks. The agent must reduce
duplication and complexity while keeping tests and API contracts passing.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

# Support both in-repo and standalone imports
try:
    from openenv.core.env_server.interfaces import Environment
    from ..models import RefactorAction, RefactorObservation, RefactorState
except ImportError:
    from openenv.core.env_server.interfaces import Environment
    from models import RefactorAction, RefactorObservation, RefactorState

from .metrics import compute_all_metrics


# Default episode length
MAX_STEPS = 50

# Path to bundled target repo
TARGET_REPO_PATH = Path(__file__).parent.parent / "target_repo"


class RefactorEnvironment(Environment):
    """
    Refactor Environment for code refactoring RL tasks.
    
    The agent can:
    - READ_FILE: Read the contents of a file
    - SEARCH: Search for a pattern in the codebase
    - APPLY_PATCH: Apply a unified diff patch
    - RUN: Run TEST, API_CHECK, or METRICS commands
    
    Reward is based on reducing duplication, complexity, and LOC
    while keeping tests and API checks passing.
    
    Example:
        >>> env = RefactorEnvironment()
        >>> obs = env.reset()
        >>> print(obs.dup_score, obs.complexity_score, obs.loc)
        >>> 
        >>> action = RefactorAction(action_type="READ_FILE", path="utils/string_helpers.py")
        >>> obs = env.step(action)
        >>> print(obs.output)
    """
    
    def __init__(self, max_steps: int = MAX_STEPS):
        """Initialize the refactor environment."""
        self.max_steps = max_steps
        self._state = RefactorState(episode_id=str(uuid4()), step_count=0)
        self._work_dir: Optional[Path] = None
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
    
    def reset(self) -> RefactorObservation:
        """
        Reset the environment to initial state.
        
        Creates a fresh copy of the target repo and computes baseline metrics.
        
        Returns:
            Initial observation with baseline metrics
        """
        # Clean up previous temp directory
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
        
        # Create new temp directory with fresh copy of target repo
        self._temp_dir = tempfile.TemporaryDirectory(prefix="refactor_env_")
        self._work_dir = Path(self._temp_dir.name) / "repo"
        shutil.copytree(TARGET_REPO_PATH, self._work_dir)
        
        # Compute baseline metrics
        metrics = compute_all_metrics(str(self._work_dir))
        
        # Initialize state
        self._state = RefactorState(
            episode_id=str(uuid4()),
            step_count=0,
            tests_pass=None,
            api_pass=None,
            baseline_dup=metrics["dup_score"],
            baseline_complexity=metrics["complexity_score"],
            baseline_loc=int(metrics["loc"]),
        )
        
        # List files in the repo
        file_list = self._list_files()
        
        return RefactorObservation(
            output=f"Environment reset. Working directory initialized.\n\nFiles in repo:\n{file_list}",
            tests_pass=None,
            api_pass=None,
            dup_score=metrics["dup_score"],
            complexity_score=metrics["complexity_score"],
            loc=int(metrics["loc"]),
            steps_remaining=self.max_steps,
            done=False,
            reward=0.0,
        )
    
    def step(self, action: RefactorAction) -> RefactorObservation:
        """
        Execute an action in the environment.
        
        Args:
            action: RefactorAction to execute
            
        Returns:
            RefactorObservation with action result and current metrics
        """
        if not isinstance(action, RefactorAction):
            raise ValueError(f"Expected RefactorAction, got {type(action)}")
        
        self._state.step_count += 1
        steps_remaining = max(0, self.max_steps - self._state.step_count)
        
        # Execute the action
        if action.action_type == "READ_FILE":
            output = self._read_file(action.path)
        elif action.action_type == "SEARCH":
            output = self._search(action.pattern)
        elif action.action_type == "APPLY_PATCH":
            output = self._apply_patch(action.diff)
        elif action.action_type == "RUN":
            output = self._run_command(action.cmd_id)
        else:
            output = f"Unknown action type: {action.action_type}"
        
        # Get current metrics
        metrics = compute_all_metrics(str(self._work_dir))
        
        # Compute reward
        reward = self._compute_reward(metrics)
        
        # Check if done
        done = steps_remaining == 0
        
        return RefactorObservation(
            output=output,
            tests_pass=self._state.tests_pass,
            api_pass=self._state.api_pass,
            dup_score=metrics["dup_score"],
            complexity_score=metrics["complexity_score"],
            loc=int(metrics["loc"]),
            steps_remaining=steps_remaining,
            done=done,
            reward=reward,
        )
    
    def _list_files(self) -> str:
        """List all Python files in the working directory."""
        files = []
        for path in self._work_dir.rglob("*.py"):
            rel_path = path.relative_to(self._work_dir)
            if "__pycache__" not in str(rel_path):
                files.append(str(rel_path))
        return "\n".join(sorted(files))
    
    def _read_file(self, path: Optional[str]) -> str:
        """Read contents of a file."""
        if not path:
            return "Error: No path provided for READ_FILE action"
        
        file_path = self._work_dir / path
        
        if not file_path.exists():
            return f"Error: File not found: {path}"
        
        if not file_path.is_file():
            return f"Error: Not a file: {path}"
        
        # Security check: ensure path is within work dir
        try:
            file_path.resolve().relative_to(self._work_dir.resolve())
        except ValueError:
            return f"Error: Path escapes working directory: {path}"
        
        try:
            content = file_path.read_text()
            return f"=== {path} ===\n{content}"
        except Exception as e:
            return f"Error reading file: {e}"
    
    def _search(self, pattern: Optional[str]) -> str:
        """Search for a pattern in the codebase."""
        if not pattern:
            return "Error: No pattern provided for SEARCH action"
        
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"
        
        results = []
        for path in self._work_dir.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            
            try:
                content = path.read_text()
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        rel_path = path.relative_to(self._work_dir)
                        results.append(f"{rel_path}:{i}: {line.strip()}")
            except Exception:
                continue
        
        if not results:
            return f"No matches found for pattern: {pattern}"
        
        return f"Found {len(results)} matches:\n" + "\n".join(results[:50])  # Limit output
    
    def _apply_patch(self, diff: Optional[str]) -> str:
        """Apply a unified diff patch."""
        if not diff:
            return "Error: No diff provided for APPLY_PATCH action"
        
        # Write patch to temp file
        patch_file = self._work_dir / ".patch"
        try:
            patch_file.write_text(diff)
        except Exception as e:
            return f"Error writing patch file: {e}"
        
        # Try to apply with patch command
        try:
            result = subprocess.run(
                ["patch", "-p1", "--no-backup-if-mismatch"],
                input=diff,
                capture_output=True,
                text=True,
                cwd=str(self._work_dir),
                timeout=10,
            )
            
            patch_file.unlink(missing_ok=True)
            
            if result.returncode == 0:
                return f"Patch applied successfully.\n{result.stdout}"
            else:
                return f"Patch failed (exit code {result.returncode}):\n{result.stderr}\n{result.stdout}"
                
        except subprocess.TimeoutExpired:
            patch_file.unlink(missing_ok=True)
            return "Error: Patch command timed out"
        except FileNotFoundError:
            # patch command not available, try manual application
            patch_file.unlink(missing_ok=True)
            return self._apply_patch_manual(diff)
        except Exception as e:
            patch_file.unlink(missing_ok=True)
            return f"Error applying patch: {e}"
    
    def _apply_patch_manual(self, diff: str) -> str:
        """Manually apply a simple unified diff (fallback when patch not available)."""
        # This is a simplified fallback - full patch logic is complex
        # For now, we just indicate that the patch command is required
        _ = diff  # Acknowledge the parameter
        return "Error: Manual patch application not fully implemented. Please ensure 'patch' command is available."
    
    def _run_command(self, cmd_id: Optional[str]) -> str:
        """Run a predefined command."""
        if not cmd_id:
            return "Error: No cmd_id provided for RUN action"
        
        if cmd_id == "TEST":
            return self._run_tests()
        elif cmd_id == "API_CHECK":
            return self._run_api_check()
        elif cmd_id == "METRICS":
            return self._run_metrics()
        else:
            return f"Error: Unknown cmd_id: {cmd_id}. Must be TEST, API_CHECK, or METRICS"
    
    def _run_tests(self) -> str:
        """Run pytest on the target repo."""
        import sys
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-v", "tests/"],
                capture_output=True,
                text=True,
                cwd=str(self._work_dir),
                timeout=60,
                env={**os.environ, "PYTHONPATH": str(self._work_dir)},
            )
            
            self._state.tests_pass = (result.returncode == 0)
            
            output = f"Tests {'PASSED' if self._state.tests_pass else 'FAILED'} (exit code {result.returncode})\n\n"
            output += result.stdout
            if result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"
            
            return output
            
        except subprocess.TimeoutExpired:
            self._state.tests_pass = False
            return "Error: Tests timed out after 60 seconds"
        except Exception as e:
            self._state.tests_pass = False
            return f"Error running tests: {e}"
    
    def _run_api_check(self) -> str:
        """Run the API contract checker."""
        import sys
        try:
            result = subprocess.run(
                [sys.executable, "api_check.py"],
                capture_output=True,
                text=True,
                cwd=str(self._work_dir),
                timeout=30,
                env={**os.environ, "PYTHONPATH": str(self._work_dir)},
            )
            
            self._state.api_pass = (result.returncode == 0)
            
            output = f"API Check {'PASSED' if self._state.api_pass else 'FAILED'} (exit code {result.returncode})\n\n"
            output += result.stdout
            if result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"
            
            return output
            
        except subprocess.TimeoutExpired:
            self._state.api_pass = False
            return "Error: API check timed out after 30 seconds"
        except Exception as e:
            self._state.api_pass = False
            return f"Error running API check: {e}"
    
    def _run_metrics(self) -> str:
        """Compute and display current metrics."""
        metrics = compute_all_metrics(str(self._work_dir))
        
        # Compare to baseline
        dup_delta = metrics["dup_score"] - self._state.baseline_dup
        complexity_delta = metrics["complexity_score"] - self._state.baseline_complexity
        loc_delta = int(metrics["loc"]) - self._state.baseline_loc
        
        output = "=== Current Metrics ===\n"
        output += f"Duplication Score: {metrics['dup_score']:.4f} (baseline: {self._state.baseline_dup:.4f}, delta: {dup_delta:+.4f})\n"
        output += f"Complexity Score:  {metrics['complexity_score']:.1f} (baseline: {self._state.baseline_complexity:.1f}, delta: {complexity_delta:+.1f})\n"
        output += f"Lines of Code:     {int(metrics['loc'])} (baseline: {self._state.baseline_loc}, delta: {loc_delta:+d})\n"
        
        return output
    
    def _compute_reward(self, metrics: dict) -> float:
        """Compute reward based on current state and metrics."""
        # If tests or API failed, return negative reward
        if self._state.tests_pass is False or self._state.api_pass is False:
            return -1.0
        
        # If we haven't run tests/API yet, give small step penalty
        if self._state.tests_pass is None or self._state.api_pass is None:
            return -0.01  # Small step cost
        
        # Both passed - compute improvement reward
        baseline_dup = self._state.baseline_dup
        baseline_complexity = self._state.baseline_complexity
        baseline_loc = self._state.baseline_loc
        
        current_dup = metrics["dup_score"]
        current_complexity = metrics["complexity_score"]
        current_loc = int(metrics["loc"])
        
        # Compute normalized improvements (positive = good)
        dup_improvement = 0.0
        if baseline_dup > 0:
            dup_improvement = (baseline_dup - current_dup) / baseline_dup
        
        complexity_improvement = 0.0
        if baseline_complexity > 0:
            complexity_improvement = (baseline_complexity - current_complexity) / baseline_complexity
        
        loc_improvement = 0.0
        if baseline_loc > 0:
            loc_improvement = (baseline_loc - current_loc) / baseline_loc * 0.5  # Weight LOC less
        
        # Sum improvements minus step cost
        reward = dup_improvement + complexity_improvement + loc_improvement - 0.01
        
        return reward
    
    @property
    def state(self) -> RefactorState:
        """Get current environment state."""
        return self._state
    
    def close(self):
        """Clean up temporary directory."""
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

