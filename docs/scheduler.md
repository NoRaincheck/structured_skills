# Scheduler

`SCHEDULER.toml` enables scheduled task execution from your skill root.

## Location

Place `SCHEDULER.toml` at the root of your skills directory.

## Example

```toml
agent = "ops-agent"
version = 1

[daily-health]
interval = "5m" # or: schedule = "monday 9am"
active_schedule = "weekdays between 09:00-17:00"
task = [
  { skill_name = "memory", function = "store", args = { key = "health", value = "ok" } },
  { skill_name = "memory", function = "get", args = { key = "health" } }
]
```

## Rules

- Use exactly one of `interval` or `schedule` per task.
- `task` can be a single table or an array of tables for ordered steps.
- `scheduler_tick` runs due tasks based on the current schedule state.

## Persistence

- `load_scheduler` is config-only: it reads/parses `SCHEDULER.toml` and does not persist state.
- Scheduler execution state lives in `scheduler-state.json`.
- Read precedence for ticks:
  - `<working-dir>/scheduler-state.json`
  - fallback `<skill-root>/scheduler-state.json`
- Write target for ticks:
  - always `<working-dir>/scheduler-state.json`

## CLI

```sh
uv run structured_skills cli load_scheduler /path/to/root/skills
uv run structured_skills cli scheduler_tick /path/to/root/skills
```
