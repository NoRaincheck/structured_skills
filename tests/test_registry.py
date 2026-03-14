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


def test_inspect_function_by_name_returns_info() -> None:
    registry = SkillRegistry(FIXTURES)
    info = registry.inspect("math-skill", resource_name="add")
    assert isinstance(info, dict)
    assert info["name"] == "add"
    assert "signature" in info
    assert "return" in info
    assert info["return"] == "int"


def test_inspect_function_with_docstring() -> None:
    registry = SkillRegistry(FIXTURES)
    info = registry.inspect("math-skill", resource_name="add")
    assert "docstring" not in info


def test_inspect_resource_file_still_works() -> None:
    registry = SkillRegistry(FIXTURES)
    content = registry.inspect("math-skill", resource_name="resources/README.txt")
    assert "deterministic resource" in content


def test_skill_proxy_returns_proxy_object() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("math-skill")
    assert proxy is not None


def test_skill_proxy_calls_function() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("math-skill")
    result = proxy.add(a=2, b=3)
    assert result == 5


def test_skill_proxy_calls_script() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("math-skill")
    result = proxy.math_ops(a=2, b=3)
    assert result == 5


def test_skill_proxy_echo_script() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("echo-skill")
    result = proxy.echo(name="Builder")
    assert "Hello, Builder!" in result


def test_skill_proxy_unknown_attribute_raises() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("math-skill")
    with pytest.raises(AttributeError, match="has no function or script"):
        proxy.nonexistent()


def test_skill_proxy_function_positional_args() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("math-skill")
    result = proxy.add(2, 3)
    assert result == 5


def test_skill_proxy_function_mixed_args() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("math-skill")
    result = proxy.add(2, b=3)
    assert result == 5


def test_skill_proxy_function_duplicate_args_raises() -> None:
    registry = SkillRegistry(FIXTURES)
    proxy = registry.skill("math-skill")
    with pytest.raises(TypeError, match="multiple values"):
        proxy.add(2, b=3, a=5)


def test_skill_proxy_unknown_skill_raises() -> None:
    registry = SkillRegistry(FIXTURES)
    with pytest.raises(KeyError, match="Skill not found"):
        registry.skill("nonexistent-skill")
