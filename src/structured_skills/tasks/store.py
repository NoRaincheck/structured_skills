from __future__ import annotations

import json
from pathlib import Path

from structured_skills.tasks.models import TaskRecord

STORE_VERSION = 1


class TaskStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict[str, TaskRecord]:
        if not self.path.exists():
            return {}

        data = json.loads(self.path.read_text())
        tasks_data = data.get("tasks", [])
        tasks: dict[str, TaskRecord] = {}
        for item in tasks_data:
            task = TaskRecord.from_dict(item)
            tasks[task.id] = task
        return tasks

    def save(self, tasks: dict[str, TaskRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STORE_VERSION,
            "tasks": [
                task.to_dict() for task in sorted(tasks.values(), key=lambda t: t.created_at)
            ],
        }

        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n")
        tmp_path.replace(self.path)

    def resolve_task_id(self, task_id_or_prefix: str, tasks: dict[str, TaskRecord]) -> str:
        if task_id_or_prefix in tasks:
            return task_id_or_prefix

        matches = sorted(task_id for task_id in tasks if task_id.startswith(task_id_or_prefix))
        if not matches:
            raise ValueError(f"Task '{task_id_or_prefix}' not found")
        if len(matches) > 1:
            raise ValueError(
                f"Task id '{task_id_or_prefix}' is ambiguous: {', '.join(matches[:5])}"
            )
        return matches[0]
