#!/usr/bin/env python3
"""Pure OpenCode provider planner driven by an editable model catalog.

Reads a catalog plus one JSON request and prints one JSON decision. It performs
no network or filesystem writes, reads no environment variables and never
changes auth, privacy settings or global defaults. Invalid input exits 2
without echoing the input.

Catalog keys (see ../assets/model_catalog.json):
  provider_order        ordered provider IDs
  default_variant       reasoning variant appended as #variant (e.g. "high")
  prefer_capabilities   capability tags preferred within a provider (e.g. 1017)
  models                list of {id, free, capabilities, variants}

Free models are forbidden. A catalog that sets `allow_free_models` to anything
other than false is rejected, and free entries are always excluded.

Catalog `id` values are registry base IDs as printed by `opencode models`.
The invocation ID is `ID#VARIANT`; discovery is normalized by stripping any
`#variant` suffix so a base-registry listing is not falsely rejected.

Request keys:
  discovery                 exact registry IDs from the installed model listing
  variant                   optional task/session variant override
  requested_order           optional task allowlist; must narrow the catalog
  override                  optional single candidate inside that allowlist
  required_capabilities     capability tags that candidates must have
  exhausted_providers       provider IDs with account-wide quota exhaustion
  attempts                  list of {"candidate": INVOCATION_ID, "outcome": ...,
                            "scope": "candidate"|"provider"}
  live_job_possible         true when owned work may still be running
  max_attempts_per_candidate hard cap including the initial attempt (default 2)
  transient_retry_limit     transient retries within that cap (default 1)
  retry_after_seconds       Retry-After attached to the latest transient error
  remaining_seconds         remaining deadline; retry requires it to fit
  provider_transient_limit  provider-scoped transport failures before skipping
                            all its models (default 2); never means quota used

Outcomes: success, quota_exhausted, transient, auth_error, unavailable_model,
code_failure, unknown. Discovery and catalog inventory prove only that an ID is
listed; they do not prove quota, credentials or a privacy/retention guarantee.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "assets" / "model_catalog.json"
OUTCOMES = {
    "success",
    "quota_exhausted",
    "transient",
    "auth_error",
    "unavailable_model",
    "code_failure",
    "unknown",
}
FREE_MARKERS = (":free", "-free", "/free")


def _fail(message: str) -> None:
    raise ValueError(message)


def _model_id(value: Any) -> str:
    if not isinstance(value, str) or not value:
        _fail("model ID must be a non-empty string")
    if any(char.isspace() for char in value):
        _fail("model ID must not contain whitespace")
    if "/" not in value or len(value) > 200:
        _fail("model ID must be PROVIDER/MODEL with an optional #VARIANT")
    return value


def _split_invocation(value: Any) -> tuple[str, str | None]:
    model = _model_id(value)
    if "#" in model:
        base, variant = model.split("#", 1)
        if not base or not variant or "#" in variant:
            _fail("invalid #variant suffix")
        return base, variant
    return model, None


def _free_marker(candidate: str) -> bool:
    lowered = candidate.lower()
    return any(marker in lowered for marker in FREE_MARKERS)


def _number(value: Any, name: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{name} must be a number")
    if not math.isfinite(value) or value < 0:
        _fail(f"{name} must be finite and non-negative")
    return float(value)


def _count(value: Any, name: str, default: int) -> int:
    number = _number(value, name, float(default))
    if number != int(number):
        _fail(f"{name} must be an integer")
    return int(number)


def _string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        _fail(f"{name} must be a list of non-empty strings")
    return list(value)


_MISSING = object()


def _free_metadata(item: dict[str, Any]) -> bool:
    """Optional `free` metadata: absent stays compatible, present must be boolean."""
    value = item.get("free", _MISSING)
    if value is _MISSING:
        return False
    if not isinstance(value, bool):
        _fail("catalog model free must be a boolean")
    return value


def _catalog(catalog: Any) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    if not isinstance(catalog, dict):
        _fail("catalog must be a JSON object")
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        _fail("catalog models must be a non-empty list")
    free_flag = catalog.get("allow_free_models", False)
    if free_flag is not False:
        _fail("free models are forbidden; allow_free_models must be false")
    default_variant = catalog.get("default_variant")
    if default_variant is not None:
        if not isinstance(default_variant, str) or not default_variant or "#" in default_variant:
            _fail("default_variant must be a non-empty string without #")
    prefer = catalog.get("prefer_capabilities", [])
    prefer_capabilities = _string_list(prefer if prefer is not None else [], "prefer_capabilities")
    provider_order = _string_list(catalog.get("provider_order", []), "provider_order")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(models):
        if not isinstance(item, dict):
            _fail("each catalog model must be an object")
        model_id = _model_id(item.get("id"))
        if "#" in model_id:
            _fail("catalog ids must be registry base IDs without #variant")
        if model_id in seen:
            _fail("catalog contains duplicate model IDs")
        seen.add(model_id)
        capabilities = item.get("capabilities", [])
        if capabilities is None:
            capabilities = []
        entry_capabilities = _string_list(capabilities, "capabilities")
        entry_variants = _string_list(item.get("variants"), "variants")
        if any("#" in variant for variant in entry_variants):
            _fail("variants must not contain #")
        entries.append(
            {
                "id": model_id,
                "provider": model_id.split("/", 1)[0],
                "free": _free_metadata(item) or _free_marker(model_id),
                "capabilities": entry_capabilities,
                "variants": entry_variants,
                "index": index,
            }
        )

    rank = {provider: position for position, provider in enumerate(provider_order)}

    def sort_key(entry: dict[str, Any]) -> tuple[int, int, int]:
        preferred = sum(1 for capability in prefer_capabilities if capability in entry["capabilities"])
        return (rank.get(entry["provider"], len(rank)), -preferred, entry["index"])

    entries.sort(key=sort_key)
    return entries, default_variant, prefer_capabilities


def _attempts(request: dict[str, Any]) -> list[dict[str, str]]:
    raw = request.get("attempts", [])
    if not isinstance(raw, list):
        _fail("attempts must be a list")
    attempts: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            _fail("each attempt must be an object")
        candidate = _model_id(item.get("candidate"))
        outcome = item.get("outcome")
        if outcome not in OUTCOMES:
            _fail("attempt outcome is not a supported class")
        scope = item.get("scope", "candidate")
        if scope not in {"candidate", "provider"}:
            _fail("attempt scope must be candidate or provider")
        attempts.append({"candidate": candidate, "outcome": str(outcome), "scope": str(scope)})
    return attempts


def _choose_variant(entry: dict[str, Any], requested: str | None, default: str | None) -> str | None:
    variant = requested or default or (entry["variants"][0] if entry["variants"] else None)
    if variant is None:
        return None
    if variant not in entry["variants"]:
        return None
    return variant


def plan(request: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic decision from the catalog, request and attempts."""
    if not isinstance(request, dict):
        _fail("request must be a JSON object")

    entries, default_variant, prefer_capabilities = _catalog(catalog)
    attempts = _attempts(request)
    excluded: list[dict[str, str]] = []

    requested_variant = request.get("variant")
    if requested_variant is not None:
        if not isinstance(requested_variant, str) or not requested_variant or "#" in requested_variant:
            _fail("variant must be a non-empty string without #")

    # Task allowlist may only narrow the catalog; it cannot add or unlock IDs.
    task_allow = request.get("requested_order")
    catalog_by_id = {entry["id"]: entry for entry in entries}
    task_variants: dict[str, str | None] = {}
    if task_allow is None:
        candidates = list(entries)
    else:
        if not isinstance(task_allow, list) or not task_allow:
            _fail("requested_order must be a non-empty list")
        for item in task_allow:
            base, variant = _split_invocation(item)
            if base not in catalog_by_id:
                _fail("requested_order contains an unlisted or unknown model")
            if _free_marker(base):
                _fail("requested_order contains a forbidden free model")
            if base in task_variants:
                _fail("requested_order contains duplicate or conflicting model IDs")
            task_variants[base] = variant
            entry = catalog_by_id[base]
            if variant is not None and variant not in entry["variants"]:
                _fail("requested_order contains an unsupported variant")
        candidates = [entry for entry in entries if entry["id"] in task_variants]
        requested_ids = set(task_variants)
        excluded.extend(
            {"candidate": entry["id"], "reason": "not_in_task_allowlist"}
            for entry in entries
            if entry["id"] not in requested_ids
        )

    # Free models are forbidden, regardless of catalog settings.
    after_free = []
    for entry in candidates:
        if entry["free"]:
            excluded.append({"candidate": entry["id"], "reason": "free_model_forbidden"})
        else:
            after_free.append(entry)
    candidates = after_free

    # Resolve the exact invocation variant for each candidate.
    variants: dict[str, str | None] = {}
    supported = []
    for entry in candidates:
        if entry["id"] in task_variants and task_variants[entry["id"]] is not None:
            requested = task_variants[entry["id"]]
        else:
            requested = requested_variant
        variant = _choose_variant(entry, requested, default_variant)
        if variant is None:
            excluded.append({"candidate": entry["id"], "reason": "variant_unsupported"})
        else:
            variants[entry["id"]] = variant
            supported.append(entry)
    candidates = supported

    # Explicit task requirements must be present on the candidate itself.
    required = request.get("required_capabilities")
    required_caps = _string_list(required if required is not None else [], "required_capabilities")
    if required_caps:
        capable = []
        for entry in candidates:
            if all(cap in entry["capabilities"] for cap in required_caps):
                capable.append(entry)
            else:
                excluded.append({"candidate": entry["id"], "reason": "capability_missing"})
        candidates = capable

    # Account-wide quota exhaustion removes every model on that provider.
    exhausted = request.get("exhausted_providers", [])
    exhausted_providers = set(_string_list(exhausted if exhausted is not None else [], "exhausted_providers"))
    unknown_providers = exhausted_providers - {entry["provider"] for entry in entries}
    if unknown_providers:
        _fail("exhausted_providers contains an unknown provider")
    for attempt in attempts:
        if attempt["outcome"] == "quota_exhausted" and attempt["scope"] == "provider":
            exhausted_providers.add(attempt["candidate"].split("/", 1)[0])
    if exhausted_providers:
        remaining = []
        for entry in candidates:
            if entry["provider"] in exhausted_providers:
                excluded.append({"candidate": entry["id"], "reason": "provider_quota_exhausted"})
            else:
                remaining.append(entry)
        candidates = remaining

    # Discovery comes from the installed listing; it is availability input only.
    discovery = request.get("discovery", [])
    if not isinstance(discovery, list):
        _fail("discovery must be a list of exact model IDs")
    discovered = {_split_invocation(item)[0] for item in discovery}
    catalog_ids = {entry["id"] for entry in entries}
    excluded.extend(
        {"candidate": item, "reason": "unlisted_model"}
        for item in sorted(discovered - catalog_ids)
    )

    available = []
    for entry in candidates:
        if entry["id"] in discovered:
            available.append(entry)
        else:
            excluded.append({"candidate": entry["id"], "reason": "not_in_discovery"})

    override = request.get("override")
    if override is not None:
        override_base, override_variant = _split_invocation(override)
        matching = [entry for entry in available if entry["id"] == override_base]
        if not matching:
            _fail("override must narrow the currently allowed and discovered candidates")
        if override_variant is not None and override_variant not in matching[0]["variants"]:
            _fail("override uses an unsupported variant")
        variants[override_base] = override_variant or variants[override_base]
        available = matching

    max_attempts = _count(request.get("max_attempts_per_candidate"), "max_attempts_per_candidate", 2)
    if max_attempts < 1:
        _fail("max_attempts_per_candidate must be at least 1")
    transient_retry_limit = _count(request.get("transient_retry_limit"), "transient_retry_limit", 1)
    retry_after = _number(request.get("retry_after_seconds"), "retry_after_seconds", 0)
    remaining = _number(request.get("remaining_seconds"), "remaining_seconds", math.inf)

    invocations = {
        entry["id"]: f"{entry['id']}#{variants[entry['id']]}" if variants[entry["id"]] else entry["id"]
        for entry in available
    }

    notes: list[str] = []
    classification: list[dict[str, Any]] = []
    for entry in available:
        invocation = invocations[entry["id"]]
        history = [item["outcome"] for item in attempts if item["candidate"] == invocation]
        classification.append(
            {
                "candidate": invocation,
                "variant": variants[entry["id"]],
                "attempts": len(history),
                "latest_outcome": history[-1] if history else None,
            }
        )

    def result(action: str, reason: str, candidate: str | None = None) -> dict[str, Any]:
        return {
            "action": action,
            "candidate": candidate,
            "reason": reason,
            "policy": {
                "free_models_forbidden": True,
                "required_capabilities": required_caps,
                "prefer_capabilities": prefer_capabilities,
                "variant": requested_variant or default_variant,
            },
            "classification": classification,
            "excluded": excluded,
            "notes": list(notes),
        }

    if request.get("live_job_possible") is True:
        notes.append("owned work may still be running; fallback is blocked until reconciled")
        return result("reconcile", "live_job_may_still_run")

    provider_limit = _count(request.get("provider_transient_limit"), "provider_transient_limit", 2)
    if provider_limit < 1:
        _fail("provider_transient_limit must be at least 1")
    provider_failures: dict[str, int] = {}
    for attempt in attempts:
        if attempt["scope"] == "provider" and attempt["outcome"] == "transient":
            provider = attempt["candidate"].split("/", 1)[0]
            provider_failures[provider] = provider_failures.get(provider, 0) + 1

    if not available:
        if required_caps and any(item["reason"] == "capability_missing" for item in excluded):
            return result("stop", "required_capability_missing")
        if any(item["reason"] == "variant_unsupported" for item in excluded):
            return result("stop", "variant_unsupported")
        if any(item["reason"] == "provider_quota_exhausted" for item in excluded):
            return result("stop", "provider_quota_exhausted")
        if any(item["reason"] == "not_in_discovery" for item in excluded):
            return result("stop", "no_discovered_candidate")
        if any(item["reason"] == "free_model_forbidden" for item in excluded):
            return result("stop", "free_models_forbidden")
        return result("stop", "no_authorized_candidate")

    for entry in available:
        invocation = invocations[entry["id"]]
        history = [item["outcome"] for item in attempts if item["candidate"] == invocation]
        if history and history[-1] == "success":
            return result("done", "latest_attempt_succeeded", invocation)
        if (provider_failures.get(entry["provider"], 0) >= provider_limit
                and (not history or history[-1] not in {"auth_error", "code_failure", "unknown"})):
            excluded.append({"candidate": entry["id"], "reason": "provider_transport_budget_exhausted"})
            continue
        if not history:
            return result("launch", "not_attempted", invocation)

        latest = history[-1]
        if latest == "success":
            return result("done", "latest_attempt_succeeded", invocation)
        if latest == "quota_exhausted":
            notes.append(f"{invocation}: quota exhausted; no same-candidate retry")
            continue
        if latest == "auth_error":
            notes.append(f"{invocation}: authentication must be repaired, not retried")
            return result("stop", "auth_error_requires_repair", invocation)
        if latest == "unavailable_model":
            notes.append(f"{invocation}: model/version/variant unavailable; trying next allowed candidate")
            continue
        if latest == "code_failure":
            notes.append(f"{invocation}: code/test failure is not a provider failure")
            return result("fix_same_model", "code_failure_same_model", invocation)
        if latest == "transient":
            retries_used = len(history) - 1
            within_cap = len(history) < max_attempts
            if within_cap and retries_used < transient_retry_limit and retry_after <= remaining:
                return result("retry", "bounded_transient_retry", invocation)
            notes.append(f"{invocation}: transient retries exhausted or Retry-After exceeds deadline")
            continue
        if latest == "unknown":
            return result("inspect", "attempt_outcome_unknown", invocation)

        _fail("unreachable attempt outcome")

    return result("stop", "no_authorized_candidate_remains")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a pure provider decision as JSON.")
    parser.add_argument("--input", "-i", default="-", help="request JSON path, or - for stdin (default)")
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG),
        help="editable model catalog JSON (default: bundled assets/model_catalog.json)",
    )
    args = parser.parse_args(argv)

    try:
        request_text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        catalog_text = Path(args.catalog).read_text(encoding="utf-8")
        decision = plan(json.loads(request_text), json.loads(catalog_text))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        message = str(error) or error.__class__.__name__
        print(f"error: {message}", file=sys.stderr)
        return 2

    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
