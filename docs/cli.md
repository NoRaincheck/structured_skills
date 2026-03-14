# CLI Reference

The `skill-tools` CLI provides commands for searching, inspecting, and executing skills.

## search

Search for skills in a directory.

```bash
skill-tools <skills_dir> search [query] [--limit N]
```

| Argument     | Description                             |
| ------------ | --------------------------------------- |
| `skills_dir` | Root directory containing skill folders |
| `query`      | Optional search query to filter skills  |

| Option      | Description                             |
| ----------- | --------------------------------------- |
| `--limit N` | Maximum number of results (default: 10) |

## inspect

Inspect a skill's metadata, resources, scripts, and functions.

```bash
skill-tools <skills_dir> inspect <skill_name> [resource_name] [--include-body]
```

| Argument        | Description                             |
| --------------- | --------------------------------------- |
| `skills_dir`    | Root directory containing skill folders |
| `skill_name`    | Name of the skill to inspect            |
| `resource_name` | Optional specific resource to view      |

| Option           | Description                               |
| ---------------- | ----------------------------------------- |
| `--include-body` | Include full content of scripts/resources |

## execute

Execute a skill target (function or script) with given arguments.

```bash
skill-tools <skills_dir> execute <skill_name> <target> --args '<json>'
```

| Argument     | Description                             |
| ------------ | --------------------------------------- |
| `skills_dir` | Root directory containing skill folders |
| `skill_name` | Name of the skill to execute            |
| `target`     | Function name or script path            |

| Option            | Description                      |
| ----------------- | -------------------------------- |
| `--args '<json>'` | JSON object of arguments to pass |

## mcp

Run as an MCP server.

```bash
skill-tools <skills_dir> mcp --server-name <name>
```

| Option                 | Description                          |
| ---------------------- | ------------------------------------ |
| `--server-name <name>` | Name for the MCP server              |
| `--port <n>`           | Port to listen on (default: 8000)    |
| `--host <host>`        | Host to bind to (default: localhost) |

## Examples

```bash
# Search all skills
skill-tools tests/fixtures/skills search

# Search with query
skill-tools tests/fixtures/skills search math

# Inspect a skill
skill-tools tests/fixtures/skills inspect echo-skill

# Inspect with script bodies
skill-tools tests/fixtures/skills inspect echo-skill --include-body

# Inspect a specific resource
skill-tools tests/fixtures/skills inspect math-skill resources/README.txt

# Execute a function
skill-tools tests/fixtures/skills execute math-skill add --args '{"a":2,"b":3}'

# Run as MCP server
skill-tools tests/fixtures/skills mcp --server-name structured_skills
```
