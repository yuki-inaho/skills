"""Exercise selection-to-launch using synthetic executables, never a provider."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/herdr-opencode-agmsg/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("provider_launch", SCRIPTS / "provider_launch.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

A, A2, B, C = "cloud/model-1017", "cloud/model", "go/model", "router/model-1017"
CATALOG = {"provider_order": ["cloud", "go", "router"], "default_variant": "high",
           "prefer_capabilities": ["1017"],
           "models": [{"id": x, "free": False, "variants": ["high"],
                       "capabilities": ["1017"] if x in (A, C) else []}
                      for x in (A, A2, B, C)]}


def request(**kwargs):
    return {"discovery": [A, A2, B, C], "live_job_possible": False, **kwargs}


def failure(candidate=A, outcome="transient", scope="provider"):
    return {"candidate": candidate + "#high", "outcome": outcome, "scope": scope}


def test_shared_transport_budget_skips_sibling_models_without_quota_claim():
    decision = launcher.plan(request(attempts=[failure(), failure()]), CATALOG)
    assert decision["candidate"] == B + "#high"
    assert {x["reason"] for x in decision["excluded"]} == {"provider_transport_budget_exhausted"}


def test_candidate_failure_does_not_skip_provider():
    decision = launcher.plan(request(attempts=[failure(scope="candidate")] * 2), CATALOG)
    assert decision["candidate"] == A2 + "#high"


def test_second_provider_failure_selects_router():
    decision = launcher.plan(request(attempts=[failure()] * 2 + [failure(B)] * 2), CATALOG)
    assert decision["candidate"] == C + "#high"


def test_required_version_skips_undated_go():
    decision = launcher.plan(request(attempts=[failure()] * 2, required_capabilities=["1017"]), CATALOG)
    assert decision["candidate"] == C + "#high"


@pytest.mark.parametrize("outcome,action", [("auth_error", "stop"), ("unknown", "inspect"),
                                           ("code_failure", "fix_same_model"), ("success", "done")])
def test_later_nontransport_result_is_not_hidden(outcome, action):
    decision = launcher.plan(request(attempts=[failure()] * 2 + [failure(outcome=outcome)]), CATALOG)
    assert decision["action"] == action


def test_reconciliation_blocks_before_switch():
    decision = launcher.plan(request(attempts=[failure()] * 2, live_job_possible=True), CATALOG)
    assert decision["action"] == "reconcile"


@pytest.mark.parametrize("updates", [{"live_job_possible": None},
                                    {"attempts": [failure()]},
                                    {"remaining_seconds": 1},
                                    {"retry_after_seconds": 4, "remaining_seconds": 6}])
def test_launch_refuses_unknown_live_work_or_insufficient_budget(tmp_path, updates):
    assignment = tmp_path / "assignment.txt"
    assignment.write_text("Synthetic task, nonce new-01")
    with pytest.raises(ValueError):
        launcher.prepare(request(**updates), CATALOG, assignment, 3)


def test_planner_choice_is_exact_argv_without_resume(tmp_path):
    assignment = tmp_path / "assignment.txt"
    assignment.write_text("Synthetic task, nonce new-02")
    decision, argv = launcher.prepare(request(attempts=[failure()] * 2, reconciled=True),
                                      CATALOG, assignment, 3)
    assert argv == ["opencode", "run", "--standalone", "--model", B + "#high", assignment.read_text()]
    assert decision["action"] == "launch"


def run_fake(tmp_path, body, timeout=3, updates=None):
    executable = tmp_path / "fake-opencode"
    executable.write_text("#!" + sys.executable + "\n" + body)
    executable.chmod(0o700)
    (tmp_path / "request.json").write_text(json.dumps(request(**(updates or {}))))
    (tmp_path / "catalog.json").write_text(json.dumps(CATALOG))
    (tmp_path / "assignment.txt").write_text("SYNTHETIC_PRIVATE_PROMPT")
    evidence = tmp_path / "attempt-01"
    command = [sys.executable, str(SCRIPTS / "provider_launch.py"),
               "--input", str(tmp_path / "request.json"), "--catalog", str(tmp_path / "catalog.json"),
               "--assignment", str(tmp_path / "assignment.txt"), "--attempt-dir", str(evidence),
               "--opencode", str(executable), "--timeout", str(timeout)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    return result, evidence, command


def test_launch_and_receipt_and_fresh_directory_guard(tmp_path):
    result, evidence, command = run_fake(tmp_path, 'print("visible synthetic output")\n')
    assert result.returncode == 0
    assert "visible synthetic output" in result.stdout
    receipt = json.loads((evidence / "receipt.json").read_text())
    assert receipt["candidate"] == A + "#high"
    assert receipt["exit_code"] == 0 and receipt["outcome"] == "unknown"
    assert receipt["pid"] > 0 and receipt["reconciliation_required"]
    assert evidence.stat().st_mode & 0o777 == 0o700
    assert "SYNTHETIC_PRIVATE_PROMPT" not in (evidence / "receipt.json").read_text()
    assert subprocess.run(command, capture_output=True).returncode == 2


def test_timeout_stops_owned_process_without_claiming_quota(tmp_path):
    result, evidence, _ = run_fake(tmp_path, "import time\ntime.sleep(60)\n", timeout=0.1)
    assert result.returncode == 124
    receipt = json.loads((evidence / "receipt.json").read_text())
    assert receipt["timed_out"] and receipt["outcome"] == "unknown"
    with pytest.raises(ProcessLookupError):
        os.kill(receipt["pid"], 0)


def test_blocked_plan_never_runs_executable(tmp_path):
    result, evidence, _ = run_fake(tmp_path, 'raise AssertionError("must not run")\n',
                                   updates={"attempts": [failure(outcome="auth_error")], "reconciled": True})
    assert result.returncode == 2
    assert not evidence.exists()


@pytest.mark.parametrize("attempts,expected", [([failure()] * 2, B),
                                             ([failure()] * 2 + [failure(B)] * 2, C)])
def test_actual_executable_receives_fallback_model(tmp_path, attempts, expected):
    result, evidence, _ = run_fake(
        tmp_path, 'import sys\nprint(sys.argv[sys.argv.index("--model") + 1])\n',
        updates={"attempts": attempts, "reconciled": True})
    assert result.returncode == 0
    assert expected + "#high" in result.stdout
    assert json.loads((evidence / "receipt.json").read_text())["candidate"] == expected + "#high"
