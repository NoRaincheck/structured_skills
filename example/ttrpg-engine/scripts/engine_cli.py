#!/usr/bin/env python3
"""CLI toolkit for TTRPG."""

from __future__ import annotations

import argparse
import json
import random

SCENE_COMPLICATIONS = [
    "Hostile forces oppose you",
    "An obstacle blocks your way",
    "Wouldn't it suck if...",
    "An NPC acts suddenly",
    "All is not as it seems",
    "Things actually go as planned",
]

ALTERED_SCENE = [
    "A major detail is enhanced or worse",
    "The environment is different",
    "Unexpected NPCs are present",
    "Add a scene complication",
    "Add a pacing move",
    "Add a random event",
]

ORACLE_HOW = [
    "Surprisingly lacking",
    "Less than expected",
    "About average",
    "About average",
    "More than expected",
    "Extraordinary",
]

PACING_MOVES = [
    "Foreshadow trouble",
    "Reveal a new detail",
    "An NPC takes action",
    "Advance a threat",
    "Advance a plot",
    "Add a random event",
]

FAILURE_MOVES = [
    "Cause harm",
    "Put someone in a spot",
    "Offer a choice",
    "Advance a threat",
    "Reveal an unwelcome truth",
    "Foreshadow trouble",
]

BASE_ACTION = [
    "seek",
    "oppose",
    "communicate",
    "move",
    "harm",
    "create",
    "reveal",
    "command",
    "take",
    "protect",
    "assist",
    "transform",
    "deceive",
    "investigate",
    "observe",
    "repair",
    "restore",
    "trade",
    "sabotage",
    "recover",
    "hunt",
    "hide",
    "ambush",
    "fortify",
    "coordinate",
    "negotiate",
    "evade",
    "challenge",
    "confront",
    "discover",
]

BASE_DETAIL = [
    "small",
    "large",
    "old",
    "new",
    "mundane",
    "simple",
    "complex",
    "unsavory",
    "specialized",
    "unexpected",
    "exotic",
    "dignified",
    "unique",
    "fragile",
    "reinforced",
    "hidden",
    "weathered",
    "ornate",
    "sparse",
    "crowded",
    "pristine",
    "contested",
    "volatile",
    "improvised",
    "coded",
    "ritual",
    "symbolic",
    "unfinished",
    "forgotten",
    "forbidden",
]

BASE_TOPIC = [
    "current need",
    "allies",
    "community",
    "history",
    "future plans",
    "enemies",
    "knowledge",
    "rumors",
    "plot arc",
    "recent events",
    "equipment",
    "faction",
    "the PCs",
    "supply lines",
    "territory",
    "leadership",
    "resources",
    "obligations",
    "debt",
    "loyalty",
    "rituals",
    "law",
    "smuggling",
    "mystery",
    "legacy",
    "disaster",
    "migration",
    "prophecy",
    "infrastructure",
    "reputation",
]

ACTION_SUFFIXES = [
    "urgently",
    "quietly",
    "openly",
    "carefully",
    "recklessly",
    "for leverage",
    "for survival",
    "under pressure",
    "with allies",
    "in secret",
]

DETAIL_SUFFIXES = [
    "by design",
    "by necessity",
    "under strain",
    "in plain sight",
    "with hidden cost",
    "with ceremonial value",
    "with tactical value",
    "for public display",
    "for private use",
    "of uncertain origin",
]

TOPIC_SUFFIXES = [
    "in crisis",
    "under negotiation",
    "under threat",
    "with unexpected allies",
    "with hidden motives",
    "during transition",
    "at a breaking point",
    "in the spotlight",
    "behind closed doors",
    "across borders",
]


def d6(rng: random.Random | None = None) -> int:
    if rng is None:
        rng = random.Random()
    return rng.randint(1, 6)


def choose(rng: random.Random, items: list[str]) -> str:
    return items[rng.randrange(len(items))]


def yesno_oracle(
    likelihood: str = "even", rng: random.Random | None = None
) -> dict[str, int | str]:
    thresholds = {"likely": 3, "even": 4, "unlikely": 5}
    if likelihood not in thresholds:
        raise ValueError(f"Invalid likelihood: {likelihood}")
    answer_roll = d6(rng)
    mod_roll = d6(rng)
    answer = "yes" if answer_roll >= thresholds[likelihood] else "no"
    modifier = "but..." if mod_roll == 1 else ("and..." if mod_roll == 6 else "")
    return {
        "answer": answer,
        "modifier": modifier,
        "answer_roll": answer_roll,
        "modifier_roll": mod_roll,
    }


def expand_keywords(base: list[str], suffixes: list[str], count: int) -> list[str]:
    """Expand base focus words to a deterministic, unique list."""
    if count < 1:
        raise ValueError("count must be >= 1")
    if count > 100:
        raise ValueError("count must be <= 100")

    expanded: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        normalized = item.strip()
        if normalized and normalized not in seen and len(expanded) < 100:
            seen.add(normalized)
            expanded.append(normalized)

    for word in base:
        add(word)
    for word in base:
        for suffix in suffixes:
            add(f"{word} {suffix}")
            if len(expanded) >= 100:
                break
        if len(expanded) >= 100:
            break
    return expanded[:count]


def focus_keywords(name: str, count: int = 1) -> list[str]:
    if name == "action":
        return expand_keywords(BASE_ACTION, ACTION_SUFFIXES, count)
    if name == "detail":
        return expand_keywords(BASE_DETAIL, DETAIL_SUFFIXES, count)
    if name == "topic":
        return expand_keywords(BASE_TOPIC, TOPIC_SUFFIXES, count)
    raise ValueError(f"Unsupported focus name: {name}")


def cmd_scene(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    complication = choose(rng, SCENE_COMPLICATIONS)
    altered_roll = d6(rng)
    payload = {
        "scene_complication": complication,
        "altered_roll": altered_roll,
        "altered_scene": altered_roll >= 5,
    }
    if altered_roll >= 5:
        payload["altered_result"] = choose(rng, ALTERED_SCENE)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_oracle_yesno(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    result = yesno_oracle(args.likelihood, rng)
    payload = {
        "likelihood": args.likelihood,
        "answer_roll": result["answer_roll"],
        "modifier_roll": result["modifier_roll"],
        "answer": result["answer"],
        "modifier": result["modifier"],
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_oracle_how(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    roll = d6(rng)
    payload = {"roll": roll, "result": ORACLE_HOW[roll - 1]}
    print(json.dumps(payload, indent=2))
    return 0


def cmd_pacing_move(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    roll = d6(rng)
    payload = {"roll": roll, "result": PACING_MOVES[roll - 1]}
    print(json.dumps(payload, indent=2))
    return 0


def cmd_failure_move(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    roll = d6(rng)
    payload = {"roll": roll, "result": FAILURE_MOVES[roll - 1]}
    print(json.dumps(payload, indent=2))
    return 0


def cmd_random_event(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    actions = focus_keywords("action", 100)
    topics = focus_keywords("topic", 100)
    payload = {
        "action_focus": choose(rng, actions),
        "topic_focus": choose(rng, topics),
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_keywords(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    words = focus_keywords(args.name, args.count)
    if args.shuffle:
        rng.shuffle(words)
    payload = {"name": args.name, "count": len(words), "keywords": words}
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One Page Solo Engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scene = sub.add_parser("scene", help="Roll scene complication and alteration")
    p_scene.add_argument("--seed", type=int, default=None, help="Random seed")
    p_scene.set_defaults(func=cmd_scene)

    p_yesno = sub.add_parser("oracle-yesno", help="Ask yes/no oracle")
    p_yesno.add_argument(
        "--likelihood",
        choices=["likely", "even", "unlikely"],
        default="even",
        help="Expected chance for yes",
    )
    p_yesno.add_argument("--seed", type=int, default=None, help="Random seed")
    p_yesno.set_defaults(func=cmd_oracle_yesno)

    p_how = sub.add_parser("oracle-how", help="Roll the 'how much' oracle")
    p_how.add_argument("--seed", type=int, default=None, help="Random seed")
    p_how.set_defaults(func=cmd_oracle_how)

    p_pacing = sub.add_parser("pacing-move", help="Roll a pacing move")
    p_pacing.add_argument("--seed", type=int, default=None, help="Random seed")
    p_pacing.set_defaults(func=cmd_pacing_move)

    p_failure = sub.add_parser("failure-move", help="Roll a failure move")
    p_failure.add_argument("--seed", type=int, default=None, help="Random seed")
    p_failure.set_defaults(func=cmd_failure_move)

    p_event = sub.add_parser("random-event", help="Generate action/topic random event")
    p_event.add_argument("--seed", type=int, default=None, help="Random seed")
    p_event.set_defaults(func=cmd_random_event)

    p_keywords = sub.add_parser("keywords", help="Generate expanded focus keywords")
    p_keywords.add_argument(
        "--name",
        choices=["action", "detail", "topic"],
        required=True,
        help="Focus table name",
    )
    p_keywords.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of keywords to output (max: 100)",
    )
    p_keywords.add_argument("--seed", type=int, default=None, help="Random seed")
    p_keywords.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle output order (use --seed for deterministic shuffle)",
    )
    p_keywords.set_defaults(func=cmd_keywords)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
