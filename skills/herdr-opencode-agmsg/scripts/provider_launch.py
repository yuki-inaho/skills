#!/usr/bin/env python3
"""Run one planner-selected OpenCode attempt in the caller's visible pane.

The coordinator classifies receipts and reconciles jobs/artifacts between calls.
This is not an unattended retry daemon. No credentials or global settings are
read or modified. Child output stays on the caller's terminal.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

from provider_plan import DEFAULT_CATALOG, plan


def prepare(request: dict, catalog: dict, assignment: Path, timeout: float,
            executable: str = "opencode", auto: bool = False) -> tuple[dict, list[str]]:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    # Unknown is not the same as confirmed stopped. A fresh launch must also
    # establish that another writer has not already taken its scope.
    if request.get("live_job_possible") is not False:
        raise ValueError("confirm live_job_possible=false after checking owned work")
    if request.get("attempts") and request.get("reconciled") is not True:
        raise ValueError("reconcile the preceding attempt's jobs and artifacts first")
    decision = plan(request, catalog)
    if decision["action"] not in {"launch", "retry"}:
        return decision, []
    delay = request.get("retry_after_seconds", 0) or 0
    # Enforce the overall remaining budget, including a candidate switch.
    remaining = request.get("remaining_seconds")
    if remaining is not None and delay + timeout > remaining:
        raise ValueError("Retry-After plus attempt timeout exceeds the remaining budget")
    prompt = assignment.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("assignment must not be empty")
    # No --session/--continue: every attempt gets a fresh native session.
    argv = [executable, "run", "--standalone", "--model", decision["candidate"]]
    if auto:
        argv.append("--auto")
    argv.append(prompt)
    return decision, argv


def stop_owned_group(process: subprocess.Popen) -> None:
    """Bound termination to the process group created for this attempt."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # The leader may exit before its children. Still target this owned group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="private planner request JSON")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--assignment", required=True, help="fresh nonce/scope packet")
    parser.add_argument("--attempt-dir", required=True, help="new private evidence directory")
    parser.add_argument("--timeout", type=float, required=True, help="hard wall-clock seconds")
    parser.add_argument("--opencode", default="opencode", help="installed executable path")
    parser.add_argument("--auto", action="store_true", help="only for already-authorized worker scope")
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.input).read_text())
        catalog = json.loads(Path(args.catalog).read_text())
        decision, argv = prepare(request, catalog, Path(args.assignment), args.timeout, args.opencode, args.auto)
        if not argv:
            print(json.dumps(decision, ensure_ascii=False))
            return 2
        evidence = Path(args.attempt_dir)
        evidence.mkdir(mode=0o700, parents=False, exist_ok=False)
    except (OSError, ValueError, TypeError):
        # Do not echo input JSON, paths, assignment text or environment values.
        print("Launch refused: check request, reconciliation, budget and fresh evidence directory.")
        return 2
    (evidence / "decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    receipt = {"candidate": decision["candidate"], "action": decision["action"],
               "started_at": None, "finished_at": None, "pid": None, "exit_code": None,
               "timed_out": False, "interrupted": False, "reconciliation_required": True,
               "outcome": "unknown"}
    process = None
    def interrupt(_signum, _frame):
        raise KeyboardInterrupt

    previous_term = signal.signal(signal.SIGTERM, interrupt)
    try:
        delay = request.get("retry_after_seconds", 0) or 0
        if delay:
            time.sleep(delay)
        receipt["started_at"] = time.time()
        process = subprocess.Popen(argv, start_new_session=True)
        receipt["pid"] = process.pid
        (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"Provider attempt: {decision['candidate']} pid={process.pid}", flush=True)
        try:
            receipt["exit_code"] = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            receipt["timed_out"] = True
            stop_owned_group(process)
            receipt["exit_code"] = process.returncode
    except KeyboardInterrupt:
        receipt["interrupted"] = True
        if process is not None:
            stop_owned_group(process)
            receipt["exit_code"] = process.returncode
    except OSError:
        receipt["launch_error"] = True
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        receipt["finished_at"] = time.time()
        (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if receipt["timed_out"]:
        return 124
    if receipt["interrupted"]:
        return 130
    return 0 if receipt["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
