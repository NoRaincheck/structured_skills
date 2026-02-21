from typing import TYPE_CHECKING

from structured_skills.skill_registry import SkillRegistry

if TYPE_CHECKING:
    from smolagents import Tool


def create_smolagents_tools(
    registry: SkillRegistry, tools: list[str] | None = None
) -> list["Tool"]:
    """
    Create smolagents Tool instances from a SkillRegistry.

    Args:
        registry: The SkillRegistry to create tools from
        tools: Optional list of tool names to create. If None, creates all tools.
               Valid names: "list_skills", "load_skill", "read_skill_resource", "run_skill"

    Returns:
        List of smolagents Tool instances
    """
    from smolagents import Tool

    tool_names = tools or [
        "list_skills",
        "load_skill",
        "read_skill_resource",
        "run_skill",
    ]
    result: list[Tool] = []

    skill_names = registry.get_skill_names()
    skills_info = f"Available skills: {', '.join(skill_names)}"

    class ListSkillsTool(Tool):
        name = "list_skills"
        description = f"List all available skills. Returns a mapping of skill names to their descriptions. {skills_info}"
        inputs = {}
        output_type = "object"

        def forward(self) -> dict[str, str]:
            return registry.list_skills()

    class LoadSkillTool(Tool):
        name = "load_skill"
        description = f"Load full instructions for a specific skill by name. {skills_info}"
        inputs = {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill to load",
            },
        }
        output_type = "string"

        def forward(self, skill_name: str) -> str:
            return registry.load_skill(skill_name)

    class ReadSkillResourceTool(Tool):
        name = "read_skill_resource"
        description = (
            f"Load full resource file, script, or function for a specific skill. {skills_info}"
        )
        inputs = {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill",
            },
            "resource_name": {
                "type": "string",
                "description": "Name of the resource to read",
            },
            "args": {
                "type": "object",
                "description": "Optional arguments for the resource",
                "nullable": True,
            },
        }
        output_type = "string"

        def forward(self, skill_name: str, resource_name: str, args: dict | None = None) -> str:
            result = registry.read_skill_resource(skill_name, resource_name, args)
            return str(result) if not isinstance(result, str) else result

    class RunSkillTool(Tool):
        name = "run_skill"
        description = f"Execute skill scripts or functions with optional arguments. {skills_info}"
        inputs = {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill",
            },
            "function_name": {
                "type": "string",
                "description": "Name of the function or script to run",
            },
            "args": {
                "type": "object",
                "description": "Optional arguments for the function",
                "nullable": True,
            },
        }
        output_type = "string"

        def forward(self, skill_name: str, function_name: str, args: dict | None = None) -> str:
            return registry.run_skill(skill_name, function_name, args)

    tool_classes = {
        "list_skills": ListSkillsTool,
        "load_skill": LoadSkillTool,
        "read_skill_resource": ReadSkillResourceTool,
        "run_skill": RunSkillTool,
    }

    for name in tool_names:
        if name in tool_classes:
            result.append(tool_classes[name]())

    return result
