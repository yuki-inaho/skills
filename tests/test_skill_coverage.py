"""Dynamic skill-coverage manifest check.

The skill list comes from the tree. A new skill without a manifest entry or a
coverage heading fails; no fixed skill count is asserted.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "skill_coverage.json"
COVERAGE_DOC = ROOT / "docs" / "skill-coverage.md"


def discover_skill_names() -> list[str]:
    return sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))


def load_manifest() -> dict[str, dict[str, str]]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data["skills"]


def test_manifest_covers_every_discovered_skill_and_nothing_else() -> None:
    discovered = set(discover_skill_names())
    manifest = set(load_manifest())
    assert discovered == manifest, {
        "missing_from_manifest": sorted(discovered - manifest),
        "stale_manifest_entries": sorted(manifest - discovered),
    }


def test_every_manifest_entry_names_a_real_test_and_a_verification_limit() -> None:
    for skill, entry in load_manifest().items():
        for key in ("scenario", "tier", "test", "proves", "does_not_prove"):
            assert entry.get(key), f"{skill}: missing {key}"
        assert (ROOT / entry["test"]).is_file(), f"{skill}: missing {entry['test']}"


def test_coverage_document_has_one_heading_per_discovered_skill() -> None:
    text = COVERAGE_DOC.read_text(encoding="utf-8")
    for skill in discover_skill_names():
        assert f"## {skill}\n" in text, f"docs/skill-coverage.md に {skill} の見出しが無い"
