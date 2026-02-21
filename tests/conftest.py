import tempfile
from pathlib import Path

import pytest

VALID_SKILL_CONTENT = """---
name: example-skill
description: An example skill for testing
---

# Example Skill

This is an example skill for testing purposes.

## Usage

Use this skill to test the structured_skills library.
"""

VALID_SKILL_WITH_SCRIPTS = """---
name: test-skill
description: A test skill with scripts
---

# Test Skill

This skill has associated scripts.
"""


def script_content() -> str:
    return '''
def greet(name: str) -> str:
    """Greet a person by name."""
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''


@pytest.fixture
def temp_skill_dir():
    """Create a temporary directory with valid skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_root = Path(tmpdir)

        example_skill = skill_root / "example-skill"
        example_skill.mkdir()
        (example_skill / "SKILL.md").write_text(VALID_SKILL_CONTENT)

        test_skill = skill_root / "test-skill"
        test_skill.mkdir()
        (test_skill / "SKILL.md").write_text(VALID_SKILL_WITH_SCRIPTS)
        scripts_dir = test_skill / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "utils.py").write_text(script_content())

        yield skill_root


@pytest.fixture
def invalid_skill_dir():
    """Create a temporary directory with invalid skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_root = Path(tmpdir)

        missing_md = skill_root / "missing-md-skill"
        missing_md.mkdir()

        invalid_yaml = skill_root / "invalid-yaml-skill"
        invalid_yaml.mkdir()
        (invalid_yaml / "SKILL.md").write_text("not yaml frontmatter")

        yield skill_root


@pytest.fixture
def empty_scripts_dir():
    """Create a skill with an empty scripts directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_root = Path(tmpdir)

        skill = skill_root / "empty-scripts-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            VALID_SKILL_CONTENT.replace("example-skill", "empty-scripts-skill")
        )
        (skill / "scripts").mkdir()

        yield skill_root
