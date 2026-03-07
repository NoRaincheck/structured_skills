import re

import pytest

from structured_skills.tasks.service import TaskService, build_task_id, slugify_task_name


def test_slugify_task_name():
    assert slugify_task_name("Daily Backup Job") == "daily-backup-job"
    assert slugify_task_name("  !!!  ") == "task"


def test_build_task_id_uses_slug_prefix():
    task_id = build_task_id("Refresh Metrics")
    assert task_id.startswith("refresh-metrics-")
    assert re.fullmatch(r"refresh-metrics-[a-f0-9]{6}", task_id)


def test_task_lifecycle_and_persistence(tmp_path):
    store_path = tmp_path / "tasks.json"
    service = TaskService(store_path)

    created = service.create_task(
        name="Nightly report",
        metadata={"source": "test"},
        recurrence="daily 09:00",
        next_run_at="2026-01-01T09:00:00+00:00",
    )
    assert created.status == "open"
    assert created.metadata["source"] == "test"

    started = service.start_task(created.id)
    assert started.status == "in_progress"
    assert started.started_at is not None
    assert started.attempts == 1

    failed = service.fail_task(created.id, "transient failure")
    assert failed.status == "failed"
    assert failed.last_error == "transient failure"

    reopened = service.reopen_task(created.id)
    assert reopened.status == "open"

    completed = service.complete_task(created.id, note="succeeded after retry")
    assert completed.status == "done"
    assert completed.last_note == "succeeded after retry"

    reloaded = TaskService(store_path).show_task(created.id)
    assert reloaded.status == "done"
    assert reloaded.last_note == "succeeded after retry"
    assert reloaded.recurrence == "daily 09:00"
    assert reloaded.next_run_at == "2026-01-01T09:00:00+00:00"


def test_closed_task_transition_guards(tmp_path):
    service = TaskService(tmp_path / "tasks.json")
    task = service.create_task("One-off")
    service.close_task(task.id)

    with pytest.raises(ValueError, match="closed task"):
        service.start_task(task.id)

    with pytest.raises(ValueError, match="closed task"):
        service.complete_task(task.id)

    with pytest.raises(ValueError, match="closed task"):
        service.fail_task(task.id, "boom")

    with pytest.raises(ValueError, match="closed task"):
        service.reopen_task(task.id)


def test_due_tasks(tmp_path):
    service = TaskService(tmp_path / "tasks.json")
    due = service.create_task("Due task", next_run_at="2026-01-01T00:00:00+00:00")
    service.create_task("Future task", next_run_at="2099-01-01T00:00:00+00:00")

    due_tasks = service.get_due_tasks(now_iso="2026-01-01T00:00:00+00:00")
    due_ids = {task.id for task in due_tasks}
    assert due.id in due_ids
