"""Read-only file/hash/count audit. Mathematical and dataflow review remain separate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re


def json_pointer(value, pointer):
    """Resolve a nonempty JSON Pointer; reject invalid escapes/array indices."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("pointer must be a nonempty JSON Pointer")
    for token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", token):
            raise ValueError("invalid JSON Pointer escape")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token):
                raise ValueError("array pointer requires a nonnegative canonical index")
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise ValueError("pointer traverses a scalar")
    return value


def audit(manifest, root):
    errors, warnings, checked = [], [], []
    contract_checks = []
    root = Path(root).resolve()
    def evidence(item, label):
        try:
            p = (root / item["path"]).resolve()
            if not p.is_relative_to(root): raise ValueError("evidence path escapes project root")
            data = p.read_bytes()
            h = hashlib.sha256(data).hexdigest()
            if item.get("sha256") and item["sha256"] != h: errors.append(f"{label}: SHA256 mismatch: {item['path']}")
            checked.append({"path":str(p.relative_to(root)),"sha256":h,"bytes":len(data)})
            return data
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{label}: {exc}")
            return None
    if manifest.get("version") != 1: errors.append("manifest version must be 1")
    if not manifest.get("claims"): errors.append("at least one explicit claim is required")

    def pinned_json(item, label):
        if not isinstance(item, dict):
            errors.append(f"{label}: pinned JSON reference must be an object")
            return None
        digest = item.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"{label}: a concrete lowercase SHA256 is required")
        raw = evidence(item, label)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            errors.append(f"{label}: invalid JSON: {exc}")
            return None

    def metric_contract(rate, label):
        ref = rate.get("metric_contract")
        if ref is None:
            warnings.append(f"{label}: no metric contract; pointer meaning, predicate and population require manual review")
            return
        source = pinned_json(ref, f"{label}/metric_contract")
        if source is None:
            return
        try:
            contract = json_pointer(source, ref["pointer"])
            if not isinstance(contract, dict):
                raise ValueError("metric contract must be an object")
            if contract.get("metric_id") != rate.get("id"):
                errors.append(f"{label}: metric id does not match contract")
            for field in ("predicate", "failure_policy", "denominator_population"):
                if not isinstance(contract.get(field), str) or not contract[field].strip():
                    errors.append(f"{label}: missing contract {field}")
            aggregation = contract.get("aggregation", {})
            if not isinstance(aggregation, dict):
                raise ValueError("contract aggregation must be an object")
            for field in ("operator", "unit", "independent_unit"):
                if not isinstance(aggregation.get(field), str) or not aggregation[field].strip():
                    errors.append(f"{label}: missing aggregation {field}")
            binding, expected = rate.get("source_binding"), contract.get("count_source")
            if not isinstance(binding, dict) or not isinstance(expected, dict):
                raise ValueError("metric contract requires source_binding and count_source objects")
            if not isinstance(binding.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", binding["sha256"]):
                errors.append(f"{label}: contracted source_binding needs a concrete lowercase SHA256")
            for field in ("path", "numerator_pointer", "denominator_pointer"):
                if not isinstance(expected.get(field), str) or not expected[field]:
                    errors.append(f"{label}: missing count_source {field}")
                elif binding.get(field) != expected[field]:
                    errors.append(f"{label}: {field} disagrees with metric contract")
            thresholds = contract.get("thresholds")
            if not isinstance(thresholds, list):
                raise ValueError("contract thresholds must be an explicit list (possibly empty)")
            threshold_names = set()
            for threshold in thresholds:
                if not isinstance(threshold, dict):
                    raise ValueError("threshold must be an object")
                name = threshold.get("name")
                if not isinstance(name, str) or not name.strip() or name in threshold_names:
                    errors.append(f"{label}: missing/duplicate threshold name")
                threshold_names.add(str(name))
                if not isinstance(threshold.get("unit"), str) or not threshold["unit"].strip():
                    errors.append(f"{label}: threshold {name} needs an explicit unit")
                doc = pinned_json(threshold, f"{label}/threshold/{name}")
                if doc is not None:
                    actual = json_pointer(doc, threshold["pointer"])
                    # JSON equality preserves distinctions such as true versus 1.
                    if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(threshold["value"], sort_keys=True, allow_nan=False):
                        errors.append(f"{label}: threshold {name} value differs from pinned source")
            contract_checks.append({"rate": label, "metric_id": rate.get("id"),
                                    "contract_path": ref["path"], "contract_pointer": ref["pointer"]})
            warnings.append(f"{label}: metric contract checks declared bindings only; manually verify predicate implementation, units, population and registration chronology")
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            errors.append(f"{label}: invalid metric contract: {exc}")
    def rates(items, label):
        names = set()
        for rate in items:
            name = rate.get("id")
            n, d = rate.get("numerator"), rate.get("denominator")
            if not name or name in names: errors.append(f"{label}: missing/duplicate rate id {name}")
            names.add(name)
            if any(not isinstance(x,int) or isinstance(x,bool) or x<0 for x in [n,d]):
                errors.append(f"{label}/{name}: invalid rate counts")
            elif n>d: errors.append(f"{label}/{name}: numerator exceeds denominator")
            elif d==0: warnings.append(f"{label}/{name}: zero denominator; untested rate")
            binding = rate.get("source_binding")
            if binding is not None:
                raw = evidence(binding, f"{label}/{name}")
                if raw is not None:
                    try:
                        source = json.loads(raw)
                        for field in ("numerator", "denominator"):
                            value = json_pointer(source, binding[field + "_pointer"])
                            if isinstance(value, bool) or not isinstance(value, int):
                                raise ValueError(f"{field} source is not an integer count")
                            if rate[field] != value:
                                errors.append(f"{label}/{name}: {field} {rate[field]} != source {value}")
                    except (ValueError, KeyError, TypeError, IndexError) as exc:
                        errors.append(f"{label}/{name}: invalid source binding: {exc}")
            else:
                warnings.append(f"{label}/{name}: rate counts not bound to source fields; inspect manually")
            metric_contract(rate, f"{label}/{name}")
    seen = set()
    for claim in manifest.get("claims", []):
        cid = claim.get("id", "<missing>")
        if cid in seen or cid == "<missing>": errors.append(f"claim: missing/duplicate id {cid}")
        seen.add(cid)
        kind = claim.get("kind")
        if kind not in {"proof","numerical","source","unverified"}: errors.append(f"{cid}: invalid kind")
        if not claim.get("statement"): errors.append(f"{cid}: missing statement")
        if not isinstance(claim.get("assumptions"),list): errors.append(f"{cid}: assumptions must be explicit list")
        ev = claim.get("evidence", [])
        if kind != "unverified" and not ev: errors.append(f"{cid}: supported claim has no evidence")
        if kind in {"proof","source"} and not any(x.get("role")==kind for x in ev): errors.append(f"{cid}: missing {kind} evidence role")
        for item in ev: evidence(item,cid)
        rates(claim.get("rates",[]),cid)
        if kind == "proof": warnings.append(f"{cid}: independently review mathematical correctness")
    runs = manifest.get("runs", [])
    run_ids = [run.get("id", "<missing>") for run in runs]
    if not runs:
        warnings.append("claims-only manifest: run records, population coverage and estimation dataflow are not audited")
    valid_run_ids = all(isinstance(value, str) and value and value != "<missing>" for value in run_ids)
    if not valid_run_ids or len(set(run_ids)) != len(run_ids):
        errors.append("run: missing/duplicate run id")
    coverage = manifest.get("coverage")
    coverage_checked = False
    if coverage is None:
        warnings.append("run coverage unchecked: provide coverage.expected_run_ids and independently verify that roster")
    elif not isinstance(coverage, dict) or not isinstance(coverage.get("expected_run_ids"), list):
        errors.append("coverage.expected_run_ids must be an explicit list")
    else:
        expected = coverage["expected_run_ids"]
        if any(not isinstance(value, str) or not value for value in expected) or len(set(expected)) != len(expected):
            errors.append("coverage.expected_run_ids contains missing/duplicate ids")
        elif valid_run_ids:
            coverage_checked = True
            missing, extra = sorted(set(expected)-set(run_ids)), sorted(set(run_ids)-set(expected))
            if missing or extra:
                errors.append(f"run coverage mismatch: missing={missing}, extra={extra}")
            warnings.append("coverage compares the declared run roster only; independently verify its completeness and all-object/scene denominators")
    for run in runs:
        rid = run.get("id","<missing>")
        evidence({"path":run.get("protocol_path",""),"sha256":run.get("protocol_sha256")},rid)
        if not run.get("protocol_sha256"): errors.append(f"{rid}: missing frozen protocol hash")
        data = evidence({"path":run.get("records_path","")},rid)
        if data is not None:
            try:
                rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
                if len(rows) != run.get("expected_records"): errors.append(f"{rid}: record count {len(rows)} != {run.get('expected_records')}")
            except (UnicodeError,json.JSONDecodeError) as exc: errors.append(f"{rid}: invalid JSONL: {exc}")
        if run.get("selection_rule") not in {"training_objective","observed_assignment_cost"}: errors.append(f"{rid}: unknown observation-only selection rule")
        if run.get("ground_truth_in_estimation") is not False: errors.append(f"{rid}: GT-free estimation not declared")
        warnings.append(f"{rid}: manually trace initialization, selection and assignment")
        if "population" in run:
            p=run["population"]
            counts=[p.get(k) for k in ["total","observed","eligible","estimated","successful"]]
            if any(not isinstance(x,int) or isinstance(x,bool) or x<0 for x in counts): errors.append(f"{rid}: invalid population counts")
            elif counts != sorted(counts,reverse=True): errors.append(f"{rid}: inconsistent population denominators")
        elif not run.get("rates"): errors.append(f"{rid}: population or independent rates required")
        rates(run.get("rates",[]),rid)
        if run.get("oracle_inputs"): warnings.append(f"{rid}: supplied oracles: {run['oracle_inputs']}")
    return {"passed":not errors,"errors":errors,"warnings":warnings,"checked_files":checked,
            "metric_contract_checks":contract_checks,
            "coverage":{"listed_runs":len(runs),"expected_run_set_checked":coverage_checked},
            "scope":"Mechanical integrity only; does not certify theory, dataflow or detector performance."}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("manifest",type=Path)
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    result=audit(json.loads(args.manifest.read_text()),args.root)
    text=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text)
    print(text)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__": main()
