"""
Component Reuse Scorer for the Style Consistency Environment.

This scorer checks that:
- R5: Models must use UI components from src/components/ui/ instead of raw HTML elements

For example, using <button> instead of <Button> from the component library is a violation.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set


@dataclass
class ComponentViolation:
    """A single component reuse violation."""

    rule: str
    file: str
    line: int
    snippet: str
    penalty: int


@dataclass
class ComponentReuseScorerResult:
    """Result from component reuse scoring."""

    violations: List[ComponentViolation] = field(default_factory=list)
    total_penalty: int = 0


class ComponentReuseScorer:
    """
    Scorer that checks for proper component library usage.

    Rule R5: Must use UI components from src/components/ui/ - penalty: -15

    Checks for:
    - Raw <button> elements instead of <Button>
    - Raw <input> elements instead of <Input>
    - Raw <table> elements instead of <Table>
    - etc.
    """

    # Penalty for R5 violations
    PENALTY = -15

    # Map of raw HTML elements to their expected component names
    ELEMENT_TO_COMPONENT = {
        "button": "Button",
        "input": "Input",
        # Note: We don't enforce Card/Badge/Table as strictly since
        # they don't have direct HTML equivalents that are commonly misused
    }

    def __init__(
        self,
        work_dir: Path,
        required_components: Set[str] = None,
        excluded_files: Set[str] = None,
    ):
        """
        Initialize the component reuse scorer.

        Args:
            work_dir: Path to the frontend template directory
            required_components: Set of component names that must be used
            excluded_files: Files to exclude from checking (e.g., the components themselves)
        """
        self.work_dir = work_dir
        self.required_components = required_components or {"Button", "Input"}
        self.excluded_files = excluded_files or set()

        # Build regex patterns for detecting raw HTML elements
        self.raw_element_patterns = {}
        for element, component in self.ELEMENT_TO_COMPONENT.items():
            if component in self.required_components:
                # Match <button, <button>, <input type=, etc.
                # Case-sensitive: only match lowercase (raw HTML), not <Button> (React component)
                self.raw_element_patterns[element] = re.compile(
                    rf"<{element}(?:\s|>|/)",
                )

    def _get_page_files(self) -> List[Path]:
        """Get all TSX/JSX files in src/pages/ directory."""
        pages_dir = self.work_dir / "src" / "pages"
        if not pages_dir.exists():
            return []

        files = []
        for pattern in ["**/*.tsx", "**/*.jsx"]:
            files.extend(pages_dir.glob(pattern))
        return files

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        rel_path = str(file_path.relative_to(self.work_dir))

        # Skip excluded files
        if rel_path in self.excluded_files:
            return True

        # Skip component library files
        if "components/ui" in rel_path:
            return True

        # Skip gitkeep files
        if file_path.name == ".gitkeep":
            return True

        return False

    def _scan_file(self, file_path: Path) -> List[ComponentViolation]:
        """Scan a single file for violations."""
        violations = []
        rel_path = str(file_path.relative_to(self.work_dir))

        try:
            content = file_path.read_text()
            lines = content.split("\n")
        except Exception:
            return violations

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # Check for each raw element
            for element, pattern in self.raw_element_patterns.items():
                matches = pattern.finditer(line)
                for match in matches:
                    # Get context around the match
                    start = max(0, match.start() - 10)
                    end = min(len(line), match.end() + 30)
                    snippet = line[start:end].strip()

                    violations.append(
                        ComponentViolation(
                            rule="R5",
                            file=rel_path,
                            line=line_num,
                            snippet=snippet[:60],
                            penalty=self.PENALTY,
                        )
                    )

        return violations

    def _check_imports(self, file_path: Path) -> List[ComponentViolation]:
        """
        Check if required components are imported.

        This is a softer check - we just flag if Button/Input etc.
        are not imported but the file has interactive elements.
        """
        # For now, we only check for raw element usage
        # Import checking could be added as a future enhancement
        return []

    def score(self) -> ComponentReuseScorerResult:
        """
        Scan all page files for component reuse violations.

        Returns:
            ComponentReuseScorerResult with all violations and total penalty
        """
        all_violations = []

        for file_path in self._get_page_files():
            if self._should_skip_file(file_path):
                continue

            violations = self._scan_file(file_path)
            all_violations.extend(violations)

        total_penalty = sum(v.penalty for v in all_violations)

        return ComponentReuseScorerResult(
            violations=all_violations,
            total_penalty=total_penalty,
        )

