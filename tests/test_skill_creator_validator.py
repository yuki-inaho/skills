"""Strict YAML frontmatter validator tests.

Each invalid case is a real file that the validator must reject. The advisory
heading check must stay a warning: an equivalent operational layout is allowed.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "skills" / "skill-creator" / "scripts" / "validate_skill.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_skill", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load()


def _skill(tmp_path: Path, name: str, frontmatter: str, body: str = "# body\n") -> Path:
    directory = tmp_path / name
    directory.mkdir()
    (directory / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return directory


def test_plain_description_is_valid(tmp_path: Path) -> None:
    path = _skill(tmp_path, "plain-skill", "name: plain-skill\ndescription: Use when testing.")
    errors, _warnings = validator.validate(path)
    assert errors == []


def test_quoted_description_with_colon_space_is_valid(tmp_path: Path) -> None:
    path = _skill(
        tmp_path,
        "quoted-skill",
        "name: quoted-skill\ndescription: 'Use when x. Triggers: a, b.'",
    )
    errors, _warnings = validator.validate(path)
    assert errors == []


def test_folded_description_is_valid(tmp_path: Path) -> None:
    path = _skill(
        tmp_path,
        "folded-skill",
        "name: folded-skill\ndescription: >-\n  Use when testing a folded description.\n  Triggers: a, b.",
    )
    errors, _warnings = validator.validate(path)
    assert errors == []


def test_literal_block_description_is_valid(tmp_path: Path) -> None:
    path = _skill(
        tmp_path,
        "literal-skill",
        "name: literal-skill\ndescription: |\n  Use when testing a literal block.\n  Second line.",
    )
    errors, _warnings = validator.validate(path)
    assert errors == []


def test_unquoted_colon_space_is_rejected(tmp_path: Path) -> None:
    path = _skill(
        tmp_path,
        "colon-skill",
        "name: colon-skill\ndescription: Use when x. Triggers: a, b.",
    )
    errors, _warnings = validator.validate(path)
    assert errors
    assert "invalid YAML" in errors[0]


def test_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    path = _skill(
        tmp_path,
        "duplicate-skill",
        "name: duplicate-skill\ndescription: Use when x.\ndescription: Use when y.",
    )
    errors, _warnings = validator.validate(path)
    assert errors
    assert "duplicate frontmatter key" in errors[0]


def test_non_mapping_frontmatter_is_rejected(tmp_path: Path) -> None:
    path = _skill(tmp_path, "list-skill", "- name: list-skill\n- description: Use when x.")
    errors, _warnings = validator.validate(path)
    assert errors
    assert "must be a YAML mapping" in errors[0]


def test_missing_frontmatter_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "missing-skill"
    directory.mkdir()
    (directory / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
    errors, _warnings = validator.validate(directory)
    assert errors
    assert "missing or malformed frontmatter" in errors[0]


def test_missing_name_is_rejected(tmp_path: Path) -> None:
    path = _skill(tmp_path, "missing-name", "description: Use when x.")
    errors, _warnings = validator.validate(path)
    assert any("'name' is required" in error for error in errors)


def test_name_directory_mismatch_is_rejected(tmp_path: Path) -> None:
    path = _skill(tmp_path, "expected-name", "name: other-name\ndescription: Use when x.")
    errors, _warnings = validator.validate(path)
    assert any("must equal directory name" in error for error in errors)


def test_non_kebab_case_name_is_rejected(tmp_path: Path) -> None:
    path = _skill(tmp_path, "Bad_Name", "name: Bad_Name\ndescription: Use when x.")
    errors, _warnings = validator.validate(path)
    assert any("kebab-case" in error for error in errors)


def test_empty_description_is_rejected(tmp_path: Path) -> None:
    path = _skill(tmp_path, "empty-description", "name: empty-description\ndescription: ''")
    errors, _warnings = validator.validate(path)
    assert any("'description' is required" in error for error in errors)


def test_non_string_description_is_rejected(tmp_path: Path) -> None:
    path = _skill(tmp_path, "number-description", "name: number-description\ndescription: 12")
    errors, _warnings = validator.validate(path)
    assert any("'description' is required" in error for error in errors)


def test_recommended_headings_are_advisory_not_errors(tmp_path: Path) -> None:
    path = _skill(
        tmp_path,
        "advisory-skill",
        "name: advisory-skill\ndescription: Use when x.",
        body="# Advisory\n\nEquivalent operational content without the suggested headings.\n",
    )
    errors, warnings = validator.validate(path)
    assert errors == []
    assert any("missing recommended headings" in warning for warning in warnings)


def test_main_returns_one_for_invalid_and_zero_for_valid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    valid = _skill(tmp_path, "cli-valid", "name: cli-valid\ndescription: Use when x.")
    invalid = _skill(tmp_path, "cli-invalid", "name: cli-invalid\ndescription: Use when x: y.")
    assert validator.main([str(valid)]) == 0
    assert validator.main([str(invalid)]) == 1
    captured = capsys.readouterr()
    assert "INVALID" in captured.out


def test_dependency_is_declared_and_portable() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = "\n".join(config["dependency-groups"]["dev"])
    assert "pyyaml" in dev.lower()
    source = VALIDATOR.read_text(encoding="utf-8")
    assert "# /// script" in source
    assert "PyYAML" in source
