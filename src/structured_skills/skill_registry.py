import os
import re
import subprocess
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Literal, NoReturn

import platformdirs

from structured_skills.cst.utils import execute_script as execute_script_impl
from structured_skills.cst.utils import extract_function_info
from structured_skills.platformdirs_utils import platformdir_env_override
from structured_skills.validator import find_skill_md, parse_frontmatter, validate

DEFAULT_SESSION_NAME = "default"
BASE_PLATFORM_DIR = Path(platformdirs.user_data_dir("structured_skills"))


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
    data_dir: Path

    @classmethod
    def create(cls, session_name: str | None = None) -> "SkillContext":
        session_name = session_name or DEFAULT_SESSION_NAME
        BASE_PLATFORM_DIR.mkdir(parents=True, exist_ok=True)
        return SkillContext(
            session_name=session_name,
            data_dir=BASE_PLATFORM_DIR / session_name,
        )


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
        self.context = context or SkillContext(
            session_name=DEFAULT_SESSION_NAME, data_dir=BASE_PLATFORM_DIR / DEFAULT_SESSION_NAME
        )

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

                    # Check context data_dir for skill-specific SKILL.md
                    if self.context is not None:
                        context_skill_md = find_skill_md(self.context.data_dir / skill_name)
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
        return {s.name: s.description for s in self.skills}

    def load_skill(self, skill_name: str) -> str:
        with platformdir_env_override(self.context.data_dir):
            skill = self.get_skill_by_name(skill_name)
            if skill is None:
                self._raise_skill_not_found("load_skill", skill_name)
            return skill.content

    def read_skill_resource(
        self, skill_name: str, resource_name: str, args: dict[str, Any] | None = None
    ) -> str | dict[str, str]:
        def _find_exact_resource(path, resource_name):
            exact_file_match = list(target_skill_dir.glob(resource_name)) + list(
                target_skill_dir.glob(f"*/{resource_name}")
            )
            if exact_file_match:
                file_target = exact_file_match.pop()
                return file_target.read_text()
            return None

        with platformdir_env_override(self.context.data_dir):
            skill = self.get_skill_by_name(skill_name)
            if skill is None:
                self._raise_skill_not_found("read_skill_resource", skill_name)

            # first check in context for exact match
            context_skill_dir = Path(platformdirs.user_data_dir(appname=skill_name))
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
                else:
                    cmd = [str(script_path)]
                    for key, val in args.items():
                        cmd.append(f"--{key}")
                        cmd.append(f"{val}")
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    return result.stdout

            scripts_dir = target_skill_dir / "scripts"
            if scripts_dir.exists():
                for script in scripts_dir.glob("*.py"):
                    content = script.read_text()
                    if f"def {resource_name}(" in content:
                        if args is None:
                            info = extract_function_info(content, resource_name)
                            return str(info)
                        else:
                            return execute_script_impl(
                                content,
                                resource_name,
                                args or {},
                                self.context.data_dir / skill_name,
                            )

        raise Exception(f"[read_skill_resource] Unable to find resource: {resource_name}")

    def run_skill(
        self,
        skill_name: str,
        function_or_script_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        with platformdir_env_override(self.context.data_dir):
            skill = self.get_skill_by_name(skill_name)
            if skill is None:
                self._raise_skill_not_found("run_skill", skill_name)

            target_skill_dir = skill.directory

            script_path = target_skill_dir / "scripts" / function_or_script_name
            if script_path.exists():
                env = os.environ.copy()
                result = subprocess.run([str(script_path)], capture_output=True, text=True, env=env)
                return result.stdout

            scripts_dir = target_skill_dir / "scripts"
            if scripts_dir.exists():
                for script in scripts_dir.glob("*.py"):
                    content = script.read_text()
                    if f"def {function_or_script_name}(" in content:
                        return str(
                            execute_script_impl(
                                content,
                                function_or_script_name,
                                args or {},
                                self.context.data_dir / skill_name,
                            )
                        )

        raise Exception(
            f"[run_skill] Failed to execute {skill_name} {function_or_script_name} {args}"
        )

        raise Exception(
            f"[run_skill] Failed to execute {skill_name} {function_or_script_name} {args}"
        )


def get_tool(
    registry: SkillRegistry,
    tool_name: Literal["list_skills", "load_skill", "read_skill_resource", "run_skill"],
):
    from structured_skills.tools import create_skill_tools

    tools = create_skill_tools(registry)
    func, description = tools[tool_name]
    func.__doc__ = description
    return func
