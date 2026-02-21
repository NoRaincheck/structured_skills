from collections.abc import Callable
from typing import Any

from structured_skills.skill_registry import SkillRegistry


def create_skill_tools(registry: SkillRegistry) -> dict[str, tuple[Callable[..., Any], str]]:
    """Create tool functions for a skill registry.

    Returns a dict mapping tool names to (function, description) tuples.
    """
    skill_names = registry.get_skill_names()
    skills_info = f"\n\nAvailable skills: {', '.join(skill_names)}"

    tools: dict[str, tuple[Callable[..., Any], str]] = {}

    def list_skills() -> dict[str, str]:
        return registry.list_skills()

    tools["list_skills"] = (
        list_skills,
        f"List all available skills. Returns a mapping of skill names to their descriptions.{skills_info}",
    )

    def load_skill(skill_name: str) -> str:
        return registry.load_skill(skill_name)

    tools["load_skill"] = (
        load_skill,
        f"Load full instructions for a specific skill by name.{skills_info}",
    )

    def read_skill_resource(
        skill_name: str, resource_name: str, args: dict[str, Any] | None = None
    ) -> str | dict[str, str]:
        return registry.read_skill_resource(skill_name, resource_name, args)

    tools["read_skill_resource"] = (
        read_skill_resource,
        f"Load full resource file, script, or function for a specific skill.{skills_info}",
    )

    def run_skill(
        skill_name: str,
        function_or_script_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        return registry.run_skill(skill_name, function_or_script_name, args)

    tools["run_skill"] = (
        run_skill,
        f"Execute skill scripts or functions with optional arguments.{skills_info}",
    )

    return tools
