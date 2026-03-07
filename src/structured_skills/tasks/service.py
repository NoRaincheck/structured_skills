from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from structured_skills.tasks.models import TASK_STATUSES, TaskRecord, TaskStatus
from structured_skills.tasks.store import TaskStore


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify_task_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "task"


def build_task_id(task_name: str) -> str:
    slug = slugify_task_name(task_name)
    entropy = f"{task_name}:{time.time_ns()}".encode()
    suffix = hashlib.sha256(entropy).hexdigest()[:6]
    return f"{slug}-{suffix}"


def _normalize_status(status: str) -> TaskStatus:
    if status not in TASK_STATUSES:
        allowed = ", ".join(TASK_STATUSES)
        raise ValueError(f"Invalid status '{status}'. Must be one of: {allowed}")
    return status  # type: ignore[return-value]


class TaskService:
    def __init__(self, store_path: Path):
        self.store = TaskStore(store_path)

    def create_task(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        recurrence: str | None = None,
        next_run_at: str | None = None,
    ) -> TaskRecord:
        normalized_name = re.sub(r"\s+", " ", name).strip()
        if not normalized_name:
            raise ValueError("Task name cannot be empty")

        now = _iso_now()
        task = TaskRecord(
            id=build_task_id(normalized_name),
            name=normalized_name,
            status="open",
            created_at=now,
            updated_at=now,
            recurrence=recurrence,
            next_run_at=next_run_at,
            metadata=metadata or {},
        )

        tasks = self.store.load()
        tasks[task.id] = task
        self.store.save(tasks)
        return task

    def list_tasks(self, status: str | None = None) -> list[TaskRecord]:
        tasks = list(self.store.load().values())
        if status is not None:
            task_status = _normalize_status(status)
            tasks = [task for task in tasks if task.status == task_status]
        return sorted(tasks, key=lambda t: t.created_at)

    def show_task(self, task_id_or_prefix: str) -> TaskRecord:
        tasks = self.store.load()
        task_id = self.store.resolve_task_id(task_id_or_prefix, tasks)
        return tasks[task_id]

    def start_task(self, task_id_or_prefix: str) -> TaskRecord:
        task = self.show_task(task_id_or_prefix)
        if task.status == "closed":
            raise ValueError("Cannot start a closed task")

        now = _iso_now()
        task.status = "in_progress"
        task.started_at = now
        task.last_run_at = now
        task.attempts += 1
        task.updated_at = now
        task.last_error = None
        self._save_task(task)
        return task

    def complete_task(self, task_id_or_prefix: str, note: str | None = None) -> TaskRecord:
        task = self.show_task(task_id_or_prefix)
        if task.status == "closed":
            raise ValueError("Cannot complete a closed task")

        now = _iso_now()
        task.status = "done"
        task.completed_at = now
        task.last_run_at = now
        task.updated_at = now
        task.last_error = None
        task.last_note = note
        self._save_task(task)
        return task

    def fail_task(self, task_id_or_prefix: str, error: str) -> TaskRecord:
        cleaned_error = error.strip()
        if not cleaned_error:
            raise ValueError("Failure error message cannot be empty")

        task = self.show_task(task_id_or_prefix)
        if task.status == "closed":
            raise ValueError("Cannot fail a closed task")

        now = _iso_now()
        task.status = "failed"
        task.failed_at = now
        task.last_run_at = now
        task.updated_at = now
        task.last_error = cleaned_error
        self._save_task(task)
        return task

    def reopen_task(self, task_id_or_prefix: str) -> TaskRecord:
        task = self.show_task(task_id_or_prefix)
        if task.status == "closed":
            raise ValueError("Cannot reopen a closed task")

        now = _iso_now()
        task.status = "open"
        task.updated_at = now
        self._save_task(task)
        return task

    def close_task(self, task_id_or_prefix: str) -> TaskRecord:
        task = self.show_task(task_id_or_prefix)
        now = _iso_now()
        task.status = "closed"
        task.updated_at = now
        self._save_task(task)
        return task

    def get_due_tasks(self, now_iso: str | None = None) -> list[TaskRecord]:
        now = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
        due: list[TaskRecord] = []
        for task in self.store.load().values():
            if task.next_run_at is None:
                continue
            try:
                task_time = _parse_iso(task.next_run_at)
            except ValueError:
                continue
            if task_time <= now:
                due.append(task)
        return sorted(due, key=lambda t: t.next_run_at or "")

    def _save_task(self, target: TaskRecord) -> None:
        tasks = self.store.load()
        task_id = self.store.resolve_task_id(target.id, tasks)
        tasks[task_id] = target
        self.store.save(tasks)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
