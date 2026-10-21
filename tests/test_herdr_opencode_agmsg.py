"""herdr-opencode-agmsg の純粋ヘルパーを合成入力で検証する。

実 provider・実 Herdr・実 agmsg は呼ばない。catalog の許可集合（free 禁止・
unlisted 除外・capability 必須・variant 分離）、registry の base ID と
`#variant` 呼び出しの正規化、provider 順序と 1017 優先、quota での乗り換え、
bounded retry、認証エラー停止、code failure の同一モデル修正、live job の
reconcile、owned tab の close 条件を確認する。CLI が入力を変更せず、未知
フィールドや秘密様の値を出力しないことも確認する。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "herdr-opencode-agmsg"
PROVIDER = SKILL / "scripts" / "provider_plan.py"
CLEANUP = SKILL / "scripts" / "cleanup_gate.py"
DEFAULT_CATALOG = SKILL / "assets" / "model_catalog.json"
DISCOVERY_FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_opencode_models.txt"

A_BASE = "example-cloud/model-a"
A2_BASE = "example-cloud/model-b"
B_BASE = "example-go/model-a"
C_BASE = "example-openrouter/model-a-1017"
F_BASE = "example-cloud/model-a:free"
A = f"{A_BASE}#high"
A2 = f"{A2_BASE}#high"
B = f"{B_BASE}#high"
C = f"{C_BASE}#high"
F = f"{F_BASE}#high"
CANARY = "SYNTHETIC_CANARY_VALUE_123"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provider_plan = _load("provider_plan", PROVIDER)
cleanup_gate = _load("cleanup_gate", CLEANUP)

CATALOG: dict[str, object] = {
    "provider_order": ["example-cloud", "example-go", "example-openrouter"],
    "allow_free_models": False,
    "default_variant": "high",
    "prefer_capabilities": ["1017"],
    "models": [
        {"id": A_BASE, "free": False, "capabilities": [], "variants": ["high"]},
        {"id": B_BASE, "free": False, "capabilities": [], "variants": ["high"]},
        {"id": C_BASE, "free": False, "capabilities": ["1017"], "variants": ["high"]},
    ],
}
DISCOVERY = [A_BASE, B_BASE, C_BASE]


def _request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "discovery": list(DISCOVERY),
        "attempts": [],
        "live_job_possible": False,
    }
    base.update(overrides)
    return base


def _attempt(candidate: str, outcome: str, scope: str | None = None) -> dict[str, str]:
    item = {"candidate": candidate, "outcome": outcome}
    if scope is not None:
        item["scope"] = scope
    return item


def _multi_model_catalog() -> dict[str, object]:
    """Two cloud models plus one each from Go and OpenRouter."""
    return {
        **CATALOG,
        "models": [
            {"id": A_BASE, "free": False, "capabilities": [], "variants": ["high"]},
            {"id": A2_BASE, "free": False, "capabilities": [], "variants": ["high"]},
            {"id": B_BASE, "free": False, "capabilities": [], "variants": ["high"]},
            {"id": C_BASE, "free": False, "capabilities": ["1017"], "variants": ["high"]},
        ],
    }


def _fixture_ids() -> list[str]:
    lines = DISCOVERY_FIXTURE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


# ---- catalog policy -------------------------------------------------------


def test_bundled_catalog_is_non_free_and_variant_aware() -> None:
    catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    assert "allow_free_models" not in catalog
    assert catalog["provider_order"][0] == "ollama-cloud"
    assert catalog["default_variant"] == "high"
    assert "1017" in catalog["prefer_capabilities"]
    for entry in catalog["models"]:
        assert "#" not in entry["id"]
        assert "high" in entry["variants"]
        assert entry["free"] is False
        assert ":free" not in entry["id"] and "-free" not in entry["id"]


def test_registry_base_ids_are_normalized_to_high_invocations() -> None:
    decision = provider_plan.plan(_request(), CATALOG)
    assert decision["action"] == "launch"
    assert decision["candidate"] == A
    assert decision["classification"][0]["variant"] == "high"


def test_realistic_registry_listing_prefers_1017_within_provider() -> None:
    catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    ids = _fixture_ids()
    assert "ollama-cloud/deepseek-v4.1-flash:1017" in ids
    decision = provider_plan.plan({"discovery": ids, "attempts": []}, catalog)
    assert decision["action"] == "launch"
    assert decision["candidate"] == "ollama-cloud/deepseek-v4.1-flash:1017#high"


def test_plain_model_is_used_when_1017_is_not_discovered() -> None:
    catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    ids = [
        "ollama-cloud/deepseek-v4.1-flash",
        "opencode-go/deepseek-v4.1-flash",
        "openrouter/deepseek/deepseek-v4.1-flash",
    ]
    decision = provider_plan.plan({"discovery": ids, "attempts": []}, catalog)
    assert decision["candidate"] == "ollama-cloud/deepseek-v4.1-flash#high"


def test_prefer_capability_reorders_even_if_catalog_lists_plain_first() -> None:
    preferred_base = "example-cloud/model-a-1017"
    catalog = {
        **CATALOG,
        "provider_order": ["example-cloud"],
        "models": [
            {"id": A_BASE, "free": False, "capabilities": [], "variants": ["high"]},
            {"id": preferred_base, "free": False, "capabilities": ["1017"], "variants": ["high"]},
        ],
    }
    decision = provider_plan.plan(_request(discovery=[A_BASE, preferred_base]), catalog)
    assert decision["candidate"] == f"{preferred_base}#high"


def test_free_model_marked_in_catalog_is_never_selected() -> None:
    catalog = {
        **CATALOG,
        "models": [
            {"id": F_BASE, "free": True, "capabilities": [], "variants": ["high"]},
            {"id": A_BASE, "free": False, "capabilities": [], "variants": ["high"]},
        ],
    }
    decision = provider_plan.plan(_request(discovery=[F_BASE, A_BASE]), catalog)
    assert decision["candidate"] == A
    assert any(item["reason"] == "free_model_forbidden" for item in decision["excluded"])


def test_obvious_free_marker_is_rejected_without_metadata() -> None:
    catalog = {
        **CATALOG,
        "models": [
            {"id": F_BASE, "free": False, "capabilities": [], "variants": ["high"]},
            {"id": A_BASE, "free": False, "capabilities": [], "variants": ["high"]},
        ],
    }
    decision = provider_plan.plan(_request(discovery=[F_BASE, A_BASE]), catalog)
    assert decision["candidate"] == A
    assert F not in [item["candidate"] for item in decision["classification"]]


def test_catalog_cannot_enable_free_models() -> None:
    with pytest.raises(ValueError):
        provider_plan.plan(_request(), {**CATALOG, "allow_free_models": True})


def test_free_metadata_is_optional_and_false_is_allowed() -> None:
    omitted = {"id": A_BASE, "capabilities": [], "variants": ["high"]}
    catalog = {**CATALOG, "models": [omitted]}
    decision = provider_plan.plan(_request(discovery=[A_BASE]), catalog)
    assert decision["action"] == "launch"
    assert decision["candidate"] == A

    explicit_false = {"id": A_BASE, "free": False, "capabilities": [], "variants": ["high"]}
    decision = provider_plan.plan(_request(discovery=[A_BASE]), {**CATALOG, "models": [explicit_false]})
    assert decision["action"] == "launch"
    assert decision["candidate"] == A


@pytest.mark.parametrize("value", [1, 0, "true", "false", None, [], {}])
def test_non_boolean_free_metadata_is_rejected_without_echoing_it(value: object) -> None:
    catalog = {
        **CATALOG,
        "models": [{"id": A_BASE, "free": value, "capabilities": [], "variants": ["high"]}],
    }
    with pytest.raises(ValueError) as raised:
        provider_plan.plan(_request(discovery=[A_BASE]), catalog)
    message = str(raised.value)
    assert "boolean" in message
    assert str(value) not in message
    assert A_BASE not in message


def test_free_only_catalog_stops() -> None:
    catalog = {
        **CATALOG,
        "models": [{"id": F_BASE, "free": True, "capabilities": [], "variants": ["high"]}],
    }
    decision = provider_plan.plan(_request(discovery=[F_BASE]), catalog)
    assert decision["action"] == "stop"
    assert decision["reason"] == "free_models_forbidden"


def test_unlisted_discovery_ids_are_ignored() -> None:
    decision = provider_plan.plan(_request(discovery=["example-cloud/unknown:free", A_BASE]), CATALOG)
    assert decision["candidate"] == A
    assert any(item["reason"] == "unlisted_model" for item in decision["excluded"])


def test_unknown_task_allowlist_is_rejected() -> None:
    with pytest.raises(ValueError):
        provider_plan.plan(_request(requested_order=["example-cloud/unknown"]), CATALOG)


def test_task_allowlist_cannot_unlock_a_free_model() -> None:
    catalog = {
        **CATALOG,
        "models": [{"id": F_BASE, "free": True, "capabilities": [], "variants": ["high"]}],
    }
    with pytest.raises(ValueError):
        provider_plan.plan(_request(requested_order=[F], discovery=[F_BASE]), catalog)


def test_task_allowlist_rejects_unsupported_variant() -> None:
    with pytest.raises(ValueError):
        provider_plan.plan(_request(requested_order=[f"{A_BASE}#max"]), CATALOG)


def test_task_override_only_narrows_the_allowlist() -> None:
    decision = provider_plan.plan(_request(requested_order=[A_BASE, B_BASE], override=B), CATALOG)
    assert decision["action"] == "launch"
    assert decision["candidate"] == B

    with pytest.raises(ValueError):
        provider_plan.plan(_request(requested_order=[A_BASE], override=B), CATALOG)


def test_variant_override_is_not_silently_substituted() -> None:
    decision = provider_plan.plan(_request(variant="max"), CATALOG)
    assert decision["action"] == "stop"
    assert decision["reason"] == "variant_unsupported"


def test_missing_required_capability_stops_without_substitution() -> None:
    # C (the only 1017 model) exists in the catalog but is not discovered.
    decision = provider_plan.plan(_request(discovery=[A_BASE, B_BASE], required_capabilities=["1017"]), CATALOG)
    assert decision["action"] == "stop"
    assert decision["reason"] == "required_capability_missing"
    assert decision["candidate"] is None
    assert any(item["reason"] == "capability_missing" for item in decision["excluded"])


def test_required_capability_selects_the_capable_model() -> None:
    decision = provider_plan.plan(
        _request(discovery=[A_BASE, B_BASE, C_BASE], required_capabilities=["1017"]), CATALOG
    )
    assert decision["action"] == "launch"
    assert decision["candidate"] == C


def test_missing_discovery_stops_without_guessing() -> None:
    for request in (_request(discovery=[]), {"attempts": []}):
        decision = provider_plan.plan(request, CATALOG)
        assert decision["action"] == "stop"
        assert decision["reason"] == "no_discovered_candidate"


# ---- provider policy ------------------------------------------------------


def test_provider_exhaustion_skips_all_models_on_that_provider() -> None:
    catalog = _multi_model_catalog()
    decision = provider_plan.plan(
        _request(
            discovery=[A_BASE, A2_BASE, B_BASE, C_BASE],
            exhausted_providers=["example-cloud"],
        ),
        catalog,
    )
    assert decision["action"] == "launch"
    assert decision["candidate"] == B
    excluded = {item["candidate"]: item["reason"] for item in decision["excluded"]}
    assert excluded[A_BASE] == "provider_quota_exhausted"
    assert excluded[A2_BASE] == "provider_quota_exhausted"


def test_provider_scoped_quota_attempt_skips_the_whole_provider() -> None:
    catalog = _multi_model_catalog()
    decision = provider_plan.plan(
        _request(
            discovery=[A_BASE, A2_BASE, B_BASE, C_BASE],
            attempts=[_attempt(A, "quota_exhausted", scope="provider")],
        ),
        catalog,
    )
    assert decision["candidate"] == B


def test_go_credit_exhaustion_moves_to_router() -> None:
    catalog = _multi_model_catalog()
    decision = provider_plan.plan(
        _request(
            discovery=[A_BASE, A2_BASE, B_BASE, C_BASE],
            attempts=[
                _attempt(A, "quota_exhausted", scope="provider"),
                _attempt(B, "quota_exhausted", scope="provider"),
            ],
        ),
        catalog,
    )
    assert decision["candidate"] == C


def test_candidate_scoped_quota_keeps_other_models_on_provider() -> None:
    catalog = _multi_model_catalog()
    decision = provider_plan.plan(
        _request(
            discovery=[A_BASE, A2_BASE, B_BASE],
            attempts=[_attempt(A, "quota_exhausted")],
        ),
        catalog,
    )
    assert decision["candidate"] == A2


def test_unavailable_model_is_candidate_specific() -> None:
    catalog = _multi_model_catalog()
    decision = provider_plan.plan(
        _request(
            discovery=[A_BASE, A2_BASE, B_BASE],
            attempts=[_attempt(A, "unavailable_model")],
        ),
        catalog,
    )
    assert decision["candidate"] == A2


def test_unknown_exhausted_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        provider_plan.plan(_request(exhausted_providers=["unknown-provider"]), CATALOG)


def test_catalog_provider_order_wins_over_model_list_order() -> None:
    catalog = {
        **CATALOG,
        "provider_order": ["example-go", "example-cloud", "example-openrouter"],
    }
    decision = provider_plan.plan(_request(), catalog)
    assert decision["action"] == "launch"
    assert decision["candidate"] == B


def test_quota_exhaustion_moves_to_next_allowed_candidate() -> None:
    decision = provider_plan.plan(_request(attempts=[_attempt(A, "quota_exhausted")]), CATALOG)
    assert decision["action"] == "launch"
    assert decision["candidate"] == B
    assert decision["classification"][0]["latest_outcome"] == "quota_exhausted"


def test_transient_error_allows_one_bounded_retry() -> None:
    decision = provider_plan.plan(
        _request(
            attempts=[_attempt(A, "transient")],
            retry_after_seconds=2,
            remaining_seconds=30,
        ),
        CATALOG,
    )
    assert decision["action"] == "retry"
    assert decision["candidate"] == A
    assert decision["reason"] == "bounded_transient_retry"


def test_retry_after_beyond_deadline_moves_on_without_retry() -> None:
    decision = provider_plan.plan(
        _request(
            attempts=[_attempt(A, "transient")],
            retry_after_seconds=120,
            remaining_seconds=10,
        ),
        CATALOG,
    )
    assert decision["action"] == "launch"
    assert decision["candidate"] == B


def test_transient_retry_limit_is_bounded() -> None:
    decision = provider_plan.plan(
        _request(attempts=[_attempt(A, "transient"), _attempt(A, "transient")]),
        CATALOG,
    )
    assert decision["action"] == "launch"
    assert decision["candidate"] == B


def test_max_attempts_cap_can_forbid_even_transient_retry() -> None:
    decision = provider_plan.plan(
        _request(attempts=[_attempt(A, "transient")], max_attempts_per_candidate=1),
        CATALOG,
    )
    assert decision["action"] == "launch"
    assert decision["candidate"] == B


def test_auth_error_stops_instead_of_silent_provider_switch() -> None:
    decision = provider_plan.plan(_request(attempts=[_attempt(A, "auth_error")]), CATALOG)
    assert decision["action"] == "stop"
    assert decision["reason"] == "auth_error_requires_repair"
    assert decision["candidate"] == A


def test_unavailable_model_uses_next_allowed_candidate() -> None:
    decision = provider_plan.plan(_request(attempts=[_attempt(A, "unavailable_model")]), CATALOG)
    assert decision["action"] == "launch"
    assert decision["candidate"] == B


def test_code_failure_keeps_same_model() -> None:
    decision = provider_plan.plan(_request(attempts=[_attempt(A, "code_failure")]), CATALOG)
    assert decision["action"] == "fix_same_model"
    assert decision["candidate"] == A
    assert decision["candidate"] != B


def test_live_job_blocks_fallback_until_reconciled() -> None:
    decision = provider_plan.plan(
        _request(attempts=[_attempt(A, "quota_exhausted")], live_job_possible=True), CATALOG
    )
    assert decision["action"] == "reconcile"
    assert decision["reason"] == "live_job_may_still_run"


def test_success_is_terminal() -> None:
    decision = provider_plan.plan(_request(attempts=[_attempt(A, "success")]), CATALOG)
    assert decision["action"] == "done"
    assert decision["candidate"] == A


def test_unknown_outcome_requires_inspection() -> None:
    decision = provider_plan.plan(_request(attempts=[_attempt(A, "unknown")]), CATALOG)
    assert decision["action"] == "inspect"
    assert decision["candidate"] == A


def test_all_candidates_exhausted_stops() -> None:
    decision = provider_plan.plan(
        _request(
            attempts=[
                _attempt(A, "quota_exhausted"),
                _attempt(B, "quota_exhausted"),
                _attempt(C, "quota_exhausted"),
            ]
        ),
        CATALOG,
    )
    assert decision["action"] == "stop"
    assert decision["reason"] == "no_authorized_candidate_remains"
    assert decision["candidate"] is None


def test_exact_candidate_id_is_preserved_without_family_substitution() -> None:
    decision = provider_plan.plan(
        _request(requested_order=[A_BASE], discovery=[A_BASE], attempts=[_attempt(A, "transient")]),
        CATALOG,
    )
    assert decision["candidate"] == A
    assert decision["candidate"].endswith("#high")


@pytest.mark.parametrize(
    "bad_request",
    [
        {"discovery": DISCOVERY, "requested_order": []},
        {"discovery": DISCOVERY, "requested_order": ["no-provider-slash"]},
        {"discovery": DISCOVERY, "attempts": [{"candidate": A, "outcome": "made_up"}]},
        {"discovery": DISCOVERY, "requested_order": [A_BASE, A_BASE]},
        {"discovery": DISCOVERY, "attempts": "not-a-list"},
        {"discovery": "not-a-list"},
        {"discovery": DISCOVERY, "attempts": [{"candidate": A, "outcome": "quota_exhausted", "scope": "global"}]},
    ],
)
def test_invalid_requests_are_rejected(bad_request: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        provider_plan.plan(bad_request, CATALOG)


# ---- cleanup gate ---------------------------------------------------------


def _cleanup(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "owned": True,
        "frontend": "exited",
        "jobs": "exited",
        "completion_evidence": True,
    }
    base.update(overrides)
    return base


def test_not_owned_tab_is_never_closed() -> None:
    assert cleanup_gate.gate(_cleanup(owned=False))["action"] == "refuse_not_owned"


@pytest.mark.parametrize("key", ["frontend", "jobs"])
def test_unknown_state_requires_inspection(key: str) -> None:
    assert cleanup_gate.gate(_cleanup(**{key: "unknown"}))["action"] == "inspect"


def test_running_work_waits() -> None:
    assert cleanup_gate.gate(_cleanup(frontend="running"))["action"] == "wait"
    assert cleanup_gate.gate(_cleanup(jobs="running"))["action"] == "wait"


def test_exited_work_without_evidence_collects_first() -> None:
    decision = cleanup_gate.gate(_cleanup(completion_evidence=False))
    assert decision["action"] == "collect_evidence"


def test_owned_exited_work_with_evidence_may_close() -> None:
    decision = cleanup_gate.gate(_cleanup())
    assert decision["action"] == "close"
    assert decision["blockers"] == []


@pytest.mark.parametrize("key", ["frontend", "jobs"])
def test_invalid_state_is_rejected(key: str) -> None:
    with pytest.raises(ValueError):
        cleanup_gate.gate(_cleanup(**{key: "vanished"}))


# ---- CLI behavior ---------------------------------------------------------


def _run(
    script: Path,
    payload: object,
    cwd: Path,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *extra],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_cli_prints_one_json_decision(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(CATALOG), encoding="utf-8")
    result = _run(
        PROVIDER,
        _request(attempts=[_attempt(A, "quota_exhausted")]),
        tmp_path,
        "--catalog",
        str(catalog_path),
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["action"] == "launch"
    assert decision["candidate"] == B


def test_cli_rejects_invalid_input_without_echoing_it(tmp_path: Path) -> None:
    payload = {"requested_order": [], "api_key": CANARY}
    result = _run(PROVIDER, payload, tmp_path)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr
    assert CANARY not in result.stderr


def test_cli_does_not_print_unknown_fields_or_secrets(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(CATALOG), encoding="utf-8")
    payload = _request(attempts=[_attempt(A, "quota_exhausted")], api_key=CANARY)
    result = _run(PROVIDER, payload, tmp_path, "--catalog", str(catalog_path))
    assert result.returncode == 0, result.stderr
    assert CANARY not in result.stdout
    assert "api_key" not in result.stdout


def test_cli_uses_bundled_catalog_with_realistic_discovery(tmp_path: Path) -> None:
    result = _run(PROVIDER, {"discovery": _fixture_ids(), "attempts": []}, tmp_path)
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["action"] == "launch"
    assert decision["candidate"] == "ollama-cloud/deepseek-v4.1-flash:1017#high"


def test_cli_accepts_an_edited_catalog(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(CATALOG), encoding="utf-8")
    result = _run(
        PROVIDER,
        _request(attempts=[_attempt(A, "quota_exhausted")]),
        tmp_path,
        "--catalog",
        str(catalog_path),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["candidate"] == B


def test_cli_writes_no_files(tmp_path: Path) -> None:
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    result = _run(CLEANUP, _cleanup(), tmp_path)
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert result.returncode == 0, result.stderr
    assert before == after == []


def test_cli_reports_missing_input_file(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(CLEANUP), "--input", str(tmp_path / "absent.json")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr
