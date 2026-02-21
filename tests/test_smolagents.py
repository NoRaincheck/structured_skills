from structured_skills.skill_registry import SkillRegistry
from structured_skills.smolagents import create_smolagents_tools


class TestCreateSmolagentsTools:
    def test_create_all_tools(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tools = create_smolagents_tools(registry)
        assert len(tools) == 4
        tool_names = [t.name for t in tools]
        assert "list_skills" in tool_names
        assert "load_skill" in tool_names
        assert "read_skill_resource" in tool_names
        assert "run_skill" in tool_names

    def test_create_specific_tools(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tools = create_smolagents_tools(registry, tools=["list_skills", "load_skill"])
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "list_skills" in tool_names
        assert "load_skill" in tool_names

    def test_list_skills_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tools = create_smolagents_tools(registry, tools=["list_skills"])
        tool = tools[0]
        result = tool.forward()
        assert isinstance(result, dict)
        assert "example-skill" in result
        assert "test-skill" in result

    def test_load_skill_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tools = create_smolagents_tools(registry, tools=["load_skill"])
        tool = tools[0]
        result = tool.forward("example-skill")
        assert "# Example Skill" in result

    def test_read_skill_resource_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tools = create_smolagents_tools(registry, tools=["read_skill_resource"])
        tool = tools[0]
        result = tool.forward("example-skill", "SKILL.md")
        assert "# Example Skill" in result

    def test_run_skill_tool(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tools = create_smolagents_tools(registry, tools=["run_skill"])
        tool = tools[0]
        result = tool.forward("test-skill", "greet", {"name": "World"})
        assert "Hello, World!" in result

    def test_tool_descriptions_include_skills(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        tools = create_smolagents_tools(registry, tools=["list_skills"])
        tool = tools[0]
        assert "example-skill" in tool.description
        assert "test-skill" in tool.description
