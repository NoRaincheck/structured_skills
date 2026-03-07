# structured_skills

[![PyPI version](https://badge.fury.io/py/structured_skills.svg)](https://badge.fury.io/py/structured_skills) [![CI](https://github.com/NoRaincheck/structured_skills/actions/workflows/ci.yml/badge.svg)](https://github.com/NoRaincheck/structured_skills/actions/workflows/ci.yml)

Structured Skills for Agents - launch MCP servers from skill directories

## No LLM Required

**The goal of this library is that it works without any LLM.** Skills are explicitly defined with scripts and resources you control. Unlike AI agents that can execute arbitrary commands, structured_skills only runs what you've explicitly defined in your skill directories. Everything is gated by the scripts you write - no surprises, no unbounded execution.

## What It Supports

- MCP server for skill discovery and execution
- Direct CLI for listing/loading/running skills
- Scheduler definitions via `SCHEDULER.toml`
- Cron-style human schedules (for example `monday 9am`, `daily 9am`, `weekdays 09:30`)
- Interval schedules via `interval` (for example `5m`, `every 15m`, `1h`)
- Sequential task steps (`task` as one item or an ordered list)
- Per-session state isolation using `--working-dir`

## Usage

Quick usage to launch MCP server:

```sh
structured_skills run path/to/root/skills --working-dir /path/to/session-or-channel
```

To test via CLI:

```sh
structured_skills cli list_skills /path/to/root/skills
structured_skills cli load_skill /path/to/root/skills <skill_name>
structured_skills cli read_skill_resource /path/to/root/skills <skill_name> <resource_name>
# use explicit per-session/channel working directories
structured_skills cli --working-dir /path/to/session-or-channel run_skill_script /path/to/root/skills <skill_name> <function_name>
structured_skills cli load_scheduler /path/to/root/skills
structured_skills cli scheduler_tick /path/to/root/skills
```

Programmatically:

```py
from structured_skills import SkillRegistry

registry = SkillRegistry("/path/to/skills")

# List all available skills
registry.list_skills()

# Load full skill instructions
registry.load_skill(skill_name)

# Read a resource (file, script, or function info)
registry.read_skill_resource(skill_name, resource_name, args)

# Execute a skill function
registry.run_skill(skill_name, function_name, args)

# Scheduler
registry.load_scheduler()
registry.scheduler_tick()
```

## `SCHEDULER.toml`

`SCHEDULER.toml` lives at the root of your skills directory.

```toml
agent = "ops-agent"
version = 1

[daily-health]
interval = "5m" # or use schedule = "monday 9am"
active_schedule = "weekdays between 09:00-17:00"
task = [
  { skill_name = "memory", function = "store", args = { key = "health", value = "ok" } },
  { skill_name = "memory", function = "get", args = { key = "health" } }
]
```

Notes:

- Use exactly one of `interval` or `schedule` per task.
- `task` can be a single table or an array of tables.
- Without a daemon, `scheduler_tick` checks if a task already ran since its previous scheduled occurrence. If not, it runs immediately.

Persistence:

- `load_scheduler` only reads/parses `SCHEDULER.toml` and does not write state.
- Scheduler run state is stored in `scheduler-state.json`.
- On read, `scheduler_tick` prefers `<working-dir>/scheduler-state.json` and falls back to `<skill-root>/scheduler-state.json` if present.
- On write, `scheduler_tick` always persists to `<working-dir>/scheduler-state.json`.

For OpenClaw-aligned persistence, pass a session or channel directory via `--working-dir` (for example, `~/.openclaw/agents/<agentId>/sessions/<session_key>`). Skill state is stored under `<working-dir>/<skill-name>`.

## Validation

Perform checks with suggested fixes:

```sh
structured_skills check path/to/root/skills
structured_skills check path/to/root/skills --fix  # try to fix observed issues
```
