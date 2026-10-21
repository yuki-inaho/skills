"""agent-jsonl-compact 0.3.0 以降の CLI 契約を合成 JSONL で確認する。

スキル本文が案内する「版確認 → 閲覧系 → 根拠位置 → partial/retry → tool 対応」が、
実際のバイナリで成立することを固定する。旧版しか無い環境では skip する
（スキル側は legacy 抽出へのフォールバックを案内している）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import parse_jsonl

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CODEX = FIXTURES / "synthetic_codex.jsonl"
CLAUDE = FIXTURES / "synthetic_claude.jsonl"
MIN_VERSION = (0, 3, 0)


def _binary() -> str:
    candidate = os.environ.get("AGENT_JSONL_COMPACT") or shutil.which("agent-jsonl-compact")
    if not candidate or not Path(candidate).is_file():
        pytest.skip("agent-jsonl-compact が見つからない（AGENT_JSONL_COMPACT か PATH で指定）")
    return candidate

def _version_info() -> dict:
    probe = subprocess.run(
        [_binary(), "version", "--output", "json"], capture_output=True, text=True
    )
    if probe.returncode != 0:
        pytest.skip("閲覧系を持たない旧バイナリのため skip（legacy フォールバック対象）")
    info = json.loads(probe.stdout)
    version = tuple(int(part) for part in info["version"].split(".")[:3])
    if version < MIN_VERSION:
        pytest.skip(f"0.3.0 未満 ({info['version']}) のため skip")
    return info


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([_binary(), *args], capture_output=True, text=True)


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    return path


def _codex_message(text: str, index: int) -> dict:
    return {
        "timestamp": f"2026-10-01T00:00:{index % 60:02d}Z",
        "type": "event_msg",
        "payload": {"type": "user_message", "message": text},
    }


def _long_fixture(path: Path, marker: str) -> Path:
    records = [
        {
            "timestamp": "2026-10-01T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": "sample-long", "cwd": "/work/sample-repo"},
        },
        _codex_message(f"{marker} " + "z" * 600, 1),
    ]
    return _write_jsonl(path, records)


def test_version_probe_exposes_reproducible_metadata() -> None:
    info = _version_info()
    for key in ("name", "version", "source_release_date", "query_schema_version", "cursor_version"):
        assert key in info, f"version --output json に {key} が必要"
    assert info["name"] == "agent-jsonl-compact"
    assert info["source_date_kind"] == "fixed_release_date_not_build_time"

    banner = _run("--version")
    assert banner.returncode == 0
    assert "agent-jsonl-compact" in banner.stdout
    assert info["version"] in banner.stdout


def test_view_excludes_reasoning_and_developer_items() -> None:
    _version_info()
    result = _run("view", "-i", str(CODEX), "--scope", "all", "--output", "jsonl")
    assert result.returncode == 0, result.stderr

    events, metadata = parse_jsonl(result.stdout)
    assert metadata is not None
    combined = result.stdout
    assert "SENTINEL_DEVELOPER_TEXT" not in combined
    assert "SENTINEL_REASONING_TEXT" not in combined
    assert metadata["counts"]["framework_excluded"]["events"] >= 2

    origins = {event["message_origin"] for event in events}
    assert origins <= {"human", "framework", "compaction", "unknown"}
    assert any(event["role"] == "user" for event in events)


def test_claude_role_user_is_not_treated_as_human_conversation() -> None:
    _version_info()
    result = _run("view", "-i", str(CLAUDE), "--scope", "all", "--output", "jsonl")
    assert result.returncode == 0, result.stderr

    events, metadata = parse_jsonl(result.stdout)
    assert metadata is not None
    assert "SENTINEL_FRAMEWORK_REMINDER" not in result.stdout
    assert "SENTINEL_COMPACTION_SUMMARY" not in result.stdout
    # isMeta / isCompactSummary はいずれも role=user だが通常会話として出さない。
    assert metadata["counts"]["framework_excluded"]["events"] == 2
    assert any(event["role"] == "user" for event in events)
    assert all(event["message_origin"] not in {"framework", "compaction"} for event in events)


def test_search_returns_original_byte_ranges() -> None:
    _version_info()
    result = _run(
        "search",
        "-i",
        str(CODEX),
        "--query",
        "sample_marker",
        "--context",
        "1",
        "--output",
        "jsonl",
    )
    assert result.returncode == 0, result.stderr

    events, metadata = parse_jsonl(result.stdout)
    assert metadata is not None
    assert events, "sample_marker のヒットが必要"
    raw = CODEX.read_bytes()

    for event in events:
        assert "sample_marker" in event["matched_queries"]
        assert event["source"]["raw_line"] >= 1
        start = event["source"]["byte_start"]
        end = event["source"]["byte_end"]
        assert b"sample_marker" in raw[start:end]

        text_bytes = event["text"].encode("utf-8")
        for match in event["matched_ranges"]:
            assert match["unit"] == "utf8_byte"
            assert match["reference"] == "original_text"
            assert text_bytes[match["start"] : match["end"]] == b"sample_marker"


def test_tool_pairing_reports_paired_and_orphan_states() -> None:
    _version_info()
    result = _run(
        "view",
        "-i",
        str(CODEX),
        "--scope",
        "tools",
        "--with-pair",
        "--output",
        "jsonl",
    )
    assert result.returncode == 0, result.stderr

    events, metadata = parse_jsonl(result.stdout)
    assert metadata is not None
    by_call: dict[str, list[dict]] = {}
    for event in events:
        by_call.setdefault(event["call_id"], []).append(event)

    paired = by_call["call-1"]
    assert len(paired) == 2
    assert {event["pair_state"] for event in paired} == {"paired"}
    assert paired[0]["paired_total"] == 1
    assert paired[0]["paired_event_ids"] == [paired[1]["event_id"]]
    assert paired[1]["paired_event_ids"] == [paired[0]["event_id"]]
    assert paired[0]["paired_ids_truncated"] is False

    orphan = by_call["call-orphan"]
    assert [event["pair_state"] for event in orphan] == ["orphan"]
    assert orphan[0]["paired_event_ids"] == []

    assert metadata["scan"]["with_pair"]["incomplete"] is False
    assert metadata["counts"]["pairs"]["paired"] == 2
    assert metadata["counts"]["pairs"]["orphan"] == 1


def test_partial_record_is_explicit_and_retry_cursor_works(tmp_path: Path) -> None:
    _version_info()
    fixture = _long_fixture(tmp_path / "long.jsonl", "retry_target")

    first = _run("view", "-i", str(fixture), "--max-record-bytes", "128", "--output", "jsonl")
    assert first.returncode == 1, "未検査 record は rc1(partial) で返る"
    _, metadata = parse_jsonl(first.stdout)
    assert metadata is not None
    assert metadata["status"] == "partial"
    uninspected = metadata["counts"]["uninspected"]
    assert uninspected["records"] == 1
    sample = uninspected["samples"][0]
    assert sample["reason"] == "max_record_bytes"
    assert sample["retry_cursor"]

    retry = _run(
        "view",
        "-i",
        str(fixture),
        "--cursor",
        sample["retry_cursor"],
        "--max-record-bytes",
        "65536",
        "--output",
        "jsonl",
    )
    assert retry.returncode == 0, retry.stderr
    assert "retry_target" in retry.stdout


def test_output_budget_cut_is_reported_as_text_complete_false(tmp_path: Path) -> None:
    _version_info()
    records = [
        {
            "timestamp": "2026-10-01T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": "sample-many", "cwd": "/work/sample-repo"},
        }
    ]
    records.extend(_codex_message(f"message {index:03d} " + "y" * 200, index) for index in range(40))
    fixture = _write_jsonl(tmp_path / "many.jsonl", records)

    result = _run("view", "-i", str(fixture), "--max-output-bytes", "8192", "--output", "jsonl")
    assert result.returncode == 0, result.stderr
    events, metadata = parse_jsonl(result.stdout)
    assert metadata is not None
    assert events
    assert any(event["text_complete"] is False for event in events)
    assert metadata["page_cursor"], "cut された表示は page cursor で再開できる"
    assert metadata["exhausted"] is False


def test_below_minimum_output_budget_is_usage_error() -> None:
    _version_info()
    result = _run("view", "-i", str(CODEX), "--max-output-bytes", "4000")
    assert result.returncode == 2
    assert "minimum" in result.stderr


def test_append_cursor_reads_only_new_lines(tmp_path: Path) -> None:
    _version_info()
    fixture = tmp_path / "append.jsonl"
    shutil.copyfile(CODEX, fixture)

    initial = _run("view", "-i", str(fixture), "--output", "jsonl")
    assert initial.returncode == 0, initial.stderr
    _, metadata = parse_jsonl(initial.stdout)
    assert metadata is not None
    cursor = metadata["append_cursor"]
    assert cursor, "走査完了後は append cursor が返る"

    with fixture.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": "2026-10-01T00:00:09Z",
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "appended_marker"},
                }
            )
            + "\n"
        )

    appended = _run(
        "view",
        "-i",
        str(fixture),
        "--after-cursor",
        cursor,
        "--output",
        "jsonl",
    )
    assert appended.returncode == 0, appended.stderr
    events, _ = parse_jsonl(appended.stdout)
    assert [event["text"] for event in events] == ["appended_marker"]
