"""SKILL.md discovery, resource reading, and deterministic execution."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from structured_skills.ast_utils import execute_script as execute_script_impl
from structured_skills.ast_utils import extract_function_info


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse a lightweight YAML-like frontmatter block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    closing_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_index = idx
            break
    if closing_index is None:
        return {}, text

    metadata: dict[str, str] = {}
    for line in lines[1:closing_index]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("'\"")

    body = "\n".join(lines[closing_index + 1 :]).lstrip("\n")
    return metadata, body


@dataclass(frozen=True)
class Skill:
    """A discovered skill from a directory containing SKILL.md."""

    name: str
    description: str
    directory: Path
    skill_md_path: Path
    skill_md_body: str


class SkillRegistry:
    """Registry for discovering and executing deterministic skill resources."""

    def __init__(self, skill_root_dir: Path):
        self.skill_root_dir = Path(skill_root_dir)

    @property
    def skills(self) -> list[Skill]:
        return self._discover_skills()

    def _discover_skills(self) -> list[Skill]:
        if not self.skill_root_dir.exists():
            raise FileNotFoundError(f"Skill root does not exist: {self.skill_root_dir}")

        skills: list[Skill] = []
        for skill_dir in sorted(p for p in self.skill_root_dir.iterdir() if p.is_dir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            raw = skill_md.read_text(encoding="utf-8")
            metadata, body = _parse_frontmatter(raw)
            name = metadata.get("name", skill_dir.name)
            description = metadata.get("description", f"Skill at {skill_dir.name}")
            skills.append(
                Skill(
                    name=name,
                    description=description,
                    directory=skill_dir,
                    skill_md_path=skill_md,
                    skill_md_body=body,
                )
            )

        if not skills:
            raise ValueError(f"No skills with SKILL.md found in: {self.skill_root_dir}")
        return skills

    def get_skill_names(self) -> list[str]:
        return [skill.name for skill in self.skills]

    def search(self, query: str = "", limit: int = 10) -> dict[str, str]:
        needle = query.strip().lower()
        if not needle:
            return {skill.name: skill.description for skill in self.skills}
        matches: dict[str, str] = {}
        for skill in self.skills:
            if needle in skill.name.lower() or needle in skill.description.lower():
                matches[skill.name] = skill.description
            if len(matches) >= limit:
                break
        return matches

    def get_skill_by_name(self, skill_name: str) -> Skill | None:
        for skill in self.skills:
            if skill.name == skill_name:
                return skill
        return None

    def _require_skill(self, skill_name: str, context: str) -> Skill:
        skill = self.get_skill_by_name(skill_name)
        if skill is None:
            raise KeyError(f"[{context}] Skill not found: {skill_name}")
        return skill

    def _resolve_resource_path(self, skill_dir: Path, resource_name: str) -> Path:
        if Path(resource_name).is_absolute():
            raise ValueError("Absolute paths are not allowed for resources")
        candidate = (skill_dir / resource_name).resolve()
        if skill_dir.resolve() not in candidate.parents and candidate != skill_dir.resolve():
            raise ValueError("Resource path escapes skill directory")
        return candidate

    def inspect(
        self, skill_name: str, resource_name: str | None = None, include_body: bool = False
    ) -> dict[str, Any] | str:
        skill = self._require_skill(skill_name, "inspect")

        if resource_name is not None:
            if resource_name == "SKILL.md":
                return skill.skill_md_path.read_text(encoding="utf-8")
            candidate = self._resolve_resource_path(skill.directory, resource_name)
            if not candidate.exists() or not candidate.is_file():
                raise FileNotFoundError(f"Resource not found: {resource_name}")
            return candidate.read_text(encoding="utf-8")

        if include_body:
            return skill.skill_md_body

        scripts_dir = skill.directory / "scripts"
        scripts: list[str] = []
        functions: dict[str, list[str]] = {}
        if scripts_dir.exists():
            for script in sorted(scripts_dir.glob("*.py")):
                scripts.append(str(script.relative_to(skill.directory)))
                functions[script.name] = self._list_functions(script)
        return {
            "name": skill.name,
            "description": skill.description,
            "path": str(skill.directory),
            "scripts": scripts,
            "functions": functions,
        }

    def _list_functions(self, script_path: Path) -> list[str]:
        parsed = ast.parse(script_path.read_text(encoding="utf-8"))
        return [n.name for n in parsed.body if isinstance(n, ast.FunctionDef)]

    def _find_function_script(self, skill: Skill, function_name: str) -> Path | None:
        scripts_dir = skill.directory / "scripts"
        if not scripts_dir.exists():
            return None
        for script in sorted(scripts_dir.glob("*.py")):
            content = script.read_text(encoding="utf-8")
            if re.search(rf"^def {re.escape(function_name)}\(", content, flags=re.MULTILINE):
                return script
        return None

    def _execute_script(
        self,
        script_path: Path,
        args: dict[str, Any] | None,
        cwd: Path,
        positional_args: list[str] | None = None,
    ) -> str:
        cmd = [sys.executable, str(script_path.resolve())]
        cmd.extend(positional_args or [])
        for key, value in (args or {}).items():
            cmd.append(f"--{key}")
            if isinstance(value, bool):
                if value:
                    continue
                cmd.pop()
                continue
            cmd.append(str(value))
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, shell=False, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Script execution failed ({script_path.name}): {result.stderr.strip() or result.stdout.strip()}"
            )
        return result.stdout

    def _execute_function(
        self, script_path: Path, function_name: str, args: dict[str, Any] | None, skill_dir: Path
    ) -> Any:
        content = script_path.read_text(encoding="utf-8")
        return execute_script_impl(
            content=content,
            function_name=function_name,
            args=args or {},
            working_dir=skill_dir,
        )

    def _has_main_guard(self, content: str) -> bool:
        return bool(
            re.search(
                r'if\s+__name__\s*==\s*["\']__main__["\']\s*:',
                content,
            )
        )

    def _get_function_parameters(self, script_path: Path, function_name: str) -> set[str] | None:
        try:
            info = extract_function_info(script_path.read_text(encoding="utf-8"), function_name)
        except Exception:
            return None
        return {param.name for param in info.parameters}

    def _select_script_function(self, script_path: Path, args: dict[str, Any] | None) -> str:
        candidates = [
            name
            for name in self._list_functions(script_path)
            if not name.startswith("_") and name != "main"
        ]
        if not candidates:
            raise ValueError(
                f"[execute] Script '{script_path.name}' has no callable functions to execute"
            )
        if len(candidates) == 1:
            return candidates[0]

        arg_keys = set((args or {}).keys())
        if arg_keys:
            matching: list[str] = []
            for candidate in candidates:
                accepted = self._get_function_parameters(script_path, candidate)
                if accepted is not None and arg_keys.issubset(accepted):
                    matching.append(candidate)
            if len(matching) == 1:
                return matching[0]
            if len(matching) > 1:
                raise ValueError(
                    f"[execute] Ambiguous non-CLI script target '{script_path.name}'. "
                    f"Matching functions: {matching}. Call execute with an explicit function name."
                )

        raise ValueError(
            f"[execute] Ambiguous non-CLI script target '{script_path.name}'. "
            f"Available functions: {candidates}. Call execute with an explicit function name."
        )

    def execute(self, skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
        """
        Execute either a script path under scripts/ or a discovered function name.

        - `target` script example: `hello.py`
        - `target` function example: `hello`
        """
        skill = self._require_skill(skill_name, "execute")
        scripts_dir = skill.directory / "scripts"
        if not scripts_dir.exists():
            raise FileNotFoundError(f"No scripts directory for skill: {skill_name}")

        script_candidate = scripts_dir / target
        if script_candidate.exists() and script_candidate.is_file():
            content = script_candidate.read_text(encoding="utf-8")
            if self._has_main_guard(content):
                return self._execute_script(script_candidate, args=args, cwd=skill.directory)
            selected_function = self._select_script_function(script_candidate, args)
            return self._execute_function(
                script_path=script_candidate,
                function_name=selected_function,
                args=args,
                skill_dir=skill.directory,
            )

        if not target.endswith(".py"):
            py_script_candidate = scripts_dir / f"{target}.py"
            if py_script_candidate.exists() and py_script_candidate.is_file():
                content = py_script_candidate.read_text(encoding="utf-8")
                if self._has_main_guard(content):
                    return self._execute_script(py_script_candidate, args=args, cwd=skill.directory)
                selected_function = self._select_script_function(py_script_candidate, args)
                return self._execute_function(
                    script_path=py_script_candidate,
                    function_name=selected_function,
                    args=args,
                    skill_dir=skill.directory,
                )

        function_script = self._find_function_script(skill, target)
        if function_script is None:
            cli_scripts = [
                script
                for script in sorted(scripts_dir.glob("*.py"))
                if self._has_main_guard(script.read_text(encoding="utf-8"))
            ]
            if len(cli_scripts) == 1:
                return self._execute_script(
                    cli_scripts[0],
                    args=args,
                    cwd=skill.directory,
                    positional_args=[target],
                )
            raise ValueError(
                f"[execute] Could not find script or function '{target}' in skill '{skill_name}'"
            )
        return self._execute_function(
            function_script, function_name=target, args=args, skill_dir=skill.directory
        )
