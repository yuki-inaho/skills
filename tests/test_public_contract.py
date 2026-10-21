"""公開物の構造（frontmatter・リンク・実在）と、変更した公開ファイルのプライバシー走査。

文言の一致は検証しない（挙動ではなく表現を固定してしまうため）。スキルが案内する
コマンドの実挙動は test_agent_jsonl_contract.py が合成データで確認する。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
POLICY = ROOT / "docs" / "PUBLIC_SKILLS_POLICY.md"
SKILLS = (
    ROOT / "skills" / "agent-jsonl-compact-reader" / "SKILL.md",
    ROOT / "skills" / "harness2-portable-workflow" / "SKILL.md",
    ROOT / "skills" / "public-repository-privacy-review" / "SKILL.md",
    ROOT / "skills" / "write-evidence-based-adr" / "SKILL.md",
    ROOT / "skills" / "review-measurement-contract" / "SKILL.md",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n"), "YAML frontmatter で始まる必要がある"
    return text.split("---", 2)[1]


def _description(frontmatter: str) -> str:
    lines = frontmatter.splitlines()
    collected: list[str] = []
    capturing = False
    for line in lines:
        if line.startswith("description:"):
            capturing = True
            remainder = line.split(":", 1)[1].strip()
            if remainder not in {">", ">-", "|", "|-"}:
                collected.append(remainder)
            continue
        if capturing:
            if line.startswith((" ", "\t")):
                collected.append(line.strip())
            elif line.strip():
                break
    return " ".join(collected).strip()


@pytest.mark.parametrize("skill", SKILLS, ids=[path.parent.name for path in SKILLS])
def test_skill_frontmatter_names_and_describes_the_skill(skill: Path) -> None:
    text = read(skill)
    frontmatter = _frontmatter(text)
    assert f"name: {skill.parent.name}" in frontmatter.splitlines()
    description = _description(frontmatter)
    assert description, "description が空"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", skill.parent.name)


@pytest.mark.parametrize(
    "skill",
    SKILLS,
    ids=[path.parent.name for path in SKILLS],
)
def test_skill_directory_contains_only_portable_files(skill: Path) -> None:
    allowed = {"SKILL.md", "agents", "references", "scripts", "assets", "LICENSE"}
    entries = {path.name for path in skill.parent.iterdir()}
    assert entries <= allowed, f"想定外の同梱物: {sorted(entries - allowed)}"


def test_policy_document_is_linked_from_readme() -> None:
    assert POLICY.is_file()
    assert "docs/PUBLIC_SKILLS_POLICY.md" in read(README)


def test_readme_lists_every_public_skill() -> None:
    readme = read(README)
    for skill in SKILLS:
        link = f"](skills/{skill.parent.name}/SKILL.md)"
        assert link in readme, f"README の一覧に {skill.parent.name} が無い"


def test_changed_public_files_have_no_private_data() -> None:
    scanned = [README, POLICY, *SKILLS, SKILLS[1].parent / "agents" / "openai.yaml"]
    scanned.extend(sorted((ROOT / "tests").rglob("*.py")))
    scanned.extend(sorted((ROOT / "tests").rglob("*.md")))
    scanned.extend(sorted((ROOT / "tests" / "fixtures").glob("*.jsonl")))

    local_path = re.compile(r"(?<![\w~])/(?:home|Users|root)/")
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    secret = re.compile(r"\b(?:sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{12,})\b")
    url = re.compile(r"https?://([^/\s\"'`)<>]+)")
    allowed_hosts = {
        "github.com",
        "codeload.github.com",
        "raw.githubusercontent.com",
        "127.0.0.1",
        "localhost",
    }

    for path in scanned:
        assert path.is_file(), f"走査対象が無い: {path}"
        text = read(path)
        assert not local_path.search(text), f"{path.name} にローカル絶対パス"
        assert not email.search(text), f"{path.name} にメールアドレスらしき文字列"
        assert not secret.search(text), f"{path.name} に秘密情報らしき文字列"
        for host in url.findall(text):
            assert host.split(":")[0] in allowed_hosts, f"{path.name} に外部 URL {host}"
