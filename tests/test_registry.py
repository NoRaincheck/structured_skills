from __future__ import annotations

from pathlib import Path

import pytest

from structured_skills.registry import SkillRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_search_lists_and_filters_skills() -> None:
    registry = SkillRegistry(FIXTURES)
    skills = registry.search()
    assert "echo-skill" in skills
    assert "math-skill" in skills

    matches = registry.search("arith")
    assert list(matches.keys()) == ["math-skill"]


def test_inspect_include_body_returns_skill_body() -> None:
    registry = SkillRegistry(FIXTURES)
    content = registry.inspect("echo-skill", include_body=True)
    assert "# Echo Skill" in content


def test_inspect_resource_reads_file_and_enforces_path_safety() -> None:
    registry = SkillRegistry(FIXTURES)
    content = registry.inspect("math-skill", resource_name="resources/README.txt")
    assert "deterministic resource" in content

    with pytest.raises(ValueError, match="escapes skill directory"):
        registry.inspect("math-skill", resource_name="../outside.txt")


def test_execute_function_and_script() -> None:
    registry = SkillRegistry(FIXTURES)
    function_result = registry.execute("math-skill", "add", {"a": 2, "b": 3})
    assert function_result == 5

    non_cli_script_result = registry.execute("math-skill", "math_ops.py", {"a": 2, "b": 3})
    assert non_cli_script_result == 5

    script_result = registry.execute("echo-skill", "echo.py", {"name": "Builder"})
    assert "Hello, Builder!" in script_result


def test_inspect_metadata_lists_targets() -> None:
    registry = SkillRegistry(FIXTURES)
    inspection = registry.inspect("echo-skill")
    assert isinstance(inspection, dict)
    assert "scripts/echo.py" in inspection["scripts"]
    assert "greet" in inspection["functions"]["echo.py"]


def test_execute_non_cli_ambiguous_script_raises() -> None:
    registry = SkillRegistry(FIXTURES)
    with pytest.raises(ValueError, match="Ambiguous non-CLI script target"):
        registry.execute("math-skill", "ambiguous_ops.py", {"a": 2, "b": 3})
