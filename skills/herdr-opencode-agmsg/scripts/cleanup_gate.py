#!/usr/bin/env python3
"""Pure owned-tab cleanup gate.

Reads a JSON request and prints one JSON decision. It never closes anything,
reads no environment variables and writes no files.

Request keys:
  owned               true only when this run created the tab/process
  frontend            "running" | "exited" | "unknown"
  jobs                "running" | "exited" | "unknown"
  completion_evidence true when completion or failure evidence is saved
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

STATES = {"running", "exited", "unknown"}


def _state(request: dict[str, Any], key: str) -> str:
    value = request.get(key)
    if value not in STATES:
        raise ValueError(f"{key} must be running, exited or unknown")
    return str(value)


def gate(request: dict[str, Any]) -> dict[str, Any]:
    """Return the required next cleanup step without performing it."""
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")

    if request.get("owned") is not True:
        return {
            "action": "refuse_not_owned",
            "reason": "tab is not owned by this run",
            "blockers": ["ownership_not_confirmed"],
        }

    frontend = _state(request, "frontend")
    jobs = _state(request, "jobs")
    evidence = request.get("completion_evidence") is True

    blockers: list[str] = []
    if frontend == "unknown":
        blockers.append("frontend_state_unknown")
    if jobs == "unknown":
        blockers.append("job_state_unknown")
    if blockers:
        return {"action": "inspect", "reason": "state cannot be determined", "blockers": blockers}

    if frontend == "running" or jobs == "running":
        running = []
        if frontend == "running":
            running.append("frontend_running")
        if jobs == "running":
            running.append("jobs_running")
        return {"action": "wait", "reason": "owned work is still running", "blockers": running}

    if not evidence:
        return {
            "action": "collect_evidence",
            "reason": "owned work exited but completion evidence is not collected",
            "blockers": ["completion_evidence_missing"],
        }

    return {"action": "close", "reason": "owned work exited and evidence is collected", "blockers": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a pure owned-tab cleanup decision as JSON.")
    parser.add_argument("--input", "-i", default="-", help="JSON file path, or - for stdin (default)")
    args = parser.parse_args(argv)

    try:
        text = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        request = json.loads(text)
        decision = gate(request)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        message = str(error) or error.__class__.__name__
        print(f"error: {message}", file=sys.stderr)
        return 2

    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
