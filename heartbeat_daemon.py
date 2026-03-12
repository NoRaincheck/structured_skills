"""Lightweight heartbeat-driven task scheduler daemon.

This module provides a stdlib-only daemon that:
- Loads TOML config on each heartbeat tick
- Computes due tasks for interval and wall-clock schedules
- Executes task commands via subprocess through a configurable shell
- Persists per-task run state in JSON or sqlite3

Supported scheduler TOML schema:

    version = 1

    [daemon]
    heartbeat = "1m"
    timezone = "local"  # "local" or "UTC"
    state_file = "./scheduler-state.json"  # or "./scheduler-state.db"
    shell = "/bin/sh"

    [tasks.refresh-cache]
    run = "bin/refresh-cache"
    every = "15m"

    [tasks.daily-report]
    run = "bin/daily-report"
    at = "09:00"

Task schedule fields:
- every = "<duration>"  # recurring interval
- at = "HH:MM" | "HH:MM:SS"  # daily wall-clock
- at = "<ISO timestamp>"  # one-off timestamp

Optional task fields:
- enabled = true
- timeout = "<duration>"
- start_at = "HH:MM" | "<ISO timestamp>"  # interval anchor

CLI:
    uv run heartbeat_daemon.py scheduler.toml
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import tomllib

DURATION_RE = re.compile(r"(\d+)([smhd])")
TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


def parse_duration(value: str) -> timedelta:
    pos = 0
    total = timedelta()
    for match in DURATION_RE.finditer(value):
        if match.start() != pos:
            raise ValueError(f"invalid duration: {value!r}")
        amount = int(match.group(1))
        unit = match.group(2)
        if unit == "s":
            total += timedelta(seconds=amount)
        elif unit == "m":
            total += timedelta(minutes=amount)
        elif unit == "h":
            total += timedelta(hours=amount)
        elif unit == "d":
            total += timedelta(days=amount)
        pos = match.end()
    if pos != len(value) or total <= timedelta(0):
        raise ValueError(f"invalid duration: {value!r}")
    return total


def parse_clock_time(value: str) -> tuple[int, int, int]:
    if not TIME_RE.match(value):
        raise ValueError(f"invalid wall-clock time: {value!r}")
    parts = [int(p) for p in value.split(":")]
    if len(parts) == 2:
        hh, mm = parts
        ss = 0
    else:
        hh, mm, ss = parts
    if not (0 <= hh < 24 and 0 <= mm < 60 and 0 <= ss < 60):
        raise ValueError(f"invalid wall-clock time: {value!r}")
    return hh, mm, ss


def _normalize_iso(value: str) -> str:
    if value.endswith("Z"):
        return value[:-1] + "+00:00"
    return value


def local_tzinfo():
    return datetime.now().astimezone().tzinfo


def parse_iso_datetime(value: str, tz_mode: str) -> datetime:
    dt = datetime.fromisoformat(_normalize_iso(value))
    if dt.tzinfo is not None:
        return dt
    if tz_mode == "UTC":
        return dt.replace(tzinfo=timezone.utc)
    return dt.replace(tzinfo=local_tzinfo())


def now_for_mode(tz_mode: str) -> datetime:
    if tz_mode == "UTC":
        return datetime.now(timezone.utc)
    return datetime.now().astimezone()


def to_mode_tz(dt: datetime, tz_mode: str) -> datetime:
    if dt.tzinfo is None:
        return parse_iso_datetime(dt.isoformat(), tz_mode)
    if tz_mode == "UTC":
        return dt.astimezone(timezone.utc)
    return dt.astimezone(local_tzinfo())


@dataclass
class DaemonConfig:
    heartbeat: timedelta
    timezone_mode: str
    state_file: Path
    shell: str


@dataclass
class Task:
    name: str
    run: str
    every: timedelta | None = None
    at_clock: tuple[int, int, int] | None = None
    at_once: datetime | None = None
    start_at_clock: tuple[int, int, int] | None = None
    start_at_once: datetime | None = None
    enabled: bool = True
    timeout: timedelta | None = None


def _resolve_path(value: str, config_path: Path) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return config_path.parent / p


def load_config(path: Path) -> tuple[DaemonConfig, list[Task]]:
    with path.open("rb") as f:
        data = tomllib.load(f)

    version = data.get("version")
    if version != 1:
        raise ValueError("version must be 1")

    daemon_data = data.get("daemon", {})
    if not isinstance(daemon_data, dict):
        raise ValueError("daemon must be a table")

    tz_mode = daemon_data.get("timezone", "local")
    if tz_mode not in ("local", "UTC"):
        raise ValueError("daemon.timezone must be 'local' or 'UTC'")

    daemon = DaemonConfig(
        heartbeat=parse_duration(str(daemon_data.get("heartbeat", "1m"))),
        timezone_mode=tz_mode,
        state_file=_resolve_path(
            str(daemon_data.get("state_file", "./scheduler-state.json")), path
        ),
        shell=str(daemon_data.get("shell", "/bin/sh")),
    )

    tasks_data = data.get("tasks")
    if tasks_data is None:
        tasks_data = {}
    if not isinstance(tasks_data, dict):
        raise ValueError("tasks must be a table of named task tables")

    tasks: list[Task] = []
    for task_name, raw in tasks_data.items():
        if not isinstance(raw, dict):
            raise ValueError(f"task {task_name!r} must be a table")
        if "run" not in raw:
            raise ValueError(f"task {task_name!r}: missing required 'run'")

        run = str(raw["run"])
        every_raw = raw.get("every")
        at_raw = raw.get("at")

        if (every_raw is None) == (at_raw is None):
            raise ValueError(f"task {task_name!r}: exactly one of 'every' or 'at' is required")

        task = Task(
            name=str(task_name),
            run=run,
            enabled=bool(raw.get("enabled", True)),
            timeout=parse_duration(str(raw["timeout"])) if "timeout" in raw else None,
        )

        if every_raw is not None:
            task.every = parse_duration(str(every_raw))
            if "start_at" in raw:
                start_at = str(raw["start_at"])
                if TIME_RE.match(start_at):
                    task.start_at_clock = parse_clock_time(start_at)
                else:
                    task.start_at_once = parse_iso_datetime(start_at, daemon.timezone_mode)
        else:
            at_value = str(at_raw)
            if TIME_RE.match(at_value):
                task.at_clock = parse_clock_time(at_value)
            else:
                task.at_once = parse_iso_datetime(at_value, daemon.timezone_mode)

        tasks.append(task)

    return daemon, tasks


def load_state(path: Path) -> dict[str, Any]:
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        return load_state_sqlite(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: Path, state: dict[str, Any]) -> None:
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        save_state_sqlite(path, state)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=True, indent=2, sort_keys=True)
    tmp.replace(path)


def _ensure_sqlite_state_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_state (
            task_name TEXT PRIMARY KEY,
            state_json TEXT NOT NULL
        )
        """
    )


def load_state_sqlite(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with sqlite3.connect(path) as conn:
        _ensure_sqlite_state_schema(conn)
        rows = conn.execute("SELECT task_name, state_json FROM task_state").fetchall()
    return {task_name: json.loads(state_json) for task_name, state_json in rows}


def save_state_sqlite(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        _ensure_sqlite_state_schema(conn)
        conn.execute("DELETE FROM task_state")
        conn.executemany(
            "INSERT INTO task_state (task_name, state_json) VALUES (?, ?)",
            (
                (
                    task_name,
                    json.dumps(task_state, ensure_ascii=True, sort_keys=True),
                )
                for task_name, task_state in state.items()
            ),
        )


def dt_to_str(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def str_to_dt(value: str | None, tz_mode: str) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(_normalize_iso(value))
    return to_mode_tz(dt, tz_mode)


def today_at(now: datetime, hh: int, mm: int, ss: int) -> datetime:
    return now.replace(hour=hh, minute=mm, second=ss, microsecond=0)


def compute_anchor(task: Task, now: datetime, tz_mode: str) -> datetime:
    if task.start_at_once is not None:
        return to_mode_tz(task.start_at_once, tz_mode)

    if task.start_at_clock is not None:
        hh, mm, ss = task.start_at_clock
        anchor = today_at(now, hh, mm, ss)
        if anchor > now:
            anchor -= timedelta(days=1)
        return anchor

    return now


def is_due(task: Task, task_state: dict[str, Any], now: datetime, tz_mode: str) -> bool:
    if not task.enabled:
        return False

    last_started = str_to_dt(task_state.get("last_started"), tz_mode)
    completed = bool(task_state.get("completed", False))

    if task.at_once is not None:
        if completed:
            return False
        return now >= to_mode_tz(task.at_once, tz_mode)

    if task.at_clock is not None:
        hh, mm, ss = task.at_clock
        due_today = today_at(now, hh, mm, ss)
        last_run_day = None
        if last_started is not None:
            last_run_day = last_started.astimezone(now.tzinfo).date()
        return now >= due_today and last_run_day != now.date()

    if task.every is not None:
        anchor = str_to_dt(task_state.get("anchor"), tz_mode)
        if anchor is None:
            anchor = compute_anchor(task, now, tz_mode)
            task_state["anchor"] = dt_to_str(anchor)

        if now < anchor:
            return False

        elapsed = now - anchor
        periods_due = int(elapsed.total_seconds() // task.every.total_seconds())
        scheduled = anchor + task.every * periods_due

        last_scheduled = str_to_dt(task_state.get("last_scheduled"), tz_mode)
        return last_scheduled is None or scheduled > last_scheduled

    return False


def mark_scheduled(task_state: dict[str, Any], task: Task, now: datetime, tz_mode: str) -> None:
    if task.at_once is not None:
        task_state["last_scheduled"] = dt_to_str(to_mode_tz(task.at_once, tz_mode))
        return

    if task.at_clock is not None:
        hh, mm, ss = task.at_clock
        task_state["last_scheduled"] = dt_to_str(today_at(now, hh, mm, ss))
        return

    if task.every is not None:
        anchor = str_to_dt(task_state["anchor"], tz_mode)
        if anchor is None:
            anchor = compute_anchor(task, now, tz_mode)
            task_state["anchor"] = dt_to_str(anchor)
        elapsed = now - anchor
        periods_due = int(elapsed.total_seconds() // task.every.total_seconds())
        scheduled = anchor + task.every * periods_due
        task_state["last_scheduled"] = dt_to_str(scheduled)


def run_task(task: Task, daemon: DaemonConfig, task_state: dict[str, Any], now: datetime) -> None:
    task_state["last_started"] = dt_to_str(now)
    try:
        result = subprocess.run(
            task.run,
            shell=True,
            executable=daemon.shell,
            timeout=task.timeout.total_seconds() if task.timeout else None,
            check=False,
        )
        finished = now_for_mode(daemon.timezone_mode)
        task_state["last_finished"] = dt_to_str(finished)
        task_state["last_exit_code"] = result.returncode
        if result.returncode == 0:
            task_state["last_success"] = dt_to_str(finished)
        if task.at_once is not None:
            task_state["completed"] = True
    except subprocess.TimeoutExpired:
        finished = now_for_mode(daemon.timezone_mode)
        task_state["last_finished"] = dt_to_str(finished)
        task_state["last_exit_code"] = "timeout"
        if task.at_once is not None:
            task_state["completed"] = True


def run_tick(config_file: Path) -> None:
    daemon, tasks = load_config(config_file)
    state = load_state(daemon.state_file)
    now = now_for_mode(daemon.timezone_mode)

    for task in tasks:
        task_state = state.setdefault(task.name, {})
        if is_due(task, task_state, now, daemon.timezone_mode):
            mark_scheduled(task_state, task, now, daemon.timezone_mode)
            save_state(daemon.state_file, state)
            run_task(task, daemon, task_state, now_for_mode(daemon.timezone_mode))
            save_state(daemon.state_file, state)


def run_loop(config_path: str) -> None:
    config_file = Path(config_path)
    while True:
        daemon, _ = load_config(config_file)
        run_tick(config_file)
        time.sleep(daemon.heartbeat.total_seconds())


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Heartbeat scheduler daemon")
    parser.add_argument(
        "config", nargs="?", default="scheduler.toml", help="Path to scheduler TOML"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    run_loop(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
