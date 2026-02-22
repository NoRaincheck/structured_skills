# structured_skills

[![PyPI version](https://badge.fury.io/py/structured_skills.svg)](https://badge.fury.io/py/structured_skills) [![CI](https://github.com/NoRaincheck/structured_skills/actions/workflows/test.yml/badge.svg)](https://github.com/NoRaincheck/structured_skills/actions/workflows/test.yml)

Structured Skills for Agents - launch MCP servers from skill directories

## No LLM Required

**This library works perfectly without any LLM.** Skills are explicitly defined with scripts and resources you control. Unlike AI agents that can execute arbitrary commands, structured_skills only runs what you've explicitly defined in your skill directories. Everything is gated by the scripts you write - no surprises, no unbounded execution.

## Usage

Quick usage to launch MCP server:

```sh
structured_skills run path/to/root/skills
```

To test via CLI:

```sh
structured_skills cli list_skills
structured_skills cli load_skill <skill_name>
structured_skills cli read_skill_resource <skill_name> <resource_name>
structured_skills cli run_skill <skill_name> <function_name>
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
```

## Validation

Perform checks with suggested fixes:

```sh
structured_skills check path/to/root/skills
structured_skills check path/to/root/skills --fix  # try to fix observed issues
```
