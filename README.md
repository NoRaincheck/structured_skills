# structured_skills

[![PyPI version](https://badge.fury.io/py/structured_skills.svg)](https://badge.fury.io/py/structured_skills) [![CI](https://github.com/NoRaincheck/structured_skills/actions/workflows/ci.yml/badge.svg)](https://github.com/NoRaincheck/structured_skills/actions/workflows/ci.yml)

Structured Skills for Agents - launch MCP servers from skill directories

## No LLM Required

**The goal of this library is that it works without any LLM.** Skills are explicitly defined with scripts and resources you control. Unlike AI agents that can execute arbitrary commands, structured_skills only runs what you've explicitly defined in your skill directories. Everything is gated by the scripts you write - no surprises, no unbounded execution.

## What It Supports

- Discover skills from a root directory containing skill folders with `SKILL.md`.
- Search and inspect skills and script/function targets.
- Read files under a skill directory with path-traversal protection.
- Execute:
  - script paths under `scripts/` (for example `echo.py`), or
  - function targets by name (for example `add`).

## Single-File Script Mode (uv)

The repository includes `structured_skills.py` as a single-file uv script:

```bash
uv run structured_skills.py <skills_dir> search [query] --limit 10
uv run structured_skills.py <skills_dir> inspect <skill_name> [resource_name] [--include-body]
uv run structured_skills.py <skills_dir> execute <skill_name> <target> --args '{"a":2,"b":3}'
```

Example:

```bash
uv run structured_skills.py tests/fixtures/skills search
uv run structured_skills.py tests/fixtures/skills inspect echo-skill
uv run structured_skills.py tests/fixtures/skills inspect echo-skill --include-body
uv run structured_skills.py tests/fixtures/skills inspect math-skill resources/README.txt
uv run structured_skills.py tests/fixtures/skills execute math-skill add --args '{"a":2,"b":3}'
uv run structured_skills.py tests/fixtures/skills mcp --server-name structured_skills
```

## Package Mode

Install/run via project tooling:

```bash
uv run pytest
uv run skill-tools tests/fixtures/skills search
uv run skill-tools tests/fixtures/skills mcp --server-name structured_skills
```

The console script entrypoint is `skill-tools` and maps to `structured_skills.main:main`.

## Heartbeat Daemon (Standalone)

The repository also includes a standalone stdlib-only scheduler at
`heartbeat_daemon.py`.

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

## MCP Server Mode (FastMCP)

`structured_skills` can run as an MCP server exposing three tools: `search`, `inspect`, and
`execute`.

- Single-file script mode:
  - `uv run structured_skills.py <skills_dir> mcp --server-name structured_skills`
- Package mode:
  - `uv run skill-tools <skills_dir> mcp --server-name structured_skills`

## Skill Proxy (Python API)

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

## Python API

Primary imports:

```python
from pathlib import Path
from structured_skills import SkillRegistry, SkillToolsBuilder

registry = SkillRegistry(Path("tests/fixtures/skills"))
result = registry.execute("math-skill", "add", {"a": 2, "b": 3})
print(result)
```
