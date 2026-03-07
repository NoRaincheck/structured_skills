from __future__ import annotations

import argparse
import json
from pathlib import Path

from structured_skills.tasks.models import TASK_STATUSES, TaskRecord
from structured_skills.tasks.service import TaskService


def add_tasks_subparser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    tasks_parser = subparsers.add_parser("tasks", help="Manage tracked tasks for runs")
    tasks_parser.add_argument(
        "--session-name",
        type=str,
        default=None,
        help="Optional session label for task state",
    )
    tasks_parser.add_argument(
        "--working-dir",
        type=Path,
        default=None,
        help="Explicit working directory for task state",
    )
    tasks_parser.add_argument(
        "--store-file",
        type=Path,
        default=None,
        help="Optional explicit tasks JSON path",
    )

    task_subparsers = tasks_parser.add_subparsers(dest="tasks_command", help="Task commands")

    create_parser = task_subparsers.add_parser("create", help="Create a task")
    create_parser.add_argument("name", type=str, help="Task name")
    create_parser.add_argument(
        "--meta",
        action="append",
        default=[],
        help="Metadata key/value in KEY=VALUE form. Can be repeated.",
    )
    create_parser.add_argument(
        "--recurrence", type=str, default=None, help="Optional recurrence pattern"
    )
    create_parser.add_argument(
        "--next-run-at",
        type=str,
        default=None,
        help="Optional next run datetime in ISO format",
    )
    create_parser.add_argument("--json", action="store_true", help="Output JSON")

    list_parser = task_subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument(
        "--status",
        choices=list(TASK_STATUSES),
        default=None,
        help="Filter by status",
    )
    list_parser.add_argument("--json", action="store_true", help="Output JSON")

    show_parser = task_subparsers.add_parser("show", help="Show task details")
    show_parser.add_argument("task_id", type=str, help="Task ID or unique prefix")
    show_parser.add_argument("--json", action="store_true", help="Output JSON")

    start_parser = task_subparsers.add_parser("start", help="Mark a task as in_progress")
    start_parser.add_argument("task_id", type=str, help="Task ID or unique prefix")

    complete_parser = task_subparsers.add_parser("complete", help="Mark a task as done")
    complete_parser.add_argument("task_id", type=str, help="Task ID or unique prefix")
    complete_parser.add_argument("--note", type=str, default=None, help="Optional completion note")

    fail_parser = task_subparsers.add_parser("fail", help="Mark a task as failed")
    fail_parser.add_argument("task_id", type=str, help="Task ID or unique prefix")
    fail_parser.add_argument("--error", required=True, type=str, help="Failure reason")

    reopen_parser = task_subparsers.add_parser("reopen", help="Reopen a task")
    reopen_parser.add_argument("task_id", type=str, help="Task ID or unique prefix")

    close_parser = task_subparsers.add_parser("close", help="Close a task")
    close_parser.add_argument("task_id", type=str, help="Task ID or unique prefix")

    due_parser = task_subparsers.add_parser("due", help="List tasks with due schedule")
    due_parser.add_argument("--json", action="store_true", help="Output JSON")

    return tasks_parser


def handle_tasks_cli(args: argparse.Namespace, store_path: Path) -> None:
    service = TaskService(store_path)

    if args.tasks_command == "create":
        metadata = _parse_metadata(args.meta)
        task = service.create_task(
            name=args.name,
            metadata=metadata,
            recurrence=args.recurrence,
            next_run_at=args.next_run_at,
        )
        if args.json:
            print(json.dumps(task.to_dict(), indent=2))
        else:
            print(f"Created task: {task.id}")
        return

    if args.tasks_command == "list":
        tasks = service.list_tasks(status=args.status)
        if args.json:
            print(json.dumps([task.to_dict() for task in tasks], indent=2))
        else:
            _print_tasks(tasks)
        return

    if args.tasks_command == "show":
        task = service.show_task(args.task_id)
        if args.json:
            print(json.dumps(task.to_dict(), indent=2))
        else:
            _print_task(task)
        return

    if args.tasks_command == "start":
        task = service.start_task(args.task_id)
        print(f"Updated {task.id} -> {task.status}")
        return

    if args.tasks_command == "complete":
        task = service.complete_task(args.task_id, note=args.note)
        print(f"Updated {task.id} -> {task.status}")
        return

    if args.tasks_command == "fail":
        task = service.fail_task(args.task_id, error=args.error)
        print(f"Updated {task.id} -> {task.status}")
        return

    if args.tasks_command == "reopen":
        task = service.reopen_task(args.task_id)
        print(f"Updated {task.id} -> {task.status}")
        return

    if args.tasks_command == "close":
        task = service.close_task(args.task_id)
        print(f"Updated {task.id} -> {task.status}")
        return

    if args.tasks_command == "due":
        tasks = service.get_due_tasks()
        if args.json:
            print(json.dumps([task.to_dict() for task in tasks], indent=2))
        else:
            _print_tasks(tasks)
        return

    raise ValueError("Unknown tasks command. Use --help for usage.")


def _parse_metadata(values: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid --meta value '{item}'. Expected KEY=VALUE format.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Metadata key cannot be empty")
        metadata[key] = value.strip()
    return metadata


def _print_tasks(tasks: list[TaskRecord]) -> None:
    if not tasks:
        print("No tasks found")
        return

    for task in tasks:
        print(f"{task.id:<24} [{task.status}] {task.name}")


def _print_task(task: TaskRecord) -> None:
    print(f"{task.id} [{task.status}] {task.name}")
    print(f"created_at: {task.created_at}")
    print(f"updated_at: {task.updated_at}")
    print(f"attempts: {task.attempts}")
    if task.last_error:
        print(f"last_error: {task.last_error}")
    if task.last_note:
        print(f"last_note: {task.last_note}")
    if task.next_run_at:
        print(f"next_run_at: {task.next_run_at}")
    if task.recurrence:
        print(f"recurrence: {task.recurrence}")
