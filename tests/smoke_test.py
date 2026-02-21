import tempfile
from pathlib import Path

from structured_skills import SkillRegistry, validate


def test_import() -> None:
    """Smoke test: verify package can be imported."""
    import structured_skills

    assert hasattr(structured_skills, "SkillRegistry")


def test_skill_registry_init() -> None:
    """Smoke test: verify SkillRegistry can be initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SkillRegistry(Path(tmpdir))
        assert registry.skill_root_dir == Path(tmpdir)


def test_validate() -> None:
    """Smoke test: verify validate function works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        errors = validate(Path(tmpdir))
        assert isinstance(errors, list)


if __name__ == "__main__":
    test_import()
    test_skill_registry_init()
    test_validate()
    print("All smoke tests passed!")
