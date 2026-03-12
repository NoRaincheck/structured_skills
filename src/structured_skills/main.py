"""Minimal CLI for structured_skills package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from structured_skills.builder import SkillToolsBuilder
from structured_skills.registry import SkillRegistry
from structured_skills.server import create_mcp_server


def _coerce_cli_value(raw: str) -> Any:
    """Coerce a CLI token to JSON scalar when possible."""
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
    """Parse execute trailing tokens like `--seed 7 --flag` into a dict."""
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

    execute = sub.add_parser("execute")
    execute.add_argument("skill_name")
    execute.add_argument("target")
    execute.add_argument("--args", default="{}", help='JSON object, e.g. {"name":"World"}')

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
    skills_builder = SkillToolsBuilder(registry)

    if args.command == "search":
        print(
            json.dumps(
                skills_builder.search(args.query, args.limit),
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0
    if args.command == "inspect":
        output = skills_builder.inspect(args.skill_name, args.resource_name, args.include_body)
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
        output = skills_builder.execute(args.skill_name, args.target, parsed_args)
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
