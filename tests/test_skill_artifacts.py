"""Artifact contracts for bundled templates and static skill corrections.

These tests check executable document/format contracts and regression guards.
They do not claim that a prose workflow was executed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "reference",
    [
        SKILLS / "write-workdoc-uv" / "references" / "workdoc-template.md",
        SKILLS / "write-workdoc-docker" / "references" / "workdoc-template.md",
    ],
    ids=["uv", "docker"],
)
def test_workdoc_template_sections_and_four_line_checklist(reference: Path) -> None:
    text = read(reference)
    for heading in (
        "## 1. 作業目的",
        "### 1.1 ゴール要求分析",
        "### 1.2 サブゴール構造",
        "### 1.3 トレーサビリティ方針",
        "## 3. 作業チェックリスト",
        "## 6. 完了の定義",
        "## 7. 作業記録",
    ):
        assert heading in text, f"{reference.name}: missing {heading}"
    blocks = re.split(r"(?=^### 手順 \d+:)", text, flags=re.MULTILINE)
    checklist_blocks = [block for block in blocks if block.startswith("### 手順 ")]
    assert len(checklist_blocks) >= 9
    for block in checklist_blocks:
        for marker in ("🖐 **操作**", "🔎 **確認**", "🧪 **テスト**", "🛠 **エラー時対処**"):
            assert marker in block, f"{reference.name}: {block.splitlines()[0]} missing {marker}"


def test_completion_summary_template_sections() -> None:
    text = read(SKILLS / "check-finished-workdoc" / "references" / "completion-summary-template.md")
    for heading in (
        "## 8. 完了照合・調査分析サマリ",
        "### 8.1 調査メタ情報",
        "### 8.3 ゴール要求分析との照合",
        "### 8.4 完了の定義との照合",
        "### 8.7 最終判定",
    ):
        assert heading in text


def test_review_rubric_numbered_sections() -> None:
    text = read(SKILLS / "review-written-workdoc" / "references" / "review-rubric.md")
    for number in range(1, 10):
        assert re.search(rf"^## {number}\. ", text, flags=re.MULTILINE), f"missing section {number}"


def test_start_work_audit_template_has_three_roles_and_neutral_runtime_note() -> None:
    template = read(SKILLS / "start-work-audit-pattern" / "assets" / "start-work-audit-template.md")
    for heading in ("### 1. 統括エージェント", "### 2. 作業エージェント", "### 3. 監査エージェント"):
        assert heading in template
    assert "40行動ごと" in template
    assert "20行動ごと" not in template
    lowered = template.lower()
    for vendor_tier in ("opus middle", "sonnet high", "codex なら"):
        assert vendor_tier not in lowered, f"runtime/vendor tier instruction remains: {vendor_tier}"
    for role_file in ("coordinator.txt", "worker.txt", "audit.txt"):
        assert (SKILLS / "start-work-audit-pattern" / "assets" / "roles" / role_file).is_file()


def test_supervisor_routing_uses_capability_labels() -> None:
    routing = read(SKILLS / "supervisor-orchestration" / "references" / "bloom-routing.md")
    assert "能力ラベル" in routing
    assert "| explore |" not in routing
    assert "| general（実行係） |" not in routing


def test_handover_has_final_check_and_privacy_caution() -> None:
    text = read(SKILLS / "handover" / "SKILL.md")
    assert "## 最終確認" in text
    assert "{{date}}" in text
    assert "private" in text
    assert "TBD" in text


def test_start_with_workdocs_zero_count_command_is_safe() -> None:
    text = read(SKILLS / "start-with-workdocs" / "SKILL.md")
    assert "grep -c -- '- \\[ \\]' temp/workdoc_*.md || true" in text
    assert "rc1" in text


def test_jax_skill_has_no_missing_trace_script_or_tool_specific_path() -> None:
    text = read(SKILLS / "jax-performance-tuning" / "SKILL.md")
    assert "scripts/analyze_trace.py" not in text
    assert "/tmp/" + "opencode" not in text
    assert "JAX_CACHE_DIR" in text
    assert "JAX_TRACE_DIR" in text
    assert any(url in text for url in (
        "https://docs.jax.dev/en/latest/profiling.html",
        "https://docs.jax.dev/en/latest/201/profiling.html",
    ))


def test_skill_creator_template_link_is_inline_code() -> None:
    text = read(SKILLS / "skill-creator" / "references" / "skill-template.md")
    assert "[references/growth-log.md](references/growth-log.md)" not in text
    assert "`references/growth-log.md`" in text


def test_public_catalog_is_neutral_and_example_is_synthetic() -> None:
    bundled = json.loads(read(SKILLS / "herdr-opencode-agmsg" / "assets" / "model_catalog.json"))
    assert bundled["models"] == []
    assert bundled["provider_order"] == []
    example = json.loads(
        read(SKILLS / "herdr-opencode-agmsg" / "assets" / "model_catalog.example.json")
    )
    assert example["models"]
    assert all(entry["id"].startswith("example-provider-") for entry in example["models"])


def test_cleanup_gate_cli_has_no_resource_warning() -> None:
    script = SKILLS / "herdr-opencode-agmsg" / "scripts" / "cleanup_gate.py"
    payload = json.dumps(
        {"owned": True, "frontend": "exited", "jobs": "exited", "completion_evidence": True}
    )
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "error"
    result = subprocess.run(
        [sys.executable, "-W", "error", str(script)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "ResourceWarning" not in result.stderr


def test_provider_plan_refuses_an_empty_catalog_clearly() -> None:
    script = SKILLS / "herdr-opencode-agmsg" / "scripts" / "provider_plan.py"
    empty = SKILLS / "herdr-opencode-agmsg" / "assets" / "model_catalog.json"
    payload = json.dumps({"discovery": ["example-provider/example-model"], "attempts": []})
    result = subprocess.run(
        [sys.executable, str(script), "--catalog", str(empty)],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["action"] == "stop"
    assert decision["reason"] == "catalog_unconfigured"
    assert decision["candidate"] is None
