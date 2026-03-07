from pathlib import Path

from mcp.server.fastmcp import FastMCP

from structured_skills.skill_registry import SkillContext, SkillRegistry
from structured_skills.tools import create_skill_tools


def create_mcp_server(
    skill_root_dir: Path,
    server_name: str = "structured_skills",
    exclude_skills: list[str] = [],
    include_skills: list[str] | None = None,
    session_name: str | None = None,
    working_dir: Path | None = None,
) -> FastMCP:
    mcp = FastMCP(server_name)
    context = SkillContext.create(session_name=session_name, working_dir=working_dir)
    registry = SkillRegistry(
        skill_root_dir,
        exclude_skills=exclude_skills,
        include_skills=include_skills,
        context=context,
    )
    tools = create_skill_tools(registry)

    list_skills_func, list_skills_desc = tools["list_skills"]
    load_skill_func, load_skill_desc = tools["load_skill"]
    read_resource_func, read_resource_desc = tools["read_skill_resource"]
    run_skill_func, run_skill_desc = tools["run_skill"]
    load_scheduler_func, load_scheduler_desc = tools["load_scheduler"]
    scheduler_tick_func, scheduler_tick_desc = tools["scheduler_tick"]

    @mcp.tool(description=list_skills_desc)
    def list_skills() -> dict[str, str]:
        return list_skills_func()

    @mcp.tool(description=load_skill_desc)
    def load_skill(skill_name: str) -> str:
        return load_skill_func(skill_name)

    @mcp.tool(description=read_resource_desc)
    def read_skill_resource(skill_name: str, resource_name: str, args: dict | None = None) -> str:
        result = read_resource_func(skill_name, resource_name, args)
        return str(result) if not isinstance(result, str) else result

    @mcp.tool(description=run_skill_desc)
    def run_skill(skill_name: str, function_name: str, args: dict | None = None) -> str:
        return run_skill_func(skill_name, function_name, args)

    @mcp.tool(description=load_scheduler_desc)
    def load_scheduler() -> dict:
        return load_scheduler_func()

    @mcp.tool(description=scheduler_tick_desc)
    def scheduler_tick(task_results: dict | None = None, now: str | None = None) -> dict:
        return scheduler_tick_func(task_results, now)

    return mcp
