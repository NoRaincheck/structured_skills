---
name: ttrpg-engine
description: Minimal solo RPG engine with CLI oracles, moves, and keyword generation.
---

# Table Top Role Play Engine Skill

Use this skill to run a lightweight GM-less RPG loop.

## What This Skill Provides

- Scene setup with complication and altered-scene checks
- Yes/No oracle with but/and modifier
- "How much" oracle
- Pacing and failure GM moves
- Random events using action/topic focus
- Expanded keyword generation for focus tables without card limits

## CLI Entry Point

Run from repository root:

```bash
uv run python example/one-page-solo-engine-skill/scripts/solo_engine_cli.py --help
```

Examples:

```bash
uv run python ./scripts/solo_engine_cli.py scene --seed 7
uv run python ./scripts/solo_engine_cli.py oracle-yesno --likelihood even --seed 7
uv run python ./scripts/solo_engine_cli.py random-event --seed 7
uv run python ./scripts/solo_engine_cli.py keywords --name action --count 10 --seed 7
```

## Notes

- `keywords` supports `action`, `detail`, and `topic`.
- Each keyword list can generate up to 100 distinct entries.
- Use `--seed` for reproducible outputs.
