import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Literal, NoReturn

from structured_skills.cst.utils import execute_script as execute_script_impl
from structured_skills.cst.utils import extract_function_info
from structured_skills.scheduler import (
    _default_task_state,
    _has_unhealthy_dependencies,
    _is_active_now,
    _is_due,
    _parse_iso_to_utc,
    read_scheduler,
    read_state,
    write_state_atomic,
)
from structured_skills.scheduler import (
    scheduler_tick as scheduler_tick_impl,
)
from structured_skills.validator import find_skill_md, parse_frontmatter, validate

DEFAULT_SESSION_NAME = "default"
DEFAULT_CONTEXT_DIRNAME = ".structured_skills"
SCHEDULER_FILENAME = "SCHEDULER.toml"
SCHEDULER_STATE_FILENAME = "scheduler-state.json"


def _sanitize_skill_name(name: str) -> str:
    """
    Convert a skill name to a valid Python identifier.

    - Replaces hyphens and spaces with underscores
    - Removes invalid characters
    - Ensures it doesn't start with a number
    """
    # Replace common separators with underscores
    sanitized = name.replace("-", "_").replace(" ", "_")
    # Remove any characters that aren't alphanumeric or underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "", sanitized)
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


@dataclass
class Skill:
    name: str
    description: str
    directory: Path
    content: str


@dataclass
class SkillContext:
    session_name: str
    working_dir: Path

    @classmethod
    def create(
        cls,
        session_name: str | None = None,
        working_dir: Path | None = None,
    ) -> "SkillContext":
        resolved_session = session_name or DEFAULT_SESSION_NAME
        resolved_working_dir = (
            Path(working_dir)
            if working_dir is not None
            else Path.cwd() / DEFAULT_CONTEXT_DIRNAME / resolved_session
        )
        resolved_working_dir.mkdir(parents=True, exist_ok=True)
        return SkillContext(
            session_name=resolved_session,
            working_dir=resolved_working_dir,
        )

    @property
    def data_dir(self) -> Path:
        """Backward-compatible alias for older callers."""
        return self.working_dir


class SkillRegistry:
    def __init__(
        self,
        skill_root_dir: Path,
        exclude_skills: list[str] = [],
        include_skills: list[str] | None = None,
        context: SkillContext | None = None,
    ):
        self.skill_root_dir = Path(skill_root_dir)
        self._skills: list[Skill] | None = None
        self._exclude_skills: list[str] = exclude_skills
        self._include_skills: list[str] | None = include_skills
        self.context = context or SkillContext.create()

    def _raise_skill_not_found(self, context: str, skill_name: str) -> NoReturn:
        similar = self.find_similar_skill_names(skill_name)
        msg = f"[{context}] Could not find: {skill_name}"
        if similar:
            msg += f" Did you mean {similar}?"
        raise Exception(msg)

    def _load_skills(self) -> list[Skill]:
        skills = []
        validation_issues = []
        for skill_dir in self.skill_root_dir.glob("*"):
            if skill_dir.is_dir() and len(validate(skill_dir)) == 0:
                skill_md = find_skill_md(skill_dir)
                if skill_md:
                    content = skill_md.read_text()
                    metadata, body = parse_frontmatter(content)
                    skill_name = metadata["name"]

                    # Apply include/exclude filters
                    if self._include_skills is not None:
                        if skill_name not in self._include_skills:
                            continue
                    elif skill_name in self._exclude_skills:
                        continue

                    # Check context working_dir for skill-specific SKILL.md
                    context_skill_md = find_skill_md(self.context.working_dir / skill_name)
                    if context_skill_md is not None and context_skill_md.exists():
                        # append additional content
                        content = f"{content.strip()}\n\n{context_skill_md.read_text()}"

                    skills.append(
                        Skill(
                            name=skill_name,
                            description=metadata["description"],
                            directory=skill_dir,
                            content=body,
                        )
                    )
            elif skill_dir.is_dir():
                validation_issues.extend(validate(skill_dir))
        if not skills:
            validation_issues_text = (
                "" if len(validation_issues) == 0 else f" Validation issues: {validation_issues}"
            )
            raise Exception(
                f"No skills found in the directory: {self.skill_root_dir}.{validation_issues_text}"
            )
        return skills

    @property
    def skills(self) -> list[Skill]:
        # we intentionally reload skills, since some skills dynamically update SKILL.md
        return self._load_skills()

    def get_skill_by_name(self, name: str) -> Skill | None:
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None

    def get_skill_names(self) -> list[str]:
        return [s.name for s in self.skills]

    def find_similar_skill_names(self, name: str) -> list[str]:
        return get_close_matches(name, self.get_skill_names(), n=3, cutoff=0.6)

    def list_skills(self) -> dict[str, str]:
        """Return all available skills mapped to their descriptions."""
        return {s.name: s.description for s in self.skills}

    def load_skill(self, skill_name: str) -> str:
        """Load and return the markdown body for a named skill."""
        skill = self.get_skill_by_name(skill_name)
        if skill is None:
            self._raise_skill_not_found("load_skill", skill_name)
        return skill.content

    def _get_scheduler_path(self) -> Path:
        path = self.skill_root_dir / SCHEDULER_FILENAME
        if not path.exists():
            raise FileNotFoundError(f"Missing {SCHEDULER_FILENAME} in {self.skill_root_dir}")
        return path

    def _get_scheduler_state_read_path(self) -> Path:
        context_state = self.context.working_dir / SCHEDULER_STATE_FILENAME
        if context_state.exists():
            return context_state
        root_state = self.skill_root_dir / SCHEDULER_STATE_FILENAME
        if root_state.exists():
            return root_state
        return context_state

    def _get_scheduler_state_write_path(self) -> Path:
        return self.context.working_dir / SCHEDULER_STATE_FILENAME

    def load_scheduler(self) -> dict[str, Any]:
        """Read and parse the root `SCHEDULER.toml` configuration."""
        scheduler_path = self._get_scheduler_path()
        return read_scheduler(scheduler_path)

    def _execute_scheduler_steps(self, task: dict[str, Any]) -> dict[str, Any]:
        steps = task.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return {"status": "skipped", "reason": "No task steps configured"}

        outputs: list[dict[str, Any]] = []
        chained_context: dict[str, Any] = {}
        for index, step in enumerate(steps, start=1):
            action = str(step.get("action", "run_skill"))
            skill_name = str(step.get("skill_name", ""))
            raw_args = step.get("args")
            if raw_args is None:
                raw_args = {}
            if not isinstance(raw_args, dict):
                return {
                    "status": "failure",
                    "reason": f"Step {index} args must be a table/object",
                    "error": f"Invalid args type: {type(raw_args).__name__}",
                }
            args = dict(raw_args)
            try:
                if action == "run_skill":
                    function_or_script_name = str(step.get("function_or_script_name", ""))
                    if not function_or_script_name:
                        return {
                            "status": "failure",
                            "reason": f"Step {index} missing function_or_script_name",
                            "error": "Missing function_or_script_name",
                        }
                    args = self._inject_chained_context(
                        skill_name=skill_name,
                        function_name=function_or_script_name,
                        explicit_args=args,
                        chained_context=chained_context,
                    )
                    run_output = self.run_skill_with_metadata(
                        skill_name=skill_name,
                        function_or_script_name=function_or_script_name,
                        args=args,
                    )
                    outputs.append({"step": index, "action": action, **run_output})
                    chained_context = self._build_step_context(run_output)
                elif action == "read_skill_resource":
                    resource_name = str(step.get("resource_name", ""))
                    if not resource_name:
                        return {
                            "status": "failure",
                            "reason": f"Step {index} missing resource_name",
                            "error": "Missing resource_name",
                        }
                    args = self._inject_chained_context(
                        skill_name=skill_name,
                        function_name=resource_name,
                        explicit_args=args,
                        chained_context=chained_context,
                    )
                    output = self.read_skill_resource(skill_name, resource_name, args)
                    run_output = self._format_run_output(
                        skill_name=skill_name,
                        function_or_script_name=resource_name,
                        args=args,
                        output=output,
                    )
                    outputs.append(
                        {
                            "step": index,
                            "action": action,
                            "resource_name": resource_name,
                            **run_output,
                        }
                    )
                    chained_context = self._build_step_context(run_output)
                else:
                    return {
                        "status": "failure",
                        "reason": f"Step {index} has unsupported action '{action}'",
                        "error": f"Unsupported action: {action}",
                    }
            except Exception as exc:
                return {
                    "status": "failure",
                    "reason": f"Step {index} failed",
                    "error": str(exc),
                    "observed_value": {"completed_steps": outputs},
                }

        return {
            "status": "success",
            "reason": f"Executed {len(outputs)} step(s)",
            "observed_value": {"steps": outputs},
        }

    def _parse_json_if_possible(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return ""
        try:
            return json.loads(stripped)
        except Exception:
            return value

    def _format_run_output(
        self,
        *,
        skill_name: str,
        function_or_script_name: str,
        args: dict[str, Any] | None,
        output: Any,
    ) -> dict[str, Any]:
        return {
            "skill": skill_name,
            "task": function_or_script_name,
            "args": args or {},
            "result": self._parse_json_if_possible(output),
        }

    def _resolve_function_source(self, target_skill_dir: Path, function_name: str) -> str | None:
        scripts_dir = target_skill_dir / "scripts"
        if not scripts_dir.exists():
            return None
        for script in scripts_dir.glob("*.py"):
            content = script.read_text()
            if f"def {function_name}(" in content:
                return content
        return None

    def _get_function_parameters(
        self, target_skill_dir: Path, function_name: str
    ) -> set[str] | None:
        source = self._resolve_function_source(target_skill_dir, function_name)
        if source is None:
            return None
        try:
            info = extract_function_info(source, function_name)
        except Exception:
            return None
        return {param.name for param in info.parameters}

    def _build_step_context(self, run_output: dict[str, Any]) -> dict[str, Any]:
        result = run_output.get("result")
        context = {
            "skill": run_output.get("skill"),
            "task": run_output.get("task"),
            "args": run_output.get("args", {}),
            "result": result,
        }
        if isinstance(result, dict):
            for key, value in result.items():
                context.setdefault(str(key), value)
        return context

    def _inject_chained_context(
        self,
        *,
        skill_name: str,
        function_name: str,
        explicit_args: dict[str, Any],
        chained_context: dict[str, Any],
    ) -> dict[str, Any]:
        if not chained_context:
            return explicit_args
        skill = self.get_skill_by_name(skill_name)
        if skill is None:
            return explicit_args

        accepted = self._get_function_parameters(skill.directory, function_name)
        if not accepted:
            return explicit_args

        merged = dict(chained_context)
        merged.update(explicit_args)
        return {key: value for key, value in merged.items() if key in accepted}

    def _build_scheduler_task_results(
        self, scheduler: dict[str, Any], state: dict[str, Any], now_dt: datetime
    ) -> dict[str, dict[str, Any]]:
        task_results: dict[str, dict[str, Any]] = {}
        cycle_statuses: dict[str, str] = {}
        for task in scheduler.get("tasks", []):
            task_id = task["id"]
            task_state = state["tasks"].setdefault(task_id, _default_task_state(task))
            cooldown_until = task_state.get("cooldown_until")
            if not task.get("enabled", True):
                cycle_statuses[task_id] = "skipped"
                continue
            if cooldown_until is not None and _parse_iso_to_utc(cooldown_until) > now_dt:
                cycle_statuses[task_id] = "skipped"
                continue
            if _has_unhealthy_dependencies(task, state, current_cycle_statuses=cycle_statuses):
                cycle_statuses[task_id] = "skipped"
                continue
            if not _is_due(task, task_state, now_dt):
                cycle_statuses[task_id] = "skipped"
                continue
            if not _is_active_now(task, now_dt):
                cycle_statuses[task_id] = "skipped"
                continue
            result = self._execute_scheduler_steps(task)
            cycle_statuses[task_id] = str(result.get("status", "skipped"))
            task_results[task_id] = result
        return task_results

    def scheduler_tick(
        self,
        task_results: dict[str, dict[str, Any]] | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        """
        Run one scheduler cycle and persist updated scheduler state.

        Args:
            task_results: Optional precomputed task result overrides keyed by task id.
            now: Optional UTC timestamp (`ISO 8601`) used for deterministic ticks.

        Returns:
            Metadata describing scheduler/state paths and cycle summary.
        """
        scheduler = self.load_scheduler()
        state_path = self._get_scheduler_state_read_path()
        state = read_state(state_path, scheduler)
        parsed_now = (
            datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(timezone.utc)
            if now
            else datetime.now(timezone.utc)
        )
        resolved_task_results = (
            task_results
            if task_results is not None
            else self._build_scheduler_task_results(scheduler, state, parsed_now)
        )
        updated_state, tick_summary = scheduler_tick_impl(
            scheduler, state, now=parsed_now, task_results=resolved_task_results
        )
        write_state_atomic(self._get_scheduler_state_write_path(), updated_state)
        return {
            "scheduler_path": str(self._get_scheduler_path()),
            "state_path": str(self._get_scheduler_state_write_path()),
            "summary": tick_summary,
        }

    def read_skill_resource(
        self, skill_name: str, resource_name: str, args: dict[str, Any] | None = None
    ) -> str | dict[str, str]:
        """
        Read a skill resource, script source, or execute a named resource function.

        If `resource_name` matches a file it is returned as text. If it matches a
        script/function and `args` are provided, the resource is executed and its
        output is returned.
        """

        def _find_exact_resource(path: Path, target_resource_name: str) -> str | None:
            exact_file_match = list(path.glob(target_resource_name)) + list(
                path.glob(f"*/{target_resource_name}")
            )
            if exact_file_match:
                file_target = exact_file_match.pop()
                return file_target.read_text()
            return None

        skill = self.get_skill_by_name(skill_name)
        if skill is None:
            self._raise_skill_not_found("read_skill_resource", skill_name)

        # first check in context for exact match
        context_skill_dir = self.context.working_dir / skill_name
        target_skill_dir = skill.directory
        resource_output = _find_exact_resource(
            context_skill_dir, resource_name
        ) or _find_exact_resource(target_skill_dir, resource_name)
        if resource_output is not None:
            return resource_output

        if "." in resource_name:
            raise Exception(f"[read_skill_resource] Unable to find resource: {resource_name}")

        script_path = target_skill_dir / f"scripts/{resource_name}.py"
        if script_path.exists():
            if args is None:
                return script_path.read_text()
            cmd = [str(script_path)]
            for key, val in args.items():
                cmd.append(f"--{key}")
                cmd.append(f"{val}")
            skill_working_dir = self.context.working_dir / skill_name
            skill_working_dir.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=skill_working_dir)
            return result.stdout

        scripts_dir = target_skill_dir / "scripts"
        if scripts_dir.exists():
            for script in scripts_dir.glob("*.py"):
                content = script.read_text()
                if f"def {resource_name}(" in content:
                    if args is None:
                        info = extract_function_info(content, resource_name)
                        return str(info)
                    return execute_script_impl(
                        content,
                        resource_name,
                        args or {},
                        self.context.working_dir / skill_name,
                    )

        raise Exception(f"[read_skill_resource] Unable to find resource: {resource_name}")

    def run_skill(
        self,
        skill_name: str,
        function_or_script_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        """Execute a skill script/function and return its output as a string."""
        return str(self._run_skill_raw(skill_name, function_or_script_name, args))

    def _run_skill_raw(
        self,
        skill_name: str,
        function_or_script_name: str,
        args: dict[str, Any] | None = None,
    ) -> Any:
        skill = self.get_skill_by_name(skill_name)
        if skill is None:
            self._raise_skill_not_found("run_skill", skill_name)

        target_skill_dir = skill.directory
        skill_working_dir = self.context.working_dir / skill_name
        skill_working_dir.mkdir(parents=True, exist_ok=True)

        script_path = target_skill_dir / "scripts" / function_or_script_name
        if script_path.exists():
            env = os.environ.copy()
            result = subprocess.run(
                [str(script_path)],
                capture_output=True,
                text=True,
                env=env,
                cwd=skill_working_dir,
            )
            return result.stdout

        content = self._resolve_function_source(target_skill_dir, function_or_script_name)
        if content is not None:
            return execute_script_impl(
                content,
                function_or_script_name,
                args or {},
                skill_working_dir,
            )

        raise Exception(
            f"[run_skill] Failed to execute {skill_name} {function_or_script_name} {args}"
        )

    def run_skill_with_metadata(
        self,
        skill_name: str,
        function_or_script_name: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output = self._run_skill_raw(skill_name, function_or_script_name, args)
        return self._format_run_output(
            skill_name=skill_name,
            function_or_script_name=function_or_script_name,
            args=args,
            output=output,
        )


def get_tool(
    registry: SkillRegistry,
    tool_name: Literal[
        "list_skills",
        "load_skill",
        "read_skill_resource",
        "run_skill",
        "load_scheduler",
        "scheduler_tick",
    ],
):
    from structured_skills.tools import create_skill_tools

    tools = create_skill_tools(registry)
    func, description = tools[tool_name]
    func.__doc__ = description
    return func
