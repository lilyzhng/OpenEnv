"""
Diff Discipline Scorer for the Style Consistency Environment.

This scorer checks that:
- R8: Only allowed files/directories are modified

For example, if a task only allows modifications to src/pages/**,
any changes to src/components/ or src/theme/ would be violations.
"""

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set


@dataclass
class DiffViolation:
    """A single diff discipline violation."""

    rule: str
    file: str
    line: int  # Always 0 for diff violations
    snippet: str
    penalty: int


@dataclass
class DiffDisciplineScorerResult:
    """Result from diff discipline scoring."""

    violations: List[DiffViolation] = field(default_factory=list)
    total_penalty: int = 0
    modified_files: List[str] = field(default_factory=list)


class DiffDisciplineScorer:
    """
    Scorer that checks for unauthorized file modifications.

    Rule R8: Only modify allowed files/directories - penalty: -20 per violation

    This scorer compares modified files against the allowed_modifications
    patterns specified in the task.
    """

    # Penalty for R8 violations
    PENALTY = -20

    def __init__(
        self,
        work_dir: Path,
        allowed_patterns: List[str] = None,
        max_new_files: int = 5,
    ):
        """
        Initialize the diff discipline scorer.

        Args:
            work_dir: Path to the frontend template directory
            allowed_patterns: Glob patterns for allowed modifications
                              e.g., ["src/pages/**", "src/components/ui/**"]
            max_new_files: Maximum number of new files allowed
        """
        self.work_dir = work_dir
        self.allowed_patterns = allowed_patterns or ["src/pages/**"]
        self.max_new_files = max_new_files

    def _match_pattern(self, file_path: str, patterns: List[str]) -> bool:
        """Check if file path matches any of the allowed patterns."""
        for pattern in patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def score(self, modified_files: List[str]) -> DiffDisciplineScorerResult:
        """
        Check if modified files are within allowed patterns.

        Args:
            modified_files: List of file paths that were modified

        Returns:
            DiffDisciplineScorerResult with violations
        """
        violations = []

        for file_path in modified_files:
            # Normalize path
            normalized = file_path.replace("\\", "/")

            # Check if modification is allowed
            if not self._match_pattern(normalized, self.allowed_patterns):
                violations.append(
                    DiffViolation(
                        rule="R8",
                        file=file_path,
                        line=0,
                        snippet=f"Unauthorized modification: {file_path}",
                        penalty=self.PENALTY,
                    )
                )

        total_penalty = sum(v.penalty for v in violations)

        return DiffDisciplineScorerResult(
            violations=violations,
            total_penalty=total_penalty,
            modified_files=modified_files,
        )

    def get_modified_files(self, baseline_files: Set[str]) -> List[str]:
        """
        Get list of files that were modified since baseline.

        This compares current state against a baseline snapshot.

        Args:
            baseline_files: Set of file paths and their hashes from baseline

        Returns:
            List of modified/added file paths
        """
        modified = []
        src_dir = self.work_dir / "src"

        if not src_dir.exists():
            return modified

        current_files = set()
        for file_path in src_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                rel_path = str(file_path.relative_to(self.work_dir))
                current_files.add(rel_path)

        # Files that are new or modified
        for file_path in current_files:
            if file_path not in baseline_files:
                modified.append(file_path)

        return modified

    def snapshot_files(self) -> Set[str]:
        """
        Take a snapshot of current file paths.

        Returns:
            Set of file paths relative to work_dir
        """
        files = set()
        src_dir = self.work_dir / "src"

        if not src_dir.exists():
            return files

        for file_path in src_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                rel_path = str(file_path.relative_to(self.work_dir))
                files.add(rel_path)

        return files

