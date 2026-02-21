---
name: memory
description: Two-layer memory system
---

# Memory

## Structure

- memory.jsonl — Long-term facts (preferences, project context, relationships). Always loaded into your context.
- history.jsonl — Append-only event log. NOT loaded into context. 

When the memory or history window is met, a message: `{"_coment":"[FULL] PLEASE CONSOLIDATE"}` is added to the top of the respective file.

## Usage

- add_memory: adds long term fact to the top of the memory stack
- add_history: adds event of interest to the top of the history stack

- search_memory: given a query string returns the top k memory
- search_history: given a query string returns the top k history

- view_memory: returns the full memory with hash
- view_history: returns the full history with hash

- consolidate_memory: rewrites memory; requires providing the correct memory hash
- consolidate_history: rewrites history; requires providing the correct history hash

## When to Update Memory?

Write important facts immediately using `add_memory`:
- user: User preferences/information ("I prefer dark mode")
- context: Project context ("The API uses OAuth2")
- notes: Miscellaneous items ("Alice is the project lead")

## Consolidation

When memory reaches 50 items a message is displayed to consolidate. 
When history reaches 150 items a message is displayed to consolidate.

When the limits are reached, items are removed from memory/history based on last-in, first-out. 

To consolidate ensure you use `view_memory` or `view_history` to examine the `hash_info` first. Then follow the structure with `[{group}]` to consolidate memories and history.

## Memories

