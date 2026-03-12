"""Builder for dynamic, SKILL-aware tool functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from structured_skills.registry import SkillRegistry

ToolName = Literal[
    "search",
    "inspect",
    "execute",
]


class SkillToolsBuilder:
    """Build callable tools from a registry."""

    TOOL_NAMES: tuple[ToolName, ...] = (
        "search",
        "inspect",
        "execute",
    )

    def __init__(self, registry: SkillRegistry, auto_build: bool = True):
        self.registry = registry
        self._callable_tools: dict[str, tuple[Callable[..., Any], str]] | None = None
        if auto_build:
            self.refresh()

    def refresh(self) -> dict[str, tuple[Callable[..., Any], str]]:
        """Rebuild tools and rebind convenience callables on the builder instance."""
        self._callable_tools = self._generate_callable_tools()
        for name, (func, _) in self._callable_tools.items():
            setattr(self, name, func)
        return self._callable_tools

    def _metadata_suffix(self) -> str:
        available_tools = ", ".join(self.TOOL_NAMES)
        available_skills = ", ".join(self.registry.get_skill_names())
        return f"\n\nExposed tools: {available_tools}\nAvailable skills: {available_skills}"

    def _generate_callable_tools(self) -> dict[str, tuple[Callable[..., Any], str]]:
        """
        Build base callables with dynamic descriptions.

        Returns:
            Mapping of tool name to `(callable, description)`.
        """
        suffix = self._metadata_suffix()
        tools: dict[str, tuple[Callable[..., Any], str]] = {}

        def search(query: str = "", limit: int = 10) -> dict[str, str]:
            return self.registry.search(query=query, limit=limit)

        tools["search"] = (
            search,
            "Search skills by name/description; empty query lists all skills." + suffix,
        )

        def inspect(
            skill_name: str, resource_name: str | None = None, include_body: bool = False
        ) -> dict[str, Any] | str:
            return self.registry.inspect(
                skill_name=skill_name,
                resource_name=resource_name,
                include_body=include_body,
            )

        tools["inspect"] = (
            inspect,
            "Inspect skill metadata, SKILL body, or a concrete resource file." + suffix,
        )

        def execute(skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
            return self.registry.execute(skill_name, target, args=args)

        tools["execute"] = (
            execute,
            "Execute a skill script or function using optional args." + suffix,
        )

        for name, (func, desc) in tools.items():
            setattr(func, "__name__", name)
            setattr(func, "__doc__", desc)
        return tools

    def build_callable_tools(
        self, force_rebuild: bool = False
    ) -> dict[str, tuple[Callable[..., Any], str]]:
        """
        Build base callables with dynamic descriptions.

        Returns:
            Mapping of tool name to `(callable, description)`.
        """
        if force_rebuild or self._callable_tools is None:
            return self.refresh()
        return self._callable_tools

    # Convenience methods for direct library usage with static typing support.
    def search(self, query: str = "", limit: int = 10) -> dict[str, str]:
        fn = self.build_callable_tools()["search"][0]
        return fn(query, limit)

    def inspect(
        self, skill_name: str, resource_name: str | None = None, include_body: bool = False
    ) -> dict[str, Any] | str:
        fn = self.build_callable_tools()["inspect"][0]
        return fn(skill_name, resource_name, include_body)

    def execute(self, skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
        fn = self.build_callable_tools()["execute"][0]
        return fn(skill_name, target, args)


def create_structured_skills(registry: SkillRegistry) -> dict[str, tuple[Callable[..., Any], str]]:
    """Create dynamic callable tools for direct Python integration."""
    return SkillToolsBuilder(registry).build_callable_tools()


def get_tool(registry: SkillRegistry, tool_name: ToolName) -> Callable[..., Any]:
    """Return one callable tool with dynamic docstring set."""
    tools = create_structured_skills(registry)
    func, description = tools[tool_name]
    func.__doc__ = description
    return func
