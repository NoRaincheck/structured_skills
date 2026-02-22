"""
tasks.py - Recurring task management with best-effort execution
"""

import hashlib
import os
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import platformdirs

SKILL_MD_TASKS = "## Tasks"
MIN_RECURRENCE_MINUTES = 30
SKILLNAME = "tasks"


def _get_data_dir() -> Path:
    """Get the data directory using platformdirs, or skill root if not available."""
    data_dir = Path(platformdirs.user_data_dir(appname=SKILLNAME))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _get_tasks_txt() -> Path:
    """Get the tasks.txt path."""
    file = _get_data_dir() / "tasks.txt"
    file.touch(exist_ok=True)
    return file


def _get_output_dir() -> Path:
    """Get the output directory path."""
    output_dir = _get_data_dir() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _get_skill_md() -> Path:
    """Get the SKILL.md path."""
    file = _get_data_dir() / "SKILL.md"
    file.touch(exist_ok=True)
    return file


def _ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)


def _iso_date() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_refno() -> str:
    dir_name = Path.cwd().name
    segments = re.split(r"[-_]", dir_name)
    prefix = "".join(seg[0].lower() for seg in segments if seg)
    if not prefix:
        prefix = dir_name[:3].lower()
    hash_input = f"{os.getpid()}{time.time()}".encode()
    hash_val = hashlib.sha256(hash_input).hexdigest()[:4]
    return f"tsk-{prefix[:2]}{hash_val}"


def _parse_task_line(line: str) -> dict | None:
    line = line.strip()
    if not line or line.startswith("_comment"):
        return None
    match = re.match(r"\[([^\]]+)\]\s*(.+?)\s*\|\s*next:([^\|]+)(?:\s*\|\s*recur:(.+))?", line)
    if not match:
        return None
    refno = match.group(1)
    description = match.group(2).strip()
    next_trigger = match.group(3).strip()
    recurrence = match.group(4).strip() if match.group(4) else None
    return {
        "refno": refno,
        "description": description,
        "next_trigger": next_trigger,
        "recurrence": recurrence,
    }


def _format_task_line(task: dict) -> str:
    line = f"[{task['refno']}] {task['description']} | next:{task['next_trigger']}"
    if task.get("recurrence"):
        line += f" | recur:{task['recurrence']}"
    return line


def _validate_recurrence(pattern: str | None) -> tuple[bool, str]:
    if not pattern:
        return True, ""
    pattern = pattern.strip().lower()
    every_match = re.match(r"^every\s+(\d+)(m|h)$", pattern)
    if every_match:
        value = int(every_match.group(1))
        unit = every_match.group(2)
        minutes = value if unit == "m" else value * 60
        if minutes < MIN_RECURRENCE_MINUTES:
            return (
                False,
                f"Recurrence must be at least {MIN_RECURRENCE_MINUTES} minutes. Got {minutes} minutes.",
            )
        return True, ""
    daily_match = re.match(r"^daily\s+(\d{1,2}):(\d{2})$", pattern)
    if daily_match:
        return True, ""
    return (
        False,
        f"Invalid recurrence pattern: {pattern}. Use 'every Nm', 'every Nh', or 'daily HH:MM'.",
    )


def _calculate_next_trigger(recurrence: str, from_time: datetime | None = None) -> str:
    if not recurrence:
        return ""
    if from_time is None:
        from_time = datetime.now(timezone.utc)
    pattern = recurrence.strip().lower()
    every_match = re.match(r"^every\s+(\d+)(m|h)$", pattern)
    if every_match:
        value = int(every_match.group(1))
        unit = every_match.group(2)
        delta = timedelta(minutes=value) if unit == "m" else timedelta(hours=value)
        next_time = from_time + delta
        return next_time.isoformat()
    daily_match = re.match(r"^daily\s+(\d{1,2}):(\d{2})$", pattern)
    if daily_match:
        hour = int(daily_match.group(1))
        minute = int(daily_match.group(2))
        next_time = from_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_time <= from_time:
            next_time += timedelta(days=1)
        return next_time.isoformat()
    return from_time.isoformat()


def _load_tasks() -> list[dict]:
    if not _get_tasks_txt().exists():
        return []
    tasks = []
    for line in _get_tasks_txt().read_text().split("\n"):
        task = _parse_task_line(line)
        if task:
            tasks.append(task)
    return tasks


def _save_tasks(tasks: list[dict]) -> None:
    _ensure_data_dir()
    lines = [_format_task_line(t) for t in tasks]
    _get_tasks_txt().write_text("\n".join(lines) + "\n")


def _update_skill_md() -> None:
    tasks_content = "\n".join([_format_task_line(t) for t in _load_tasks()])
    updated = f"{SKILL_MD_TASKS}\n\n{tasks_content}\n"
    _get_skill_md().write_text(updated)


def create_task(
    description: str,
    recurrence: str | None = None,
    trigger_time: str | None = None,
) -> str:
    # ensure not newlines due to flat format
    description = re.sub(r"\s+", " ", description)
    valid, error = _validate_recurrence(recurrence)
    if not valid:
        raise ValueError(error)
    refno = _generate_refno()
    if trigger_time:
        next_trigger = trigger_time
    elif recurrence:
        next_trigger = _calculate_next_trigger(recurrence)
    else:
        next_trigger = _iso_date()
    task = {
        "refno": refno,
        "description": description,
        "next_trigger": next_trigger,
        "recurrence": recurrence,
    }
    tasks = _load_tasks()
    tasks.append(task)
    _save_tasks(tasks)
    _update_skill_md()
    return refno


def list_tasks() -> list[dict]:
    return _load_tasks()


def get_due_tasks() -> list[dict]:
    now = datetime.now(timezone.utc)
    due = []
    for task in _load_tasks():
        try:
            trigger_time = datetime.fromisoformat(task["next_trigger"].replace("Z", "+00:00"))
            if trigger_time <= now:
                due.append(task)
        except Exception:
            due.append(task)
    return due


def complete_task(refno: str, output: str) -> str:
    tasks = _load_tasks()
    task = next((t for t in tasks if t["refno"] == refno), None)
    if not task:
        raise ValueError(f"Task not found: {refno}")
    completed_time = _iso_date()
    output_dir = _get_output_dir() / refno
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_time = completed_time.replace(":", "-").replace("+", "Z")
    hash_val = hashlib.sha256(output.encode()).hexdigest()[:4]
    output_file = output_dir / f"{safe_time}-{hash_val}.md"
    frontmatter = [
        "---",
        f"refno: {refno}",
        f"description: {task['description']}",
        f"completed: {completed_time}",
    ]
    if task.get("recurrence"):
        frontmatter.append(f"recurrence: {task['recurrence']}")
        next_trigger = _calculate_next_trigger(task["recurrence"])
        frontmatter.append(f"next_trigger: {next_trigger}")
    frontmatter.append("---")
    frontmatter.append("")
    content = "\n".join(frontmatter) + output
    output_file.write_text(content)
    if task.get("recurrence"):
        task["next_trigger"] = _calculate_next_trigger(task["recurrence"])
        _save_tasks(tasks)
        _update_skill_md()
    else:
        tasks = [t for t in tasks if t["refno"] != refno]
        _save_tasks(tasks)
        _update_skill_md()
    return str(output_file)


def delete_task(refno: str) -> bool:
    tasks = _load_tasks()
    original_count = len(tasks)
    tasks = [t for t in tasks if t["refno"] != refno]
    if len(tasks) == original_count:
        return False
    _save_tasks(tasks)
    _update_skill_md()
    return True


def update_task(refno: str, description: str | None = None, recurrence: str | None = None) -> bool:
    tasks = _load_tasks()
    task = next((t for t in tasks if t["refno"] == refno), None)
    if not task:
        return False
    if recurrence is not None:
        valid, error = _validate_recurrence(recurrence)
        if not valid:
            raise ValueError(error)
        task["recurrence"] = recurrence if recurrence else None
        if recurrence:
            task["next_trigger"] = _calculate_next_trigger(recurrence)
    if description is not None:
        task["description"] = description
    _save_tasks(tasks)
    _update_skill_md()
    return True


def reset():

    _ensure_data_dir()
    _get_tasks_txt().write_text("")
    if _get_output_dir().exists():
        shutil.rmtree(_get_output_dir())
    _get_skill_md().write_text("")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Task management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create_task", help="Create a new task")
    create_parser.add_argument("description", help="Task description")
    create_parser.add_argument(
        "--recurrence", "-r", help="Recurrence pattern (e.g., 'every 30m', 'daily 09:00')"
    )
    create_parser.add_argument("--trigger-time", "-t", help="Initial trigger time (ISO format)")

    list_parser = subparsers.add_parser("list_tasks", help="List all tasks")

    due_parser = subparsers.add_parser("get_due_tasks", help="Get due tasks")

    complete_parser = subparsers.add_parser("complete_task", help="Complete a task")
    complete_parser.add_argument("refno", help="Task reference number")
    complete_parser.add_argument("output", help="Task output/notes")

    delete_parser = subparsers.add_parser("delete_task", help="Delete a task")
    delete_parser.add_argument("refno", help="Task reference number")

    update_parser = subparsers.add_parser("update_task", help="Update a task")
    update_parser.add_argument("refno", help="Task reference number")
    update_parser.add_argument("--description", "-d", help="New description")
    update_parser.add_argument("--recurrence", "-r", help="New recurrence pattern")

    reset_parser = subparsers.add_parser("reset", help="Reset all tasks and output")

    args = parser.parse_args()

    if args.command == "create_task":
        refno = create_task(args.description, args.recurrence, args.trigger_time)
        print(f"Created task: {refno}")
    elif args.command == "list_tasks":
        tasks = list_tasks()
        for t in tasks:
            recur = f" | recur:{t['recurrence']}" if t.get("recurrence") else ""
            print(f"[{t['refno']}] {t['description']} | next:{t['next_trigger']}{recur}")
    elif args.command == "get_due_tasks":
        tasks = get_due_tasks()
        if not tasks:
            print("No due tasks")
        for t in tasks:
            recur = f" | recur:{t['recurrence']}" if t.get("recurrence") else ""
            print(f"[{t['refno']}] {t['description']} | next:{t['next_trigger']}{recur}")
    elif args.command == "complete_task":
        output_file = complete_task(args.refno, args.output)
        print(f"Completed task: {args.refno}")
        print(f"Output saved to: {output_file}")
    elif args.command == "delete_task":
        if delete_task(args.refno):
            print(f"Deleted task: {args.refno}")
        else:
            print(f"Task not found: {args.refno}")
    elif args.command == "update_task":
        if update_task(args.refno, args.description, args.recurrence):
            print(f"Updated task: {args.refno}")
        else:
            print(f"Task not found: {args.refno}")
    elif args.command == "reset":
        reset()
        print("Tasks and output reset successfully")
