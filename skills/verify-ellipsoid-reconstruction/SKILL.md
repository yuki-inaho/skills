---
name: verify-ellipsoid-reconstruction
description: 'Use when auditing or improving evidence-backed reconstruction of unknown 3D ellipsoids from projected ellipses, partial silhouettes, or bounding boxes. Triggers: theory reports, synthetic benchmarks, uv implementations, ellipsoid SLAM or static identity experiments, and dense same-class occlusion. Separate geometric identifiability, estimator behavior, observation oracles, and real detector performance; preserve preregistered failures and verify workflow improvements.'
---

# Verify Ellipsoid Reconstruction

## Validate the generated study before its estimators

Compare the actual geometry, motion and random distribution with the registered specification using an independent invariant. Configuration labels, plausible pictures and nonintersection checks are insufficient. For a layered lattice, for example, verify the relative layer phase as well as minimum separation. Keep a previous faulty generator as a negative control when available, and link the audited source hashes to the generated data. Declare what varies across seeds and what remains the same; repeated seeds of one packing model do not establish performance over arbitrary scenes.

## Establish the observation contract

Read the current request, workdoc, source entry points, frozen settings and raw results. Record their paths. Distinguish explicit requirements, hypotheses and provisional assumptions. Continue authorized reversible work and revise the plan when evidence warrants it; preserve the original DoD and amendments.

Read `references/geometric-contract.md` when checking notation, observability or occlusion. For each stage, tabulate known quantities, unknowns, auxiliary observations, oracles, coordinate gauge and proof/experiment scope. Separate full amodal conics, visible filled-mask fits, true silhouette arcs, and occluder-cut boundaries. Separate known cameras from odometry or priors; known IDs from anonymous association; geometric shape from detection-error covariance; static projection crossing from independently moving objects.

Do not treat a bbox-inscribed ellipse as a projected ellipsoid without justifying the observation model. Inspect initialization in existing demos before using their output as evidence of unknown-shape recovery.

## Verify geometry and implementation independently

Define world-to-camera rotation, camera center, homogeneous scale, semiaxes, SPD constraints and front visibility. Derive the tangent-plane projection equation. Verify it through an independent route, such as a unit-sphere tangent circle or ray–surface discriminant; repeating the same conic projection is not independent validation.

Use rank and an explicit ambiguity in addition to parameter counting. Count distinct camera centers and distinguish exact rank from conditioning. Respect axis swaps, sign symmetries and repeated eigenvalues; a sphere has no observable orientation. Trace the use of ellipse centers as approximate triangulation rays rather than silently identifying them with projected 3D centers.

Inspect actual estimator inputs, initialization, candidate selection and assignment for truth leakage; declared booleans do not establish dataflow. Allow GT only in explicitly labeled observation-generation oracles and evaluation. Exclude heldout observations from fitting and selection, and separate development scenes from final evaluation scenes.

## Protect experiments and denominators

Fix seeds, primary metrics, thresholds, initialization policy and failure definitions before outcomes. Keep protocols immutable. Record corrections and development changes separately; retain failures and original results. Do not silently resample missing views or tune on evaluation scenes while still calling them heldout.

In dense scenes, retain all objects. Report observation coverage, eligibility, abstention, optimizer failure, accepted-estimate precision and all-object recall separately. Include visible unmapped objects, complete occlusion and reappearance in ID accounting. Use scenes, not correlated contour points or frames, as independent units where appropriate.

Use an explicit numerator and denominator for every rate. Reconstruction populations may form a decreasing sequence, but assignment precision, any-visible recall, first-frame reappearance recall and unknown-map rejection generally have different populations. A zero denominator is untested, not a perfect rate. State the detection supply rule separately from the matching rule.

For ellipse/bbox comparisons, share underlying detector-error realizations, camera priors, IDs and truth-free candidates. Distinguish ideal information loss from performance of separately trained detectors. Supports derived from one five-parameter ellipse are correlated; explain approximate weighting.

## Verification

Use the bundled script with `references/evidence-schema.md` for mechanical file/hash/count checks. Replace the example paths with the actual skill and project directories:

```bash
python3 /path/to/verify-ellipsoid-reconstruction/scripts/audit_evidence.py \
  /path/to/project/manifest.json --root /path/to/project \
  --output /path/to/project/audit.json
```

Require exit status zero and `passed: true` for mechanical consistency. Inspect every warning even when it passes. The script cannot certify mathematical correctness or truth-free dataflow on its own.

Bind reported rate counts to their source JSON fields when available. Check both the pointer's meaning and its value: a correct fraction attached to the wrong metric is still wrong. Keep reconstruction success, timing success, convergence and detection supply distinct. Never reinterpret passing a median threshold as every-scene success.

For reusable publication checks, attach the `metric_contract` described in `references/evidence-schema.md`. Independently review and pin its metric name, success predicate, failure rule, threshold source, aggregation and independent sampling units, denominator population, and count pointers. Inspect the actual evaluator and raw records before approving that mapping. Record whether the contract preceded the evaluation or was reconstructed afterward. A retrospective mapping improves reporting integrity; it does not preregister an old experiment. The checker detects disagreement with this declared contract, not an internally consistent but scientifically wrong contract.

Provide an expected run roster when auditing completion. Treat a claims-only manifest as a file/count review with unexamined run coverage and dataflow; treat a matched roster as agreement with a declaration, not proof that all required scenes or objects were included. Resolve or explicitly report each warning before using mechanical `passed` as evidence.

Read `references/pose-time-contract.md` for approximate camera poses, time offset, shared interpolation error or timing information. Test all-invalid starts as well as successful estimates; an exception that prevents saving a failed row can invalidate a failure-rate denominator.

## Improve through a fixed judge

Pin the harness version, inspect its API, and run a credential-free smoke example. Record proposal, execution/probe, adoption and reusable lessons separately. Respect the environment's permissions regardless of upstream defaults. Distinguish the original demonstration, a research adapter and model-backed recursive improvement; a deterministic proposer is not model self-training.

Keep model weights, scientific thresholds and evaluation data outside the mutable candidate surface. Select improvements using development observations without hidden GT in the runtime selector. Store a lesson only after evidence, scope and a forward check. Prefer a transferable rule to a scene-specific success story.

Forward-test complex revisions in a fresh agent with the skill, a user-like request and raw artifacts. Do not disclose the anticipated defect. Review actual findings before adopting a revision.

When revising this audit workflow, read `references/growth-log.md` for previously tested improvements and their limits; preserve successful controls and explicit negative controls.

## Report and persist accurately

Map each DoD item to proof, source, command output, raw data or inspected artifact. Classify claims as proved, numerically supported under stated conditions, attributed, or unverified. Report source contradictions with version, exact scope, a self-contained counterexample and independent verification; do not reject unrelated source results wholesale.

Use a permitted persistence mechanism. If a write or push is rejected, preserve a reviewable draft and record the block. Do not claim installation or persistence without a successful result, and do not route around a rejected path.
