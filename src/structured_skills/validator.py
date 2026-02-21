"""
Structured Skills Validation Logic.

Extended from: https://github.com/agentskills/agentskills/tree/main
"""

import argparse
import ast
import unicodedata
from pathlib import Path
from typing import Optional

import strictyaml
import yaml

MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500

STDLIB_MODULES = {
    "_ast",
    "_builtins",
    "_collections_abc",
    "_functools",
    "_io",
    "_locale",
    "_operator",
    "_signal",
    "_sre",
    "_stat",
    "_string",
    "_symtable",
    "_thread",
    "_tracemalloc",
    "_warnings",
    "_weakref",
    "abc",
    "argparse",
    "array",
    "ast",
    "base64",
    "binascii",
    "bisect",
    "builtins",
    "calendar",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "codeop",
    "collections",
    "colorsys",
    "compile",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "crypt",
    "csv",
    "dataclasses",
    "datetime",
    "decimal",
    "difflib",
    "dis",
    "doctest",
    "email",
    "encoding",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "fractions",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "graphlib",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "imaplib",
    "imghdr",
    "imp",
    "importlib",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "keyword",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "multiprocessing",
    "netrc",
    "nntplib",
    "ntpath",
    "numbers",
    "operator",
    "optparse",
    "os",
    "pathlib",
    "pickle",
    "pickletools",
    "pipes",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "posixpath",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "sched",
    "secrets",
    "select",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtpd",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "sqlite3",
    "sre",
    "sre_compile",
    "sre_constants",
    "sre_parse",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symbol",
    "sys",
    "sysconfig",
    "tabnanny",
    "tarfile",
    "telnetlib",
    "tempfile",
    "termios",
    "test",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "token",
    "tokenize",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "urllib.parse",
    "urllib.request",
    "urllib.response",
    "urllib.error",
    "urllib.parse",
    "urllib.robotparser",
    "usertypes",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "xml",
    "xml.dom",
    "xml.dom.minidom",
    "xml.dom.pulldom",
    "xml.etree",
    "xml.etree.ElementTree",
    "xml.parsers",
    "xml.sax",
    "xml.sax.handler",
    "xml.sax.saxutils",
    "xml.sax.xmlreader",
    "xmlrpc",
    "xmlrpc.client",
    "xmlrpc.server",
    "zipfile",
    "zipimport",
    "zlib",
}

# Allowed frontmatter fields per Agent Skills Spec
ALLOWED_FIELDS = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "compatibility",
}


def find_skill_md(skill_dir: Path) -> Optional[Path]:
    """Find the SKILL.md file in a skill directory.

    Prefers SKILL.md (uppercase) but accepts skill.md (lowercase).

    Args:
        skill_dir: Path to the skill directory

    Returns:
        Path to the SKILL.md file, or None if not found
    """
    for name in ("SKILL.md", "skill.md"):
        path = skill_dir / name
        if path.exists():
            return path
    return None


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from SKILL.md content.

    Args:
        content: Raw content of SKILL.md file

    Returns:
        Tuple of (metadata dict, markdown body)

    Raises:
        ValueError: If frontmatter is missing or invalid
    """
    if not content.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter not properly closed with ---")

    frontmatter_str = parts[1]
    body = parts[2].strip()

    try:
        parsed = strictyaml.load(frontmatter_str)
        metadata = parsed.data
    except strictyaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in frontmatter: {e}")

    if not isinstance(metadata, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")

    if "metadata" in metadata and isinstance(metadata["metadata"], dict):
        processed: dict = {}
        for k, v in metadata["metadata"].items():
            if isinstance(v, list):
                processed[str(k)] = v
            else:
                processed[str(k)] = str(v)
        metadata["metadata"] = processed

    return metadata, body


def find_scripts(skill_dir: Path) -> list[Path]:
    """Checks the validity of python files in scripts/ (if exists)

    Args:
        skill_dir: Path to the skill directory

    Raises:
        ValueError: if scripts/ folder exists without any python files
    """
    script_path = skill_dir.joinpath("scripts")
    if not script_path.exists():
        return []

    scripts: list[Path] = list(script_path.glob("*.py"))
    if len(scripts) == 0:
        raise ValueError("scripts/ directory exists but no Python scripts found")
    return scripts


def extract_imports(script_path: Path) -> set[str]:
    """Extract imported module names from a Python script.

    Args:
        script_path: Path to the Python script

    Returns:
        Set of imported module names (excluding stdlib and relative imports)
    """
    try:
        source = script_path.read_text()
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module not in STDLIB_MODULES:
                    imports.add(module)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            module = node.module.split(".")[0]
            if module == "relative":
                continue
            if module not in STDLIB_MODULES:
                imports.add(module)

    return imports


def _validate_name(name: str, skill_dir: Optional[Path] = None) -> list[str]:
    """Validate skill name format and directory match.

    Skill names support i18n characters (Unicode letters) plus hyphens.
    Names must be lowercase and cannot start/end with hyphens.
    """
    errors = []

    if not name or not isinstance(name, str) or not name.strip():
        errors.append("Field 'name' must be a non-empty string")
        return errors

    name = unicodedata.normalize("NFKC", name.strip())

    if len(name) > MAX_SKILL_NAME_LENGTH:
        errors.append(
            f"Skill name '{name}' exceeds {MAX_SKILL_NAME_LENGTH} character limit "
            f"({len(name)} chars)"
        )

    if name != name.lower():
        errors.append(f"Skill name '{name}' must be lowercase")

    if name.startswith("-") or name.endswith("-"):
        errors.append("Skill name cannot start or end with a hyphen")

    if "--" in name:
        errors.append("Skill name cannot contain consecutive hyphens")

    if not all(c.isalnum() or c == "-" for c in name):
        errors.append(
            f"Skill name '{name}' contains invalid characters. "
            "Only letters, digits, and hyphens are allowed."
        )

    if skill_dir is not None:
        dir_name = unicodedata.normalize("NFKC", skill_dir.name)
        if dir_name != name:
            errors.append(f"Directory name '{skill_dir.name}' must match skill name '{name}'")

    return errors


def _validate_description(description: str) -> list[str]:
    """Validate description format."""
    errors = []

    if not description or not isinstance(description, str) or not description.strip():
        errors.append("Field 'description' must be a non-empty string")
        return errors

    if len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(
            f"Description exceeds {MAX_DESCRIPTION_LENGTH} character limit "
            f"({len(description)} chars)"
        )

    return errors


def _validate_compatibility(compatibility: str) -> list[str]:
    """Validate compatibility format."""
    errors = []

    if not isinstance(compatibility, str):
        errors.append("Field 'compatibility' must be a string")
        return errors

    if len(compatibility) > MAX_COMPATIBILITY_LENGTH:
        errors.append(
            f"Compatibility exceeds {MAX_COMPATIBILITY_LENGTH} character limit "
            f"({len(compatibility)} chars)"
        )

    return errors


def _validate_dependencies(metadata: dict, skill_dir: Path) -> list[str]:
    """Validate that non-stdlib imports are declared in metadata.dependencies.

    Args:
        metadata: Parsed YAML frontmatter dictionary
        skill_dir: Path to the skill directory

    Returns:
        List of validation error messages. Empty list means valid.
    """
    errors = []

    try:
        scripts = find_scripts(skill_dir)
    except ValueError:
        return errors

    if not scripts:
        return errors

    all_imports: set[str] = set()
    for script in scripts:
        all_imports.update(extract_imports(script))

    if not all_imports:
        return errors

    metadata_dict = metadata.get("metadata", {})
    raw_deps = metadata_dict.get("dependencies")
    if isinstance(raw_deps, str):
        declared_deps = [raw_deps]
    elif isinstance(raw_deps, list):
        declared_deps = list(raw_deps)
    else:
        declared_deps = []

    declared_set = set(declared_deps)

    missing = all_imports - declared_set
    if missing:
        errors.append(
            f"Missing dependencies in metadata.dependencies: {', '.join(sorted(missing))}"
        )

    return errors


def _validate_metadata_fields(metadata: dict) -> list[str]:
    """Validate that only allowed fields are present."""
    errors = []

    extra_fields = set(metadata.keys()) - ALLOWED_FIELDS
    if extra_fields:
        errors.append(
            f"Unexpected fields in frontmatter: {', '.join(sorted(extra_fields))}. "
            f"Only {sorted(ALLOWED_FIELDS)} are allowed."
        )

    return errors


def validate_metadata(metadata: dict, skill_dir: Optional[Path] = None) -> list[str]:
    """Validate parsed skill metadata.

    This is the core validation function that works on already-parsed metadata,
    avoiding duplicate file I/O when called from the parser.

    Args:
        metadata: Parsed YAML frontmatter dictionary
        skill_dir: Optional path to skill directory (for name-directory match check)

    Returns:
        List of validation error messages. Empty list means valid.
    """
    errors = []
    errors.extend(_validate_metadata_fields(metadata))

    if "name" not in metadata:
        errors.append("Missing required field in frontmatter: name")
    else:
        errors.extend(_validate_name(metadata["name"], skill_dir))

    if "description" not in metadata:
        errors.append("Missing required field in frontmatter: description")
    else:
        errors.extend(_validate_description(metadata["description"]))

    if "compatibility" in metadata:
        errors.extend(_validate_compatibility(metadata["compatibility"]))

    return errors


def fix_dependencies(skill_dir: Path) -> list[str]:
    """Auto-populate metadata.dependencies based on script imports.

    Args:
        skill_dir: Path to the skill directory

    Returns:
        List of dependencies that were added
    """
    skill_dir = Path(skill_dir)

    try:
        scripts = find_scripts(skill_dir)
    except ValueError:
        return []

    if not scripts:
        return []

    all_imports: set[str] = set()
    for script in scripts:
        all_imports.update(extract_imports(script))

    if not all_imports:
        return []

    skill_md = find_skill_md(skill_dir)
    if skill_md is None:
        return []

    content = skill_md.read_text()
    metadata, body = parse_frontmatter(content)

    if "metadata" not in metadata:
        metadata["metadata"] = {}

    raw_deps = metadata["metadata"].get("dependencies")
    if isinstance(raw_deps, str):
        existing_deps = [raw_deps]
    elif isinstance(raw_deps, list):
        existing_deps = list(raw_deps)
    else:
        existing_deps = []

    existing_set = set(existing_deps)

    new_deps = all_imports - existing_set
    if new_deps:
        metadata["metadata"]["dependencies"] = sorted(existing_deps + list(new_deps))

    new_content = _rebuild_frontmatter(metadata, body)
    skill_md.write_text(new_content)

    return sorted(new_deps)


def _rebuild_frontmatter(metadata: dict, body: str) -> str:
    """Rebuild SKILL.md content from metadata dict and body."""

    yaml_str = yaml.dump(metadata, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}\n"


def validate(skill_dir: Path) -> list[str]:
    """Validate a skill directory.

    Args:
        skill_dir: Path to the skill directory

    Returns:
        List of validation error messages. Empty list means valid.
    """
    skill_dir = Path(skill_dir)

    if not skill_dir.exists():
        return [f"Path does not exist: {skill_dir}"]

    if not skill_dir.is_dir():
        return [f"Not a directory: {skill_dir}"]

    skill_md = find_skill_md(skill_dir)
    if skill_md is None:
        return ["Missing required file: SKILL.md"]

    try:
        content = skill_md.read_text()
        metadata, _ = parse_frontmatter(content)
    except ValueError as e:
        return [str(e)]

    try:
        _ = find_scripts(skill_dir)
    except ValueError as e:
        return [str(e)]

    errors = validate_metadata(metadata, skill_dir)
    errors.extend(_validate_dependencies(metadata, skill_dir))
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="SkillStructParser", description="Structured Skill Parsing"
    )
    parser.add_argument("skill_dir")
    args = parser.parse_args()
    validate(Path(args.skill_dir))
