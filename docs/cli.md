# CLI Reference

The `structured_skills cli` command provides direct access to skills and scheduler behavior.

## Basic Pattern

```sh
uv run structured_skills cli <command> <skill_dir> [args]
```

Global options for `cli`:

- `--working-dir /path/to/session-or-channel`
- `--session-name <name>`

Persistence note:

- `load_scheduler` reads `SCHEDULER.toml` only (no state write).
- `scheduler_tick` reads `scheduler-state.json` from `--working-dir` first (then skill root as fallback), and always writes updated state to `--working-dir/scheduler-state.json`.

## Commands

### List skills

```sh
uv run structured_skills cli list_skills /path/to/root/skills
```

### Load a skill

```sh
uv run structured_skills cli load_skill /path/to/root/skills <skill_name>
```

### Read skill resource

```sh
uv run structured_skills cli read_skill_resource /path/to/root/skills <skill_name> <resource_name>
```

With arguments:

```sh
uv run structured_skills cli read_skill_resource /path/to/root/skills <skill_name> <resource_name> \
  --args '{"key":"value"}'
```

### Run skill function or script

```sh
uv run structured_skills cli run_skill_script /path/to/root/skills <skill_name> <function_or_script>
```

With arguments:

```sh
uv run structured_skills cli run_skill_script /path/to/root/skills <skill_name> <function_or_script> \
  --args '{"key":"value"}'
```

### Load scheduler definition

```sh
uv run structured_skills cli load_scheduler /path/to/root/skills
```

### Run one scheduler tick

```sh
uv run structured_skills cli scheduler_tick /path/to/root/skills
```

Optional scheduler tick overrides:

- `--task-results '{"task-id":{"status":"completed"}}'`
- `--now '2026-03-07T14:30:00Z'`
