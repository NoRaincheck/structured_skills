"""
memory.py dynamically updates SKILL.md
"""

import hashlib
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path
from typing import Literal

import platformdirs

SKILL_MD_MEMORIES = "## Memories"
MEMORY_WINDOW = 50
HISTORY_WINDOW = 150
WARNING_MESSAGE = "_comment:FULL PLEASE CONSOLIDATE"
DEFAULT_GROUP = "notes"
SKILLNAME = "memory"


def _get_data_dir() -> Path:
    """Get the data directory using platformdirs, or skill root if not available."""
    data_dir = Path(platformdirs.user_data_dir(appname=SKILLNAME))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _get_skill_md() -> Path:
    """Get the SKILL.md path."""
    file = _get_data_dir() / "SKILL.md"
    file.touch(exist_ok=True)
    return file


def _get_memory_txt() -> Path:
    """Get the memory.txt path."""
    file = _get_data_dir() / "memory.txt"
    file.touch(exist_ok=True)
    return file


def _get_history_txt() -> Path:
    """Get the history.txt path."""
    file = _get_data_dir() / "history.txt"
    file.touch(exist_ok=True)
    return file


def _ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)


def _iso_date():
    return datetime.now(timezone.utc).isoformat()


def _update_skill():
    _ensure_data_dir()
    memory = f"{SKILL_MD_MEMORIES}\n\n" + _get_memory_txt().read_text()
    with _get_skill_md().open("w") as f:
        f.write(memory)


def _compact(items: list[str], window: int) -> str:
    if len(items) < window:
        return "\n".join(items)
    no_warning = [x for x in items if not x.startswith("_coment:")]
    items = [WARNING_MESSAGE] + no_warning[:window]
    return "\n".join(items)


def _add_event(
    target: Path,
    window: int,
    text: str,
    group: Literal["user", "context", "notes"] | str | None = None,
):
    group = group or DEFAULT_GROUP
    item = [f"[{group}] {text}"] + [s for s in target.read_text().split("\n")]
    with target.open("w") as f:
        f.write(_compact(item, window))


def add_memory(text: str, group: Literal["user", "context", "notes"] | None = None):
    _add_event(_get_memory_txt(), MEMORY_WINDOW, text, group)
    _update_skill()


def add_history(text, group: Literal["user", "context", "notes"] | None = None):
    event_time = _iso_date()
    _add_event(_get_history_txt(), HISTORY_WINDOW, f"{event_time} {text}", group)


def _search_event(
    target: Path,
    query: str,
    group: Literal["user", "context", "notes"] | str | None = "",
    top_k: int = 5,
) -> list[str]:
    if group not in ["user", "context", "notes"]:
        group = None
    items = [x.strip() for x in target.read_text().split("\n") if "_comment" not in x]
    if group is not None:
        items = [x for x in items if f"[{group}]" in x]

    # compaction may screw things up so we need to safely get the content.
    content = []
    for item in items:
        if "]" in item:
            content.append(item.rsplit("]", 1)[1])
        else:
            content.append(item)

    matches = get_close_matches(query, content, cutoff=0)[:top_k]
    results = []
    for match in matches:
        results.append(items[content.index(match)])
    return results


def search_memory(
    query: str,
    group: Literal["user", "context", "notes"] | str | None = "",
    top_k: int = 5,
) -> str:
    results = _search_event(_get_memory_txt(), query, group, top_k)
    return "\n".join(results)


def search_history(
    query: str,
    group: Literal["user", "context", "notes"] | str | None = "",
    top_k: int = 5,
) -> str:
    results = _search_event(_get_history_txt(), query, group, top_k)
    return "\n".join(results)


def _get_hash(target: Path) -> str:
    with target.open("rb") as f:
        hash_digest = hashlib.md5(f.read()).hexdigest()
    hash_info = f"hash_info: {hash_digest[:2]}"
    return hash_info


def _view_event(target: Path) -> str:
    hash_info = _get_hash(target)
    items = target.read_text().split("\n")
    return f"{hash_info}\n" + "\n".join(items)


def view_memory() -> str:
    return _view_event(_get_memory_txt())


def view_history() -> str:
    return _view_event(_get_history_txt())


def consolidate_memory(memories: str, hash: str):
    hash_info = _get_hash(_get_memory_txt()).split(" ")[1]
    if hash_info != hash.strip():
        return "Hash do not match! No consolidation occurred. Check the hash by running view_memory"

    items: list[str] = [item.strip() for item in memories.split("\n")]
    cleaned_memories: list[str] = []
    for item in items:
        if item.strip().startswith("["):
            cleaned_memories.append(item)
        else:
            cleaned_memories.append(f"[notes] {item}")
    with _get_memory_txt().open("w") as f:
        f.write("\n".join(cleaned_memories))
    _update_skill()


def consolidate_history(history: str, hash: str):
    event_time = _iso_date()
    hash_info = _get_hash(_get_history_txt()).split(" ")[1]
    if hash_info != hash.strip():
        return (
            "Hash do not match! No consolidation occurred. Check the hash by running view_history"
        )
    items: list[str] = [item.strip() for item in history.split("\n")]
    cleaned_history: list[str] = []
    for item in items:
        if item.strip().startswith("["):
            cleaned_history.append(item)
        else:
            cleaned_history.append(f"[notes] [{event_time}] {item}")
    with _get_history_txt().open("w") as f:
        f.write("\n".join(cleaned_history))


def reset():
    _ensure_data_dir()
    _get_memory_txt().write_text("")
    _get_history_txt().write_text("")
    _get_memory_txt().write_text("")


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
        results = search_memory(args.query, args.group, args.top_k)
        for result in results:
            print(result)
    elif args.command == "search_history":
        results = search_history(args.query, args.group, args.top_k)
        for result in results:
            print(result)
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
