# Structured Skills

Structured, explicit skills for agents - **no LLM required**.

The goal of this library is that it works without any LLM. Skills are explicitly defined with scripts and resources you control. Unlike AI agents that can execute arbitrary commands, structured_skills only runs what you've explicitly defined in your skill directories. Everything is gated by the scripts you write - no surprises, no unbounded execution.

## What It Supports

- Discover skills from a root directory containing skill folders with `SKILL.md`
- Search and inspect skills and script/function targets
- Read files under a skill directory with path-traversal protection
- Execute:
  - Script paths under `scripts/` (for example `echo.py`)
  - Function targets by name (for example `add`)

## CLI Commands

The package provides the `skill-tools` CLI:

```bash
# Search skills
skill-tools <skills_dir> search [query] --limit 10

# Inspect a skill
skill-tools <skills_dir> inspect <skill_name> [resource_name] [--include-body]

# Execute a skill target
skill-tools <skills_dir> execute <skill_name> <target> --args '{"a":2,"b":3}'

# Run as MCP server
skill-tools <skills_dir> mcp --server-name structured_skills
```

Example:

```bash
skill-tools tests/fixtures/skills search
skill-tools tests/fixtures/skills inspect echo-skill
skill-tools tests/fixtures/skills inspect echo-skill --include-body
skill-tools tests/fixtures/skills inspect math-skill resources/README.txt
skill-tools tests/fixtures/skills execute math-skill add --args '{"a":2,"b":3}'
```

## Python API

Primary imports:

```python
from pathlib import Path
from structured_skills import SkillRegistry, SkillToolsBuilder

registry = SkillRegistry(Path("tests/fixtures/skills"))
result = registry.execute("math-skill", "add", {"a": 2, "b": 3})
print(result)
```

## Skill Proxy

The registry provides a `skill()` method that returns a proxy object, allowing you to call skill functions and scripts as if they were methods on an object:

```python
from pathlib import Path
from structured_skills import SkillRegistry

registry = SkillRegistry(Path("skills"))

# Call a function directly
proxy = registry.skill("math-skill")
result = proxy.add(a=2, b=3)  # Returns 5

# Call a script
result = proxy.math_ops(a=2, b=3)  # Returns 5

# Works with positional args too
result = proxy.add(2, 3)  # Returns 5
```

The proxy:

- Discovers functions and scripts in the skill's `scripts/` directory
- Lets you call them as Python methods with keyword or positional arguments
- Raises `AttributeError` if the function/script doesn't exist
- Raises `TypeError` for duplicate argument values

## MCP Server Mode

`structured_skills` can run as an MCP server exposing three tools: `search`, `inspect`, and `execute`.

```bash
skill-tools <skills_dir> mcp --server-name structured_skills
```

## Heartbeat Daemon

The repository includes a standalone stdlib-only scheduler at `heartbeat_daemon.py`.

Run it with:

```bash
uv run heartbeat_daemon.py scheduler.toml
```

`scheduler.toml` uses a flat root with named task tables:

```toml
version = 1

[daemon]
heartbeat = "1m"
timezone = "UTC"
state_file = "./scheduler-state.json"
shell = "/bin/sh"

[tasks.poll-inbox]
run = "bin/poll-inbox"
every = "5m"

[tasks.daily-summary]
run = "bin/daily-summary"
at = "09:00"

[tasks.backfill-march]
run = "bin/backfill --month 2026-03"
at = "2026-03-15T04:00:00Z"
```

Each task must define `run` and exactly one schedule mode:

- `every = "<duration>"` for recurring runs
- `at = "HH:MM"` or `at = "HH:MM:SS"` for daily runs
- `at = "<ISO timestamp>"` for one-off runs

Optional task keys currently supported:

- `enabled = true`
- `timeout = "10m"`
- `start_at = "..."` (for `every` tasks)
