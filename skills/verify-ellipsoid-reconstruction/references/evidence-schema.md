# Mechanical evidence manifest

Use a JSON object with `version: 1`, `claims`, and optional `runs`.

Each claim needs unique `id`, `kind` (`proof`, `numerical`, `source`, `unverified`), nonempty `statement`, an explicit `assumptions` list, and `evidence` entries. Each evidence entry has a path relative to the project root, optionally SHA256. Proof/source claims need an entry with `role: proof` or `role: source`. Unverified claims may lack evidence.

Each run needs `id`, `protocol_path`, `protocol_sha256`, `records_path`, `expected_records`, `selection_rule`, `ground_truth_in_estimation`, and a `population` or nonempty `rates` list. Records are JSONL, counting every nonblank line including failures. Use `training_objective` for selection between fitted estimates or `observed_assignment_cost` for ID assignment from the current observed frame. Neither declaration proves GT-free behavior: `ground_truth_in_estimation: false` still requires manual code/dataflow confirmation. List observation-generation privileges in `oracle_inputs`.

Population fields `total`, `observed`, `eligible`, `estimated`, `successful` must be nonnegative integers in decreasing order. If a study uses incompatible denominators, use independent `rates` instead of coercing them into this schema. A rate has a nonempty `id`, integer `numerator` and integer `denominator`, with `0 <= numerator <= denominator`. Claims may also contain `rates`. Give the population meaning in the claim statement or an accompanying manual audit. Denominator zero produces an untested warning; it is never interpreted as 100%.

For example, an ID claim may include separate rates `{ "id": "precision", "numerator": 98, "denominator": 100 }`, `{ "id": "any_visible_recall", "numerator": 98, "denominator": 150 }`, and `{ "id": "unknown_rejection", "numerator": 0, "denominator": 0 }`. The last result is untested. Do not infer a common population from these records.

At least one claim is required. Retain a manual generator audit (including a specification-specific geometric invariant), dataflow inspection and source/observation hash links alongside the mechanical manifest.

The validator checks file existence, hashes, JSONL parsing, counts, declarations and denominator nesting. It does not infer numerical correctness, prove a theorem, or audit estimation dataflow automatically. Preserve a separate manual audit.

## Bind rates to actual source fields

Optionally attach `source_binding` to a rate. Supply a project-relative `path`, optional `sha256`, and `numerator_pointer` / `denominator_pointer` using nonempty JSON Pointers beginning with `/`. Dictionary keys use the standard `~0` and `~1` escapes; array tokens are integer indices. The source fields must be integer counts, not booleans or rounded percentages. Both counts must equal the declared rate. Missing paths, invalid pointers, changed hashes and mismatched values are errors. Unbound rates produce a manual-review warning.

For example, bind reconstruction to `/groups/condition/method/passed` and `/groups/condition/method/n_scenes`; bind clock success to the separate `/groups/condition/method/timing_passed`. Inspect those meanings manually. The checker cannot infer from an arbitrary pointer whether a rate was given the right scientific name. It checks reproducible arithmetic and provenance, not free-form prose semantics.

## Pin a metric contract

The version-1 manifest remains accepted without this optional extension, with explicit manual-review warnings. Add a rate field `metric_contract` containing `path`, required lowercase `sha256`, and `pointer` to one metric record in a separate JSON file. That record requires:

| Field | Meaning and check |
|---|---|
| `metric_id` | Must equal the rate's `id`. |
| `predicate` | Nonempty success definition to inspect against evaluator code and raw records. |
| `failure_policy` | Nonempty treatment of invalid, missing, unestimated and nonconverged cases. |
| `denominator_population` | Explicit target population; an accepted subset is not all objects. |
| `aggregation` | Object with nonempty `operator`, `unit`, `independent_unit`; object counts can still have scene-level independent sampling. |
| `count_source` | `path`, `numerator_pointer`, `denominator_pointer`; all must exactly equal the rate's `source_binding`. That binding also needs a concrete SHA256. |
| `thresholds` | Explicit list, possibly empty for a threshold-free count. Each entry has unique `name`, `unit`, project-relative `path`, required `sha256`, JSON `pointer`, and `value`. The value is checked against the pinned source using JSON equality. |

Example contract record, stored under `/metrics/clock_within_40ms`:

```json
{
  "metric_id": "clock_within_40ms",
  "predicate": "valid estimate AND abs(tau_hat - tau_true) <= timing_tolerance",
  "failure_policy": "Every registered scene remains; absent/invalid timing estimates fail.",
  "denominator_population": "All registered evaluation scenes in the stated condition.",
  "aggregation": {"operator": "count_true", "unit": "scene", "independent_unit": "scene"},
  "count_source": {
    "path": "results/summary.json",
    "numerator_pointer": "/method/timing_passed",
    "denominator_pointer": "/method/n_scenes"
  },
  "thresholds": [{
    "name": "timing_tolerance", "unit": "s", "path": "protocol.json",
    "sha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256",
    "pointer": "/timing_success_seconds", "value": 0.04
  }]
}
```

The contract can reject a numerically consistent timing rate bound to reconstruction `passed`, or a success rate bound to `estimated_count`, **when the reviewed contract specifies the correct field**. It does not interpret the free-text predicate, execute it on the raw population, infer unit conversions, or establish that the registry itself is correct. A contract written to repeat the wrong pointer can still pass. Recount independently and record the source evaluator/hash in a manual audit. Check the contract's actual creation/freeze chronology; an after-the-fact contract is not preregistration. Do not add fixed mappings for particular seeds to the generic skill.

## Declare coverage without overstating it

Optionally add `coverage: {"expected_run_ids": ["run_a", "run_b"]}` to the manifest. IDs must be unique, and the listed `runs` must match this set exactly. Duplicate/missing run IDs and omitted/extra expected runs are errors. Each run's existing JSONL count check still applies. A claims-only manifest now warns that run records, population coverage and estimation dataflow are unexamined; a missing expected roster warns that run coverage is unchecked.

Matching the declared roster cannot detect a scientifically incomplete roster, an incorrect `expected_records`, or omitted objects hidden inside an otherwise correctly counted row. Check the registered seeds and all-object population independently. The output's `metric_contract_checks` lists the contracts inspected, and `coverage.expected_run_set_checked` describes a performed comparison; neither field means that scientific semantics or completeness were proved. Existing `passed`, `errors`, `warnings`, `checked_files` and `scope` keys remain available.

Before publication, keep this short manual table with each nontrivial rate: metric name; executable success rule; threshold and source; aggregation rule; counted unit; independent sampling unit; denominator population; failure treatment; exact source pointers; independent recount evidence. Mechanical success is one entry in that record, not approval of the prose claim.
