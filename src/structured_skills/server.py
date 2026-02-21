from pathlib import Path

from mcp.server.fastmcp import FastMCP

from structured_skills.skill_registry import SkillRegistry


def create_mcp_server(
    skill_root_dir: Path, server_name: str = "structured_skills", exclude_skills: list[str] = []
) -> FastMCP:
    mcp = FastMCP(server_name)
    registry = SkillRegistry(skill_root_dir, exclude_skills=exclude_skills)

    skill_names = registry.get_skill_names()
    skills_info = f"\n\nAvailable skills: {', '.join(skill_names)}"

    @mcp.tool(
        description=f"List all available skills. Returns a mapping of skill names to their descriptions.{skills_info}"
    )
    def list_skills() -> dict[str, str]:
        """List all available skills. Returns a mapping of skill names to their descriptions."""
        return registry.list_skills()

    @mcp.tool(description=f"Load full instructions for a specific skill by name.{skills_info}")
    def load_skill(skill_name: str) -> str:
        """Load full instructions for a specific skill by name."""
        return registry.load_skill(skill_name)

    @mcp.tool(
        description=f"Load full resource file, script, or function for a specific skill.{skills_info}"
    )
    def read_skill_resource(skill_name: str, resource_name: str, args: dict | None = None) -> str:
        """Load full resource file, script, or function for a specific skill."""
        result = registry.read_skill_resource(skill_name, resource_name, args)
        return str(result) if not isinstance(result, str) else result

    @mcp.tool(
        description=f"Execute skill scripts or functions with optional arguments.{skills_info}"
    )
    def run_skill(skill_name: str, function_name: str, args: dict | None = None) -> str:
        """Execute skill scripts or functions with optional arguments."""
        return registry.run_skill(skill_name, function_name, args)

    return mcp
