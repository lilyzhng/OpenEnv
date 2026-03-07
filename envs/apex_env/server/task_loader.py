"""Load APEX tasks from HuggingFace dataset."""

import random
from typing import Any


class TaskLoader:
    """Loads tasks from mercor/APEX-v1-extended (100 trainable tasks with rubrics)."""

    def __init__(self, dataset_name: str = "mercor/APEX-v1-extended"):
        self._tasks: list[dict[str, Any]] | None = None
        self._dataset_name = dataset_name

    def _load(self) -> None:
        if self._tasks is not None:
            return
        from datasets import load_dataset

        ds = load_dataset(self._dataset_name, split="train")
        self._tasks = list(ds)

    def get_task(
        self, seed: int | None = None, task_id: str | None = None
    ) -> dict[str, Any]:
        self._load()
        assert self._tasks is not None

        if task_id is not None:
            for t in self._tasks:
                if str(t.get("task_id", "")) == str(task_id):
                    return t
            raise ValueError(f"Task {task_id} not found in dataset")

        if seed is not None:
            return self._tasks[seed % len(self._tasks)]

        return random.choice(self._tasks)

    def __len__(self) -> int:
        self._load()
        assert self._tasks is not None
        return len(self._tasks)
