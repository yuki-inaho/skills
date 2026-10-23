#!/usr/bin/env python3
"""Thin ordinary-task executor for the native Harness² skill example.

The manifest already fixes the argv, the answer file, the model label and the
timeout.  This program supplies only the missing step: launch the *installed*
`opencode` CLI once, in its own workspace, with `--auto --format json`, then
accept a strict `{"cases": [...]}` answer.

It is not an orchestration layer and it performs no retries.  It:

* requires a fresh run directory and creates one workspace without deleting any
  existing path; a prior executor receipt makes the request fail instead of
  being overwritten, so an upstream retry needs its own fresh attempt;
* rejects symlinks, occupied outputs and paths that overlap the task, harness or
  resources, and writes the answer with an exclusive create;
* starts the CLI through PATH in a new process group, saves the real argv, cwd,
  CLI version, stdout events, stderr, exit code, timeout, session id and cost;
* extracts the answer only from an exact JSON envelope (a file, or one fenced
  block / the whole final text), never from a wrapped or partial object;
* rejects missing, duplicate or unknown case ids, invalid enum values and
  placeholder rationales instead of repairing them;
* checks that the task, harness, resources and copied skills are unchanged;
* on timeout kills only the process group it owns, retains the workspace, and
  asks the local active-session API about the exact reported session id before
  cancelling that one execution; after an interrupt acknowledgement it polls
  that exact id for a bounded interval and claims a stop only when absence and
  the owned frontend exit are both verified.

The permission fence is a tool policy, not an OS sandbox.  The upstream native
stage loop may still call the editor more than once; this executor does not loop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

MODEL_RE = re.compile(r"[^\s/#]+/[^\s#]+#[A-Za-z0-9._-]+\Z")
FREE_IDS = frozenset(
    {"free", "auto", "default", "any", "best", "cheapest", "fallback", "*"}
)
FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```", re.S)
PLACEHOLDER = re.compile(
    r"^\s*(?:todo|tbd|n/?a|placeholder|\.{3,}|-|<[^>]*>)\s*$", re.I
)
ANSWER_KEYS = {"id", "decision", "output_target", "completion", "rationale"}
API_TIMEOUT_S = 10
STOP_POLL_TIMEOUT_S = 10.0
STOP_POLL_INTERVAL_S = 0.25
OWNED_RUN_PATHS = (
    "workspace",
    "agent_events.jsonl",
    "agent_stderr.log",
    "session_api.json",
    "trajectory.md",
    "executor_receipt.json",
    "exit.json",
    "completion.json",
)


class ExecutorError(RuntimeError):
    """A preparation or answer-contract failure, never a model answer to repair."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def iter_files(root: Path):
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.name.endswith((".pyc", ".pyo")):
            continue
        if path.is_file() and not path.is_symlink():
            yield path


def tree_digest(root: Path) -> str | None:
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    for path in iter_files(root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def copy_tree(src: Path, dst: Path) -> None:
    if not src.is_dir():
        return
    for path in iter_files(src):
        target = dst / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _atomic_text(path: Path, text: str) -> None:
    """Replace *path* without following a pre-existing symlink at that name."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def write_json(path: Path, doc: Any) -> None:
    _atomic_text(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def write_json_exclusive(path: Path, doc: Any) -> None:
    """Create *path* exactly once; never overwrite or follow an existing name."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def open_exclusive(path: Path) -> Any:
    """Open a new run artifact for writing, refusing any existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(handle, "wb")


def reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ExecutorError(
            f"{label} must not be a symlink, including a dangling one: {path}"
        )


def inside(path: Path, root: Path) -> bool:
    """True when *path* is *root* or below it (never the reverse).

    Native core copies the candidate harness below its own ``run_dir``, so
    containment in that direction is normal.  Writing the run dir or answer
    *into* a task, harness or resources input is what must be refused.
    """
    return path == root or root in path.parents


def checked_paths(
    raw_run_dir: Path, raw_out: Path, inputs: Mapping[str, Path]
) -> tuple[Path, Path]:
    """Validate a fresh run directory and an exclusive answer path."""
    reject_symlink(raw_run_dir, "--run-dir")
    reject_symlink(raw_out, "--out")
    run_dir = raw_run_dir.resolve()
    out = raw_out.resolve()

    for label, root in inputs.items():
        if inside(run_dir, root):
            raise ExecutorError(
                f"--run-dir is inside {label} ({root}); choose a path outside the inputs"
            )
        if inside(out, root):
            raise ExecutorError(
                f"--out is inside {label} ({root}); choose a path outside the inputs"
            )

    if run_dir.exists() and not run_dir.is_dir():
        raise ExecutorError(f"--run-dir exists and is not a directory: {run_dir}")
    if out.exists() or out.is_symlink():
        raise ExecutorError(
            f"--out is occupied: {out}; this executor never overwrites an existing path"
        )

    workspace = run_dir / "workspace"
    if inside(out, workspace):
        raise ExecutorError(f"--out must stay outside the executor workspace: {out}")
    for rel in OWNED_RUN_PATHS:
        owned = run_dir / rel
        if owned.is_symlink() or owned.exists():
            raise ExecutorError(
                f"--run-dir is not a fresh attempt: {owned} already exists; "
                "use a new run directory instead of erasing prior evidence"
            )

    if not run_dir.exists():
        try:
            run_dir.mkdir(parents=True)
        except FileExistsError as exc:
            raise ExecutorError(
                f"--run-dir was created concurrently; choose a fresh path: {run_dir}"
            ) from exc
    return run_dir, out


def validate_model(value: str | None) -> str:
    if value is None or not value.strip():
        raise ExecutorError("--model is required; the manifest must fix one model id")
    model = value.strip()
    if not MODEL_RE.fullmatch(model):
        raise ExecutorError(
            f"--model {model!r} is not an exact provider/model#variant id"
        )
    provider, rest = model.split("/", 1)
    name, variant = rest.rsplit("#", 1)
    for part in (provider, name, variant):
        if part.lower() in FREE_IDS:
            raise ExecutorError(f"--model {model!r} names a free/automatic id")
    return model


def read_source(task_dir: Path) -> tuple[dict[str, Any], list[str], dict[str, tuple[str, ...]], set[str]]:
    path = task_dir / "source" / "cases.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutorError(f"cannot read source cases {path}: {exc}") from exc
    cases = doc.get("cases") if isinstance(doc, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ExecutorError("source/cases.json has no non-empty `cases` list")
    ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ExecutorError(f"source/cases.json: cases[{index}] has no string id")
        ids.append(case["id"])
    if len(ids) != len(set(ids)):
        raise ExecutorError("source/cases.json has duplicate case ids")
    schema_doc = doc.get("answer_schema")
    if not isinstance(schema_doc, dict) or not isinstance(schema_doc.get("cases"), list):
        raise ExecutorError("source/cases.json has no `answer_schema.cases` template")
    templates = [item for item in schema_doc["cases"] if isinstance(item, dict)]
    if not templates:
        raise ExecutorError("answer_schema.cases has no object template")
    template = templates[0]
    allowed: dict[str, tuple[str, ...]] = {}
    for key in ("decision", "output_target", "completion"):
        raw = template.get(key)
        if not isinstance(raw, str):
            raise ExecutorError(f"answer_schema template has no string {key!r}")
        values = tuple(part.strip() for part in raw.split("|") if part.strip())
        if not values:
            raise ExecutorError(f"answer_schema {key!r} has no allowed values")
        allowed[key] = values
    required = set(template)
    if required != ANSWER_KEYS:
        raise ExecutorError(
            f"answer_schema template keys {sorted(required)} != {sorted(ANSWER_KEYS)}"
        )
    return doc, ids, allowed, required


def install_harness(harness: Path, resources: Path | None, workspace: Path) -> dict[str, str | None]:
    """Build the executable workspace and return the digests used for the fence."""
    parts: list[str] = []
    for rel in (
        "systemprompt.md",
        "guardrails.md",
        "LongTermMEMORY.md",
        "tool_descriptions/tool_guidance.md",
    ):
        path = harness / rel
        if path.is_file():
            body = path.read_text(encoding="utf-8", errors="replace").strip()
            if body:
                parts.append(body)
    if not parts:
        parts.append("# Role\n\nAnswer the task from the fixed cases and the copied skills.")
    (workspace / "AGENTS.md").write_text(
        "\n\n---\n\n".join(parts) + "\n", encoding="utf-8"
    )

    copy_tree(harness, workspace / "harness")
    if (harness / "scripts").is_dir():
        copy_tree(harness / "scripts", workspace / "scripts")

    if resources is not None and resources.is_dir():
        copy_tree(resources, workspace / "resources")
        for skill in sorted(resources.iterdir()):
            if not skill.is_dir():
                continue
            copy_tree(skill, workspace / "skills" / skill.name)
            copy_tree(skill, workspace / ".opencode" / "skills" / skill.name)

    for skill in sorted((harness / "skills").glob("*")):
        if not skill.is_dir():
            continue
        copy_tree(skill, workspace / "skills" / skill.name)
        copy_tree(skill, workspace / ".opencode" / "skills" / skill.name)

    return {
        "skills": tree_digest(workspace / "skills"),
        "resources": (
            tree_digest(workspace / "resources")
            if (workspace / "resources").is_dir()
            else None
        ),
        "scripts": (
            tree_digest(workspace / "scripts")
            if (workspace / "scripts").is_dir()
            else None
        ),
        "oc_skills": (
            tree_digest(workspace / ".opencode" / "skills")
            if (workspace / ".opencode" / "skills").is_dir()
            else None
        ),
    }


def mission_text(task_text: str, instruction: str, case_ids: list[str], allowed: Mapping[str, tuple[str, ...]]) -> str:
    ids = "\n".join(f"- {case_id}" for case_id in case_ids)
    values = "\n".join(
        f"- `{key}`: " + ", ".join(f"`{value}`" for value in allowed[key])
        for key in ("decision", "output_target", "completion")
    )
    return f"""{task_text.strip()}

---

# Executor instructions

You are answering the fixed case set in this workspace. Read `AGENTS.md`,
`task.md`, `source/cases.json` and the relevant copied skill files under
`skills/`. The `skills/<name>/` copies are complete. The only skills in scope are
the copied files in this workspace; do not use a globally installed skill. Do not
read outside this workspace. Do not modify `source/` or `harness/`. Do not use the
network, install packages, run inference or run helper scripts on real data.

{instruction.strip()}

Answer every case id exactly once:

{ids}

Allowed values:

{values}

`rationale` must be a brief evidence-based sentence, not a placeholder. Write
`answer.json` in the workspace root as exactly one JSON object:

{{"cases": [
  {{"id": "copy exact case id", "decision": "proceed", "output_target": "none",
    "completion": "incomplete", "rationale": "brief evidence and next action"}}
]}}

Reply with the same JSON object as your final message. Do not add a wrapper,
commentary or extra top-level keys.
"""


def parse_events(path: Path) -> dict[str, Any]:
    state: dict[str, Any] = {
        "session_id": None,
        "session_ids": [],
        "event_count": 0,
        "tool_events": [],
        "texts": [],
        "costs": [],
    }
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return state
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        state["event_count"] += 1
        part = event.get("part") if isinstance(event.get("part"), dict) else {}
        session_id = event.get("sessionID") or part.get("sessionID")
        if isinstance(session_id, str) and session_id and session_id not in state["session_ids"]:
            state["session_ids"].append(session_id)
            if state["session_id"] is None:
                state["session_id"] = session_id
        kind = event.get("type")
        if kind == "tool_use":
            inner = part.get("state") if isinstance(part.get("state"), dict) else {}
            raw = inner.get("input") if isinstance(inner.get("input"), dict) else {}
            state["tool_events"].append(
                {
                    "tool": part.get("tool"),
                    "command": raw.get("command"),
                    "path": raw.get("filePath") or raw.get("path"),
                    "status": inner.get("status"),
                }
            )
        elif kind in ("step_finish", "step-finish"):
            cost = part.get("cost")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                state["costs"].append(float(cost))
        elif kind == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                state["texts"].append(text)
    costs = state.pop("costs")
    state["cost_usd"] = round(sum(costs), 6) if costs else None
    state["cost_source"] = "reported" if costs else "unmeasured"
    state["text"] = "\n".join(state.pop("texts"))
    return state


def exact_object(text: str) -> dict[str, Any] | None:
    """Parse exactly one `{"cases": [...]}`` object and nothing else."""
    text = text.strip()
    if not text:
        return None
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(doc, dict) or set(doc) != {"cases"}:
        return None
    if not isinstance(doc["cases"], list):
        return None
    return doc


def extract_answer(workspace: Path, final_text: str) -> tuple[dict[str, Any] | None, str, list[str]]:
    """Return (object, source, errors).  No substring scan and no repair."""
    answer_path = workspace / "answer.json"
    if answer_path.is_file():
        try:
            text = answer_path.read_text(encoding="utf-8")
        except OSError as exc:
            return None, "answer.json", [f"answer.json is unreadable: {exc}"]
        doc = exact_object(text)
        if doc is None:
            return None, "answer.json", [
                "answer.json is not exactly one {\"cases\": [...]} object"
            ]
        return doc, "answer.json", []

    blocks = FENCE.findall(final_text or "")
    if len(blocks) == 1:
        doc = exact_object(blocks[0])
        if doc is not None:
            return doc, "final text fence", []
        return None, "final text fence", [
            "the final text fence is not exactly one {\"cases\": [...]} object"
        ]
    doc = exact_object(final_text or "")
    if doc is not None:
        return doc, "final text", []
    return None, "final text", [
        "no exact answer.json and no single exact {\"cases\": [...]} object in the final text"
    ]


def validate_answer(
    doc: dict[str, Any] | None,
    case_ids: list[str],
    allowed: Mapping[str, tuple[str, ...]],
    required: set[str],
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return None, [], ["answer is not a JSON object"]
    if set(doc) != {"cases"}:
        return None, [], ["answer top-level keys must be exactly ['cases']"]
    cases = doc.get("cases")
    if not isinstance(cases, list):
        return None, [], ["answer has no `cases` list"]
    got_ids: list[str] = []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            errors.append(f"cases[{index}] is not an object")
            continue
        if set(item) != required:
            errors.append(
                f"cases[{index}] keys {sorted(item)} != {sorted(required)}"
            )
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"cases[{index}].id is not a non-empty string")
            continue
        got_ids.append(case_id)
        for key in ("decision", "output_target", "completion"):
            value = item.get(key)
            if value not in allowed[key]:
                errors.append(f"{case_id}: {key} {value!r} is not allowed")
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < 3:
            errors.append(f"{case_id}: rationale is empty")
        elif PLACEHOLDER.fullmatch(rationale):
            errors.append(f"{case_id}: rationale is a placeholder")
        normalized.append(
            {
                "id": case_id,
                "decision": item.get("decision"),
                "output_target": item.get("output_target"),
                "completion": item.get("completion"),
                "rationale": rationale,
            }
        )
    if len(got_ids) != len(set(got_ids)):
        errors.append("duplicate case ids")
    if set(got_ids) != set(case_ids):
        missing = sorted(set(case_ids) - set(got_ids))
        extra = sorted(set(got_ids) - set(case_ids))
        errors.append(f"case id mismatch: missing={missing[:8]} extra={extra[:8]}")
    if errors:
        return None, got_ids, errors
    by_id = {item["id"]: item for item in normalized}
    return {"cases": [by_id[case_id] for case_id in case_ids]}, got_ids, []


def kill_group(proc: subprocess.Popen[bytes], grace: float = 10.0) -> int | None:
    if proc.poll() is not None:
        return proc.returncode
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
    try:
        return proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            return proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return None


def cli_version(opencode: str) -> str:
    try:
        result = subprocess.run(
            [opencode, "--version"], capture_output=True, text=True, timeout=15
        )
        return ((result.stdout or "") + (result.stderr or "")).strip()[:200]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"{type(exc).__name__}: {exc}"


def _api_request(
    opencode: str, argv: list[str], cwd: Path, *, timeout: float = API_TIMEOUT_S
) -> tuple[subprocess.CompletedProcess[str] | None, str]:
    try:
        result = subprocess.run(
            [opencode, "api", *argv],
            capture_output=True,
            text=True,
            timeout=max(0.5, min(timeout, API_TIMEOUT_S)),
            cwd=str(cwd),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return result, ""


def _active_api_state(
    result: subprocess.CompletedProcess[str] | None, session_id: str
) -> tuple[str, str]:
    """Classify one active-map response without retaining any other entry."""
    if result is None:
        return "pending", "unavailable"
    try:
        body = json.loads(result.stdout or "")
    except json.JSONDecodeError:
        body = None
    data = body.get("data") if isinstance(body, dict) else None
    if result.returncode != 0 or not isinstance(data, dict):
        return "pending", "response"
    if session_id not in data:
        return "inactive", "absent"
    value = data.get(session_id)
    if isinstance(value, dict) and value.get("type") == "running":
        return "active", "running"
    return "pending", "unrecognized"


def _poll_session_inactive(
    opencode: str, session_id: str, run_dir: Path
) -> dict[str, Any]:
    """Poll only the exact owned id for a bounded interval after a cancel ack.

    An interrupt acknowledgement proves that the request was accepted, not that
    the remote session became inactive.  Only absence from the active map ends
    the poll as verified; unchanged activity and unavailable/malformed responses
    stay unverified.
    """
    deadline = time.monotonic() + STOP_POLL_TIMEOUT_S
    observed: list[str] = []
    while True:
        remaining = deadline - time.monotonic()
        result, _error = _api_request(
            opencode,
            ["get", "/api/session/active"],
            run_dir,
            timeout=remaining if remaining > 0 else 0.5,
        )
        state, _detail = _active_api_state(result, session_id)
        observed.append(state)
        if state == "inactive":
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(STOP_POLL_INTERVAL_S, remaining))
    return {
        "attempted": True,
        "api": "/api/session/active",
        "exact_session_id_only": True,
        "polls": len(observed),
        "observed_states": observed,
        "bounded_s": STOP_POLL_TIMEOUT_S,
        "verified_inactive": bool(observed) and observed[-1] == "inactive",
    }


def reconcile_session(
    opencode: str,
    session_id: str | None,
    run_dir: Path,
    *,
    timed_out: bool = False,
    frontend_exited: bool = False,
) -> dict[str, Any]:
    """Prove the exact owned session against the local active-session API.

    The local API is ``GET /api/session/active`` with a ``data`` map of active
    session ids to ``{"type": "running"}``.  Only that map's entry for the exact
    reported session id is examined; unrelated entries are never copied into the
    receipt.  A missing id means the API reports it inactive, while a failed or
    malformed response stays ``pending``.  On a timeout, only the exact known id
    that is still active is interrupted.

    An ``interrupted: true`` acknowledgement only means the request was accepted.
    It never proves inactivity by itself: after it, only the exact id is polled
    for a bounded interval, and ``stopped_claimed`` is set only when that poll
    verifies absence *and* the caller confirms the owned frontend exited.
    """
    evidence: dict[str, Any] = {
        "attempted": False,
        "api": "/api/session/active",
        "remote_session_state": "pending",
        "owned_session_present": None,
        "stopped_claimed": False,
        "cancellation": {"attempted": False, "interrupted": None},
        "reason": "no session id was reported",
    }
    if not session_id:
        write_json(run_dir / "session_api.json", evidence)
        return evidence
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", session_id):
        evidence["reason"] = "session id is not a safe API path segment"
        write_json(run_dir / "session_api.json", evidence)
        return evidence

    evidence["attempted"] = True
    evidence["session_id"] = session_id
    active_argv = ["get", "/api/session/active"]
    result, error = _api_request(opencode, active_argv, run_dir)
    evidence["active_argv"] = ["api", *active_argv]
    evidence["returncode"] = result.returncode if result else None
    if result is None:
        evidence["reason"] = f"active-session API unavailable: {error}"
        write_json(run_dir / "session_api.json", evidence)
        return evidence

    stdout = result.stdout or ""
    evidence["response_sha256"] = sha256_bytes(stdout.encode())
    state, detail = _active_api_state(result, session_id)

    if state == "pending":
        if detail == "unrecognized":
            evidence["reason"] = (
                "the exact session id has an unrecognized active-map value; "
                "session state stays pending"
            )
        else:
            evidence["reason"] = (
                "active-session API did not return a usable data map "
                f"(rc={result.returncode}); session state stays pending"
            )
    elif state == "inactive":
        evidence["owned_session_present"] = False
        evidence["remote_session_state"] = "inactive"
        evidence["reason"] = (
            "the exact session id is absent from /api/session/active, which the "
            "API reports as inactive; this is not a claim about the OS process"
        )
    else:
        evidence["owned_session_present"] = True
        evidence["remote_session_state"] = "active"
        evidence["reason"] = (
            "the exact session id is present in /api/session/active with "
            "type=running"
        )

    if timed_out and evidence["remote_session_state"] == "active":
        cancel_argv = ["post", f"/api/session/{session_id}/interrupt"]
        cancel, cancel_error = _api_request(opencode, cancel_argv, run_dir)
        evidence["cancellation"] = {
            "attempted": True,
            "argv": ["api", *cancel_argv],
            "returncode": cancel.returncode if cancel else None,
            "interrupted": None,
            "frontend_exited": bool(frontend_exited),
        }
        if cancel is None:
            evidence["cancellation"]["error"] = cancel_error
            evidence["reason"] = (
                "timeout; the exact owned session was active but the interrupt "
                f"request was unavailable: {cancel_error}"
            )
        elif cancel.returncode == 0:
            try:
                cancel_body = json.loads(cancel.stdout or "{}")
            except json.JSONDecodeError:
                cancel_body = None
            if isinstance(cancel_body, dict) and isinstance(
                cancel_body.get("interrupted"), bool
            ):
                evidence["cancellation"]["interrupted"] = cancel_body["interrupted"]
                if cancel_body["interrupted"]:
                    poll = _poll_session_inactive(opencode, session_id, run_dir)
                    evidence["cancellation"]["verification"] = poll
                    if poll["verified_inactive"]:
                        evidence["owned_session_present"] = False
                    if poll["verified_inactive"] and frontend_exited:
                        evidence["remote_session_state"] = "inactive"
                        evidence["stopped_claimed"] = True
                        evidence["reason"] = (
                            "timeout; after the interrupt acknowledgement the exact "
                            "session id was absent from bounded post-cancel polling "
                            "and the owned frontend had exited; this is not an OS "
                            "process claim"
                        )
                    elif poll["verified_inactive"]:
                        evidence["remote_session_state"] = "pending"
                        evidence["reason"] = (
                            "timeout; the exact session id was absent from "
                            "post-cancel polling but the owned frontend exit was "
                            "not confirmed, so stopped_claimed stays false"
                        )
                    elif poll["observed_states"][-1:] == ["active"]:
                        evidence["remote_session_state"] = "pending"
                        evidence["reason"] = (
                            "timeout; the interrupt was acknowledged but the exact "
                            "session id was still active after bounded polling; an "
                            "acknowledgement is not proof of inactivity"
                        )
                    else:
                        evidence["remote_session_state"] = "pending"
                        evidence["reason"] = (
                            "timeout; the interrupt was acknowledged but the exact "
                            "session id's post-cancel state could not be verified"
                        )
                else:
                    evidence["reason"] = (
                        "timeout; the exact owned session was active but the "
                        "interrupt response did not confirm an interrupted execution"
                    )
            else:
                evidence["reason"] = (
                    "timeout; the interrupt response was not a usable "
                    "interrupted boolean"
                )
        else:
            evidence["reason"] = (
                "timeout; the exact owned session was active but the interrupt "
                f"request failed (rc={cancel.returncode})"
            )

    write_json(run_dir / "session_api.json", evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solve.py", description=__doc__)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--harness", required=True, type=Path)
    parser.add_argument("--resources", type=Path, default=None)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--timeout-s", type=int, default=240)
    parser.add_argument("--title", default="")
    parser.add_argument("--opencode", default=None)
    args = parser.parse_args(argv)

    try:
        model = validate_model(args.model)
        if args.timeout_s < 1 or args.timeout_s > 3600:
            raise ExecutorError("--timeout-s must be between 1 and 3600")
        task_dir = args.task.resolve()
        harness = args.harness.resolve()
        if not (task_dir / "task.md").is_file():
            raise ExecutorError(f"missing task prompt: {task_dir / 'task.md'}")
        if not harness.is_dir():
            raise ExecutorError(f"missing harness directory: {harness}")
        source_doc, case_ids, allowed, required = read_source(task_dir)
        resources = args.resources.resolve() if args.resources else None
        if resources is not None and not resources.is_dir():
            raise ExecutorError(f"missing resources directory: {resources}")
        inputs = {
            "the task directory": task_dir,
            "the task source": task_dir / "source",
            "the harness": harness,
        }
        if resources is not None:
            inputs["the resources"] = resources
        run_dir, out = checked_paths(
            args.run_dir.expanduser(), args.out.expanduser(), inputs
        )
        workspace = run_dir / "workspace"
        try:
            workspace.mkdir()
        except FileExistsError as exc:
            raise ExecutorError(
                f"the executor workspace is not fresh: {workspace}"
            ) from exc
    except ExecutorError as exc:
        print(f"solve: {exc}", file=sys.stderr)
        return 2

    task_text = (task_dir / "task.md").read_text(encoding="utf-8", errors="replace")
    (workspace / "task.md").write_text(task_text, encoding="utf-8")
    copy_tree(task_dir / "source", workspace / "source")
    install = install_harness(harness, resources, workspace)
    (workspace / "MISSION.md").write_text(
        mission_text(
            task_text,
            str(source_doc.get("instruction") or ""),
            case_ids,
            allowed,
        ),
        encoding="utf-8",
    )

    opencode = args.opencode or shutil.which("opencode") or "opencode"
    version = cli_version(opencode)
    label = args.title or f"exec-{task_dir.name}-{int(time.time())}-{os.getpid()}"
    prompt = (
        "Read MISSION.md and do what it asks. Answer every case from source/cases.json "
        "and the copied skills, write answer.json in this workspace root, and reply with "
        "the same JSON object."
    )
    launch_argv = [
        opencode,
        "run",
        "--auto",
        "--format",
        "json",
        "--model",
        model,
        "--title",
        label,
        "--file",
        "MISSION.md",
        prompt,
    ]

    before = {
        "source": sha256_file(workspace / "source" / "cases.json"),
        "task": sha256_file(workspace / "task.md"),
        "harness": tree_digest(workspace / "harness"),
        "workspace_harness": tree_digest(harness),
        **install,
    }
    events_path = run_dir / "agent_events.jsonl"
    stderr_path = run_dir / "agent_stderr.log"
    env = dict(os.environ)
    env["PWD"] = str(workspace)
    env["OPENCODE_PERMISSION"] = json.dumps(
        {
            "external_directory": {
                "*": "deny",
                str(workspace): "allow",
                f"{workspace}/**": "allow",
            },
            "webfetch": "deny",
            "websearch": "deny",
            "skill": "deny",
        }
    )
    env["OPENCODE_CONFIG_PROJECT_DISABLE"] = "1"
    env["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"

    started_unix = time.time()
    started = time.monotonic()
    timed_out = False
    returncode: int | None = None
    proc: subprocess.Popen[bytes] | None = None
    try:
        out_handle = open_exclusive(events_path)
        err_handle = open_exclusive(stderr_path)
    except FileExistsError as exc:
        print(f"solve: run artifact appeared concurrently: {exc}", file=sys.stderr)
        return 2
    with out_handle, err_handle:
        try:
            proc = subprocess.Popen(
                launch_argv,
                cwd=str(workspace),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out_handle,
                stderr=err_handle,
                start_new_session=True,
            )
            deadline = time.monotonic() + args.timeout_s
            while proc.poll() is None:
                if time.monotonic() > deadline:
                    timed_out = True
                    break
                time.sleep(0.1)
            returncode = kill_group(proc) if proc.poll() is None else proc.returncode
        except OSError as exc:
            print(f"solve: could not launch opencode: {exc}", file=sys.stderr)
            returncode = 127

    parsed = parse_events(events_path)
    frontend_exited = proc is not None and proc.poll() is not None
    session = reconcile_session(
        opencode,
        parsed.get("session_id"),
        run_dir,
        timed_out=timed_out,
        frontend_exited=frontend_exited,
    )
    answer_doc, answer_source, answer_errors = extract_answer(
        workspace, parsed.get("text") or ""
    )
    normalized, answer_ids, validation_errors = validate_answer(
        answer_doc, case_ids, allowed, required
    ) if not answer_errors else (None, [], answer_errors)

    after = {
        "source": sha256_file(workspace / "source" / "cases.json"),
        "task": sha256_file(workspace / "task.md"),
        "harness": tree_digest(workspace / "harness"),
        "skills": tree_digest(workspace / "skills"),
        "resources": tree_digest(workspace / "resources"),
        "scripts": tree_digest(workspace / "scripts"),
        "oc_skills": tree_digest(workspace / ".opencode" / "skills"),
    }
    violations: list[str] = []
    if after["source"] != before["source"]:
        violations.append("source/cases.json changed inside the executor workspace")
    if after["task"] != before["task"]:
        violations.append("task.md changed inside the executor workspace")
    if after["harness"] != before["harness"]:
        violations.append("harness/ changed inside the executor workspace")
    for key in ("skills", "resources", "scripts", "oc_skills"):
        if before.get(key) is not None and after.get(key) != before.get(key):
            violations.append(f"copied {key} changed inside the executor workspace")

    answer_written = False
    output_error = ""
    if not violations and not validation_errors and normalized is not None:
        try:
            write_json_exclusive(out, normalized)
            answer_written = True
        except FileExistsError:
            output_error = (
                f"--out became occupied: {out}; refusing to overwrite an existing path"
            )
        except OSError as exc:
            output_error = f"cannot write --out {out}: {exc}"

    stderr_tail = ""
    try:
        stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    except OSError:
        pass
    answer_errors = validation_errors + ([output_error] if output_error else [])
    _atomic_text(
        run_dir / "trajectory.md",
        "# Executor trajectory\n\n"
        f"[ACTION] {' '.join(launch_argv)}\n"
        f"[OBSERVATION] events={parsed.get('event_count')} "
        f"sessions={','.join(parsed.get('session_ids') or []) or 'none'} "
        f"cost_usd={parsed.get('cost_usd')} ({parsed.get('cost_source')})\n"
        f"[BOUNDARY] {'ok' if not violations else 'violations=' + str(len(violations))}\n"
        f"[SESSION] {session.get('remote_session_state')}\n"
        f"[ERROR] {'; '.join(answer_errors) if answer_errors else ''}\n",
    )
    receipt = {
        "schema": "harness2_skills_executor/1",
        "argv": launch_argv,
        "cwd": str(workspace),
        "opencode_path": opencode,
        "opencode_version": version,
        "model_requested": model,
        "model_from_argv": model,
        "model_verified": False,
        "model_source": "configured argv label; not provider proof",
        "process_pid": proc.pid if proc else None,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_kind": "wall" if timed_out else "",
        "timeout_s": args.timeout_s,
        "started_unix": started_unix,
        "ended_unix": time.time(),
        "wall_s": round(time.monotonic() - started, 3),
        "stdout_path": str(events_path),
        "stderr_path": str(stderr_path),
        "stderr_tail": stderr_tail,
        "session_id": parsed.get("session_id"),
        "session_ids": parsed.get("session_ids"),
        "session_reconciliation": session,
        "event_count": parsed.get("event_count"),
        "tool_events": parsed.get("tool_events"),
        "cost_usd": parsed.get("cost_usd"),
        "cost_source": parsed.get("cost_source"),
        "answer_source": answer_source,
        "answer_case_ids": answer_ids,
        "answer_error": "; ".join(answer_errors),
        "answer_written": answer_written,
        "answer_sha256": sha256_file(out) if answer_written else None,
        "before": before,
        "after": after,
        "source_unchanged": after["source"] == before["source"],
        "task_unchanged": after["task"] == before["task"],
        "harness_unchanged": after["harness"] == before["harness"],
        "skills_unchanged": after["skills"] == before.get("skills"),
        "resources_unchanged": after["resources"] == before.get("resources"),
        "scripts_unchanged": after["scripts"] == before.get("scripts"),
        "oc_skills_unchanged": after["oc_skills"] == before.get("oc_skills"),
        "boundary_violations": violations,
        "boundary_ok": not violations,
        "workspace_retained": True,
        "stopped_claimed": session.get("stopped_claimed", False),
        "permission_fence": {
            "external_directory": "workspace only",
            "webfetch": "deny",
            "websearch": "deny",
            "skill": "deny",
            "limit": "tool permission policy, not an OS sandbox",
        },
        "limits": [
            "one CLI launch; this executor performs no retries",
            "a retry needs a fresh run directory; an existing executor receipt is never erased",
            "the upstream native stage loop may call the editor more than once",
            "a detached descendant outside the owned process group can survive a timeout",
            "session cancellation is bounded to the exact reported id that the local API still reports active",
            "an interrupt acknowledgement is not proof of inactivity; a stop is claimed only after bounded exact-id polling verifies absence and the owned frontend has exited",
            "a configured --model is not proof of the provider actually used",
        ],
    }
    write_json(run_dir / "executor_receipt.json", receipt)

    if output_error:
        print(f"solve: {output_error}", file=sys.stderr)
        return 2
    if violations:
        print("solve: boundary violation; answer rejected", file=sys.stderr)
        for violation in violations[:10]:
            print(f"  {violation}", file=sys.stderr)
        return 2
    if timed_out or returncode not in (0, None):
        print(
            f"solve: opencode failed: timed_out={timed_out} rc={returncode}",
            file=sys.stderr,
        )
        return returncode if returncode and returncode > 0 else 1
    if validation_errors:
        print("solve: answer rejected", file=sys.stderr)
        for error in validation_errors[:10]:
            print(f"  {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
