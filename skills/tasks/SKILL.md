---
name: tasks
description: Recurring task management with best-effort execution
---

# Tasks

## Structure

- tasks.txt - Task definitions with trigger times and recurrence patterns
- output/<refno>/ - Completed task outputs as markdown files

## Recurrence Patterns

Simple format with **minimum 30-minute increments**:

- `every 30m` - Every 30 minutes
- `every 1h` - Every hour
- `every 2h` - Every 2 hours
- `every 24h` - Every 24 hours
- `daily HH:MM` - Daily at specific UTC time (e.g., `daily 09:00`)

## Usage

- create_task: Create a new task (optionally recurring)
- list_tasks: List all tasks
- get_due_tasks: Get tasks that are due now (next_trigger <= current time)
- complete_task: Mark task as done, save output to output/<refno>/
- delete_task: Remove a task entirely

## Best Effort Execution

Tasks are executed on a best-effort basis:

- Call `get_due_tasks()` to see which tasks need execution
- Missed executions don't accumulate
- Failed tasks still save output; recurring tasks re-schedule
- Agent decides when to re-attempt failed tasks

## Output Format

When a task completes, output is saved to:
`output/<refno>/<isodatetime>-<hash>.md`

With YAML frontmatter containing:
- refno: Task reference number
- description: Task description
- completed: Completion timestamp
- recurrence: Recurrence pattern (if recurring)
- next_trigger: Next scheduled run (if recurring)

## Tasks
