#!/usr/bin/env python3
"""Transform a single Python script into a SKILL.md-based skill.

This script is standalone and uses only the Python standard library.
It copies the source script into a generated skill folder and builds a
heuristic SKILL.md from static analysis (docstrings, AST, imports, and
common script patterns such as argparse and __main__).
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent


@dataclass
class ScriptSignals:
    """Collected heuristics extracted from a Python script."""

    module_doc: str = ""
    imports: set[str] = field(default_factory=set)
    functions: list[str] = field(default_factory=list)
    has_main_guard: bool = False
    uses_argparse: bool = False
    argparse_options: list[str] = field(default_factory=list)
    touches_files: bool = False
    touches_network: bool = False
    runs_subprocess: bool = False
    uses_env: bool = False


def slugify(name: str) -> str:
    """Convert arbitrary text into a stable skill slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "generated-skill"


def titleize(slug: str) -> str:
    """Build a human-readable title from a slug."""
    return " ".join(piece.capitalize() for piece in slug.split("-") if piece)


def _format_option(arg: str) -> str:
    arg = arg.strip()
    if not arg:
        return ""
    if arg.startswith("--") or arg.startswith("-"):
        return arg
    return f"<{arg}>"


def analyze_script(path: Path) -> ScriptSignals:
    """Analyze a script and derive high-signal metadata."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    signals = ScriptSignals(module_doc=(ast.get_docstring(tree) or "").strip())

    class Visitor(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                root = alias.name.split(".")[0]
                signals.imports.add(root)
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.module:
                root = node.module.split(".")[0]
                signals.imports.add(root)
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if not node.name.startswith("_"):
                signals.functions.append(node.name)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if not node.name.startswith("_"):
                signals.functions.append(node.name)
            self.generic_visit(node)

        def visit_If(self, node: ast.If) -> None:
            # Detect: if __name__ == "__main__":
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"
            ):
                signals.has_main_guard = True
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            # argparse heuristics
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in {"ArgumentParser", "add_argument", "parse_args"}:
                signals.uses_argparse = True

            if func_name == "add_argument":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        formatted = _format_option(arg.value)
                        if formatted and formatted not in signals.argparse_options:
                            signals.argparse_options.append(formatted)

            # file/network/process/env heuristics
            if func_name in {"open"}:
                signals.touches_files = True
            if func_name in {"urlopen", "urlretrieve", "request"}:
                signals.touches_network = True
            if func_name in {"system", "popen", "run", "Popen", "call", "check_output"}:
                # A mild over-approximation by design.
                signals.runs_subprocess = True
            if func_name in {"getenv"}:
                signals.uses_env = True
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            # os.environ usage
            if node.attr == "environ":
                signals.uses_env = True
            self.generic_visit(node)

    Visitor().visit(tree)

    # Additional import-based heuristics.
    network_imports = {"urllib", "http", "socket", "requests"}
    process_imports = {"subprocess"}
    file_imports = {"pathlib", "tempfile"}
    if signals.imports.intersection(network_imports):
        signals.touches_network = True
    if signals.imports.intersection(process_imports):
        signals.runs_subprocess = True
    if signals.imports.intersection(file_imports):
        signals.touches_files = True
    if "argparse" in signals.imports:
        signals.uses_argparse = True

    return signals


def derive_description(signals: ScriptSignals, script_name: str) -> str:
    """Choose a compact description for frontmatter."""
    if signals.module_doc:
        first = signals.module_doc.splitlines()[0].strip()
        if first:
            return first[:120]
    if signals.uses_argparse:
        return f"CLI automation generated from {script_name}"
    if signals.functions:
        return f"Python helper logic generated from {script_name}"
    return f"Generated skill from {script_name}"


def build_skill_md(
    *,
    skill_name: str,
    title: str,
    source_script: Path,
    copied_script_rel: str,
    signals: ScriptSignals,
) -> str:
    """Render a heuristic SKILL.md."""
    description = derive_description(signals, source_script.name)

    purpose_line = "Run this script as a deterministic utility skill."
    if signals.touches_network:
        purpose_line = "Run this script when you need network-backed automation."
    elif signals.runs_subprocess:
        purpose_line = "Run this script when shell/system orchestration is needed."
    elif signals.touches_files:
        purpose_line = "Run this script for file and local data workflows."

    population_guesses: list[str] = []
    if signals.module_doc:
        population_guesses.append("Module docstring content")
    if signals.uses_argparse:
        population_guesses.append("argparse parser/options")
    if signals.functions:
        population_guesses.append("public top-level functions")
    if signals.imports:
        population_guesses.append("imported modules")
    if not population_guesses:
        population_guesses.append("filename and script structure")

    options_text = "None detected."
    if signals.argparse_options:
        options_text = ", ".join(signals.argparse_options[:20])

    functions_text = "None detected."
    if signals.functions:
        functions_text = ", ".join(signals.functions[:20])

    imports_text = "None detected."
    if signals.imports:
        imports_text = ", ".join(sorted(signals.imports)[:20])

    invocation_hint = f"python {copied_script_rel}"
    if signals.has_main_guard:
        invocation_hint = f"python {copied_script_rel}  # script entrypoint enabled"

    body = f"""\
---
name: {skill_name}
description: {description}
---

# {title}

{purpose_line}

## Generated From

- Source script: `{source_script}`
- Skill script: `{copied_script_rel}`

## Heuristic Population Guess

This skill metadata was auto-populated from: {", ".join(population_guesses)}.

## Script Signals

- Uses `__main__` guard: {"yes" if signals.has_main_guard else "no"}
- Uses argparse: {"yes" if signals.uses_argparse else "no"}
- Argparse options: {options_text}
- Public functions: {functions_text}
- Imports: {imports_text}
- Touches files: {"yes" if signals.touches_files else "no"}
- Touches network: {"yes" if signals.touches_network else "no"}
- Runs subprocesses/system commands: {"yes" if signals.runs_subprocess else "no"}
- Uses environment variables: {"yes" if signals.uses_env else "no"}

## How To Run

```bash
{invocation_hint}
```
"""
    return dedent(body).rstrip() + "\n"


def build_skill(script_path: Path, output_root: Path, force: bool = False) -> Path:
    """Create a skill folder from one Python script."""
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    if script_path.suffix != ".py":
        raise ValueError(f"Expected a .py file, got: {script_path}")

    signals = analyze_script(script_path)
    skill_name = slugify(script_path.stem)
    title = titleize(skill_name) or "Generated Skill"

    skill_dir = output_root / skill_name
    scripts_dir = skill_dir / "scripts"
    target_script = scripts_dir / script_path.name
    skill_md = skill_dir / "SKILL.md"

    if skill_dir.exists() and not force:
        raise FileExistsError(
            f"Destination skill already exists: {skill_dir}. Use --force to overwrite."
        )

    if skill_dir.exists() and force:
        shutil.rmtree(skill_dir)

    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(script_path, target_script)

    rendered = build_skill_md(
        skill_name=skill_name,
        title=title,
        source_script=script_path.resolve(),
        copied_script_rel=str(target_script.relative_to(skill_dir)),
        signals=signals,
    )
    skill_md.write_text(rendered, encoding="utf-8")

    return skill_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Transform one Python script into a SKILL.md-based skill folder "
            "using stdlib-only heuristics."
        )
    )
    parser.add_argument("script", help="Path to a single .py script")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where the generated skill folder will be created (default: current dir)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing generated skill folder if present",
    )
    args = parser.parse_args()

    script_path = Path(args.script).expanduser().resolve()
    output_root = Path(args.output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    skill_dir = build_skill(script_path, output_root, force=args.force)
    print(skill_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
