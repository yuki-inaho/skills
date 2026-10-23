#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6,<7"]
# ///
"""Strict frontmatter validator for SKILL.md files.

The validator uses a real YAML safe parser. It rejects duplicate mapping keys and
non-mapping frontmatter instead of treating the fields as opaque regex captures.
Recommended headings are advisory: a skill may use equivalent operational
headings and still pass.

Hard errors (exit 1):
  - SKILL.md exists and starts with a frontmatter block delimited by '---'
  - the frontmatter is a YAML mapping
  - mapping keys are unique
  - 'name' is a non-empty kebab-case string equal to the directory name
  - 'description' is a non-empty string

Advisory warnings (exit still 0):
  - description does not contain 'Use when'
  - recommended sections are absent (equivalent content is allowed)
  - no fenced code block

Usage:
  uv run validate_skill.py [path ...]
  # defaults to the 'skills' directory of the repository that contains this script

PyYAML is declared in the repository's pyproject dev group. The PEP 723 block
lets a single copied script run with `uv run validate_skill.py`, without adding
a repository-local virtual environment.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

RECOMMENDED_SECTIONS = (
    "## When to use",
    "## Prerequisites",
    "## Procedure",
    "## Verification",
    "## Failure handling",
    "## Growth log",
)
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class FrontmatterError(ValueError):
    """Raised when the frontmatter cannot be parsed as a strict YAML mapping."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe loader that refuses duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"duplicate frontmatter key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def split_frontmatter(text: str) -> str | None:
    """Return the YAML block, or None when the delimiters are absent."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return None


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse frontmatter strictly. Raises FrontmatterError on any defect."""
    block = split_frontmatter(text)
    if block is None:
        raise FrontmatterError("missing or malformed frontmatter block")
    try:
        data = yaml.load(block, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as error:
        problem = getattr(error, "problem", None) or error.__class__.__name__
        mark = getattr(error, "problem_mark", None)
        location = f" (line {mark.line + 2}, column {mark.column + 1})" if mark else ""
        raise FrontmatterError(f"invalid YAML{location}: {problem}") from error
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return data


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    skill_md = path / "SKILL.md" if path.is_dir() else path
    directory = skill_md.parent
    if not skill_md.is_file():
        return [f"{skill_md}: not found"], warnings

    text = skill_md.read_text(encoding="utf-8")
    try:
        fields = parse_frontmatter(text)
    except FrontmatterError as error:
        return [f"{skill_md}: {error}"], warnings

    name = fields.get("name")
    description = fields.get("description")
    if not isinstance(name, str) or not name:
        errors.append(f"{skill_md}: 'name' is required and must be a string")
    else:
        if not KEBAB_CASE.fullmatch(name):
            errors.append(f"{skill_md}: 'name' must be kebab-case")
        if name != directory.name:
            errors.append(
                f"{skill_md}: 'name' ({name!r}) must equal directory name ({directory.name!r})"
            )
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{skill_md}: 'description' is required and must be a non-empty string")
    elif "Use when" not in description:
        warnings.append(f"{skill_md}: description should contain 'Use when ...'")

    missing = [section for section in RECOMMENDED_SECTIONS if f"\n{section}\n" not in text]
    if missing:
        warnings.append(
            f"{skill_md}: missing recommended headings {missing!r}; "
            "equivalent operational content is acceptable"
        )
    if "```" not in text:
        warnings.append(f"{skill_md}: no fenced code block")
    return errors, warnings


def default_targets() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    skills = repo_root / "skills"
    return sorted(p for p in skills.iterdir() if p.is_dir()) if skills.is_dir() else []


def main(argv: list[str]) -> int:
    targets = [Path(arg) for arg in argv] or default_targets()
    if not targets:
        print("no skills found to validate", file=sys.stderr)
        return 1
    errors: list[str] = []
    warnings: list[str] = []
    for target in targets:
        target_errors, target_warnings = validate(target)
        errors.extend(target_errors)
        warnings.extend(target_warnings)
        status = "INVALID" if target_errors else "ok"
        print(f"{status:8} {target}")
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(f"validated {len(targets)} skill(s): {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
