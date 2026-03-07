---
name: memory
description: Lightweight memory and history
---

# Memory

## Structure

- `memory.txt` - Long-term facts (preferences, project context, relationships). Loaded into context through `SKILL.md`.
- `history.txt` - Append-only event log. Not loaded into context.

When a file reaches its window size, a warning line (`_comment:FULL PLEASE CONSOLIDATE`) is added at the top.

## Usage

- `add_memory` - Add a long-term fact to the top of memory.
- `add_history` - Add an event to the top of history.

- `search_memory` - Return top `k` memory matches for a query.
- `search_history` - Return top `k` history matches for a query.

- `view_memory` - Return full memory plus a short hash.
- `view_history` - Return full history plus a short hash.

- `consolidate_memory` - Rewrite memory with hash check.
- `consolidate_history` - Rewrite history with hash check.

## When to Update Memory?

Write important facts immediately using `add_memory`:
- `user`: user preferences/information (`I prefer dark mode`)
- `context`: project context (`The API uses OAuth2`)
- `notes`: miscellaneous items (`Alice is the project lead`)

## Consolidation

When memory reaches 50 items a warning is shown to consolidate.
When history reaches 150 items a message is displayed to consolidate.

At the limits, older items are dropped (last-in, first-out view at the top).

Use `view_memory` or `view_history` to read `hash_info` first, then pass the same hash to consolidation.
