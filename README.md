# structured_skills

Structured Skills for Agents - launch MCP servers from skill directories

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

## smolagents Integration

structured_skills provides integration with [smolagents](https://github.com/huggingface/smolagents):

```sh
uv pip install structured_skills[smolagents]
```

```py
from structured_skills import SkillRegistry
from structured_skills.smolagents import create_smolagents_tools

registry = SkillRegistry("/path/to/skills")

# Create all tools
tools = create_smolagents_tools(registry)

# Or create specific tools
tools = create_smolagents_tools(registry, tools=["list_skills", "load_skill"])

# Use with smolagents
from smolagents import CodeAgent, HfApiModel

agent = CodeAgent(tools=tools, model=HfApiModel())
agent.run("List available skills")
```

## Validation

Perform checks with suggested fixes:

```sh
structured_skills check path/to/root/skills
structured_skills check path/to/root/skills --fix  # try to fix observed issues
```
