# Validation

Validate your skills directory before running in production.

## Validate

```sh
uv run structured_skills check /path/to/root/skills
```

## Validate and Auto-fix

```sh
uv run structured_skills check /path/to/root/skills --fix
```

When `--fix` is used, `structured_skills` attempts dependency fixes and runs formatting/linting passes in the target skills directory.

## Notes

- Validation runs per skill directory under the provided root.
- Hidden directories are ignored.
- A non-zero exit status is returned when validation errors remain.
