"""Contracts for the thin public native Harness² skill example.

These tests are offline: they run ``prepare.py``, a fake ``opencode`` CLI and
``judge.py``.  They never call a model, a provider, a network service or a
private workspace.  The optional fork dry-run test skips when no public fork is
available, and reads only its public CLI.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "harness2-skills"
FIXTURES = EXAMPLE / "fixtures"
FAMILIES = ("workdocs", "coordination", "specialists")
PYTHON = sys.executable


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load_module("example_prepare", EXAMPLE / "prepare.py")
solve = load_module("example_solve", EXAMPLE / "solve.py")
judge = load_module("example_judge", EXAMPLE / "judge.py")


def run_script(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(script), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def prepare_family(tmp_path: Path, family: str) -> Path:
    output = tmp_path / f"prepared-{family}"
    result = run_script(
        EXAMPLE / "prepare.py",
        "--family",
        family,
        "--model",
        "example/provider#high",
        "--output",
        str(output),
        "--skills-root",
        str(ROOT / "skills"),
    )
    assert result.returncode == 0, result.stderr
    return output


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_skills() -> list[str]:
    return sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))


def all_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for family in FAMILIES:
        doc = read_json(FIXTURES / "cases" / f"{family}.json")
        cases.extend(doc["cases"])
    return cases


FAKE = r'''#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

mode = os.environ.get("FAKE_OPENCODE_MODE", "good")
api_mode = os.environ.get("FAKE_OPENCODE_API_MODE", "unknown")
OWNED_SESSION = "ses_fake_123"
API_STATE = Path(".fake-api-state.json")


def load_api_state():
    try:
        return json.loads(API_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_api_state(state):
    API_STATE.write_text(json.dumps(state), encoding="utf-8")


if "--version" in sys.argv:
    print("fake-opencode 9.9.9")
    raise SystemExit(0)
if sys.argv[1:2] == ["api"]:
    call = {"argv": sys.argv, "cwd": os.getcwd()}
    with Path("opencode-api-calls.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(call) + "\n")
    args = sys.argv[2:]
    if args[:2] == ["get", "/api/session/active"]:
        if api_mode == "unknown":
            raise SystemExit(1)
        if api_mode == "malformed":
            print("not-json")
            raise SystemExit(0)
        state = load_api_state()
        state["gets"] = int(state.get("gets", 0)) + 1
        save_api_state(state)
        data = {}
        acknowledged = bool(state.get("acked"))
        active_now = api_mode in ("active", "ack_then_stillactive") or (
            api_mode == "ack_then_inactive" and not acknowledged
        )
        if active_now:
            data[OWNED_SESSION] = {"type": "running"}
            data["ses_unrelated_do_not_dump"] = {"type": "running"}
        print(json.dumps({"data": data}))
        raise SystemExit(0)
    if args[:1] == ["post"] and args[1:2] and args[1].endswith("/interrupt"):
        if args[1] != f"/api/session/{OWNED_SESSION}/interrupt":
            print("refusing unknown cancel target", file=sys.stderr)
            raise SystemExit(4)
        state = load_api_state()
        state["posts"] = int(state.get("posts", 0)) + 1
        state["acked"] = True
        save_api_state(state)
        print(
            json.dumps(
                {
                    "interrupted": api_mode
                    in ("active", "ack_then_inactive", "ack_then_stillactive")
                }
            )
        )
        raise SystemExit(0)
    raise SystemExit(1)
if sys.argv[1:2] != ["run"]:
    raise SystemExit(2)

Path("argv.json").write_text(
    json.dumps({"argv": sys.argv, "cwd": os.getcwd()}), encoding="utf-8"
)
source = json.loads(Path("source/cases.json").read_text(encoding="utf-8"))
print(json.dumps({"type": "session", "sessionID": "ses_fake_123"}))
if mode == "timeout":
    print(json.dumps({"type": "text", "part": {"text": "slow"}}), flush=True)
    time.sleep(30)
    raise SystemExit(0)

cases = []
for case in source["cases"]:
    cases.append(
        {
            "id": case["id"],
            "decision": "inspect",
            "output_target": "none",
            "completion": "incomplete",
            "rationale": "The fixed facts do not establish the requested outcome.",
        }
    )
if mode == "wrapper":
    body = {"answer": {"cases": cases}}
elif mode == "missing":
    body = {"cases": cases[:-1]}
elif mode == "malformed":
    body = {"cases": [{"id": "not-a-case"}]}
else:
    body = {"cases": cases}
Path("answer.json").write_text(json.dumps(body), encoding="utf-8")
print(json.dumps({"type": "step_finish", "part": {"cost": 0.0123}}))
print(json.dumps({"type": "text", "part": {"text": "done"}}))
'''


def fake_bin(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cli = bin_dir / "opencode"
    cli.write_text(textwrap.dedent(FAKE), encoding="utf-8")
    cli.chmod(cli.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    return cli, env


def solver_argv(
    prepared: Path,
    run_dir: Path,
    *,
    task: Path | None = None,
    harness: Path | None = None,
    out: Path | None = None,
    timeout_s: int = 20,
    model: str = "example/provider#high",
) -> list[str]:
    task_dir = task or (prepared / "tasks" / "workdocs-all")
    return [
        str(EXAMPLE / "solve.py"),
        "--task",
        str(task_dir),
        "--harness",
        str(harness or (prepared / "base")),
        "--resources",
        str(prepared / "resources"),
        "--model",
        model,
        "--out",
        str(out or (run_dir / "answer.json")),
        "--run-dir",
        str(run_dir),
        "--timeout-s",
        str(timeout_s),
    ]


def run_solver(
    tmp_path: Path,
    prepared: Path,
    env: dict[str, str],
    *,
    task: Path | None = None,
    timeout_s: int = 20,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    run_dir = tmp_path / "solve-run"
    result = run_script(
        *solver_argv(prepared, run_dir, task=task, timeout_s=timeout_s), env=env
    )
    return result, run_dir


# -- prepare -----------------------------------------------------------------


@pytest.mark.parametrize("family", FAMILIES)
def test_prepare_builds_complete_strict_output(tmp_path: Path, family: str) -> None:
    output = prepare_family(tmp_path, family)
    manifest = read_json(output / "manifest.json")
    receipt = read_json(output / "prepare-receipt.json")

    assert manifest["schema"] == 1
    assert manifest["name"] == f"h2-{family}-k1"
    assert manifest["editor"]["model"] == "example/provider#high"
    assert manifest["executor"]["model"] == "example/provider#high"
    assert "example/provider#high" in manifest["executor"]["argv"]
    assert isinstance(manifest["executor"]["argv"], list)
    assert isinstance(manifest["judge"]["argv"], list)
    assert manifest["executor"]["answer"] == "answer.json"
    assert manifest["leak_globs"] == prepare.LEAK_GLOBS
    for key in ("base_harness", "tasks_dir", "task_prompt", "task_source"):
        assert not Path(manifest[key]).is_absolute()

    cases = read_json(output / "tasks" / f"{family}-all" / "source" / "cases.json")
    assert cases["family"] == family
    assert "expected" not in cases
    assert len(cases["cases"]) == 14
    assert receipt["cases"] == 14
    assert receipt["decision_fields"] == 42
    assert receipt["oracle_in_model_inputs"] is False
    assert receipt["oracle_location"] == "oracle/expected.json"
    assert (output / "oracle" / "expected.json").is_file()
    assert (output / "tools" / "solve.py").is_file()
    assert (output / "tools" / "judge.py").is_file()

    # No answer-key-shaped file is inside the model's base or task copies.
    for root in (output / "base", output / "tasks"):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name
            assert not any(
                name.startswith(prefix)
                for prefix in ("expected", "judge", "oracle", "heldout")
            ), path


@pytest.mark.parametrize("family", FAMILIES)
def test_prepare_retains_complete_resources_and_rewrites_links(tmp_path: Path, family: str) -> None:
    output = prepare_family(tmp_path, family)
    receipt = read_json(output / "prepare-receipt.json")
    cases = read_json(output / "tasks" / f"{family}-all" / "source" / "cases.json")
    skills = sorted({case["skill"] for case in cases["cases"]})

    for skill in skills:
        source = ROOT / "skills" / skill
        snapshot = output / "resources" / skill
        source_files = {
            path.relative_to(source).as_posix()
            for path in source.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        snapshot_files = {
            path.relative_to(snapshot).as_posix()
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        assert snapshot_files == source_files, skill

        entry = receipt["skill_hashes"][skill]
        assert entry["base_tree_sha256"]
        assert entry["resources_tree_sha256"]
        assert (output / "base" / "skills" / skill / "SKILL.md").is_file()
        text = (output / "base" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        for source_rel, target_rel in entry["normalization"].items():
            assert source_rel not in text, (skill, source_rel)
            assert (output / "base" / "skills" / skill / target_rel).is_file(), (
                skill,
                target_rel,
            )
        # Every flattened reference/asset the copied SKILL.md points at exists.
        for target in re.findall(r"scripts/(?:reference|asset)_[A-Za-z0-9_.-]+", text):
            assert (output / "base" / "skills" / skill / target).is_file(), (
                skill,
                target,
            )


def test_prepare_rejects_missing_occupied_and_free_inputs(tmp_path: Path) -> None:
    missing = run_script(
        EXAMPLE / "prepare.py",
        "--family",
        "workdocs",
        "--output",
        str(tmp_path / "missing"),
        "--skills-root",
        str(ROOT / "skills"),
    )
    assert missing.returncode == 2
    assert not (tmp_path / "missing").exists()

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "file").write_text("x", encoding="utf-8")
    used = run_script(
        EXAMPLE / "prepare.py",
        "--family",
        "workdocs",
        "--model",
        "example/provider#high",
        "--output",
        str(occupied),
        "--skills-root",
        str(ROOT / "skills"),
    )
    assert used.returncode == 2

    for model in ("free", "auto", "example/free#high", "provider/model"):
        result = run_script(
            EXAMPLE / "prepare.py",
            "--family",
            "workdocs",
            "--model",
            model,
            "--output",
            str(tmp_path / "free"),
            "--skills-root",
            str(ROOT / "skills"),
        )
        assert result.returncode == 2, model
        assert not (tmp_path / "free").exists()

    inside = ROOT / "skills" / ".prepare-test-should-not-exist"
    guarded = run_script(
        EXAMPLE / "prepare.py",
        "--family",
        "workdocs",
        "--model",
        "example/provider#high",
        "--output",
        str(inside),
        "--skills-root",
        str(ROOT / "skills"),
    )
    assert guarded.returncode == 2
    assert not inside.exists()


def test_prepare_rejects_symlink_and_dangling_output_without_touching_targets(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    link = tmp_path / "output-link"
    link.symlink_to(target)
    result = run_script(
        EXAMPLE / "prepare.py",
        "--family",
        "workdocs",
        "--model",
        "example/provider#high",
        "--output",
        str(link),
        "--skills-root",
        str(ROOT / "skills"),
    )
    assert result.returncode == 2
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert link.is_symlink()

    missing = tmp_path / "missing-target"
    dangling = tmp_path / "dangling-output"
    dangling.symlink_to(missing)
    result = run_script(
        EXAMPLE / "prepare.py",
        "--family",
        "workdocs",
        "--model",
        "example/provider#high",
        "--output",
        str(dangling),
        "--skills-root",
        str(ROOT / "skills"),
    )
    assert result.returncode == 2
    assert dangling.is_symlink()
    assert not missing.exists()


def test_prepare_mirrors_or_rewrites_every_script_invocation(tmp_path: Path) -> None:
    output = prepare_family(tmp_path, "coordination")
    receipt = read_json(output / "prepare-receipt.json")
    mirrored = receipt["script_adaptations"]["herdr-opencode-agmsg"]["mirrored"]
    assert "scripts/provider_plan.py" in mirrored
    assert "scripts/cleanup_gate.py" in mirrored
    for target in mirrored:
        assert (output / "base" / target).is_file()
    for skill_md in (output / "base" / "skills").glob("*/SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        for ref in re.findall(
            r"(?:python3?\s+)((?:skills/[a-z0-9][a-z0-9_-]*/)?scripts/[A-Za-z0-9_.-]+\.py)",
            text,
        ):
            assert (output / "base" / ref).is_file(), (skill_md, ref)


def test_prepared_base_passes_the_actual_public_fork_surface(tmp_path: Path) -> None:
    fork = os.environ.get("HARNESS2_FORK", "")
    if not fork:
        pytest.skip("HARNESS2_FORK is not set; the actual fork surface check is optional here")
    fork_path = Path(fork)
    if not (fork_path / "harness2" / "core" / "tree.py").is_file():
        pytest.skip(f"HARNESS2_FORK does not look like the public fork: {fork_path}")
    output = prepare_family(tmp_path, "coordination")
    code = textwrap.dedent(
        """
        import json
        from pathlib import Path
        from harness2.core import tree
        from harness2.substrate.opencode import OPENCODE_SURFACE
        base = Path(__import__("sys").argv[1])
        rejected = []
        body = tree.read_tree(OPENCODE_SURFACE, base, rejected=rejected)
        print(json.dumps({"census": tree.validate(OPENCODE_SURFACE, body, allow_subagents=False), "rejected": rejected}))
        """
    )
    result = subprocess.run(
        [PYTHON, "-c", code, str(output / "base")],
        cwd=fork_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["rejected"] == []
    assert verdict["census"]["skills"] == 7
    assert verdict["census"]["always_on_chars"] <= 24000


def test_prepare_manifest_passes_the_actual_public_fork_dry_run(tmp_path: Path) -> None:
    output = prepare_family(tmp_path, "workdocs")
    fork = os.environ.get("HARNESS2_FORK", "")
    if not fork:
        pytest.skip("HARNESS2_FORK is not set; the actual fork dry-run is optional here")
    fork_path = Path(fork)
    if not (fork_path / "harness2" / "cli" / "ordinary.py").is_file():
        pytest.skip(f"HARNESS2_FORK does not look like the public fork: {fork_path}")
    run_output = tmp_path / "dry-run-output"
    result = subprocess.run(
        [
            PYTHON,
            "-m",
            "harness2.cli.ordinary",
            "--manifest",
            str(output / "manifest.json"),
            "--output",
            str(run_output),
            "--k",
            "1",
            "--modes",
            "parallel",
            "--dry-run",
        ],
        cwd=fork_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["schema"] == 1
    assert plan["tasks"] == ["workdocs-all"]
    assert plan["executor"]["declared_model"] == "example/provider#high"
    assert plan["editor"]["model"] == "example/provider#high"
    assert plan["judge_enabled"] is True
    assert plan["k"] == 1
    assert not run_output.exists()


# -- solver ------------------------------------------------------------------


def test_solver_fake_cli_good_answer_and_receipt(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)
    result, run_dir = run_solver(tmp_path, prepared, env)
    assert result.returncode == 0, result.stderr
    answer = read_json(run_dir / "answer.json")
    source_ids = [
        case["id"]
        for case in read_json(prepared / "tasks" / "workdocs-all" / "source" / "cases.json")[
            "cases"
        ]
    ]
    assert [case["id"] for case in answer["cases"]] == source_ids
    receipt = read_json(run_dir / "executor_receipt.json")
    assert receipt["returncode"] == 0
    assert receipt["timed_out"] is False
    assert receipt["answer_written"] is True
    assert receipt["answer_sha256"]
    assert receipt["session_id"] == "ses_fake_123"
    assert receipt["cost_usd"] == pytest.approx(0.0123)
    assert receipt["cost_source"] == "reported"
    assert receipt["model_verified"] is False
    assert receipt["source_unchanged"] is True
    assert receipt["task_unchanged"] is True
    assert receipt["harness_unchanged"] is True
    assert receipt["boundary_ok"] is True
    assert receipt["permission_fence"]["external_directory"] == "workspace only"
    assert receipt["permission_fence"]["webfetch"] == "deny"
    assert receipt["permission_fence"]["skill"] == "deny"
    argv = read_json(run_dir / "workspace" / "argv.json")
    assert argv["argv"][1] == "run"
    assert "--auto" in argv["argv"] and "--format" in argv["argv"] and "json" in argv["argv"]
    assert argv["argv"][argv["argv"].index("--model") + 1] == "example/provider#high"


@pytest.mark.parametrize("mode", ["wrapper", "missing", "malformed"])
def test_solver_rejects_wrong_wrapper_missing_case_and_malformed(
    tmp_path: Path, mode: str
) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)
    env["FAKE_OPENCODE_MODE"] = mode
    result, run_dir = run_solver(tmp_path, prepared, env)
    assert result.returncode != 0
    assert not (run_dir / "answer.json").exists()
    receipt = read_json(run_dir / "executor_receipt.json")
    assert receipt["answer_written"] is False
    assert receipt["answer_error"]


def test_solver_timeout_kills_only_owned_group_and_retains_workspace(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)
    env["FAKE_OPENCODE_MODE"] = "timeout"
    started = time.monotonic()
    result, run_dir = run_solver(tmp_path, prepared, env, timeout_s=1)
    elapsed = time.monotonic() - started
    assert result.returncode != 0
    assert elapsed < 20
    receipt = read_json(run_dir / "executor_receipt.json")
    assert receipt["timed_out"] is True
    assert receipt["workspace_retained"] is True
    assert receipt["stopped_claimed"] is False
    assert receipt["session_reconciliation"]["remote_session_state"] == "pending"
    assert (run_dir / "workspace").is_dir()
    assert (run_dir / "agent_events.jsonl").is_file()
    assert (run_dir / "agent_stderr.log").is_file()


def test_solver_rejects_occupied_and_symlinked_paths_without_deleting(
    tmp_path: Path,
) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)

    occupied = tmp_path / "occupied-answer.json"
    occupied.write_text("sentinel", encoding="utf-8")
    run_dir = tmp_path / "run-with-occupied-out"
    result = run_script(
        *solver_argv(prepared, run_dir, out=occupied), env=env
    )
    assert result.returncode == 2
    assert occupied.read_text(encoding="utf-8") == "sentinel"
    assert not run_dir.exists()

    target = tmp_path / "run-target"
    target.mkdir()
    sentinel = target / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    linked_run = tmp_path / "linked-run"
    linked_run.symlink_to(target)
    result = run_script(*solver_argv(prepared, linked_run), env=env)
    assert result.returncode == 2
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert linked_run.is_symlink()

    missing = tmp_path / "missing-run-target"
    dangling_run = tmp_path / "dangling-run"
    dangling_run.symlink_to(missing)
    result = run_script(*solver_argv(prepared, dangling_run), env=env)
    assert result.returncode == 2
    assert dangling_run.is_symlink()
    assert not missing.exists()

    out_link = tmp_path / "linked-answer.json"
    out_link.symlink_to(occupied)
    run_dir = tmp_path / "run-with-linked-out"
    result = run_script(*solver_argv(prepared, run_dir, out=out_link), env=env)
    assert result.returncode == 2
    assert occupied.read_text(encoding="utf-8") == "sentinel"
    assert out_link.is_symlink()
    assert not run_dir.exists()

    run_with_workspace = tmp_path / "run-with-workspace"
    workspace = run_with_workspace / "workspace"
    workspace.mkdir(parents=True)
    workspace_sentinel = workspace / "keep.txt"
    workspace_sentinel.write_text("keep", encoding="utf-8")
    result = run_script(*solver_argv(prepared, run_with_workspace), env=env)
    assert result.returncode == 2
    assert workspace_sentinel.read_text(encoding="utf-8") == "keep"
    assert not (run_with_workspace / "executor_receipt.json").exists()


def test_solver_rejects_overlap_with_task_harness_and_source(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)
    task_dir = prepared / "tasks" / "workdocs-all"
    task_sentinel = task_dir / "keep-sentinel.txt"
    task_sentinel.write_text("keep", encoding="utf-8")

    result = run_script(*solver_argv(prepared, task_dir), env=env)
    assert result.returncode == 2
    assert task_sentinel.read_text(encoding="utf-8") == "keep"
    assert (task_dir / "task.md").is_file()

    source = task_dir / "source" / "cases.json"
    source_before = source.read_bytes()
    out_in_source = task_dir / "source" / "answer.json"
    result = run_script(
        *solver_argv(prepared, tmp_path / "run-source-overlap", out=out_in_source),
        env=env,
    )
    assert result.returncode == 2
    assert not out_in_source.exists()
    assert source.read_bytes() == source_before

    out_in_harness = prepared / "base" / "answer.json"
    result = run_script(
        *solver_argv(prepared, tmp_path / "run-harness-overlap", out=out_in_harness),
        env=env,
    )
    assert result.returncode == 2
    assert not out_in_harness.exists()


def test_solver_refuses_prior_receipt_but_accepts_native_scaffold(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)

    prior = tmp_path / "prior-run"
    prior.mkdir()
    prior_receipt = prior / "executor_receipt.json"
    prior_receipt.write_text("prior-receipt", encoding="utf-8")
    result = run_script(*solver_argv(prepared, prior), env=env)
    assert result.returncode == 2
    assert prior_receipt.read_text(encoding="utf-8") == "prior-receipt"
    assert not (prior / "workspace").exists()

    native = tmp_path / "native-run"
    native.mkdir()
    (native / "input").mkdir()
    (native / "harness").mkdir()
    native_run = native / "run.json"
    native_run.write_text('{"native": "scaffold"}', encoding="utf-8")
    # The native adapter opens its own logs before launching the executor and
    # copies the task and candidate harness below run_dir.
    (native / "stdout.log").write_text("", encoding="utf-8")
    (native / "stderr.log").write_text("", encoding="utf-8")
    shutil.copytree(
        prepared / "tasks" / "workdocs-all",
        native / "input" / "task",
    )
    shutil.copytree(
        prepared / "base",
        native / "harness",
        dirs_exist_ok=True,
    )
    result = run_script(
        *solver_argv(
            prepared,
            native,
            task=native / "input" / "task",
            harness=native / "harness",
        ),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert native_run.read_text(encoding="utf-8") == '{"native": "scaffold"}'
    assert (native / "executor_receipt.json").is_file()
    assert (native / "answer.json").is_file()


def test_solver_queries_only_the_exact_owned_session(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)
    env["FAKE_OPENCODE_API_MODE"] = "active"
    result, run_dir = run_solver(tmp_path, prepared, env)
    assert result.returncode == 0, result.stderr
    evidence = read_json(run_dir / "session_api.json")
    assert evidence["remote_session_state"] == "active"
    assert evidence["owned_session_present"] is True
    assert evidence["stopped_claimed"] is False
    text = (run_dir / "session_api.json").read_text(encoding="utf-8")
    assert "ses_unrelated_do_not_dump" not in text
    assert "ses_fake_123" in text


@pytest.mark.parametrize(
    ("api_mode", "state", "stopped", "cancelled", "verified"),
    [
        ("ack_then_inactive", "inactive", True, True, True),
        ("ack_then_stillactive", "pending", False, True, False),
        ("inactive", "inactive", False, False, False),
        ("unknown", "pending", False, False, False),
        ("malformed", "pending", False, False, False),
    ],
)
def test_solver_timeout_cancels_only_exact_active_owned_session(
    tmp_path: Path, api_mode: str, state: str, stopped: bool, cancelled: bool,
    verified: bool,
) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)
    env["FAKE_OPENCODE_API_MODE"] = api_mode
    env["FAKE_OPENCODE_MODE"] = "timeout"
    result, run_dir = run_solver(tmp_path, prepared, env, timeout_s=1)
    assert result.returncode != 0
    evidence = read_json(run_dir / "session_api.json")
    assert evidence["remote_session_state"] == state
    assert evidence["stopped_claimed"] is stopped
    assert evidence["cancellation"]["attempted"] is cancelled
    if cancelled:
        assert evidence["cancellation"]["interrupted"] is True
        assert evidence["cancellation"]["frontend_exited"] is True
        check = evidence["cancellation"]["verification"]
        assert check["attempted"] is True
        assert check["exact_session_id_only"] is True
        assert check["verified_inactive"] is verified
        assert check["polls"] >= 1
        assert check["observed_states"]
        assert "interrupted" not in evidence["remote_session_state"]
        if verified:
            assert check["observed_states"][-1] == "inactive"
            assert evidence["owned_session_present"] is False
        else:
            assert set(check["observed_states"]) == {"active"}
    calls = [
        json.loads(line)
        for line in (run_dir / "opencode-api-calls.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    gets = [call for call in calls if call["argv"][2:3] == ["get"]]
    assert gets
    assert all(call["argv"][3] == "/api/session/active" for call in gets)
    interrupts = [call for call in calls if call["argv"][2:3] == ["post"]]
    assert bool(interrupts) is cancelled
    if interrupts:
        assert len(interrupts) == 1
        assert interrupts[0]["argv"][3] == "/api/session/ses_fake_123/interrupt"
    assert "ses_unrelated_do_not_dump" not in (run_dir / "session_api.json").read_text(
        encoding="utf-8"
    )


def test_reconcile_does_not_claim_stop_without_owned_frontend_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli, _env = fake_bin(tmp_path)
    monkeypatch.setenv("FAKE_OPENCODE_API_MODE", "ack_then_inactive")
    run_dir = tmp_path / "api-only-run"
    run_dir.mkdir()
    evidence = solve.reconcile_session(
        str(cli),
        "ses_fake_123",
        run_dir,
        timed_out=True,
        frontend_exited=False,
    )
    assert evidence["cancellation"]["verification"]["verified_inactive"] is True
    assert evidence["cancellation"]["frontend_exited"] is False
    assert evidence["remote_session_state"] == "pending"
    assert evidence["stopped_claimed"] is False


def test_solver_passes_paths_with_spaces_as_literal_argv(tmp_path: Path) -> None:
    spaced = tmp_path / "dir with spaces"
    spaced.mkdir()
    prepared = prepare_family(spaced, "workdocs")
    _cli, env = fake_bin(spaced)
    result, run_dir = run_solver(spaced, prepared, env)
    assert result.returncode == 0, result.stderr
    recorded = read_json(run_dir / "workspace" / "argv.json")
    assert recorded["argv"][1] == "run"
    assert "dir with spaces" in str(prepared)
    assert (run_dir / "workspace" / "source" / "cases.json").is_file()
    receipt = read_json(run_dir / "executor_receipt.json")
    assert receipt["harness_unchanged"] is True
    assert receipt["source_unchanged"] is True


def test_solver_rejects_free_model_before_launch(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    _cli, env = fake_bin(tmp_path)
    run_dir = tmp_path / "run"
    result = run_script(
        EXAMPLE / "solve.py",
        "--task",
        str(prepared / "tasks" / "workdocs-all"),
        "--harness",
        str(prepared / "base"),
        "--resources",
        str(prepared / "resources"),
        "--model",
        "free",
        "--out",
        str(run_dir / "answer.json"),
        "--run-dir",
        str(run_dir),
        env=env,
    )
    assert result.returncode == 2
    assert not (run_dir / "answer.json").exists()


# -- judge -------------------------------------------------------------------


def gold_answer(prepared: Path) -> dict[str, Any]:
    expected = read_json(prepared / "oracle" / "expected.json")["expected"]
    cases = read_json(prepared / "tasks" / "workdocs-all" / "source" / "cases.json")["cases"]
    rows = []
    for case in cases:
        row = expected[case["id"]]
        rows.append(
            {
                "id": case["id"],
                "decision": row["decision"][0]
                if isinstance(row["decision"], list)
                else row["decision"],
                "output_target": row["output_target"],
                "completion": row["completion"],
                "rationale": "Gold synthetic answer for the judge control.",
            }
        )
    return {"cases": rows}


def run_judge(prepared: Path, answer: dict[str, Any], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "judge-answer.json"
    path.write_text(json.dumps(answer), encoding="utf-8")
    return run_script(
        EXAMPLE / "judge.py",
        "--task",
        str(prepared / "tasks" / "workdocs-all"),
        "--answer",
        str(path),
        "--expected",
        str(prepared / "oracle" / "expected.json"),
    )


def test_judge_gold_and_always_stop_and_always_proceed_controls(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    gold = gold_answer(prepared)
    result = run_judge(prepared, gold, tmp_path)
    assert result.returncode == 0, result.stderr
    scored = json.loads(result.stdout)
    assert scored["n_passed"] == scored["n_criteria"] == 42
    assert scored["all_pass"] is True

    for decision in ("stop", "proceed"):
        control = json.loads(json.dumps(gold))
        for case in control["cases"]:
            case["decision"] = decision
        result = run_judge(prepared, control, tmp_path)
        assert result.returncode == 0
        scored = json.loads(result.stdout)
        assert scored["all_pass"] is False
        assert 0 < scored["n_passed"] < scored["n_criteria"]


def test_judge_duplicate_and_missing_cases_are_unknown_not_zero(tmp_path: Path) -> None:
    prepared = prepare_family(tmp_path, "workdocs")
    gold = gold_answer(prepared)

    duplicate = json.loads(json.dumps(gold))
    duplicate["cases"].append(duplicate["cases"][0])
    result = run_judge(prepared, duplicate, tmp_path)
    assert result.returncode != 0
    assert json.loads(result.stdout)["unknown"] is True

    missing = json.loads(json.dumps(gold))
    missing["cases"] = missing["cases"][:-1]
    result = run_judge(prepared, missing, tmp_path)
    assert result.returncode != 0
    assert json.loads(result.stdout)["unknown"] is True


# -- fixtures and publication boundary ---------------------------------------


def test_dynamic_case_fixtures_cover_every_public_skill_once_per_boundary() -> None:
    skills = discover_skills()
    assert skills, "skills/*/SKILL.md が見つからない"
    cases = all_cases()
    assert len(cases) == 2 * len(skills)
    assert len({case["id"] for case in cases}) == len(cases)
    by_skill: dict[str, list[str]] = {}
    for case in cases:
        by_skill.setdefault(case["skill"], []).append(case["id"])
    assert sorted(by_skill) == skills
    for skill, ids in by_skill.items():
        assert sorted(ids) == [f"{skill}--boundary", f"{skill}--positive"], skill
    assert len(cases) * 3 == 126

    expected = read_json(FIXTURES / "expected.json")["expected"]
    assert set(expected) == {case["id"] for case in cases}
    for row in expected.values():
        for key in ("decision", "output_target", "completion"):
            value = row[key]
            assert isinstance(value, (str, list))
            if isinstance(value, list):
                assert value and all(isinstance(item, str) for item in value)
    for family in FAMILIES:
        doc = read_json(FIXTURES / "cases" / f"{family}.json")
        assert doc["family"] == family
        assert len(doc["cases"]) == 14
        assert all("expected" not in case for case in doc["cases"])


def test_heldout_cases_are_separate_and_not_in_the_task_fixtures() -> None:
    heldout = read_json(FIXTURES / "heldout" / "cases.json")
    heldout_expected = read_json(FIXTURES / "heldout-expected.json")
    assert len(heldout["cases"]) == 3
    assert len(heldout_expected["expected"]) == 3
    heldout_ids = {case["id"] for case in heldout["cases"]}
    assert heldout_ids == set(heldout_expected["expected"])
    assert heldout_ids.isdisjoint({case["id"] for case in all_cases()})
    for case in heldout["cases"]:
        assert "expected" not in case
        assert "facts_and_request" in case


def test_example_source_contains_no_private_or_absolute_path() -> None:
    forbidden = (
        "/" + "home/",
        "/" + "Users/",
        "tomato" + "-workflow",
        "orchard" + "-",
        "yuki-inaho" + "/.local",
        "private-provider" + "-catalog",
        "herdr" + ".sock",
    )
    for path in EXAMPLE.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in forbidden:
            assert token not in text, f"{path}: contains {token!r}"
