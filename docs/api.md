# Python API

## SkillRegistry

The main class for managing and interacting with skills.

```python
from pathlib import Path
from structured_skills import SkillRegistry
```

### Constructor

```python
registry = SkillRegistry(root: Path)
```

| Parameter | Type   | Description                             |
| --------- | ------ | --------------------------------------- |
| `root`    | `Path` | Root directory containing skill folders |

### Methods

#### `search(query: str = "", limit: int = 10) -> list[SkillSummary]`

Search for skills matching a query.

```python
results = registry.search("math", limit=5)
for skill in results:
    print(skill.name, skill.description)
```

#### `inspect(name: str, resource: str | None = None, include_body: bool = False) -> SkillSpec`

Get detailed information about a skill.

```python
spec = registry.inspect("math-skill")
print(spec.name, spec.description)
print(spec.scripts)  # List of available scripts
print(spec.functions)  # List of available functions
```

#### `execute(name: str, target: str, args: dict) -> Any`

Execute a skill target (function or script) with arguments.

```python
result = registry.execute("math-skill", "add", {"a": 2, "b": 3})
print(result)  # 5
```

#### `skill(name: str) -> SkillProxy`

Get a proxy object for calling skill functions/scripts as methods.

```python
proxy = registry.skill("math-skill")
result = proxy.add(a=2, b=3)  # 5
result = proxy.math_ops(a=2, b=3)  # Calls scripts/math_ops.py
```

## SkillProxy

A proxy object that allows calling skill functions and scripts as Python methods.

```python
proxy = registry.skill("skill-name")
result = proxy.function_name(arg1=value1, arg2=value2)
```

### Method Calls

- **Functions**: Call Python functions defined in the skill
- **Scripts**: Call scripts in the `scripts/` directory as methods

### Exceptions

- `AttributeError`: Function or script doesn't exist
- `TypeError`: Duplicate argument values provided

## SkillToolsBuilder

Builder class for creating SkillTools instances.

```python
from structured_skills import SkillToolsBuilder

tools = (
    SkillToolsBuilder(Path("skills"))
    .with_search()
    .with_inspect()
    .with_execute()
    .build()
)
```

### Methods

| Method           | Description                   |
| ---------------- | ----------------------------- |
| `with_search()`  | Add search capability         |
| `with_inspect()` | Add inspect capability        |
| `with_execute()` | Add execute capability        |
| `build()`        | Build the SkillTools instance |

## Types

### SkillSummary

```python
class SkillSummary(TypedDict):
    name: str
    description: str
```

### SkillSpec

```python
class SkillSpec(TypedDict):
    name: str
    description: str
    scripts: list[str]
    functions: list[str]
    resources: dict[str, str]
```

## Single-File Script

You can also use the single-file script directly with uv:

```python
# As a module
uv run structured_skills.py <skills_dir> search
uv run structured_skills.py <skills_dir> inspect <skill>
uv run structured_skills.py <skills_dir> execute <skill> <target> --args '{}'
```
