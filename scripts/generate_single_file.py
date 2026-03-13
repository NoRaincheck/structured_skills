#!/usr/bin/env python3
"""
Generate structured_skills.py from src/structured_skills/ package.
For internal use only as part of managing the repo scripts
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path("src/structured_skills")
OUTPUT_FILE = Path("structured_skills.py")
HEARTBEAT_FILE = SRC_DIR.joinpath("heartbeat_daemon.py")
OUTPUT_HEARTBEAT_FILE = Path("heartbeat_daemon.py")

HEADER = '''#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["fastmcp>=3.0.0"]
# ///

"""Single-file `structured_skills` CLI, MCP server, and library helpers.

**Note this script is automatically generated**

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

'''

FOOTER = """

if __name__ == "__main__":
    raise SystemExit(main())
"""


def read_source_files() -> list[tuple[str, Path]]:
    order = ["ast_utils", "registry", "builder", "server", "main"]
    files = []
    for name in order:
        path = SRC_DIR / f"{name}.py"
        if not path.exists():
            print(f"Warning: {path} not found", file=sys.stderr)
            continue
        files.append((name, path))
    return files


def strip_imports_and_docstring(content: str) -> str:
    lines = content.splitlines()
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith('"""'):
            if stripped == '"""':
                i += 1
                while i < len(lines) and lines[i].strip() != '"""':
                    i += 1
                i += 1
                continue
            elif stripped.count('"""') == 2:
                i += 1
                continue
            else:
                result.append(line)
                i += 1
                continue

        if not stripped:
            result.append(line)
            i += 1
            continue

        if i < len(lines) - 1 and lines[i + 1].strip() and not lines[i + 1].strip().startswith("#"):
            next_stripped = lines[i + 1].strip()
            if next_stripped in ('"""', "'''"):
                result.append(line)
                i += 1
                continue

        if stripped.startswith("from ") or stripped.startswith("import "):
            i += 1
            while i < len(lines):
                curr = lines[i].rstrip()
                if curr and not curr[0].isspace():
                    break
                i += 1
            continue

        if stripped.startswith(("@", "def ", "class ")):
            result.append(line)
            i += 1
            continue

        result.append(line)
        i += 1

    while result and not result[-1].strip():
        result.pop()

    return "\n".join(result) + "\n"


def process_content(name: str, content: str) -> str:
    content = strip_imports_and_docstring(content)

    if name == "ast_utils":
        if "def update_code(" in content:
            start = content.find("\ndef update_code(")
            end = content.find("\n\n", start + 2)
            if end != -1:
                content = content[:start] + content[end + 2 :]

    if name == "registry":
        content = content.replace("execute_script_impl(", "execute_script(")

    return content


def generate() -> str:
    parts = [HEADER]

    for name, path in read_source_files():
        content = path.read_text(encoding="utf-8")
        processed = process_content(name, content)
        parts.append(processed)

    parts.append(FOOTER)

    result = "".join(parts)

    existing = ""
    if OUTPUT_FILE.exists():
        existing = OUTPUT_FILE.read_text(encoding="utf-8")

    if result == existing:
        print("No changes needed.")
        return result

    OUTPUT_FILE.write_text(result, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE}")

    # run uv ruff format and uv ruff check on the output
    subprocess.run(["uv", "run", "ruff", "format", OUTPUT_FILE])
    subprocess.run(["uv", "run", "ruff", "check", OUTPUT_FILE, "--fix"])

    # finally copy the hartbeat_daemon.py
    shutil.copy(HEARTBEAT_FILE, OUTPUT_HEARTBEAT_FILE)
    return result


if __name__ == "__main__":
    generate()
