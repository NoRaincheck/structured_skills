import json
from datetime import datetime, timezone

import pytest

from structured_skills.scheduler import (
    parse_scheduler,
    read_state,
    scheduler_tick,
    write_state_atomic,
)


def _sample_scheduler() -> str:
    return """agent = "ops-monitor"
version = 1

[disk-space-check]
title = "Check disk usage"
enabled = true
priority = "high"
interval = "every 15m"
active_schedule = "weekdays between 09:00-17:00"
cooldown = "30m"
extra_field = "preserve me"
task = { skill_name = "test-skill", function = "greet", args = { name = "Ops" } }
"""


def test_parse_scheduler_valid_and_unknown_fields():
    parsed = parse_scheduler(_sample_scheduler())
    assert parsed["agent"] == "ops-monitor"
    assert parsed["version"] == 1
    assert len(parsed["tasks"]) == 1
    task = parsed["tasks"][0]
    assert task["id"] == "disk-space-check"
    assert task["schedule"] == "15m"
    assert task["active_schedule"] == "weekdays between 09:00-17:00"
    assert task["unknown_fields"]["extra_field"] == "preserve me"
    assert len(task["steps"]) == 1
    assert task["steps"][0]["skill_name"] == "test-skill"
    assert task["steps"][0]["function_or_script_name"] == "greet"


def test_parse_scheduler_invalid_toml():
    with pytest.raises(ValueError, match="Invalid SCHEDULER.toml"):
        parse_scheduler("[bad")


def test_read_state_and_tick_updates(tmp_path):
    scheduler = parse_scheduler(_sample_scheduler())
    state_path = tmp_path / "scheduler-state.json"
    state = read_state(state_path, scheduler)

    now = datetime(2026, 3, 9, 9, 30, 0, tzinfo=timezone.utc)
    updated_state, summary = scheduler_tick(
        scheduler,
        state,
        now=now,
        task_results={
            "disk-space-check": {
                "status": "failure",
                "reason": "Disk usage above threshold",
                "dedup_key": "disk-88",
                "observed_value": {"usage_percent": 88},
                "alerted": True,
            }
        },
    )

    task_state = updated_state["tasks"]["disk-space-check"]
    assert summary["status"] == "failure"
    assert task_state["last_run"]["status"] == "failure"
    assert task_state["last_failure"]["dedup_key"] == "disk-88"
    assert task_state["last_alerted_at"] == "2026-03-09T09:30:00Z"
    assert task_state["cooldown_until"] == "2026-03-09T10:00:00Z"
    assert len(task_state["recent_runs"]) == 1

    write_state_atomic(state_path, updated_state)
    loaded = json.loads(state_path.read_text())
    assert loaded["scheduler"]["last_status"] == "failure"


def test_active_schedule_skips_outside_window(tmp_path):
    scheduler = parse_scheduler(
        """agent = "ops-monitor"
version = 1

[weekend-only]
title = "Weekend task"
schedule = "every-run"
active_schedule = "weekends between 09:00-17:00"
task = { skill_name = "test-skill", function = "greet", args = { name = "Weekend" } }
"""
    )
    state = read_state(tmp_path / "scheduler-state.json", scheduler)
    monday = datetime(2026, 3, 9, 10, 0, 0, tzinfo=timezone.utc)
    updated_state, summary = scheduler_tick(
        scheduler,
        state,
        now=monday,
        task_results={"weekend-only": {"status": "success", "reason": "should not run"}},
    )

    assert summary["skipped"][0]["task_id"] == "weekend-only"
    assert summary["skipped"][0]["reason"] == "Task is outside active_schedule"
    assert updated_state["tasks"]["weekend-only"]["last_run"]["status"] == "skipped"


@pytest.mark.parametrize(
    ("schedule", "expected_weekdays", "expected_hour", "expected_minute", "expected_normalized"),
    [
        ("monday 9am", [0], 9, 0, "monday 09:00"),
        ("daily 9am", None, 9, 0, "daily 09:00"),
        ("weekdays 9am", [0, 1, 2, 3, 4], 9, 0, "weekdays 09:00"),
        ("tuesday 14:30", [1], 14, 30, "tuesday 14:30"),
        ("every day 9am", None, 9, 0, "daily 09:00"),
    ],
)
def test_parse_scheduler_cron_style_schedule(
    schedule, expected_weekdays, expected_hour, expected_minute, expected_normalized
):
    parsed = parse_scheduler(
        f"""agent = "ops-monitor"
version = 1

[cron-check]
title = "Cron check"
schedule = "{schedule}"
task = {{ skill_name = "test-skill", function = "greet", args = {{ name = "Cron" }} }}
"""
    )
    task = parsed["tasks"][0]
    info = task["schedule_info"]

    assert task["schedule"] == expected_normalized
    assert info["normalized"] == expected_normalized
    assert info["cron_weekdays"] == expected_weekdays
    assert info["cron_hour"] == expected_hour
    assert info["cron_minute"] == expected_minute
    assert info["interval_seconds"] is None
    assert info["every_run"] is False


def test_parse_scheduler_daily_alias_stays_interval():
    parsed = parse_scheduler(
        """agent = "ops-monitor"
version = 1

[daily-interval]
title = "Daily interval"
interval = "daily"
task = { skill_name = "test-skill", function = "greet", args = { name = "Daily" } }
"""
    )
    info = parsed["tasks"][0]["schedule_info"]
    assert parsed["tasks"][0]["schedule"] == "24h"
    assert info["interval_seconds"] == 24 * 60 * 60
    assert info["cron_weekdays"] is None
    assert info["cron_hour"] is None
    assert info["cron_minute"] is None


def test_cron_schedule_due_if_not_run_since_previous_occurrence(tmp_path):
    scheduler = parse_scheduler(
        """agent = "ops-monitor"
version = 1

[monday-check]
title = "Monday check"
schedule = "monday 9am"
task = { skill_name = "test-skill", function = "greet", args = { name = "Monday" } }
"""
    )
    state = read_state(tmp_path / "scheduler-state.json", scheduler)
    now = datetime(2026, 3, 9, 10, 0, 0, tzinfo=timezone.utc)  # Monday

    updated_state, summary = scheduler_tick(
        scheduler,
        state,
        now=now,
        task_results={"monday-check": {"status": "success", "reason": "ran"}},
    )

    assert summary["executed"][0]["task_id"] == "monday-check"
    assert updated_state["tasks"]["monday-check"]["last_run"]["status"] == "success"


def test_cron_schedule_not_due_if_already_run_since_previous_occurrence(tmp_path):
    scheduler = parse_scheduler(
        """agent = "ops-monitor"
version = 1

[monday-check]
title = "Monday check"
schedule = "monday 9am"
task = { skill_name = "test-skill", function = "greet", args = { name = "Monday" } }
"""
    )
    state = read_state(tmp_path / "scheduler-state.json", scheduler)
    state["tasks"]["monday-check"]["last_run"] = {
        "run_id": "existing-run",
        "started_at": "2026-03-09T09:20:00Z",
        "finished_at": "2026-03-09T09:20:00Z",
        "status": "success",
        "reason": "already ran",
        "dedup_key": None,
        "observed_value": None,
        "error": None,
    }

    now = datetime(2026, 3, 9, 10, 0, 0, tzinfo=timezone.utc)  # Monday
    _, summary = scheduler_tick(
        scheduler,
        state,
        now=now,
        task_results={"monday-check": {"status": "success", "reason": "should not run"}},
    )

    assert summary["skipped"][0]["task_id"] == "monday-check"
    assert summary["skipped"][0]["reason"] == "Task is not due"


def test_cron_schedule_due_when_last_run_before_previous_occurrence(tmp_path):
    scheduler = parse_scheduler(
        """agent = "ops-monitor"
version = 1

[monday-check]
title = "Monday check"
schedule = "monday 9am"
task = { skill_name = "test-skill", function = "greet", args = { name = "Monday" } }
"""
    )
    state = read_state(tmp_path / "scheduler-state.json", scheduler)
    state["tasks"]["monday-check"]["last_run"] = {
        "run_id": "existing-run",
        "started_at": "2026-03-08T12:00:00Z",
        "finished_at": "2026-03-08T12:00:00Z",  # Sunday before previous Monday 09:00
        "status": "success",
        "reason": "old run",
        "dedup_key": None,
        "observed_value": None,
        "error": None,
    }

    now = datetime(2026, 3, 9, 10, 0, 0, tzinfo=timezone.utc)  # Monday
    _, summary = scheduler_tick(
        scheduler,
        state,
        now=now,
        task_results={"monday-check": {"status": "success", "reason": "ran again"}},
    )

    assert summary["executed"][0]["task_id"] == "monday-check"


def test_parse_scheduler_accepts_task_array():
    parsed = parse_scheduler(
        """agent = "ops-monitor"
version = 1

[array-steps]
interval = "10m"
task = [
  { skill_name = "test-skill", function = "greet", args = { name = "Step1" } },
  { skill_name = "test-skill", function = "add", args = { a = 1, b = 2 } }
]
"""
    )
    task = parsed["tasks"][0]
    assert len(task["steps"]) == 2
    assert task["steps"][0]["function_or_script_name"] == "greet"
    assert task["steps"][1]["function_or_script_name"] == "add"
