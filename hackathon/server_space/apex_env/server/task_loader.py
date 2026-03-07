"""Load APEX tasks from HuggingFace dataset with difficulty tiers."""
from __future__ import annotations

import json
import random
from typing import Any, Literal, Optional


DifficultyTier = Literal["easy", "hard"]

# Binary split: rubric_count <= threshold = easy, > threshold = hard
# Threshold = median rubric_count in APEX-v1-extended (empirically ~10)
_RUBRIC_THRESHOLD = 10


def compute_difficulty_score(task: dict[str, Any]) -> float:
    """Compute difficulty score = rubric criteria count.

    Rubric count is the purest proxy for task difficulty: more criteria =
    more things the agent must get right. File count was removed because
    files are resources (help the agent), not difficulty.
    """
    rubric_raw = task.get("Rubric JSON", task.get("rubric", "{}"))
    if isinstance(rubric_raw, str):
        try:
            rubric = json.loads(rubric_raw)
        except (json.JSONDecodeError, TypeError):
            rubric = {}
    else:
        rubric = rubric_raw

    if isinstance(rubric, dict):
        return float(len(rubric))
    elif isinstance(rubric, list):
        return float(len(rubric))
    return 0.0


def get_difficulty_tier(task: dict[str, Any]) -> DifficultyTier:
    """Classify a task into easy/hard based on rubric criteria count."""
    score = compute_difficulty_score(task)
    if score <= _RUBRIC_THRESHOLD:
        return "easy"
    else:
        return "hard"


class TaskLoader:
    """Loads tasks from mercor/APEX-v1-extended (100 trainable tasks with rubrics).

    Supports difficulty-based filtering for curriculum learning:
        loader.get_task(difficulty="easy")   # simple tasks (few rubric criteria)
        loader.get_task(difficulty="hard")   # complex tasks (many rubric criteria)
        loader.get_tasks_by_tier()           # get all tasks grouped by tier
    """

    def __init__(self, dataset_name: str = "mercor/APEX-v1-extended"):
        self._tasks: list[dict[str, Any]] | None = None
        self._dataset_name = dataset_name
        self._tier_cache: dict[DifficultyTier, list[dict[str, Any]]] | None = None

    def _load(self) -> None:
        if self._tasks is not None:
            return
        from datasets import load_dataset

        ds = load_dataset(self._dataset_name, split="train")
        self._tasks = list(ds)
        self._tier_cache = None

    def _build_tier_cache(self) -> dict[DifficultyTier, list[dict[str, Any]]]:
        if self._tier_cache is not None:
            return self._tier_cache
        self._load()
        assert self._tasks is not None

        cache: dict[DifficultyTier, list[dict[str, Any]]] = {
            "easy": [], "hard": [],
        }
        for t in self._tasks:
            tier = get_difficulty_tier(t)
            cache[tier].append(t)

        self._tier_cache = cache
        return cache

    def get_task(
        self,
        seed: int | None = None,
        task_id: str | None = None,
        difficulty: DifficultyTier | None = None,
    ) -> dict[str, Any]:
        self._load()
        assert self._tasks is not None

        if task_id is not None:
            for t in self._tasks:
                if str(t.get("task_id", t.get("Task ID", ""))) == str(task_id):
                    return t
            raise ValueError(f"Task {task_id} not found in dataset")

        pool = self._tasks
        if difficulty is not None:
            tier_cache = self._build_tier_cache()
            pool = tier_cache[difficulty]
            if not pool:
                raise ValueError(f"No tasks found for difficulty={difficulty}")

        if seed is not None:
            return pool[seed % len(pool)]

        return random.choice(pool)

    def get_tasks_by_tier(self) -> dict[DifficultyTier, list[dict[str, Any]]]:
        """Return all tasks grouped by difficulty tier."""
        return self._build_tier_cache()

    def __len__(self) -> int:
        self._load()
        assert self._tasks is not None
        return len(self._tasks)
