from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import structured_skills.heartbeat_daemon as hd


def _write_config(tmp_path: Path, body: str) -> Path:
    config = tmp_path / "scheduler.toml"
    config.write_text(body, encoding="utf-8")
    return config


def test_parse_duration_accepts_compound_units() -> None:
    assert hd.parse_duration("45s") == timedelta(seconds=45)
    assert hd.parse_duration("1h30m") == timedelta(hours=1, minutes=30)
    assert hd.parse_duration("1d12h") == timedelta(days=1, hours=12)


@pytest.mark.parametrize("raw", ["", "0s", "10", "1x", "1m-2s", "m10"])
def test_parse_duration_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid duration"):
        hd.parse_duration(raw)


def test_load_config_reads_flat_named_tasks_schema(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path,
        """
version = 1

[daemon]
heartbeat = "30s"
timezone = "UTC"
state_file = "./state.json"
shell = "/bin/sh"

[tasks.refresh-cache]
run = "bin/refresh-cache"
every = "15m"
timeout = "2m"

[tasks.daily-report]
run = "bin/daily-report"
at = "09:00"
enabled = false
""".strip(),
    )

    daemon, tasks = hd.load_config(config)
    task_map = {task.name: task for task in tasks}

    assert daemon.heartbeat == timedelta(seconds=30)
    assert daemon.timezone_mode == "UTC"
    assert daemon.state_file == tmp_path / "state.json"
    assert daemon.shell == "/bin/sh"
    assert "refresh-cache" in task_map
    assert task_map["refresh-cache"].every == timedelta(minutes=15)
    assert task_map["refresh-cache"].timeout == timedelta(minutes=2)
    assert task_map["daily-report"].at_clock == (9, 0, 0)
    assert task_map["daily-report"].enabled is False


def test_load_config_requires_exactly_one_schedule_mode(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path,
        """
version = 1

[tasks.bad]
run = "echo bad"
every = "1m"
at = "09:00"
""".strip(),
    )
    with pytest.raises(ValueError, match="exactly one of 'every' or 'at'"):
        hd.load_config(config)


def test_every_schedule_uses_anchor_without_drift() -> None:
    task = hd.Task(
        name="sync-partner-data",
        run="echo sync",
        every=timedelta(hours=1),
        start_at_once=datetime(2026, 3, 12, 0, 0, tzinfo=timezone.utc),
    )
    state: dict[str, str] = {}

    now = datetime(2026, 3, 12, 2, 10, tzinfo=timezone.utc)
    assert hd.is_due(task, state, now, "UTC") is True
    hd.mark_scheduled(state, task, now, "UTC")
    assert state["last_scheduled"].startswith("2026-03-12T02:00:00")

    same_period = datetime(2026, 3, 12, 2, 59, tzinfo=timezone.utc)
    assert hd.is_due(task, state, same_period, "UTC") is False

    next_period = datetime(2026, 3, 12, 3, 1, tzinfo=timezone.utc)
    assert hd.is_due(task, state, next_period, "UTC") is True


def test_daily_at_runs_once_per_day() -> None:
    task = hd.Task(name="daily-report", run="echo report", at_clock=(9, 0, 0))
    state: dict[str, str] = {}

    first_run = datetime(2026, 3, 12, 9, 1, tzinfo=timezone.utc)
    assert hd.is_due(task, state, first_run, "UTC") is True
    state["last_started"] = first_run.isoformat()

    later_same_day = datetime(2026, 3, 12, 20, 0, tzinfo=timezone.utc)
    assert hd.is_due(task, state, later_same_day, "UTC") is False

    next_day = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    assert hd.is_due(task, state, next_day, "UTC") is True


def test_one_off_at_completes_after_first_run() -> None:
    task = hd.Task(
        name="one-off-backfill",
        run="echo backfill",
        at_once=datetime(2026, 3, 15, 4, 0, tzinfo=timezone.utc),
    )
    state: dict[str, object] = {}
    now = datetime(2026, 3, 15, 4, 1, tzinfo=timezone.utc)

    assert hd.is_due(task, state, now, "UTC") is True
    state["completed"] = True
    assert hd.is_due(task, state, now, "UTC") is False


def test_state_roundtrip_with_sqlite_backend(tmp_path: Path) -> None:
    state_file = tmp_path / "scheduler-state.db"
    state: dict[str, object] = {
        "refresh-cache": {
            "anchor": "2026-03-12T00:00:00+00:00",
            "last_scheduled": "2026-03-12T00:15:00+00:00",
            "last_exit_code": 0,
        },
        "daily-report": {"last_started": "2026-03-12T09:00:00+00:00"},
    }

    hd.save_state(state_file, state)
    loaded = hd.load_state(state_file)

    assert loaded == state
