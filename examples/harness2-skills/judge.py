#!/usr/bin/env python3
"""Independent post-selection judge for the thin skill example.

The native ordinary adapter runs this only after an adoption record exists.  It
reads three things and writes one JSON object to stdout:

* the staged task source (`source/cases.json`), for the exact case ids and enums;
* a copy of the answer;
* a separate expected file passed with `--expected`.

It scores only the structured fields `decision`, `output_target` and
`completion`, one criterion per case and field (three per case).  A malformed,
duplicate, missing or extra case is *unknown* (non-zero exit, no denominator),
never 0/n.  The judge never reads the harness, the editor workspace, the
evidence tree or the model transcript, and it never writes into them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FIELDS = ("decision", "output_target", "completion")


class JudgeError(RuntimeError):
    """The judge cannot produce a denominator from this input."""


def unknown(message: str) -> int:
    print(
        json.dumps(
            {
                "unknown": True,
                "error": message,
                "criteria": [],
            },
            indent=2,
        )
    )
    return 2


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeError(f"cannot read {label} {path}: {exc}") from exc


def load_source(task_dir: Path) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    doc = load_json(task_dir / "source" / "cases.json", "task source")
    cases = doc.get("cases") if isinstance(doc, dict) else None
    if not isinstance(cases, list) or not cases:
        raise JudgeError("task source has no non-empty `cases` list")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(cases) or not all(isinstance(item, str) and item for item in ids):
        raise JudgeError("task source has a case without a string id")
    if len(ids) != len(set(ids)):
        raise JudgeError("task source has duplicate case ids")
    schema = doc.get("answer_schema")
    templates = schema.get("cases") if isinstance(schema, dict) else None
    if not isinstance(templates, list) or not templates or not isinstance(templates[0], dict):
        raise JudgeError("task source has no answer_schema template")
    allowed: dict[str, tuple[str, ...]] = {}
    for field in FIELDS:
        raw = templates[0].get(field)
        if not isinstance(raw, str):
            raise JudgeError(f"answer_schema has no string {field!r}")
        values = tuple(part.strip() for part in raw.split("|") if part.strip())
        if not values:
            raise JudgeError(f"answer_schema {field!r} has no allowed values")
        allowed[field] = values
    return ids, allowed


def load_expected(path: Path, ids: list[str]) -> dict[str, dict[str, str]]:
    doc = load_json(path, "expected file")
    expected = doc.get("expected") if isinstance(doc, dict) else None
    if not isinstance(expected, dict):
        raise JudgeError("expected file has no `expected` object")
    if not set(ids) <= set(expected):
        raise JudgeError(
            "expected keys do not cover the task cases "
            f"(missing={sorted(set(ids) - set(expected))[:5]})"
        )
    out: dict[str, dict[str, tuple[str, ...]]] = {}
    for case_id in ids:
        row = expected[case_id]
        if not isinstance(row, dict):
            raise JudgeError(f"expected[{case_id!r}] is not an object")
        values: dict[str, tuple[str, ...]] = {}
        for field in FIELDS:
            raw = row.get(field)
            if isinstance(raw, str) and raw:
                values[field] = (raw,)
            elif (
                isinstance(raw, list)
                and raw
                and all(isinstance(item, str) and item for item in raw)
            ):
                values[field] = tuple(raw)
            else:
                raise JudgeError(f"expected[{case_id!r}].{field} is missing")
        out[case_id] = values
    return out


def load_answer(path: Path, ids: list[str], allowed: dict[str, tuple[str, ...]]) -> dict[str, dict[str, Any]]:
    doc = load_json(path, "answer")
    if not isinstance(doc, dict) or set(doc) != {"cases"}:
        raise JudgeError("answer top-level keys must be exactly ['cases']")
    cases = doc.get("cases")
    if not isinstance(cases, list):
        raise JudgeError("answer has no `cases` list")
    got: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            raise JudgeError(f"cases[{index}] is not an object")
        required = {"id", *FIELDS, "rationale"}
        if set(item) != required:
            raise JudgeError(
                f"cases[{index}] keys {sorted(item)} != {sorted(required)}"
            )
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise JudgeError(f"cases[{index}].id is not a non-empty string")
        if case_id in got:
            raise JudgeError(f"duplicate case id {case_id!r}")
        for field in FIELDS:
            if item.get(field) not in allowed[field]:
                raise JudgeError(f"{case_id}: {field} {item.get(field)!r} is not allowed")
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise JudgeError(f"{case_id}: rationale is empty")
        got[case_id] = item
    missing = sorted(set(ids) - set(got))
    extra = sorted(set(got) - set(ids))
    if missing or extra:
        raise JudgeError(f"case id mismatch: missing={missing[:8]} extra={extra[:8]}")
    return got


def judge(task_dir: Path, answer_path: Path, expected_path: Path) -> dict[str, Any]:
    ids, allowed = load_source(task_dir)
    expected = load_expected(expected_path, ids)
    answer = load_answer(answer_path, ids, allowed)
    criteria = []
    passed = 0
    for case_id in ids:
        for field in FIELDS:
            ok = answer[case_id][field] in expected[case_id][field]
            passed += int(ok)
            criteria.append({"name": f"{case_id}.{field}", "passed": ok})
    total = len(criteria)
    return {
        "criteria": criteria,
        "n_passed": passed,
        "n_criteria": total,
        "all_pass": passed == total,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="judge.py", description=__doc__)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--answer", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=Path)
    args = parser.parse_args(argv)

    task_dir = args.task.resolve()
    answer_path = args.answer.resolve()
    expected_path = args.expected.resolve()
    try:
        if task_dir in expected_path.parents or expected_path == task_dir:
            raise JudgeError(
                "--expected must stay outside the staged task directory"
            )
        if not answer_path.is_file():
            raise JudgeError(f"answer is missing: {answer_path}")
        result = judge(task_dir, answer_path, expected_path)
    except JudgeError as exc:
        return unknown(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
