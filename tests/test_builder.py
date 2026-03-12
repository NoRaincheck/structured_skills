from __future__ import annotations

from pathlib import Path

from structured_skills.builder import SkillToolsBuilder, get_tool
from structured_skills.registry import SkillRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_builder_includes_dynamic_docstring_metadata() -> None:
    registry = SkillRegistry(FIXTURES)
    tools = SkillToolsBuilder(registry).build_callable_tools()
    _, description = tools["execute"]
    assert "Exposed tools:" in description
    assert "Available skills:" in description
    assert "echo-skill" in description
    assert "math-skill" in description


def test_get_tool_sets_doc_and_executes() -> None:
    registry = SkillRegistry(FIXTURES)
    execute = get_tool(registry, "execute")
    assert execute.__doc__ is not None
    assert "Available skills:" in execute.__doc__
    result = execute("math-skill", "add", {"a": 4, "b": 5})
    assert result == 9


def test_builder_binds_convenience_tool_methods() -> None:
    registry = SkillRegistry(FIXTURES)
    tools = SkillToolsBuilder(registry)
    searchable = tools.search()
    assert "math-skill" in searchable
    inspection = tools.inspect("echo-skill")
    assert isinstance(inspection, dict)
    assert inspection["name"] == "echo-skill"
    result = tools.execute("math-skill", "add", {"a": 3, "b": 7})
    assert result == 10
