import pytest

from structured_skills.validator import (
    MAX_DESCRIPTION_LENGTH,
    MAX_SKILL_NAME_LENGTH,
    _validate_compatibility,
    _validate_description,
    _validate_name,
    find_skill_md,
    parse_frontmatter,
    validate,
    validate_metadata,
)


class TestFindSkillMd:
    def test_finds_uppercase_skill_md(self, temp_skill_dir):
        skill_dir = temp_skill_dir / "example-skill"
        result = find_skill_md(skill_dir)
        assert result is not None
        assert result.name == "SKILL.md"

    def test_finds_lowercase_skill_md(self, tmp_path):
        skill_dir = tmp_path / "lowercase-skill"
        skill_dir.mkdir()
        (skill_dir / "skill.md").write_text("---\nname: test\ndescription: test\n---\nbody")
        result = find_skill_md(skill_dir)
        assert result is not None
        assert result.name.lower() == "skill.md"

    def test_returns_none_when_not_found(self, tmp_path):
        skill_dir = tmp_path / "no-skill-md"
        skill_dir.mkdir()
        result = find_skill_md(skill_dir)
        assert result is None


class TestParseFrontmatter:
    def test_parses_valid_frontmatter(self):
        content = "---\nname: test-skill\ndescription: A test\n---\n# Body"
        metadata, body = parse_frontmatter(content)
        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test"
        assert body == "# Body"

    def test_raises_on_missing_frontmatter(self):
        content = "# No frontmatter"
        with pytest.raises(ValueError, match="must start with YAML frontmatter"):
            parse_frontmatter(content)

    def test_raises_on_unclosed_frontmatter(self):
        content = "---\nname: test"
        with pytest.raises(ValueError, match="not properly closed"):
            parse_frontmatter(content)

    def test_raises_on_invalid_yaml(self):
        content = "---\nname: [invalid yaml: unclosed\n---\nbody"
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_frontmatter(content)


class TestValidateName:
    def test_valid_name(self):
        errors = _validate_name("valid-skill-name")
        assert len(errors) == 0

    def test_valid_name_with_unicode(self):
        errors = _validate_name("skill-name-中文")
        assert len(errors) == 0

    def test_empty_name(self):
        errors = _validate_name("")
        assert len(errors) > 0
        assert "non-empty" in errors[0]

    def test_uppercase_name(self):
        errors = _validate_name("Invalid-Name")
        assert len(errors) > 0
        assert "lowercase" in errors[0]

    def test_name_starts_with_hyphen(self):
        errors = _validate_name("-invalid")
        assert len(errors) > 0
        assert "start or end with a hyphen" in errors[0]

    def test_name_ends_with_hyphen(self):
        errors = _validate_name("invalid-")
        assert len(errors) > 0

    def test_consecutive_hyphens(self):
        errors = _validate_name("invalid--name")
        assert len(errors) > 0
        assert "consecutive hyphens" in errors[0]

    def test_name_too_long(self):
        long_name = "a" * (MAX_SKILL_NAME_LENGTH + 1)
        errors = _validate_name(long_name)
        assert len(errors) > 0
        assert "exceeds" in errors[0]

    def test_directory_name_mismatch(self, tmp_path):
        skill_dir = tmp_path / "different-name"
        errors = _validate_name("skill-name", skill_dir)
        assert len(errors) > 0
        assert "must match" in errors[0]


class TestValidateDescription:
    def test_valid_description(self):
        errors = _validate_description("A valid description")
        assert len(errors) == 0

    def test_empty_description(self):
        errors = _validate_description("")
        assert len(errors) > 0
        assert "non-empty" in errors[0]

    def test_description_too_long(self):
        long_desc = "a" * (MAX_DESCRIPTION_LENGTH + 1)
        errors = _validate_description(long_desc)
        assert len(errors) > 0
        assert "exceeds" in errors[0]


class TestValidateCompatibility:
    def test_valid_compatibility(self):
        errors = _validate_compatibility(">=1.0.0")
        assert len(errors) == 0

    def test_non_string_compatibility(self):
        errors = _validate_compatibility(123)  # type: ignore
        assert len(errors) > 0
        assert "must be a string" in errors[0]


class TestValidateMetadata:
    def test_valid_metadata(self):
        metadata = {"name": "test-skill", "description": "A test skill"}
        errors = validate_metadata(metadata)
        assert len(errors) == 0

    def test_missing_required_fields(self):
        metadata = {}
        errors = validate_metadata(metadata)
        assert len(errors) > 0
        assert any("name" in e for e in errors)
        assert any("description" in e for e in errors)

    def test_extra_fields(self):
        metadata = {"name": "test", "description": "test", "extra": "field"}
        errors = validate_metadata(metadata)
        assert len(errors) > 0
        assert "Unexpected fields" in errors[0]


class TestValidate:
    def test_valid_skill_directory(self, temp_skill_dir):
        skill_dir = temp_skill_dir / "example-skill"
        errors = validate(skill_dir)
        assert len(errors) == 0

    def test_nonexistent_directory(self, tmp_path):
        errors = validate(tmp_path / "nonexistent")
        assert len(errors) > 0
        assert "does not exist" in errors[0]

    def test_not_a_directory(self, tmp_path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        errors = validate(file_path)
        assert len(errors) > 0
        assert "Not a directory" in errors[0]

    def test_missing_skill_md(self, invalid_skill_dir):
        skill_dir = invalid_skill_dir / "missing-md-skill"
        errors = validate(skill_dir)
        assert len(errors) > 0
        assert "Missing required file" in errors[0]

    def test_empty_scripts_directory(self, empty_scripts_dir):
        skill_dir = empty_scripts_dir / "empty-scripts-skill"
        errors = validate(skill_dir)
        assert len(errors) > 0
        assert "no Python scripts found" in errors[0]
