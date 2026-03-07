"""Load APEX tasks from HuggingFace dataset with difficulty tiers."""

import json
import random
from typing import Any, Literal


DifficultyTier = Literal["easy", "medium", "hard"]

# Thresholds derived from APEX-v1-extended analysis (see s2_findings_apex_analysis.md)
# Score = rubric_count * 2 + file_count * 1.5 + (2 if has_files else 0)
_EASY_THRESHOLD = 23.0
_HARD_THRESHOLD = 29.5


def compute_difficulty_score(task: dict[str, Any]) -> float:
    """Compute difficulty score from rubric criteria count and file attachments.

    Based on 2D curriculum analysis: rubric complexity (reasoning depth)
    and file count (information gathering complexity) are independent dimensions.
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
        rubric_count = len(rubric)
    elif isinstance(rubric, list):
        rubric_count = len(rubric)
    else:
        rubric_count = 0

    files_raw = task.get("File Attachments", task.get("file_attachments", ""))
    if isinstance(files_raw, str):
        file_list = [f for f in files_raw.strip().split("\n") if f.strip()]
    elif isinstance(files_raw, list):
        file_list = files_raw
    else:
        file_list = []
    file_count = len(file_list)
    has_files = file_count > 0

    return rubric_count * 2 + file_count * 1.5 + (2 if has_files else 0)


def get_difficulty_tier(task: dict[str, Any]) -> DifficultyTier:
    """Classify a task into easy/medium/hard based on difficulty score."""
    score = compute_difficulty_score(task)
    if score <= _EASY_THRESHOLD:
        return "easy"
    elif score <= _HARD_THRESHOLD:
        return "medium"
    else:
        return "hard"


class TaskLoader:
    """Loads tasks from mercor/APEX-v1-extended (100 trainable tasks with rubrics).

    Supports difficulty-based filtering for curriculum learning:
        loader.get_task(difficulty="easy")   # simple tasks (few rubric criteria, few files)
        loader.get_task(difficulty="hard")   # complex tasks (many criteria, many files)
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
            "easy": [], "medium": [], "hard": [],
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
