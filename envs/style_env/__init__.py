"""
Style Consistency Environment.

An RL environment for training models to generate frontend code that adheres
to product-specific design systems and avoids "AI slop" aesthetics.
"""

from .client import StyleEnv
from .models import StyleAction, StyleObservation, StyleState, ScoreBreakdown, RuleViolation

__all__ = [
    "StyleEnv",
    "StyleAction",
    "StyleObservation",
    "StyleState",
    "ScoreBreakdown",
    "RuleViolation",
]

