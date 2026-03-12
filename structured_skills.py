#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["fastmcp>=3.0.0"]
# ///

"""Single-file `structured_skills` CLI, MCP server, and library helpers.

This script is designed to run in uv script mode and mirrors the package
implementation. It supports:

- discovering skills under a root directory (folders containing `SKILL.md`)
- searching and inspecting skills
- reading skill-local resources safely
- executing script targets or function targets from each skill's `scripts/`
- running a FastMCP server that exposes `search`, `inspect`, and `execute`

CLI usage:
    uv run structured_skills.py <skills_dir> search [query] --limit 10
    uv run structured_skills.py <skills_dir> inspect <skill_name> [resource_name] [--include-body]
    uv run structured_skills.py <skills_dir> execute <skill_name> <target> --args '{"a":2,"b":3}'
    uv run structured_skills.py <skills_dir> mcp --server-name structured_skills

The module also exposes `SkillRegistry`, `SkillToolsBuilder`, `create_structured_skills`,
`get_tool`, and `create_mcp_server` for direct Python usage.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

SECRET_VARIABLE = "__SKILL_TOOLS_VALUE"
ToolName = Literal[
    "search",
    "inspect",
    "execute",
]


@contextmanager
def _script_exec_context(working_dir: Path | None):
    old_cwd = Path.cwd()
    try:
        if working_dir:
            working_dir.mkdir(parents=True, exist_ok=True)
            os.chdir(working_dir)
        yield
    finally:
        os.chdir(old_cwd)


@dataclass
class ParameterInfo:
    name: str
    annotation: str | None
    default: str | None


@dataclass
class FunctionInfo:
    name: str
    parameters: list[ParameterInfo]
    return_type: str | None
    docstring: str | None


class FunctionNotFoundError(Exception):
    pass


def extract_function_info(source: str, function_name: str) -> FunctionInfo:
    module = ast.parse(source)
    func: ast.FunctionDef | None = None
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            func = node
            break
    if func is None:
        raise FunctionNotFoundError(f"Function '{function_name}' not found in source")

    params: list[ParameterInfo] = []
    positional = func.args.args
    defaults = list(func.args.defaults)
    non_default_count = len(positional) - len(defaults)
    default_by_name: dict[str, ast.expr] = {}
    for index, arg in enumerate(positional):
        if index >= non_default_count:
            default_by_name[arg.arg] = defaults[index - non_default_count]

    for arg in positional:
        annotation = ast.unparse(arg.annotation) if arg.annotation else None
        default_expr = default_by_name.get(arg.arg)
        default = ast.unparse(default_expr) if default_expr else None
        params.append(ParameterInfo(name=arg.arg, annotation=annotation, default=default))

    return_type = ast.unparse(func.returns) if func.returns else None

    docstring = ast.get_docstring(func)

    return FunctionInfo(
        name=func.name,
        parameters=params,
        return_type=return_type,
        docstring=docstring,
    )


def execute_script(
    content: str,
    function_name: str,
    args: dict[str, Any],
    working_dir: Path | None = None,
) -> Any:
    context: dict[str, Any] = {"__builtins__": __builtins__, "__name__": "__structured_skills__"}
    with _script_exec_context(working_dir):
        exec(content, context, context)
    if function_name not in context or not callable(context[function_name]):
        raise FunctionNotFoundError(f"Function '{function_name}' not found after script execution")
    context[SECRET_VARIABLE] = context[function_name](**args)
    return context[SECRET_VARIABLE]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
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
    name: str
    description: str
    directory: Path
    skill_md_path: Path
    skill_md_body: str


class SkillRegistry:
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
                f"Script execution failed ({script_path.name}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return result.stdout

    def _execute_function(
        self, script_path: Path, function_name: str, args: dict[str, Any] | None, skill_dir: Path
    ) -> Any:
        content = script_path.read_text(encoding="utf-8")
        return execute_script(
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
                    f"Matching functions: {matching}. "
                    "Call execute with an explicit function name."
                )

        raise ValueError(
            f"[execute] Ambiguous non-CLI script target '{script_path.name}'. "
            f"Available functions: {candidates}. "
            "Call execute with an explicit function name."
        )

    def execute(self, skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
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


class SkillToolsBuilder:
    TOOL_NAMES: tuple[ToolName, ...] = (
        "search",
        "inspect",
        "execute",
    )

    def __init__(self, registry: SkillRegistry, auto_build: bool = True):
        self.registry = registry
        self._callable_tools: dict[str, tuple[Callable[..., Any], str]] | None = None
        if auto_build:
            self.refresh()

    def refresh(self) -> dict[str, tuple[Callable[..., Any], str]]:
        self._callable_tools = self._generate_callable_tools()
        for name, (func, _) in self._callable_tools.items():
            setattr(self, name, func)
        return self._callable_tools

    def _metadata_suffix(self) -> str:
        available_tools = ", ".join(self.TOOL_NAMES)
        available_skills = ", ".join(self.registry.get_skill_names())
        return f"\n\nExposed tools: {available_tools}\nAvailable skills: {available_skills}"

    def _generate_callable_tools(self) -> dict[str, tuple[Callable[..., Any], str]]:
        suffix = self._metadata_suffix()
        tools: dict[str, tuple[Callable[..., Any], str]] = {}

        def search(query: str = "", limit: int = 10) -> dict[str, str]:
            return self.registry.search(query=query, limit=limit)

        tools["search"] = (
            search,
            "Search skills by name/description; empty query lists all skills." + suffix,
        )

        def inspect(
            skill_name: str, resource_name: str | None = None, include_body: bool = False
        ) -> dict[str, Any] | str:
            return self.registry.inspect(
                skill_name=skill_name,
                resource_name=resource_name,
                include_body=include_body,
            )

        tools["inspect"] = (
            inspect,
            "Inspect skill metadata, SKILL body, or a concrete resource file." + suffix,
        )

        def execute(skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
            return self.registry.execute(skill_name, target, args=args)

        tools["execute"] = (
            execute,
            "Execute a skill script or function using optional args." + suffix,
        )

        for name, (func, desc) in tools.items():
            setattr(func, "__name__", name)
            setattr(func, "__doc__", desc)
        return tools

    def build_callable_tools(
        self, force_rebuild: bool = False
    ) -> dict[str, tuple[Callable[..., Any], str]]:
        if force_rebuild or self._callable_tools is None:
            return self.refresh()
        return self._callable_tools

    # Convenience methods for direct library usage with static typing support.
    def search(self, query: str = "", limit: int = 10) -> dict[str, str]:
        fn = self.build_callable_tools()["search"][0]
        return fn(query, limit)

    def inspect(
        self, skill_name: str, resource_name: str | None = None, include_body: bool = False
    ) -> dict[str, Any] | str:
        fn = self.build_callable_tools()["inspect"][0]
        return fn(skill_name, resource_name, include_body)

    def execute(self, skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
        fn = self.build_callable_tools()["execute"][0]
        return fn(skill_name, target, args)


def create_structured_skills(registry: SkillRegistry) -> dict[str, tuple[Callable[..., Any], str]]:
    return SkillToolsBuilder(registry).build_callable_tools()


def get_tool(registry: SkillRegistry, tool_name: ToolName) -> Callable[..., Any]:
    tools = create_structured_skills(registry)
    func, description = tools[tool_name]
    func.__doc__ = description
    return func


def create_mcp_server(skill_root_dir: Path, server_name: str = "structured_skills") -> Any:
    """Create a FastMCP server exposing skill tool operations."""
    try:
        fastmcp_module = __import__("mcp.server.fastmcp", fromlist=["FastMCP"])
        fastmcp_class = getattr(fastmcp_module, "FastMCP")
    except (ModuleNotFoundError, ImportError, AttributeError) as exc:
        raise RuntimeError(
            "FastMCP is required for MCP server mode but is not installed or importable. "
            "Install it with `uv add fastmcp` for package mode, or run this file via "
            "`uv run structured_skills.py ...` so script dependencies are resolved."
        ) from exc

    mcp = fastmcp_class(server_name)
    registry = SkillRegistry(skill_root_dir)
    tools = SkillToolsBuilder(registry).build_callable_tools()

    search_func, search_desc = tools["search"]
    inspect_func, inspect_desc = tools["inspect"]
    execute_func, execute_desc = tools["execute"]

    @mcp.tool(description=search_desc)
    def search(query: str = "", limit: int = 10) -> dict[str, str]:
        return search_func(query=query, limit=limit)

    @mcp.tool(description=inspect_desc)
    def inspect(
        skill_name: str, resource_name: str | None = None, include_body: bool = False
    ) -> dict[str, Any] | str:
        return inspect_func(
            skill_name=skill_name,
            resource_name=resource_name,
            include_body=include_body,
        )

    @mcp.tool(description=execute_desc)
    def execute(skill_name: str, target: str, args: dict[str, Any] | None = None) -> Any:
        return execute_func(skill_name=skill_name, target=target, args=args)

    return mcp


def _coerce_cli_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _parse_execute_passthrough(tokens: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            raise ValueError(f"Unexpected positional token for execute args: {token}")
        key = token[2:]
        value: Any = True
        if "=" in key:
            key, raw_value = key.split("=", 1)
            value = _coerce_cli_value(raw_value)
        elif index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
            value = _coerce_cli_value(tokens[index + 1])
            index += 1
        parsed[key.replace("-", "_")] = value
        index += 1
    return parsed


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SKILL.md tools builder CLI")
    parser.add_argument("skills_dir", help="Root directory containing skill folders with SKILL.md")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--limit", type=int, default=10)

    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("skill_name")
    inspect_cmd.add_argument("resource_name", nargs="?", default=None)
    inspect_cmd.add_argument("--include-body", action="store_true")

    execute_cmd = sub.add_parser("execute")
    execute_cmd.add_argument("skill_name")
    execute_cmd.add_argument("target")
    execute_cmd.add_argument("--args", default="{}", help='JSON object, e.g. {"name":"World"}')

    mcp = sub.add_parser("mcp")
    mcp.add_argument("--server-name", default="structured_skills")

    parsed, unknown = parser.parse_known_args(argv)
    if unknown:
        if parsed.command == "execute":
            setattr(parsed, "execute_passthrough", unknown)
            return parsed
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    setattr(parsed, "execute_passthrough", [])
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    registry = SkillRegistry(Path(args.skills_dir))

    if args.command == "search":
        print(
            json.dumps(
                registry.search(args.query, args.limit),
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0
    if args.command == "inspect":
        output = registry.inspect(args.skill_name, args.resource_name, args.include_body)
        if isinstance(output, (dict, list)):
            print(json.dumps(output, ensure_ascii=True, indent=2))
        else:
            print(output)
        return 0
    if args.command == "execute":
        parsed_args: dict[str, Any] = json.loads(args.args)
        if not isinstance(parsed_args, dict):
            raise ValueError("--args must decode to a JSON object")
        passthrough_args = _parse_execute_passthrough(args.execute_passthrough)
        parsed_args.update(passthrough_args)
        output = registry.execute(args.skill_name, args.target, parsed_args)
        if isinstance(output, (dict, list)):
            print(json.dumps(output, ensure_ascii=True, indent=2))
        else:
            print(output)
        return 0
    if args.command == "mcp":
        mcp = create_mcp_server(Path(args.skills_dir), server_name=args.server_name)
        mcp.run()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
