# Skill Tools

`skill_tools` discovers SKILL.md-based skills, inspects runnable targets, reads skill
resources, and executes deterministic Python scripts/functions inside each skill.

## What It Supports

- Discover skills from a root directory containing skill folders with `SKILL.md`.
- Search and inspect skills and script/function targets.
- Read files under a skill directory with path-traversal protection.
- Execute:
  - script paths under `scripts/` (for example `echo.py`), or
  - function targets by name (for example `add`).

## Single-File Script Mode (uv)

The repository includes `skill_tools.py` as a single-file uv script:

```bash
uv run skill_tools.py <skills_dir> search [query] --limit 10
uv run skill_tools.py <skills_dir> inspect <skill_name> [resource_name] [--include-body]
uv run skill_tools.py <skills_dir> execute <skill_name> <target> --args '{"a":2,"b":3}'
```

Example:

```bash
uv run skill_tools.py tests/fixtures/skills search
uv run skill_tools.py tests/fixtures/skills inspect echo-skill
uv run skill_tools.py tests/fixtures/skills inspect echo-skill --include-body
uv run skill_tools.py tests/fixtures/skills inspect math-skill resources/README.txt
uv run skill_tools.py tests/fixtures/skills execute math-skill add --args '{"a":2,"b":3}'
uv run skill_tools.py tests/fixtures/skills mcp --server-name skill_tools
```

## Package Mode

Install/run via project tooling:

```bash
uv run pytest
uv run skill-tools tests/fixtures/skills search
uv run skill-tools tests/fixtures/skills mcp --server-name skill_tools
```

The console script entrypoint is `skill-tools` and maps to `skill_tools.main:main`.

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

`skill_tools` can run as an MCP server exposing three tools: `search`, `inspect`, and
`execute`.

- Single-file script mode:
  - `uv run skill_tools.py <skills_dir> mcp --server-name skill_tools`
- Package mode:
  - `uv run skill-tools <skills_dir> mcp --server-name skill_tools`

## Python API

Primary imports:

```python
from pathlib import Path
from skill_tools import SkillRegistry, SkillToolsBuilder

registry = SkillRegistry(Path("tests/fixtures/skills"))
tools = SkillToolsBuilder(registry).build_callable_tools()
result = tools["execute"][0]("math-skill", "add", {"a": 2, "b": 3})
```
