import argparse
import subprocess
import sys
from pathlib import Path

from structured_skills.server import create_mcp_server
from structured_skills.skill_registry import SkillRegistry
from structured_skills.validator import (
    _get_declared_dependencies,
    fix_dependencies,
    parse_frontmatter,
    validate,
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="structured_skills",
        description="Structured Skills for Agents - Launch MCP servers from skill directories",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser("run", help="Launch MCP server for skills")
    run_parser.add_argument("skill_dir", type=Path, help="Path to skill root directory")
    run_parser.add_argument(
        "--exclude-skills",
        nargs="*",
        default=[],
        help="List of skill names to exclude",
    )

    cli_parser = subparsers.add_parser("cli", help="CLI tools for skill management")
    cli_subparsers = cli_parser.add_subparsers(dest="cli_command", help="CLI subcommands")

    list_skills_parser = cli_subparsers.add_parser("list_skills", help="List skills")
    list_skills_parser.add_argument("skill_dir", type=Path, help="Path to skill root directory")

    load_skill_parser = cli_subparsers.add_parser("load_skill", help="Load a skill")
    load_skill_parser.add_argument("skill_dir", type=Path, help="Path to skill root directory")
    load_skill_parser.add_argument("skill_name", help="Name of the skill to load")

    read_resource_parser = cli_subparsers.add_parser(
        "read_skill_resource", help="Read a skill resource"
    )
    read_resource_parser.add_argument("skill_dir", type=Path, help="Path to skill root directory")
    read_resource_parser.add_argument("skill_name", help="Name of the skill")
    read_resource_parser.add_argument("resource_name", help="Name of the resource")
    read_resource_parser.add_argument(
        "--args", type=str, default=None, help="JSON args for the resource"
    )

    run_skill_parser = cli_subparsers.add_parser("run_skill_script", help="Run a skill script")
    run_skill_parser.add_argument("skill_dir", type=Path, help="Path to skill root directory")
    run_skill_parser.add_argument("skill_name", help="Name of the skill")
    run_skill_parser.add_argument("function_or_script", help="Function or script name to run")
    run_skill_parser.add_argument("--args", type=str, default=None, help="JSON args for the script")

    check_parser = subparsers.add_parser("check", help="Validate skill directory")
    check_parser.add_argument("skill_dir", type=Path, help="Path to skill directory")
    check_parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")

    return parser


def handle_cli(args: argparse.Namespace) -> None:
    registry = SkillRegistry(args.skill_dir)

    if args.cli_command == "list_skills":
        skills = registry.list_skills()
        for name, desc in skills.items():
            print(f"{name}: {desc}")

    elif args.cli_command == "load_skill":
        content = registry.load_skill(args.skill_name)
        print(content)

    elif args.cli_command == "read_skill_resource":
        import json

        args_dict = json.loads(args.args) if args.args else None
        result = registry.read_skill_resource(args.skill_name, args.resource_name, args_dict)
        if isinstance(result, dict):
            print(json.dumps(result, indent=2))
        else:
            print(result)

    elif args.cli_command == "run_skill_script":
        import json

        args_dict = json.loads(args.args) if args.args else None
        result = registry.run_skill(args.skill_name, args.function_or_script, args_dict)
        print(result)

    else:
        print("Unknown CLI command. Use --help for usage.")
        sys.exit(1)


def _get_all_dependencies(skill_dir: Path) -> set[str]:
    """Extract all unique dependencies from skills in a directory."""
    all_deps: set[str] = set()

    for sub_dir in skill_dir.iterdir():
        if not sub_dir.is_dir() or sub_dir.name.startswith("."):
            continue

        skill_md = sub_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text()
            metadata, _ = parse_frontmatter(content)
            all_deps.update(_get_declared_dependencies(metadata))
        except ValueError:
            continue

    return all_deps


def _show_deps_warning(skill_dir: Path) -> None:
    """Show warning about dependencies if any skills have them."""
    deps = _get_all_dependencies(skill_dir)
    if not deps:
        return

    deps_str = " ".join(f"--with {dep}" for dep in sorted(deps))
    print("\nWarning: Skills have dependencies. To run the server with dependencies, use:")
    print(f"  uvx structured_skills {deps_str} -- run {skill_dir}")


def handle_check(args: argparse.Namespace) -> None:
    skill_dir = args.skill_dir

    if not skill_dir.is_dir():
        print(f"Error: {skill_dir} is not a directory")
        sys.exit(1)

    all_errors: list[tuple[Path, list[str]]] = []

    for sub_dir in skill_dir.iterdir():
        if sub_dir.is_dir() and not sub_dir.name.startswith("."):
            errors = validate(sub_dir)
            if errors:
                all_errors.append((sub_dir, errors))

    if all_errors:
        print("Validation errors found:\n")
        for dir_path, errors in all_errors:
            print(f"{dir_path}:")
            for error in errors:
                print(f"  - {error}")

        if not args.fix:
            sys.exit(1)
    else:
        print("All skills validated successfully!")
        _show_deps_warning(skill_dir)

    if args.fix:
        print("\nFixing skills...")
        fixed_count = 0

        for sub_dir in skill_dir.iterdir():
            if not sub_dir.is_dir() or sub_dir.name.startswith("."):
                continue

            fixed_deps = fix_dependencies(sub_dir)
            if fixed_deps:
                print(f"  {sub_dir.name}: added dependencies: {', '.join(fixed_deps)}")
                fixed_count += 1

        if fixed_count == 0:
            print("  No dependencies to fix.")

        print("\nRunning ruff...")
        result_check = subprocess.run(
            ["uv", "run", "ruff", "check", ".", "--fix"],
            cwd=skill_dir,
            capture_output=True,
            text=True,
        )
        if result_check.stdout:
            print(f"  ruff check output:\n{result_check.stdout}")
        if result_check.stderr:
            print(f"  ruff check errors:\n{result_check.stderr}")

        result_format = subprocess.run(
            ["uv", "run", "ruff", "format", "."],
            cwd=skill_dir,
            capture_output=True,
            text=True,
        )
        if result_format.stdout:
            print(f"  ruff format output:\n{result_format.stdout}")

        all_errors_after: list[tuple[Path, list[str]]] = []
        for sub_dir in skill_dir.iterdir():
            if sub_dir.is_dir() and not sub_dir.name.startswith("."):
                errors = validate(sub_dir)
                if errors:
                    all_errors_after.append((sub_dir, errors))

        if all_errors_after:
            print("\nValidation errors still present after fix:\n")
            for dir_path, errors in all_errors_after:
                print(f"{dir_path}:")
                for error in errors:
                    print(f"  - {error}")
            sys.exit(1)
        else:
            print("\nAll skills validated successfully after fix!")
            _show_deps_warning(skill_dir)
    else:
        sys.exit(1)


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "run":
        mcp = create_mcp_server(args.skill_dir, exclude_skills=args.exclude_skills)
        mcp.run()

    elif args.command == "cli":
        handle_cli(args)

    elif args.command == "check":
        handle_check(args)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
