"""AST helpers for introspection and deterministic function execution."""

from __future__ import annotations

import ast
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SECRET_VARIABLE = "__SKILL_TOOLS_VALUE"


@contextmanager
def _script_exec_context(working_dir: Path | None):
    """Temporarily execute code with `working_dir` as cwd."""
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
    """Return function metadata from Python source using AST."""
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


def update_code(source: str, new_call: str) -> str:
    """Append `new_call` while preserving source as text."""
    return source + "\n" + new_call + "\n"


def execute_script(
    content: str,
    function_name: str,
    args: dict[str, Any],
    working_dir: Path | None = None,
) -> Any:
    """Execute a named function from source with injected args."""
    context: dict[str, Any] = {"__builtins__": __builtins__, "__name__": "__structured_skills__"}
    with _script_exec_context(working_dir):
        exec(content, context, context)
    if function_name not in context or not callable(context[function_name]):
        raise FunctionNotFoundError(f"Function '{function_name}' not found after script execution")
    context[SECRET_VARIABLE] = context[function_name](**args)
    return context[SECRET_VARIABLE]
