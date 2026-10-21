"""共有 fixture。実データ・絶対パスを含めない。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def parse_jsonl(text: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """record_type=event の行と metadata 行へ分ける（cursor 行は無視）。"""
    events: list[dict[str, Any]] = []
    metadata: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        obj = json.loads(line)
        kind = obj.get("record_type")
        if kind == "event":
            events.append(obj)
        elif kind == "metadata":
            metadata = obj
    return events, metadata
