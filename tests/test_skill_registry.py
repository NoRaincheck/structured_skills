import json

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

    def test_run_skill_with_metadata_json_shape(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        result = registry.run_skill_with_metadata("test-skill", "add", {"a": 2, "b": 3})
        assert result["skill"] == "test-skill"
        assert result["task"] == "add"
        assert result["args"] == {"a": 2, "b": 3}
        assert result["result"] == 5

    def test_run_skill_not_found(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        with pytest.raises(Exception, match="Failed to execute"):
            registry.run_skill("test-skill", "nonexistent", {})

    def test_load_scheduler(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        scheduler = registry.load_scheduler()
        assert scheduler["agent"] == "test-agent"
        assert len(scheduler["tasks"]) == 1
        assert scheduler["tasks"][0]["id"] == "test-check"

    def test_scheduler_tick_writes_context_state(self, temp_skill_dir, tmp_path):
        context_dir = tmp_path / "session-a"
        registry = SkillRegistry(temp_skill_dir, context=None)
        registry.context.working_dir = context_dir
        result = registry.scheduler_tick(
            task_results={
                "test-check": {
                    "status": "success",
                    "reason": "Signal healthy",
                    "dedup_key": "signal-ok",
                    "observed_value": {"ok": True},
                }
            },
            now="2026-03-07T09:30:00Z",
        )
        assert "summary" in result
        assert result["summary"]["status"] == "success"
        state_path = context_dir / "scheduler-state.json"
        assert state_path.exists()
        state_content = state_path.read_text()
        assert '"status": "success"' in state_content

    def test_scheduler_tick_auto_executes_toml_steps(self, temp_skill_dir, tmp_path):
        registry = SkillRegistry(temp_skill_dir)
        registry.context.working_dir = tmp_path / "auto-session"
        result = registry.scheduler_tick(now="2026-03-07T09:30:00Z")
        assert "summary" in result
        assert result["summary"]["status"] == "success"
        state_path = registry.context.working_dir / "scheduler-state.json"
        state_content = state_path.read_text()
        assert "Executed 1 step(s)" in state_content

    def test_scheduler_tick_step_failure_short_circuits(self, temp_skill_dir, tmp_path):
        scheduler_path = temp_skill_dir / "SCHEDULER.toml"
        scheduler_path.write_text(
            """agent = "test-agent"
version = 1

[test-check]
schedule = "every-run"
task = [
  { skill_name = "test-skill", function = "nonexistent", args = {} },
  { skill_name = "test-skill", function = "greet", args = { name = "World" } }
]
"""
        )
        registry = SkillRegistry(temp_skill_dir)
        registry.context.working_dir = tmp_path / "failure-session"
        result = registry.scheduler_tick(now="2026-03-07T09:30:00Z")
        assert "summary" in result
        assert result["summary"]["status"] == "failure"
        state_path = registry.context.working_dir / "scheduler-state.json"
        state_content = state_path.read_text()
        assert "Step 1 failed" in state_content

    def test_scheduler_tick_chains_context_between_steps(self, temp_skill_dir, tmp_path):
        scheduler_path = temp_skill_dir / "SCHEDULER.toml"
        scheduler_path.write_text(
            """agent = "test-agent"
version = 1

[test-check]
schedule = "every-run"
task = [
  { skill_name = "test-skill", function = "greet", args = { name = "World" } },
  { skill_name = "test-skill", function = "consume_result", args = { prefix = "Result: " } }
]
"""
        )
        registry = SkillRegistry(temp_skill_dir)
        registry.context.working_dir = tmp_path / "chained-session"
        result = registry.scheduler_tick(now="2026-03-07T09:30:00Z")
        assert result["summary"]["status"] == "success"
        state_path = registry.context.working_dir / "scheduler-state.json"
        state = json.loads(state_path.read_text())
        runs = state["tasks"]["test-check"]["recent_runs"]
        step_outputs = runs[0]["observed_value"]["steps"]
        assert step_outputs[1]["result"]["combined"] == "Result: Hello, World!"


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

    def test_get_scheduler_tools(self, temp_skill_dir):
        registry = SkillRegistry(temp_skill_dir)
        load_scheduler = get_tool(registry, "load_scheduler")
        scheduler_tick = get_tool(registry, "scheduler_tick")
        parsed = load_scheduler()
        assert parsed["agent"] == "test-agent"
        tick = scheduler_tick(now="2026-03-07T09:30:00Z")
        assert "summary" in tick
