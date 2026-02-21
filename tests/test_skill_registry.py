import pytest
from structured_skills.skill_registry import SkillRegistry, get_tool


class TestSkillRegistry:
    def test_init(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        assert registry.skill_root_dir == temp_skill_dir

    def test_skills_property(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        skills = registry.skills
        assert len(skills) == 2
        skill_names = [s.name for s in skills]
        assert "example-skill" in skill_names
        assert "test-skill" in skill_names

    def test_get_skill_by_name(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        skill = registry.get_skill_by_name("example-skill")
        assert skill is not None
        assert skill.name == "example-skill"
        assert "example skill for testing" in skill.description.lower()

    def test_get_skill_by_name_not_found(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        skill = registry.get_skill_by_name("nonexistent")
        assert skill is None

    def test_get_skill_names(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        names = registry.get_skill_names()
        assert "example-skill" in names
        assert "test-skill" in names

    def test_list_skills(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        skills = registry.list_skills()
        assert isinstance(skills, dict)
        assert "example-skill" in skills

    def test_load_skill(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        content = registry.load_skill("example-skill")
        assert "# Example Skill" in content

    def test_load_skill_not_found(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        with pytest.raises(Exception, match="Could not find"):
            registry.load_skill("nonexistent-skill")

    def test_exclude_skills(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir, exclude_skills=["example-skill"])
        names = registry.get_skill_names()
        assert "example-skill" not in names
        assert "test-skill" in names

    def test_find_similar_skill_names(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        similar = registry.find_similar_skill_names("example-skil")
        assert "example-skill" in similar

    def test_read_skill_resource_content(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        content = registry.read_skill_resource("example-skill", "SKILL.md")
        assert "# Example Skill" in content

    def test_read_skill_resource_function_info(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        info = registry.read_skill_resource("test-skill", "greet")
        assert "greet" in str(info)

    def test_read_skill_resource_not_found(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        with pytest.raises(Exception, match="Unable to find resource"):
            registry.read_skill_resource("test-skill", "nonexistent")

    def test_run_skill_function(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        result = registry.run_skill("test-skill", "greet", {"name": "World"})
        assert "Hello, World!" in result

    def test_run_skill_function_add(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        result = registry.run_skill("test-skill", "add", {"a": 2, "b": 3})
        assert "5" in result

    def test_run_skill_not_found(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        with pytest.raises(Exception, match="Failed to execute"):
            registry.run_skill("test-skill", "nonexistent", {})


class TestSkill:
    def test_skill_dataclass(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        skill = registry.get_skill_by_name("example-skill")
        assert skill is not None
        assert skill.name == "example-skill"
        assert skill.description == "An example skill for testing"
        assert skill.directory.name == "example-skill"
        assert "# Example Skill" in skill.content


class TestGetTool:
    def test_get_list_skills_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tool = get_tool(registry, "list_skills")
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "List all available skills" in tool.__doc__

    def test_get_load_skill_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tool = get_tool(registry, "load_skill")
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "Load full instructions" in tool.__doc__

    def test_get_read_skill_resource_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tool = get_tool(registry, "read_skill_resource")
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "resource" in tool.__doc__.lower()

    def test_get_run_skill_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tool = get_tool(registry, "run_skill")
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "Execute" in tool.__doc__ or "scripts" in tool.__doc__

    def test_tool_execution(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        list_skills = get_tool(registry, "list_skills")
        result = list_skills()
        assert "example-skill" in result
