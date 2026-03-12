"""FastMCP server wiring for structured_skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from structured_skills.builder import SkillToolsBuilder
from structured_skills.registry import SkillRegistry


def create_mcp_server(skill_root_dir: Path, server_name: str = "structured_skills") -> Any:
    """Create a FastMCP server exposing skill tool operations."""
    fastmcp_module = __import__("mcp.server.fastmcp", fromlist=["FastMCP"])
    fastmcp_class = getattr(fastmcp_module, "FastMCP")

    mcp = fastmcp_class(server_name)
    registry = SkillRegistry(skill_root_dir)
    tools = SkillToolsBuilder(registry).build_callable_tools()

    search_func, search_desc = tools["search"]
    inspect_func, inspect_desc = tools["inspect"]
    execute_func, execute_desc = tools["execute"]

    @mcp.tool(description=search_desc)
    def search(query: str = "", limit: int = 10) -> dict[str, str]:
        return search_func(query=query, limit=limit)

    @mcp.tool(description=inspect_desc)
    def inspect(
        skill_name: str, resource_name: str | None = None, include_body: bool = False
    ) -> dict[str, Any] | str:
        return inspect_func(
            skill_name=skill_name,
            resource_name=resource_name,
            include_body=include_body,
        )

    @mcp.tool(description=execute_desc)
    def execute(skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
        return execute_func(skill_name=skill_name, target=target, args=args)

    return mcp
