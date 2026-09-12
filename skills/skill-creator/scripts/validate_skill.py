#!/usr/bin/env python3
"""Minimal dependency-free validator for SKILL.md files.

Checks (hard errors -> exit 1):
  - SKILL.md exists and starts with a frontmatter block delimited by '---'
  - frontmatter has non-empty 'name' and 'description'
  - 'name' equals the containing directory name

Warnings (exit still 0):
  - description does not contain 'Use when'
  - missing recommended sections (When to use / Prerequisites / Procedure /
    Verification / Failure handling / Growth log)
  - no fenced code block

Usage:
  python3 validate_skill.py [path ...]
  # defaults to the 'skills' directory next to the repository root that contains this script
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RECOMMENDED_SECTIONS = (
    "## When to use",
    "## Prerequisites",
    "## Procedure",
    "## Verification",
    "## Failure handling",
    "## Growth log",
)
FRONTMATTER_FIELD = re.compile(r"^(name|description):\s*(.+)$", re.MULTILINE)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace("''", "'").replace('\\"', '"') if value[0] == "'" else inner
    return value


def parse_frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    block = text[4:end]
    fields: dict[str, str] = {}
    # only single-line name/description are supported (quote multi-line values instead)
    for match in FRONTMATTER_FIELD.finditer(block):
        fields[match.group(1)] = _unquote(match.group(2))
    return fields


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    skill_md = path / "SKILL.md" if path.is_dir() else path
    directory = skill_md.parent
    if not skill_md.is_file():
        return [f"{skill_md}: not found"], warnings
    text = skill_md.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    if fields is None:
        return [f"{skill_md}: missing or malformed frontmatter block"], warnings
    name = fields.get("name", "")
    description = fields.get("description", "")
    if not name:
        errors.append(f"{skill_md}: 'name' is required")
    elif name != directory.name:
        errors.append(f"{skill_md}: 'name' ({name!r}) must equal directory name ({directory.name!r})")
    if not description:
        errors.append(f"{skill_md}: 'description' is required")
    elif "Use when" not in description:
        warnings.append(f"{skill_md}: description should contain 'Use when ...'")
    for section in RECOMMENDED_SECTIONS:
        if f"\n{section}\n" not in text:
            warnings.append(f"{skill_md}: missing recommended section {section!r}")
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
