"""Public structural contracts discovered from the tree.

The skill set is discovered dynamically; no fixed skill count is asserted. The
frontmatter parser is the same strict YAML path used by the bundled validator,
so a regex cannot make an invalid file look valid. Prose wording is not
mirrored here; only format contracts and file existence are checked.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
POLICY = ROOT / "docs" / "PUBLIC_SKILLS_POLICY.md"
VALIDATOR = ROOT / "skills" / "skill-creator" / "scripts" / "validate_skill.py"
ALLOWED_CHILDREN = {"SKILL.md", "agents", "references", "scripts", "assets", "LICENSE"}


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_skill", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def discover_skills() -> list[Path]:
    return sorted((ROOT / "skills").glob("*/SKILL.md"))


def test_at_least_one_skill_is_discovered() -> None:
    assert discover_skills(), "skills/*/SKILL.md が見つからない"


def test_every_skill_frontmatter_is_strict_yaml() -> None:
    for skill in discover_skills():
        fields = validator.parse_frontmatter(read(skill))
        assert isinstance(fields, dict)
        assert fields["name"] == skill.parent.name
        assert isinstance(fields["description"], str)
        assert fields["description"].strip()


def test_skill_names_are_kebab_case_and_description_is_nonempty() -> None:
    for skill in discover_skills():
        fields = validator.parse_frontmatter(read(skill))
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"])


def test_skill_directories_contain_only_portable_files() -> None:
    for skill in discover_skills():
        entries = {path.name for path in skill.parent.iterdir()}
        assert entries <= ALLOWED_CHILDREN, (
            f"{skill.parent.name}: unexpected bundled entries {sorted(entries - ALLOWED_CHILDREN)}"
        )


def test_policy_document_is_linked_from_readme() -> None:
    assert POLICY.is_file()
    assert "docs/PUBLIC_SKILLS_POLICY.md" in read(README)


def test_readme_lists_every_discovered_skill() -> None:
    readme = read(README)
    for skill in discover_skills():
        assert f"](skills/{skill.parent.name}/SKILL.md)" in readme, (
            f"README の一覧に {skill.parent.name} が無い"
        )


def _generated_metadata_block() -> tuple[int, set[str]]:
    text = read(README)
    match = re.search(
        r"<!-- BEGIN GENERATED:openai-metadata -->(.*?)<!-- END GENERATED:openai-metadata -->",
        text,
        flags=re.DOTALL,
    )
    assert match, "README に生成ブロックが無い"
    block = match.group(1)
    count_match = re.search(r"[（(](\d+)[）)]", block)
    assert count_match, "生成ブロックに件数が無い"
    names = set(re.findall(r"`([a-z0-9-]+)`", block))
    return int(count_match.group(1)), names


def test_readme_metadata_block_matches_the_tree() -> None:
    actual = {
        skill.parent.name
        for skill in discover_skills()
        if (skill.parent / "agents" / "openai.yaml").is_file()
    }
    count, listed = _generated_metadata_block()
    assert count == len(actual)
    assert listed == actual


def test_relative_markdown_links_resolve_inside_each_skill() -> None:
    """A SKILL.md link to a bundled reference/asset must point at a real file."""
    link = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for skill in discover_skills():
        for target in link.findall(read(skill)):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            resolved = (skill.parent / target).resolve()
            assert resolved.is_file(), f"{skill.parent.name}: missing link target {target}"


def test_referenced_bundled_scripts_exist() -> None:
    """A command that points at a local scripts/ path must have a real bundle."""
    command_path = re.compile(r"(?:python3?|bash|sh)\s+((?:\./)?(?:scripts|assets)/[\w./-]+)")
    for skill in discover_skills():
        for target in command_path.findall(read(skill)):
            resolved = (skill.parent / target).resolve()
            assert resolved.is_file(), f"{skill.parent.name}: missing bundled command {target}"
