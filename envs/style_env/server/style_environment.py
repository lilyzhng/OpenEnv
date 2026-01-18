"""
Style Consistency Environment Implementation.

An RL environment for training models to generate frontend code that adheres
to product-specific design systems and avoids "AI slop" aesthetics.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import uuid4

# Support both in-repo and standalone imports
try:
    from openenv.core.env_server.interfaces import Environment
    from ..models import (
        StyleAction,
        StyleObservation,
        StyleState,
        ScoreBreakdown,
        RuleViolation,
    )
except ImportError:
    from openenv.core.env_server.interfaces import Environment
    from models import (
        StyleAction,
        StyleObservation,
        StyleState,
        ScoreBreakdown,
        RuleViolation,
    )

from .scorers import (
    LintScorer,
    TokenScorer,
    ComponentReuseScorer,
    DiffDisciplineScorer,
)


# Default episode length
MAX_STEPS = 30

# Path to bundled frontend template
FRONTEND_TEMPLATE_PATH = Path(__file__).parent.parent / "frontend_template"

# Path to prompts
PROMPTS_PATH = Path(__file__).parent.parent / "prompts" / "prompts.jsonl"


class StyleEnvironment(Environment):
    """
    Style Consistency Environment for frontend code evaluation.

    The agent can:
    - READ_FILE: Read the contents of a file
    - CREATE_FILE: Create a new file with content
    - APPLY_PATCH: Apply a unified diff patch
    - RUN: Run BUILD, LINT, or SCORE commands
    - GET_PROFILE: Get current product profile rules

    Reward is based on:
    - Hard gates: build, lint, format must pass (otherwise reward = -1.0)
    - Style score: 0-100 based on rule violations

    Example:
        >>> env = StyleEnvironment()
        >>> obs = env.reset()
        >>> print(obs.current_profile, obs.task_description)
        >>>
        >>> action = StyleAction(action_type="GET_PROFILE")
        >>> obs = env.step(action)
        >>> print(obs.output)  # Profile rules
        >>>
        >>> action = StyleAction(
        ...     action_type="CREATE_FILE",
        ...     path="src/pages/Settings.tsx",
        ...     content="export default function Settings() { ... }"
        ... )
        >>> obs = env.step(action)
        >>>
        >>> action = StyleAction(action_type="RUN", cmd_id="SCORE")
        >>> obs = env.step(action)
        >>> print(obs.score_breakdown.total_score)
    """

    def __init__(self, max_steps: int = MAX_STEPS):
        """Initialize the style environment."""
        self.max_steps = max_steps
        self._state = StyleState(episode_id=str(uuid4()), step_count=0)
        self._work_dir: Optional[Path] = None
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self._baseline_files: Set[str] = set()
        self._current_task: Optional[Dict] = None
        self._tasks: List[Dict] = []
        self._task_index = 0
        self._modified_files: List[str] = []

        # Load tasks
        self._load_tasks()

    def _load_tasks(self):
        """Load evaluation tasks from prompts.jsonl."""
        if PROMPTS_PATH.exists():
            try:
                with open(PROMPTS_PATH, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self._tasks.append(json.loads(line))
            except Exception as e:
                print(f"Warning: Could not load prompts: {e}")

        # If no tasks loaded, create a default task
        if not self._tasks:
            self._tasks = [
                {
                    "id": "default-001",
                    "profile": "enterprise",
                    "task": "Create a simple Settings page with a form and save button.",
                    "constraints": [
                        "Must use Button and Input components from src/components/ui/",
                        "No gradients or purple colors",
                    ],
                    "target_files": ["src/pages/Settings.tsx"],
                    "allowed_modifications": ["src/pages/**"],
                    "max_new_files": 2,
                    "difficulty": "easy",
                }
            ]

    def _get_profile_config(self, profile_name: str) -> Dict:
        """Get profile configuration for scoring."""
        profiles = {
            "enterprise": {
                "forbidden_colors": {
                    "purple-400", "purple-500", "purple-600",
                    "fuchsia-400", "fuchsia-500", "fuchsia-600",
                    "pink-400", "pink-500", "pink-600",
                    "rose-400", "rose-500", "rose-600",
                    "violet-400", "violet-500", "violet-600",
                    "cyan-400", "cyan-500",
                    "lime-400", "lime-500",
                },
                "check_gradients": True,
                "required_components": {"Button", "Input"},
            },
            "consumer": {
                "forbidden_colors": {
                    "fuchsia-400", "fuchsia-500", "fuchsia-600",
                    "pink-400", "pink-500", "pink-600",
                    "rose-400", "rose-500", "rose-600",
                    "lime-400", "lime-500",
                    "yellow-400", "yellow-500",
                },
                "check_gradients": True,
                "required_components": {"Button", "Input"},
            },
        }
        return profiles.get(profile_name, profiles["enterprise"])

    def reset(self) -> StyleObservation:
        """
        Reset the environment to initial state.

        Creates a fresh copy of the frontend template and selects a task.

        Returns:
            Initial observation with task description and profile
        """
        # Clean up previous temp directory
        if self._temp_dir is not None:
            self._temp_dir.cleanup()

        # Create new temp directory with fresh copy of template
        # Ignore node_modules to speed up copy - we'll symlink it
        self._temp_dir = tempfile.TemporaryDirectory(prefix="style_env_")
        self._work_dir = Path(self._temp_dir.name) / "frontend"
        shutil.copytree(
            FRONTEND_TEMPLATE_PATH,
            self._work_dir,
            ignore=shutil.ignore_patterns("node_modules", "dist", ".git"),
        )

        # Symlink node_modules from the template to avoid reinstalling
        template_node_modules = FRONTEND_TEMPLATE_PATH / "node_modules"
        work_node_modules = self._work_dir / "node_modules"
        if template_node_modules.exists() and not work_node_modules.exists():
            work_node_modules.symlink_to(template_node_modules)

        # Select next task (round-robin)
        self._current_task = self._tasks[self._task_index % len(self._tasks)]
        self._task_index += 1

        # Initialize state
        self._state = StyleState(
            episode_id=str(uuid4()),
            step_count=0,
            current_profile=self._current_task.get("profile", "enterprise"),
            task_id=self._current_task.get("id", "unknown"),
            build_passed=None,
            lint_passed=None,
            format_passed=None,
            last_score=None,
        )

        # Take baseline snapshot for diff discipline
        diff_scorer = DiffDisciplineScorer(self._work_dir)
        self._baseline_files = diff_scorer.snapshot_files()
        self._modified_files = []

        # Build initial output
        output_lines = [
            "Style Environment Reset",
            "=" * 40,
            f"Task ID: {self._current_task.get('id')}",
            f"Profile: {self._current_task.get('profile')}",
            "",
            "## Task Description",
            self._current_task.get("task", "No task description"),
            "",
            "## Constraints",
        ]
        for constraint in self._current_task.get("constraints", []):
            output_lines.append(f"- {constraint}")

        output_lines.extend([
            "",
            "## Target Files",
            ", ".join(self._current_task.get("target_files", [])),
            "",
            "## Available Actions",
            "- READ_FILE: Read a file's contents",
            "- CREATE_FILE: Create a new file",
            "- APPLY_PATCH: Apply a unified diff",
            "- RUN BUILD/LINT/SCORE: Run evaluation commands",
            "- GET_PROFILE: Get detailed profile rules",
        ])

        return StyleObservation(
            output="\n".join(output_lines),
            current_profile=self._state.current_profile,
            task_description=self._current_task.get("task", ""),
            build_passed=None,
            lint_passed=None,
            format_passed=None,
            score_breakdown=None,
            steps_remaining=self.max_steps,
            done=False,
            reward=0.0,
        )

    def step(self, action: StyleAction) -> StyleObservation:
        """
        Execute an action in the environment.

        Args:
            action: StyleAction to execute

        Returns:
            StyleObservation with action result
        """
        if not isinstance(action, StyleAction):
            raise ValueError(f"Expected StyleAction, got {type(action)}")

        self._state.step_count += 1
        steps_remaining = max(0, self.max_steps - self._state.step_count)

        # Execute the action
        if action.action_type == "READ_FILE":
            output = self._read_file(action.path)
        elif action.action_type == "CREATE_FILE":
            output = self._create_file(action.path, action.content)
        elif action.action_type == "APPLY_PATCH":
            output = self._apply_patch(action.diff)
        elif action.action_type == "RUN":
            output = self._run_command(action.cmd_id)
        elif action.action_type == "GET_PROFILE":
            output = self._get_profile()
        else:
            output = f"Unknown action type: {action.action_type}"

        # Compute reward
        reward = self._compute_reward()

        # Check if done
        done = steps_remaining == 0

        return StyleObservation(
            output=output,
            current_profile=self._state.current_profile,
            task_description=self._current_task.get("task", "") if self._current_task else "",
            build_passed=self._state.build_passed,
            lint_passed=self._state.lint_passed,
            format_passed=self._state.format_passed,
            score_breakdown=self._get_last_score_breakdown(),
            steps_remaining=steps_remaining,
            done=done,
            reward=reward,
        )

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

    def _create_file(self, path: Optional[str], content: Optional[str]) -> str:
        """Create a new file with content."""
        if not path:
            return "Error: No path provided for CREATE_FILE action"
        if content is None:
            return "Error: No content provided for CREATE_FILE action"

        file_path = self._work_dir / path

        # Security check
        try:
            file_path.resolve().relative_to(self._work_dir.resolve())
        except ValueError:
            return f"Error: Path escapes working directory: {path}"

        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

            # Track modification
            if path not in self._modified_files:
                self._modified_files.append(path)

            # Auto-format the file to avoid format failures
            # This allows agents to focus on style rules, not whitespace
            self._auto_format_file(path)

            return f"Created file: {path} ({len(content)} bytes)"
        except Exception as e:
            return f"Error creating file: {e}"

    def _auto_format_file(self, path: str) -> None:
        """Auto-format a file using prettier."""
        try:
            subprocess.run(
                ["pnpm", "exec", "prettier", "--write", path],
                capture_output=True,
                text=True,
                cwd=str(self._work_dir),
                timeout=30,
            )
        except Exception:
            # Silently ignore format errors - they'll be caught by the scorer
            pass

    def _apply_patch(self, diff: Optional[str]) -> str:
        """Apply a unified diff patch."""
        if not diff:
            return "Error: No diff provided for APPLY_PATCH action"

        try:
            result = subprocess.run(
                ["patch", "-p1", "--no-backup-if-mismatch"],
                input=diff,
                capture_output=True,
                text=True,
                cwd=str(self._work_dir),
                timeout=10,
            )

            if result.returncode == 0:
                # Track modified files from patch
                for line in diff.split("\n"):
                    if line.startswith("+++"):
                        # Extract file path from +++ b/path/to/file
                        parts = line.split()
                        if len(parts) >= 2:
                            file_path = parts[1]
                            if file_path.startswith("b/"):
                                file_path = file_path[2:]
                            if file_path not in self._modified_files:
                                self._modified_files.append(file_path)

                return f"Patch applied successfully.\n{result.stdout}"
            else:
                return f"Patch failed (exit code {result.returncode}):\n{result.stderr}\n{result.stdout}"

        except subprocess.TimeoutExpired:
            return "Error: Patch command timed out"
        except FileNotFoundError:
            return "Error: 'patch' command not found. Ensure it is installed."
        except Exception as e:
            return f"Error applying patch: {e}"

    def _run_command(self, cmd_id: Optional[str]) -> str:
        """Run a predefined command."""
        if not cmd_id:
            return "Error: No cmd_id provided for RUN action"

        if cmd_id == "BUILD":
            return self._run_build()
        elif cmd_id == "LINT":
            return self._run_lint()
        elif cmd_id == "SCORE":
            return self._run_score()
        else:
            return f"Error: Unknown cmd_id: {cmd_id}. Must be BUILD, LINT, or SCORE"

    def _run_build(self) -> str:
        """Run pnpm build."""
        lint_scorer = LintScorer(self._work_dir)
        passed, output = lint_scorer.run_build()
        self._state.build_passed = passed
        return f"Build {'PASSED' if passed else 'FAILED'}\n\n{output}"

    def _run_lint(self) -> str:
        """Run pnpm lint."""
        lint_scorer = LintScorer(self._work_dir)
        passed, output = lint_scorer.run_lint()
        self._state.lint_passed = passed
        return f"Lint {'PASSED' if passed else 'FAILED'}\n\n{output}"

    def _run_score(self) -> str:
        """Run full scoring."""
        profile_config = self._get_profile_config(self._state.current_profile)

        # Run lint scorer
        lint_scorer = LintScorer(self._work_dir)
        lint_result = lint_scorer.score()

        self._state.build_passed = lint_result.build_passed
        self._state.lint_passed = lint_result.lint_passed
        self._state.format_passed = lint_result.format_passed

        # If hard gates fail, score is 0
        if not lint_result.all_passed:
            score_breakdown = ScoreBreakdown(
                total_score=0,
                max_score=100,
                hard_gates={
                    "build": lint_result.build_passed,
                    "lint": lint_result.lint_passed,
                    "format": lint_result.format_passed,
                },
                rule_violations=[],
                penalties_total=0,
            )
            self._state.last_score = 0
            self._last_score_breakdown = score_breakdown

            return self._format_score_output(score_breakdown, lint_result)

        # Run style scorers
        all_violations = []

        # Token scorer (R1-R4)
        token_scorer = TokenScorer(
            self._work_dir,
            forbidden_colors=profile_config["forbidden_colors"],
            check_gradients=profile_config["check_gradients"],
        )
        token_result = token_scorer.score()
        for v in token_result.violations:
            all_violations.append(RuleViolation(
                rule=v.rule,
                file=v.file,
                line=v.line,
                snippet=v.snippet,
                penalty=v.penalty,
            ))

        # Component reuse scorer (R5)
        component_scorer = ComponentReuseScorer(
            self._work_dir,
            required_components=profile_config["required_components"],
        )
        component_result = component_scorer.score()
        for v in component_result.violations:
            all_violations.append(RuleViolation(
                rule=v.rule,
                file=v.file,
                line=v.line,
                snippet=v.snippet,
                penalty=v.penalty,
            ))

        # Diff discipline scorer (R8)
        diff_scorer = DiffDisciplineScorer(
            self._work_dir,
            allowed_patterns=self._current_task.get("allowed_modifications", ["src/pages/**"]),
            max_new_files=self._current_task.get("max_new_files", 5),
        )
        diff_result = diff_scorer.score(self._modified_files)
        for v in diff_result.violations:
            all_violations.append(RuleViolation(
                rule=v.rule,
                file=v.file,
                line=v.line,
                snippet=v.snippet,
                penalty=v.penalty,
            ))

        # Calculate total score
        total_penalty = sum(v.penalty for v in all_violations)
        total_score = max(0, 100 + total_penalty)

        score_breakdown = ScoreBreakdown(
            total_score=total_score,
            max_score=100,
            hard_gates={
                "build": True,
                "lint": True,
                "format": True,
            },
            rule_violations=all_violations,
            penalties_total=total_penalty,
        )

        self._state.last_score = total_score
        self._last_score_breakdown = score_breakdown

        return self._format_score_output(score_breakdown, lint_result)

    def _format_score_output(self, breakdown: ScoreBreakdown, lint_result) -> str:
        """Format score breakdown as readable output."""
        lines = [
            "=" * 50,
            "STYLE SCORE REPORT",
            "=" * 50,
            "",
            f"Total Score: {breakdown.total_score} / {breakdown.max_score}",
            "",
            "## Hard Gates",
            f"  Build:  {'✓ PASS' if breakdown.hard_gates.get('build') else '✗ FAIL'}",
            f"  Lint:   {'✓ PASS' if breakdown.hard_gates.get('lint') else '✗ FAIL'}",
            f"  Format: {'✓ PASS' if breakdown.hard_gates.get('format') else '✗ FAIL'}",
            "",
        ]

        if not all(breakdown.hard_gates.values()):
            lines.append("## Hard Gate Failures (Score = 0)")
            if not breakdown.hard_gates.get("build"):
                lines.append(f"\nBuild Output:\n{lint_result.build_output[:500]}")
            if not breakdown.hard_gates.get("lint"):
                lines.append(f"\nLint Output:\n{lint_result.lint_output[:500]}")
            if not breakdown.hard_gates.get("format"):
                lines.append(f"\nFormat Output:\n{lint_result.format_output[:500]}")
        else:
            lines.append(f"## Rule Violations ({len(breakdown.rule_violations)} found)")
            lines.append(f"Total Penalty: {breakdown.penalties_total}")
            lines.append("")

            if breakdown.rule_violations:
                for v in breakdown.rule_violations[:20]:  # Limit output
                    lines.append(f"  [{v.rule}] {v.file}:{v.line}")
                    lines.append(f"         {v.snippet}")
                    lines.append(f"         Penalty: {v.penalty}")
                    lines.append("")

                if len(breakdown.rule_violations) > 20:
                    lines.append(f"  ... and {len(breakdown.rule_violations) - 20} more violations")
            else:
                lines.append("  No violations found! 🎉")

        return "\n".join(lines)

    def _get_profile(self) -> str:
        """Get current product profile rules."""
        profile_name = self._state.current_profile
        config = self._get_profile_config(profile_name)

        lines = [
            f"# Profile: {profile_name}",
            "",
            "## Forbidden Patterns",
            f"- Check gradients: {config['check_gradients']}",
            f"- Forbidden colors: {', '.join(sorted(config['forbidden_colors']))}",
            "",
            "## Required Components",
            f"Must use from src/components/ui/: {', '.join(config['required_components'])}",
            "",
            "## General Rules",
            "- R1: No raw color values (#xxx, rgb(), hsl()) - Penalty: -10",
            "- R2: No gradient classes (bg-gradient-to-*, from-*, to-*, via-*) - Penalty: -8",
            "- R3: No forbidden neon colors - Penalty: -5",
            "- R4: No inline styles (style={{...}}) - Penalty: -10",
            "- R5: Must use UI component library, no raw <button>/<input> - Penalty: -15",
            "- R8: Only modify allowed files - Penalty: -20",
            "",
            "## Allowed Modifications for This Task",
            ", ".join(self._current_task.get("allowed_modifications", ["src/pages/**"])),
        ]

        return "\n".join(lines)

    def _get_last_score_breakdown(self) -> Optional[ScoreBreakdown]:
        """Get the last score breakdown if available."""
        return getattr(self, "_last_score_breakdown", None)

    def _compute_reward(self) -> float:
        """Compute reward based on current state."""
        # If hard gates failed, return -1.0
        if self._state.build_passed is False or self._state.lint_passed is False:
            return -1.0

        # If we have a score, use it
        if self._state.last_score is not None:
            # Normalize to [-0.5, 1.0] range
            # 100 → 1.0, 50 → 0.25, 0 → -0.5
            normalized = (self._state.last_score / 100) * 1.5 - 0.5
            return normalized - 0.01  # Small step cost

        # Default small step cost
        return -0.01

    @property
    def state(self) -> StyleState:
        """Get current environment state."""
        return self._state

    def close(self):
        """Clean up temporary directory."""
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

