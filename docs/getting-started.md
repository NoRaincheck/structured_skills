# Getting Started

## Requirements

- Python `>=3.10`
- [`uv`](https://docs.astral.sh/uv/)

## Install

```sh
uv pip install structured_skills
```

## Run as MCP Server

```sh
uv run structured_skills run /path/to/root/skills
```

Optional flags:

- `--working-dir /path/to/session-or-channel` for isolated skill state
- `--session-name <name>` to label context
- `--include-skills skill_a skill_b` to allowlist skills
- `--exclude-skills skill_x` to block specific skills

## MCP Config Example

```json
{
  "mcpServers": {
    "skills": {
      "command": "uvx",
      "args": ["structured_skills", "run", "/path/to/root/skills"]
    }
  }
}
```

## Skill State Isolation

For OpenClaw-style persistence, pass a session or channel path via `--working-dir`.

State is stored under:

`<working-dir>/<skill-name>`
