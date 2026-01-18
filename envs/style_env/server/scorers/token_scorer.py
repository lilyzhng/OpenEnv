"""
Token Scorer for the Style Consistency Environment.

This scorer scans for forbidden patterns:
- R1: Raw color values (#xxx, rgb(), hsl())
- R2: Gradient classes (bg-gradient-to-*, from-*, to-*, via-*)
- R3: Forbidden neon colors from profile blacklist
- R4: Inline styles (style={{...}})
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set


@dataclass
class TokenViolation:
    """A single token violation."""

    rule: str
    file: str
    line: int
    snippet: str
    penalty: int


@dataclass
class TokenScorerResult:
    """Result from token scoring."""

    violations: List[TokenViolation] = field(default_factory=list)
    total_penalty: int = 0


class TokenScorer:
    """
    Scorer that checks for forbidden color/style patterns.

    Rules:
    - R1: No raw color values (#xxx, rgb(), hsl()) - penalty: -10
    - R2: No gradient classes - penalty: -8
    - R3: No forbidden neon colors - penalty: -5
    - R4: No inline styles - penalty: -10
    """

    # Penalties for each rule
    PENALTIES = {
        "R1": -10,  # Raw color values
        "R2": -8,   # Gradient classes
        "R3": -5,   # Forbidden neon colors
        "R4": -10,  # Inline styles
    }

    # Regex patterns
    RAW_COLOR_PATTERN = re.compile(
        r"""
        (?:
            \#[0-9a-fA-F]{3,8}           |  # Hex colors
            rgb\s*\([^)]+\)              |  # rgb()
            rgba\s*\([^)]+\)             |  # rgba()
            hsl\s*\([^)]+\)              |  # hsl()
            hsla\s*\([^)]+\)                # hsla()
        )
        """,
        re.VERBOSE,
    )

    GRADIENT_PATTERN = re.compile(
        r"""
        (?:
            bg-gradient-to-[trbl]{1,2}  |  # bg-gradient-to-r, bg-gradient-to-br, etc.
            from-[a-z]+-\d{2,3}         |  # from-blue-500
            to-[a-z]+-\d{2,3}           |  # to-purple-600
            via-[a-z]+-\d{2,3}             # via-pink-500
        )
        """,
        re.VERBOSE,
    )

    INLINE_STYLE_PATTERN = re.compile(
        r"""
        style\s*=\s*\{\s*\{[^}]*\}\s*\}  |  # style={{...}}
        style\s*=\s*\{[^}]+\}               # style={...}
        """,
        re.VERBOSE,
    )

    def __init__(
        self,
        work_dir: Path,
        forbidden_colors: Set[str] = None,
        check_gradients: bool = True,
    ):
        """
        Initialize the token scorer.

        Args:
            work_dir: Path to the frontend template directory
            forbidden_colors: Set of forbidden Tailwind color classes
            check_gradients: Whether to check for gradient classes
        """
        self.work_dir = work_dir
        self.forbidden_colors = forbidden_colors or set()
        self.check_gradients = check_gradients

        # Build regex for forbidden colors
        if self.forbidden_colors:
            # Match color classes like "bg-purple-500", "text-fuchsia-400", etc.
            color_pattern = "|".join(
                re.escape(c) for c in self.forbidden_colors
            )
            self.forbidden_color_pattern = re.compile(
                rf"(?:bg|text|border|ring|fill|stroke)-(?:{color_pattern})"
            )
        else:
            self.forbidden_color_pattern = None

    def _get_tsx_files(self) -> List[Path]:
        """Get all TSX/JSX files in src/ directory."""
        src_dir = self.work_dir / "src"
        if not src_dir.exists():
            return []

        files = []
        for pattern in ["**/*.tsx", "**/*.jsx"]:
            files.extend(src_dir.glob(pattern))
        return files

    def _scan_file(self, file_path: Path) -> List[TokenViolation]:
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

            # R1: Raw color values
            for match in self.RAW_COLOR_PATTERN.finditer(line):
                violations.append(
                    TokenViolation(
                        rule="R1",
                        file=rel_path,
                        line=line_num,
                        snippet=match.group()[:50],
                        penalty=self.PENALTIES["R1"],
                    )
                )

            # R2: Gradient classes
            if self.check_gradients:
                for match in self.GRADIENT_PATTERN.finditer(line):
                    violations.append(
                        TokenViolation(
                            rule="R2",
                            file=rel_path,
                            line=line_num,
                            snippet=match.group()[:50],
                            penalty=self.PENALTIES["R2"],
                        )
                    )

            # R3: Forbidden neon colors
            if self.forbidden_color_pattern:
                for match in self.forbidden_color_pattern.finditer(line):
                    violations.append(
                        TokenViolation(
                            rule="R3",
                            file=rel_path,
                            line=line_num,
                            snippet=match.group()[:50],
                            penalty=self.PENALTIES["R3"],
                        )
                    )

            # R4: Inline styles
            for match in self.INLINE_STYLE_PATTERN.finditer(line):
                violations.append(
                    TokenViolation(
                        rule="R4",
                        file=rel_path,
                        line=line_num,
                        snippet=match.group()[:50],
                        penalty=self.PENALTIES["R4"],
                    )
                )

        return violations

    def score(self) -> TokenScorerResult:
        """
        Scan all TSX/JSX files for token violations.

        Returns:
            TokenScorerResult with all violations and total penalty
        """
        all_violations = []

        for file_path in self._get_tsx_files():
            violations = self._scan_file(file_path)
            all_violations.extend(violations)

        total_penalty = sum(v.penalty for v in all_violations)

        return TokenScorerResult(
            violations=all_violations,
            total_penalty=total_penalty,
        )

