import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import tomllib

RECENT_RUNS_LIMIT = 20
ALLOWED_PRIORITIES = {"low", "normal", "high", "critical"}


@dataclass(frozen=True)
class ScheduleInfo:
    normalized: str
    interval_seconds: int | None
    every_run: bool
    cron_weekdays: tuple[int, ...] | None = None
    cron_hour: int | None = None
    cron_minute: int | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _snake_case(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _to_int(value: str, *, field_name: str) -> int:
    try:
        return int(value.strip())
    except Exception as exc:  # pragma: no cover - narrow helper
        raise ValueError(f"Invalid integer for {field_name}: {value}") from exc


def parse_duration_to_seconds(value: str) -> int:
    match = re.fullmatch(r"(\d+)([mhd])", value.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration: {value}")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 60 * 60
    return amount * 24 * 60 * 60


_DAY_ALIASES = {
    "mon": ("monday", (0,)),
    "monday": ("monday", (0,)),
    "tue": ("tuesday", (1,)),
    "tues": ("tuesday", (1,)),
    "tuesday": ("tuesday", (1,)),
    "wed": ("wednesday", (2,)),
    "wednesday": ("wednesday", (2,)),
    "thu": ("thursday", (3,)),
    "thur": ("thursday", (3,)),
    "thurs": ("thursday", (3,)),
    "thursday": ("thursday", (3,)),
    "fri": ("friday", (4,)),
    "friday": ("friday", (4,)),
    "sat": ("saturday", (5,)),
    "saturday": ("saturday", (5,)),
    "sun": ("sunday", (6,)),
    "sunday": ("sunday", (6,)),
    "daily": ("daily", None),
    "every day": ("daily", None),
    "weekdays": ("weekdays", (0, 1, 2, 3, 4)),
    "weekends": ("weekends", (5, 6)),
}


def _parse_clock_time(value: str) -> tuple[int, int]:
    value = value.strip().lower()

    # 24-hour clock format, e.g. 14:30.
    hhmm_match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", value)
    if hhmm_match:
        return int(hhmm_match.group(1)), int(hhmm_match.group(2))

    # 12-hour clock format, e.g. 9am, 9:30pm.
    ampm_match = re.fullmatch(r"(1[0-2]|[1-9])(?::([0-5]\d))?\s*([ap]m)", value)
    if ampm_match:
        hour = int(ampm_match.group(1))
        minute = int(ampm_match.group(2) or "0")
        meridiem = ampm_match.group(3)
        if meridiem == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
        return hour, minute

    raise ValueError(f"Invalid time value: {value}")


def _parse_cron_style_schedule(value: str) -> ScheduleInfo | None:
    match = re.fullmatch(r"(.+?)\s+([0-9apm:\s]+)", value)
    if not match:
        return None

    schedule_key = re.sub(r"\s+", " ", match.group(1).strip())
    time_part = re.sub(r"\s+", " ", match.group(2).strip())
    day_info = _DAY_ALIASES.get(schedule_key)
    if day_info is None:
        return None

    hour, minute = _parse_clock_time(time_part)
    normalized_day, weekdays = day_info
    normalized = f"{normalized_day} {hour:02d}:{minute:02d}"
    return ScheduleInfo(
        normalized=normalized,
        interval_seconds=None,
        every_run=False,
        cron_weekdays=weekdays,
        cron_hour=hour,
        cron_minute=minute,
    )


def normalize_schedule(raw_value: str) -> ScheduleInfo:
    value = re.sub(r"\s+", " ", raw_value.strip().lower())
    if value == "every-run":
        return ScheduleInfo(normalized="every-run", interval_seconds=None, every_run=True)

    cron_schedule = _parse_cron_style_schedule(value)
    if cron_schedule is not None:
        return cron_schedule

    every_prefix = re.fullmatch(r"every\s+(.+)", value)
    if every_prefix:
        value = every_prefix.group(1).strip()

    # symbolic aliases
    aliases = {
        "hourly": "1h",
        "every hour": "1h",
        "daily": "24h",
        "every day": "24h",
    }
    value = aliases.get(value, value)
    value = re.sub(r"\s+", "", value)

    # minute/hour/day words
    word_match = re.fullmatch(r"(\d+)(minutes?|hours?|days?)", value)
    if word_match:
        amount = word_match.group(1)
        unit_text = word_match.group(2)
        unit = (
            "m" if unit_text.startswith("minute") else "h" if unit_text.startswith("hour") else "d"
        )
        value = f"{amount}{unit}"

    seconds = parse_duration_to_seconds(value)
    return ScheduleInfo(normalized=value, interval_seconds=seconds, every_run=False)


def _normalize_active_schedule(raw_value: str) -> str:
    value = re.sub(r"\s+", " ", raw_value.strip().lower())
    return value


def _parse_task_steps(task_id: str, raw_steps: Any) -> list[dict[str, Any]]:
    def _normalize_single(step: Any, index: int) -> dict[str, Any]:
        if not isinstance(step, dict):
            raise ValueError(f"Task '{task_id}' step #{index} must be a table/object")
        skill_name = step.get("skill_name")
        if not isinstance(skill_name, str) or not skill_name.strip():
            raise ValueError(f"Task '{task_id}' step #{index} requires non-empty 'skill_name'")

        action_raw = step.get("action")
        action = str(action_raw).strip().lower() if action_raw is not None else "run_skill"
        if action not in {"run_skill", "read_skill_resource"}:
            raise ValueError(
                f"Task '{task_id}' step #{index} has invalid action '{action}'. "
                "Allowed: run_skill, read_skill_resource"
            )

        args = step.get("args")
        if args is None:
            normalized_args: dict[str, Any] = {}
        elif isinstance(args, dict):
            normalized_args = args
        else:
            raise ValueError(f"Task '{task_id}' step #{index} field 'args' must be a table/object")

        normalized_step: dict[str, Any] = {
            "action": action,
            "skill_name": skill_name.strip(),
            "args": normalized_args,
        }

        function_name = (
            step.get("function") or step.get("function_or_script_name") or step.get("script")
        )
        resource_name = step.get("resource_name")
        if action == "run_skill":
            if not isinstance(function_name, str) or not function_name.strip():
                raise ValueError(
                    f"Task '{task_id}' step #{index} requires 'function' for run_skill action"
                )
            normalized_step["function_or_script_name"] = function_name.strip()
        else:
            if not isinstance(resource_name, str) or not resource_name.strip():
                raise ValueError(
                    f"Task '{task_id}' step #{index} requires 'resource_name' for read_skill_resource action"
                )
            normalized_step["resource_name"] = resource_name.strip()
        return normalized_step

    if isinstance(raw_steps, dict):
        return [_normalize_single(raw_steps, 1)]
    if isinstance(raw_steps, list):
        if not raw_steps:
            raise ValueError(f"Task '{task_id}' field 'task' cannot be an empty list")
        return [_normalize_single(step, index + 1) for index, step in enumerate(raw_steps)]
    raise ValueError(
        f"Task '{task_id}' field 'task' must be a table/object or list of tables/objects"
    )


def _parse_task_table(task_id: str, table: Any) -> dict[str, Any]:
    if not isinstance(table, dict):
        raise ValueError(f"Task '{task_id}' must be a TOML table/object")

    if "task" not in table:
        raise ValueError(f"Task '{task_id}' missing required field: task")

    interval_raw = table.get("interval")
    schedule_raw = table.get("schedule")
    if interval_raw is not None and schedule_raw is not None:
        raise ValueError(f"Task '{task_id}' must define exactly one of 'interval' or 'schedule'")
    if interval_raw is None and schedule_raw is None:
        raise ValueError(f"Task '{task_id}' must define one of 'interval' or 'schedule'")

    schedule_source = interval_raw if interval_raw is not None else schedule_raw
    if not isinstance(schedule_source, str) or not schedule_source.strip():
        raise ValueError(f"Task '{task_id}' scheduling field must be a non-empty string")
    schedule_info = normalize_schedule(schedule_source)

    active_schedule_raw = table.get("active_schedule")
    if active_schedule_raw is not None and not isinstance(active_schedule_raw, str):
        raise ValueError(f"Task '{task_id}' field 'active_schedule' must be a string")

    enabled_raw = table.get("enabled", True)
    if not isinstance(enabled_raw, bool):
        raise ValueError(f"Task '{task_id}' field 'enabled' must be a boolean")

    priority_raw = str(table.get("priority", "normal")).lower()
    if priority_raw not in ALLOWED_PRIORITIES:
        raise ValueError(
            f"Task '{task_id}' has invalid priority '{priority_raw}'. Allowed: {sorted(ALLOWED_PRIORITIES)}"
        )

    depends_on_raw = table.get("depends_on", [])
    if isinstance(depends_on_raw, str):
        depends_on = [item.strip() for item in depends_on_raw.split(",") if item.strip()]
    elif isinstance(depends_on_raw, list):
        depends_on = [str(item).strip() for item in depends_on_raw if str(item).strip()]
    else:
        raise ValueError(f"Task '{task_id}' field 'depends_on' must be a string or list")

    tags_raw = table.get("tags", [])
    if isinstance(tags_raw, str):
        tags = [item.strip() for item in tags_raw.split(",") if item.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(item).strip() for item in tags_raw if str(item).strip()]
    else:
        raise ValueError(f"Task '{task_id}' field 'tags' must be a string or list")

    max_retries_raw = table.get("max_retries")
    max_retries = None
    if max_retries_raw is not None:
        if isinstance(max_retries_raw, int):
            max_retries = max_retries_raw
        elif isinstance(max_retries_raw, str):
            max_retries = _to_int(max_retries_raw, field_name="max_retries")
        else:
            raise ValueError(f"Task '{task_id}' field 'max_retries' must be an integer")

    steps = _parse_task_steps(task_id, table["task"])
    title = table.get("title", task_id)
    if not isinstance(title, str):
        raise ValueError(f"Task '{task_id}' field 'title' must be a string")

    known_keys = {
        "title",
        "enabled",
        "priority",
        "interval",
        "schedule",
        "task",
        "active_schedule",
        "cooldown",
        "timeout",
        "max_retries",
        "state_key",
        "depends_on",
        "tags",
    }

    return {
        "section": task_id,
        "id": task_id,
        "title": title,
        "enabled": enabled_raw,
        "priority": priority_raw,
        "schedule": schedule_info.normalized,
        "schedule_info": {
            "normalized": schedule_info.normalized,
            "interval_seconds": schedule_info.interval_seconds,
            "every_run": schedule_info.every_run,
            "cron_weekdays": list(schedule_info.cron_weekdays)
            if schedule_info.cron_weekdays is not None
            else None,
            "cron_hour": schedule_info.cron_hour,
            "cron_minute": schedule_info.cron_minute,
        },
        "task": table["task"],
        "steps": steps,
        "cooldown": table.get("cooldown"),
        "timeout": table.get("timeout"),
        "active_schedule": active_schedule_raw,
        "max_retries": max_retries,
        "state_key": table.get("state_key"),
        "depends_on": depends_on,
        "tags": tags,
        "unknown_fields": {key: value for key, value in table.items() if key not in known_keys},
    }


def _parse_time_hhmm(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", value.strip())
    if not match:
        raise ValueError(f"Invalid time value: {value}")
    return int(match.group(1)), int(match.group(2))


def _is_within_time_window(now: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    start_h, start_m = _parse_time_hhmm(start_hhmm)
    end_h, end_m = _parse_time_hhmm(end_hhmm)
    minutes_now = now.hour * 60 + now.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    # Same start/end means full-day activity.
    if start_minutes == end_minutes:
        return True

    if start_minutes < end_minutes:
        return start_minutes <= minutes_now < end_minutes
    # Cross-midnight window, e.g. 22:00-06:00.
    return minutes_now >= start_minutes or minutes_now < end_minutes


def _is_active_now(task: dict[str, Any], now: datetime) -> bool:
    raw_active = task.get("active_schedule")
    if not raw_active:
        return True

    schedule = _normalize_active_schedule(raw_active)

    day_filter_match = re.match(r"^(weekdays|weekends)\b", schedule)
    day_filter: str | None = None
    if day_filter_match:
        day_filter = day_filter_match.group(1)
        schedule = schedule[day_filter_match.end() :].strip()

    # Allow optional glue words.
    for prefix in ("between ", "from "):
        if schedule.startswith(prefix):
            schedule = schedule[len(prefix) :].strip()
            break

    # Strip optional "to" form.
    schedule = schedule.replace(" to ", "-")

    if day_filter == "weekdays" and now.weekday() >= 5:
        return False
    if day_filter == "weekends" and now.weekday() < 5:
        return False

    if not schedule:
        return True

    window_match = re.fullmatch(
        r"([01]?\d:[0-5]\d|2[0-3]:[0-5]\d)\s*-\s*([01]?\d:[0-5]\d|2[0-3]:[0-5]\d)", schedule
    )
    if window_match:
        return _is_within_time_window(now, window_match.group(1), window_match.group(2))

    # Comma-separated mini DSL: weekdays, between 09:00-17:00
    tokens = [token.strip() for token in schedule.split(",") if token.strip()]
    if not tokens:
        return True
    for token in tokens:
        if token in {"weekdays", "weekends"}:
            if token == "weekdays" and now.weekday() >= 5:
                return False
            if token == "weekends" and now.weekday() < 5:
                return False
            continue
        token = token.replace("between ", "").replace("from ", "").replace(" to ", "-").strip()
        token_match = re.fullmatch(
            r"([01]?\d:[0-5]\d|2[0-3]:[0-5]\d)\s*-\s*([01]?\d:[0-5]\d|2[0-3]:[0-5]\d)",
            token,
        )
        if token_match and not _is_within_time_window(
            now, token_match.group(1), token_match.group(2)
        ):
            return False
    return True


def parse_scheduler(content: str) -> dict[str, Any]:
    if not content.strip():
        raise ValueError("SCHEDULER.toml is empty")

    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid SCHEDULER.toml: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("SCHEDULER.toml must decode to a top-level table/object")

    agent_raw = parsed.get("agent", "default")
    if not isinstance(agent_raw, str) or not agent_raw.strip():
        raise ValueError("SCHEDULER.toml field 'agent' must be a non-empty string")

    version_raw = parsed.get("version", 1)
    if isinstance(version_raw, int):
        version = version_raw
    elif isinstance(version_raw, str):
        version = _to_int(version_raw, field_name="version")
    else:
        raise ValueError("SCHEDULER.toml field 'version' must be an integer")

    tasks: list[dict[str, Any]] = []
    header_keys = {"agent", "version"}
    for key, value in parsed.items():
        if key in header_keys:
            continue
        tasks.append(_parse_task_table(task_id=key, table=value))

    if not tasks:
        raise ValueError("SCHEDULER.toml must define at least one task table")

    return {
        "agent": agent_raw.strip(),
        "version": version,
        "header_fields": {"agent": agent_raw, "version": str(version)},
        "tasks": tasks,
    }


def read_scheduler(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing SCHEDULER.toml at {path}")
    return parse_scheduler(path.read_text())


def _default_run_record() -> dict[str, Any]:
    return {
        "run_id": "",
        "started_at": "",
        "finished_at": "",
        "status": "skipped",
        "reason": "",
        "dedup_key": None,
        "observed_value": None,
        "error": None,
    }


def _default_task_state(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": task["title"],
        "state_key": task.get("state_key"),
        "enabled": task.get("enabled", True),
        "last_run": None,
        "last_success": None,
        "last_failure": None,
        "cooldown_until": None,
        "consecutive_successes": 0,
        "consecutive_failures": 0,
        "last_observed_value": None,
        "last_alerted_at": None,
        "last_seen_dedup_key": None,
        "recent_runs": [],
        "unknown_fields": deepcopy(task.get("unknown_fields", {})),
    }


def initialize_state(scheduler: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    return {
        "schema_version": 1,
        "agent": scheduler.get("agent", "default"),
        "updated_at": _iso(now),
        "scheduler": {
            "last_started_at": None,
            "last_finished_at": None,
            "last_status": "success",
            "last_error": None,
            "run_count": 0,
        },
        "tasks": {task["id"]: _default_task_state(task) for task in scheduler.get("tasks", [])},
    }


def read_state(
    path: Path, scheduler: dict[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    now = now or utc_now()
    if path.exists():
        loaded = json.loads(path.read_text())
    else:
        loaded = initialize_state(scheduler, now=now)

    loaded.setdefault("schema_version", 1)
    loaded["agent"] = scheduler.get("agent", loaded.get("agent", "default"))
    loaded.setdefault("updated_at", _iso(now))
    loaded.setdefault("scheduler", {})
    loaded["scheduler"].setdefault("last_started_at", None)
    loaded["scheduler"].setdefault("last_finished_at", None)
    loaded["scheduler"].setdefault("last_status", "success")
    loaded["scheduler"].setdefault("last_error", None)
    loaded["scheduler"].setdefault("run_count", 0)
    loaded.setdefault("tasks", {})

    for task in scheduler.get("tasks", []):
        task_state = loaded["tasks"].setdefault(task["id"], _default_task_state(task))
        task_state["title"] = task["title"]
        task_state["state_key"] = task.get("state_key")
        task_state["enabled"] = task.get("enabled", True)
        task_state.setdefault("recent_runs", [])
        task_state.setdefault("unknown_fields", deepcopy(task.get("unknown_fields", {})))

    return loaded


def write_state_atomic(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, indent=2, sort_keys=False) + "\n")
    temp_path.replace(path)


def _parse_iso_to_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _get_previous_scheduled(info: dict[str, Any], now: datetime) -> datetime:
    hour = info.get("cron_hour")
    minute = info.get("cron_minute")
    if hour is None or minute is None:
        raise ValueError("cron_hour and cron_minute are required for cron-style schedules")

    now_utc = now.astimezone(timezone.utc)
    candidate = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > now_utc:
        candidate -= timedelta(days=1)

    weekdays = info.get("cron_weekdays")
    if weekdays is None:
        return candidate

    weekday_set = {int(day) for day in weekdays}
    for _ in range(8):
        if candidate.weekday() in weekday_set:
            return candidate
        candidate -= timedelta(days=1)
    raise ValueError("Unable to compute previous scheduled occurrence for cron-style schedule")


def _is_due(task: dict[str, Any], task_state: dict[str, Any], now: datetime) -> bool:
    info = task["schedule_info"]
    if info["every_run"]:
        return True
    last_run = task_state.get("last_run")
    if not last_run or not last_run.get("finished_at"):
        return True
    if info.get("cron_hour") is not None and info.get("cron_minute") is not None:
        previous = _get_previous_scheduled(info, now)
        last_finished = _parse_iso_to_utc(last_run["finished_at"])
        return last_finished < previous
    interval = info.get("interval_seconds")
    if interval is None:
        return True
    last_finished = _parse_iso_to_utc(last_run["finished_at"])
    return now >= last_finished + timedelta(seconds=interval)


def _has_unhealthy_dependencies(
    task: dict[str, Any], state: dict[str, Any], *, current_cycle_statuses: dict[str, str]
) -> bool:
    for dependency_id in task.get("depends_on", []):
        dep_status = current_cycle_statuses.get(dependency_id)
        if dep_status is not None:
            if dep_status != "success":
                return True
            continue
        dep_state = state.get("tasks", {}).get(dependency_id, {})
        last_run = dep_state.get("last_run")
        if not last_run or last_run.get("status") != "success":
            return True
    return False


def _record_run(task_state: dict[str, Any], run_record: dict[str, Any]) -> None:
    task_state["last_run"] = run_record
    task_state["recent_runs"] = [run_record] + list(task_state.get("recent_runs", []))
    task_state["recent_runs"] = task_state["recent_runs"][:RECENT_RUNS_LIMIT]
    task_state["last_observed_value"] = run_record.get("observed_value")
    task_state["last_seen_dedup_key"] = run_record.get("dedup_key")

    status = run_record["status"]
    if status == "success":
        task_state["last_success"] = run_record
        task_state["consecutive_successes"] = int(task_state.get("consecutive_successes", 0)) + 1
        task_state["consecutive_failures"] = 0
    elif status == "failure":
        task_state["last_failure"] = run_record
        task_state["consecutive_failures"] = int(task_state.get("consecutive_failures", 0)) + 1
        task_state["consecutive_successes"] = 0


def scheduler_tick(
    scheduler: dict[str, Any],
    state: dict[str, Any],
    *,
    now: datetime | None = None,
    task_results: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or utc_now()
    now_iso = _iso(now)
    task_results = task_results or {}

    sched_state = state["scheduler"]
    sched_state["last_started_at"] = now_iso
    cycle_statuses: dict[str, str] = {}
    summary: dict[str, Any] = {
        "started_at": now_iso,
        "finished_at": None,
        "executed": [],
        "skipped": [],
    }

    all_statuses: list[str] = []
    for task in scheduler.get("tasks", []):
        task_id = task["id"]
        task_state = state["tasks"].setdefault(task_id, _default_task_state(task))
        task_state["title"] = task["title"]
        task_state["state_key"] = task.get("state_key")
        task_state["enabled"] = task.get("enabled", True)
        task_state["unknown_fields"] = deepcopy(task.get("unknown_fields", {}))

        run_record = _default_run_record()
        run_record["run_id"] = f"scheduler-{now_iso}-{task_id}"
        run_record["started_at"] = now_iso
        run_record["finished_at"] = now_iso
        run_record["observed_value"] = None

        cooldown_until = task_state.get("cooldown_until")
        if not task.get("enabled", True):
            run_record["status"] = "skipped"
            run_record["reason"] = "Task is disabled"
        elif cooldown_until is not None and _parse_iso_to_utc(cooldown_until) > now:
            run_record["status"] = "skipped"
            run_record["reason"] = "Task is in cooldown"
        elif _has_unhealthy_dependencies(task, state, current_cycle_statuses=cycle_statuses):
            run_record["status"] = "skipped"
            run_record["reason"] = "Task dependencies are not healthy"
        elif not _is_due(task, task_state, now):
            run_record["status"] = "skipped"
            run_record["reason"] = "Task is not due"
        elif not _is_active_now(task, now):
            run_record["status"] = "skipped"
            run_record["reason"] = "Task is outside active_schedule"
        else:
            result = task_results.get(task_id)
            if result is None:
                run_record["status"] = "skipped"
                run_record["reason"] = "No task result provided"
            else:
                status = str(result.get("status", "skipped")).lower()
                if status not in {"success", "failure", "skipped"}:
                    status = "skipped"
                run_record["status"] = status
                run_record["reason"] = str(result.get("reason", ""))
                run_record["dedup_key"] = result.get("dedup_key")
                run_record["observed_value"] = result.get("observed_value")
                run_record["error"] = result.get("error")
                if status == "failure" and task.get("cooldown"):
                    cooldown_seconds = parse_duration_to_seconds(task["cooldown"])
                    task_state["cooldown_until"] = _iso(now + timedelta(seconds=cooldown_seconds))
                if result.get("alerted"):
                    task_state["last_alerted_at"] = now_iso

        _record_run(task_state, run_record)
        cycle_statuses[task_id] = run_record["status"]
        all_statuses.append(run_record["status"])

        if run_record["status"] == "skipped":
            summary["skipped"].append({"task_id": task_id, "reason": run_record["reason"]})
        else:
            summary["executed"].append(
                {"task_id": task_id, "status": run_record["status"], "reason": run_record["reason"]}
            )

    if all(status == "success" for status in all_statuses):
        scheduler_status = "success"
    elif any(status == "failure" for status in all_statuses) and any(
        status != "failure" for status in all_statuses
    ):
        scheduler_status = "partial"
    elif any(status == "failure" for status in all_statuses):
        scheduler_status = "failure"
    else:
        scheduler_status = "partial"

    sched_state["last_status"] = scheduler_status
    sched_state["last_error"] = None
    sched_state["last_finished_at"] = now_iso
    sched_state["run_count"] = int(sched_state.get("run_count", 0)) + 1
    state["updated_at"] = now_iso

    summary["finished_at"] = now_iso
    summary["status"] = scheduler_status
    return state, summary


__all__ = [
    "parse_scheduler",
    "read_scheduler",
    "read_state",
    "scheduler_tick",
    "write_state_atomic",
    "_default_task_state",
    "_has_unhealthy_dependencies",
    "_is_active_now",
    "_is_due",
    "_parse_iso_to_utc",
]
