"""Simple file-backed memory/history helpers for the memory skill."""

import hashlib
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path
from typing import Literal

SKILL_MD_MEMORIES = "## Memories"
MEMORY_WINDOW = 50
HISTORY_WINDOW = 150
WARNING_MESSAGE = "_comment:FULL PLEASE CONSOLIDATE"
DEFAULT_GROUP = "notes"
VALID_GROUPS = {"user", "context", "notes"}


def _path(filename: str) -> Path:
    file = Path(filename)
    file.touch(exist_ok=True)
    return file


def _get_skill_md() -> Path:
    return _path("SKILL.md")


def _get_memory_txt() -> Path:
    return _path("memory.txt")


def _get_history_txt() -> Path:
    return _path("history.txt")


def _iso_date() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_lines(target: Path) -> list[str]:
    return target.read_text().splitlines()


def _write_lines(target: Path, lines: list[str]) -> None:
    target.write_text("\n".join(lines))


def _normalize_group(group: Literal["user", "context", "notes"] | str | None) -> str:
    if group is not None and group in VALID_GROUPS:
        return group
    return DEFAULT_GROUP


def _update_skill() -> None:
    _get_skill_md().write_text(f"{SKILL_MD_MEMORIES}\n\n{_get_memory_txt().read_text()}")


def _compact(items: list[str], window: int) -> list[str]:
    if len(items) < window:
        return items
    no_warning = [line for line in items if not line.startswith(("_comment:", "_coment:"))]
    return [WARNING_MESSAGE, *no_warning[:window]]


def _add_event(
    target: Path,
    window: int,
    text: str,
    group: Literal["user", "context", "notes"] | str | None = None,
) -> None:
    event = f"[{_normalize_group(group)}] {text}"
    items = [event, *_read_lines(target)]
    _write_lines(target, _compact(items, window))


def add_memory(text: str, group: Literal["user", "context", "notes"] | None = None) -> None:
    _add_event(_get_memory_txt(), MEMORY_WINDOW, text, group)
    _update_skill()


def add_history(text: str, group: Literal["user", "context", "notes"] | None = None) -> None:
    _add_event(_get_history_txt(), HISTORY_WINDOW, f"{_iso_date()} {text}", group)


def _entry_content(line: str) -> str:
    return line.rsplit("]", 1)[1].strip() if "]" in line else line.strip()


def _search_event(
    target: Path,
    query: str,
    group: Literal["user", "context", "notes"] | str | None = "",
    top_k: int = 5,
) -> list[str]:
    valid_group = group if group in VALID_GROUPS else None
    lines = [
        line.strip() for line in _read_lines(target) if "_comment" not in line and line.strip()
    ]
    if valid_group is not None:
        lines = [line for line in lines if line.startswith(f"[{valid_group}]")]

    candidates = [(line, _entry_content(line)) for line in lines]
    contents = [content for _, content in candidates]
    matches = get_close_matches(query, contents, n=max(top_k * 2, top_k), cutoff=0)

    results: list[str] = []
    for match in matches:
        for original, content in candidates:
            if content == match and original not in results:
                results.append(original)
                if len(results) == top_k:
                    return results
    return results


def search_memory(
    query: str,
    group: Literal["user", "context", "notes"] | str | None = "",
    top_k: int = 5,
) -> str:
    return "\n".join(_search_event(_get_memory_txt(), query, group, top_k))


def search_history(
    query: str,
    group: Literal["user", "context", "notes"] | str | None = "",
    top_k: int = 5,
) -> str:
    return "\n".join(_search_event(_get_history_txt(), query, group, top_k))


def _get_hash(target: Path) -> str:
    hash_digest = hashlib.md5(target.read_bytes()).hexdigest()
    return f"hash_info: {hash_digest[:2]}"


def _view_event(target: Path) -> str:
    return "\n".join([_get_hash(target), *_read_lines(target)])


def view_memory() -> str:
    return _view_event(_get_memory_txt())


def view_history() -> str:
    return _view_event(_get_history_txt())


def _normalize_consolidated_items(items: list[str], add_timestamp: bool) -> list[str]:
    timestamp = _iso_date()
    normalized: list[str] = []
    for item in items:
        if not item:
            continue
        if item.startswith("["):
            normalized.append(item)
            continue
        if add_timestamp:
            normalized.append(f"[{DEFAULT_GROUP}] [{timestamp}] {item}")
        else:
            normalized.append(f"[{DEFAULT_GROUP}] {item}")
    return normalized


def consolidate_memory(memories: str, hash: str) -> str | None:
    if _get_hash(_get_memory_txt()).split(" ")[1] != hash.strip():
        return "Hash do not match! No consolidation occurred. Check the hash by running view_memory"
    _write_lines(
        _get_memory_txt(),
        _normalize_consolidated_items([item.strip() for item in memories.split("\n")], False),
    )
    _update_skill()
    return None


def consolidate_history(history: str, hash: str) -> str | None:
    if _get_hash(_get_history_txt()).split(" ")[1] != hash.strip():
        return (
            "Hash do not match! No consolidation occurred. Check the hash by running view_history"
        )
    _write_lines(
        _get_history_txt(),
        _normalize_consolidated_items([item.strip() for item in history.split("\n")], True),
    )
    return None


def reset() -> None:
    _get_memory_txt().write_text("")
    _get_history_txt().write_text("")
    _update_skill()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add_memory command
    add_memory_parser = subparsers.add_parser("add_memory", help="Add memory entry")
    add_memory_parser.add_argument("text", help="Memory text to add")
    add_memory_parser.add_argument(
        "--group", choices=["user", "context", "notes"], default="notes", help="Memory group"
    )

    # add_history command
    add_history_parser = subparsers.add_parser("add_history", help="Add history entry")
    add_history_parser.add_argument("text", help="History text to add")
    add_history_parser.add_argument(
        "--group", choices=["user", "context", "notes"], default="notes", help="History group"
    )

    # search_memory command
    search_memory_parser = subparsers.add_parser("search_memory", help="Search memory")
    search_memory_parser.add_argument("query", help="Search query")
    search_memory_parser.add_argument(
        "--group", choices=["user", "context", "notes"], default="", help="Memory group to search"
    )
    search_memory_parser.add_argument(
        "--top_k", type=int, default=5, help="Number of results to return"
    )

    # search_history command
    search_history_parser = subparsers.add_parser("search_history", help="Search history")
    search_history_parser.add_argument("query", help="Search query")
    search_history_parser.add_argument(
        "--group", choices=["user", "context", "notes"], default="", help="History group to search"
    )
    search_history_parser.add_argument(
        "--top_k", type=int, default=5, help="Number of results to return"
    )

    # view_memory command
    subparsers.add_parser("view_memory", help="View full memory")

    # view_history command
    subparsers.add_parser("view_history", help="View full history")

    # reset command
    subparsers.add_parser("reset", help="Reset all memory and history")

    # consolidate_memory command
    consolidate_memory_parser = subparsers.add_parser(
        "consolidate_memory", help="Consolidate memory"
    )
    consolidate_memory_parser.add_argument("memories", help="Memory content to consolidate")
    consolidate_memory_parser.add_argument("hash", help="Memory hash for validation")

    # consolidate_history command
    consolidate_history_parser = subparsers.add_parser(
        "consolidate_history", help="Consolidate history"
    )
    consolidate_history_parser.add_argument("history", help="History content to consolidate")
    consolidate_history_parser.add_argument("hash", help="History hash for validation")

    args = parser.parse_args()

    if args.command == "add_memory":
        add_memory(args.text, args.group)
        print(f"Added memory: {args.text}")
    elif args.command == "add_history":
        add_history(args.text, args.group)
        print(f"Added history: {args.text}")
    elif args.command == "search_memory":
        print(search_memory(args.query, args.group, args.top_k))
    elif args.command == "search_history":
        print(search_history(args.query, args.group, args.top_k))
    elif args.command == "view_memory":
        print(view_memory())
    elif args.command == "view_history":
        print(view_history())
    elif args.command == "reset":
        reset()
        print("Memory and history reset successfully")
    elif args.command == "consolidate_memory":
        result = consolidate_memory(args.memories, args.hash)
        if result:
            print(result)
        else:
            print("Memory consolidated successfully")
    elif args.command == "consolidate_history":
        result = consolidate_history(args.history, args.hash)
        if result:
            print(result)
        else:
            print("History consolidated successfully")
