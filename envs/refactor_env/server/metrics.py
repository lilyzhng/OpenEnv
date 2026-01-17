"""
Metrics computation for the Refactor Environment.

Computes:
- dup_score: Duplication score using token n-gram similarity
- complexity_score: Cyclomatic complexity using radon
- loc: Lines of code (non-blank, non-comment)
"""

import os
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from radon.complexity import cc_visit
    from radon.raw import analyze
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False


def get_python_files(directory: str) -> List[Path]:
    """Get all Python files in a directory, excluding tests and __pycache__."""
    directory = Path(directory)
    python_files = []
    
    for path in directory.rglob("*.py"):
        # Skip test files and cache directories
        path_str = str(path)
        if "__pycache__" in path_str:
            continue
        if "test_" in path.name or path.name.startswith("test"):
            continue
        if path.name == "api_check.py":
            continue
            
        python_files.append(path)
    
    return python_files


def tokenize(code: str) -> List[str]:
    """Tokenize Python code into meaningful tokens."""
    # Remove comments and docstrings (simplified)
    code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", '', code, flags=re.DOTALL)
    
    # Split into tokens (identifiers, operators, etc.)
    tokens = re.findall(r'\b\w+\b|[^\s\w]', code)
    return tokens


def get_ngrams(tokens: List[str], n: int = 5) -> List[Tuple[str, ...]]:
    """Extract n-grams from a list of tokens."""
    if len(tokens) < n:
        return []
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def compute_duplication_score(directory: str) -> float:
    """
    Compute duplication score using 5-gram similarity.
    
    Higher scores mean more duplication.
    Score is normalized to [0, 1] range.
    
    Returns:
        Float between 0 (no duplication) and 1 (everything duplicated)
    """
    python_files = get_python_files(directory)
    
    if not python_files:
        return 0.0
    
    # Collect all n-grams from all files
    all_ngrams: List[Tuple[str, ...]] = []
    
    for path in python_files:
        try:
            code = path.read_text()
            tokens = tokenize(code)
            ngrams = get_ngrams(tokens, n=5)
            all_ngrams.extend(ngrams)
        except Exception:
            continue
    
    if not all_ngrams:
        return 0.0
    
    # Count n-gram occurrences
    ngram_counts = Counter(all_ngrams)
    
    # Calculate duplication: ratio of duplicated n-grams
    total_ngrams = len(all_ngrams)
    duplicated_ngrams = sum(count - 1 for count in ngram_counts.values() if count > 1)
    
    if total_ngrams == 0:
        return 0.0
    
    # Normalize: duplicated / total gives proportion of redundant n-grams
    dup_score = duplicated_ngrams / total_ngrams
    
    return min(1.0, dup_score)


def compute_complexity_score(directory: str) -> float:
    """
    Compute cyclomatic complexity score using radon.
    
    Returns sum of complexity scores for all functions/methods.
    Lower is better.
    """
    if not RADON_AVAILABLE:
        # Fallback: simple heuristic based on control flow keywords
        return _compute_complexity_fallback(directory)
    
    python_files = get_python_files(directory)
    total_complexity = 0.0
    
    for path in python_files:
        try:
            code = path.read_text()
            blocks = cc_visit(code)
            for block in blocks:
                total_complexity += block.complexity
        except Exception:
            continue
    
    return total_complexity


def _compute_complexity_fallback(directory: str) -> float:
    """Fallback complexity computation when radon is not available."""
    python_files = get_python_files(directory)
    total_complexity = 0.0
    
    # Simple heuristic: count control flow statements
    control_keywords = ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'with', 'and', 'or']
    
    for path in python_files:
        try:
            code = path.read_text()
            for keyword in control_keywords:
                total_complexity += len(re.findall(rf'\b{keyword}\b', code))
        except Exception:
            continue
    
    return total_complexity


def compute_loc(directory: str) -> int:
    """
    Compute lines of code (non-blank, non-comment lines).
    
    Returns total LOC across all Python files.
    """
    python_files = get_python_files(directory)
    total_loc = 0
    
    for path in python_files:
        try:
            code = path.read_text()
            
            if RADON_AVAILABLE:
                # Use radon for accurate LOC
                raw = analyze(code)
                total_loc += raw.loc  # Logical lines of code
            else:
                # Simple fallback: count non-empty, non-comment lines
                lines = code.split('\n')
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        total_loc += 1
        except Exception:
            continue
    
    return total_loc


def compute_all_metrics(directory: str) -> Dict[str, float]:
    """
    Compute all metrics for a directory.
    
    Returns:
        Dictionary with keys: dup_score, complexity_score, loc
    """
    return {
        "dup_score": compute_duplication_score(directory),
        "complexity_score": compute_complexity_score(directory),
        "loc": compute_loc(directory),
    }


if __name__ == "__main__":
    # Test with target_repo
    import sys
    
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = os.path.join(os.path.dirname(__file__), "..", "target_repo")
    
    metrics = compute_all_metrics(target_dir)
    print(f"Metrics for {target_dir}:")
    print(f"  Duplication Score: {metrics['dup_score']:.4f}")
    print(f"  Complexity Score: {metrics['complexity_score']:.1f}")
    print(f"  Lines of Code: {metrics['loc']}")

