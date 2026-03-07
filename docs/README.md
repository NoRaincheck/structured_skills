# Structured Skills

Structured, explicit skills for agents.

`structured_skills` launches an MCP server from skill directories and provides a deterministic CLI for listing, loading, and running skills.

## Why Structured Skills

- No hidden tool execution paths
- Explicit scripts and resources only
- Works without requiring an LLM runtime
- Per-session isolation with `--working-dir`
- Built-in scheduler support via `SCHEDULER.toml`

## Quick Start

```sh
# launch MCP server from a skills root
uv run structured_skills run /path/to/root/skills

# list skills through CLI
uv run structured_skills cli list_skills /path/to/root/skills
```

## MCP Configuration

Use a standard MCP config entry:

```json
{
  "mcpServers": {
    "skills": {
      "command": "uvx",
      "args": [
        "structured_skills",
        "run",
        "/path/to/root/skills"
      ]
    }
  }
}
```

## Docs Map

- [Getting Started](/getting-started)
- [CLI Reference](/cli)
- [Scheduler](/scheduler)
- [Validation](/validation)
- [smolagents Integration](/integrations/smolagents)
