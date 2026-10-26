# Review Rubric For Written Workdocs

Review operational clarity and the requested outcome, not template compliance.
Apply only criteria relevant to the current user request. A compact plan may be
self-contained without phase headings, trace IDs, or one checkbox per command.

## Goal and context

- Can another agent identify the requested deliverables, actual working context,
  inputs, constraints and completion criteria without guessing?
- Are commands and paths concrete where needed for execution? Are unknowns
  labelled rather than filled with invented facts?
- Does the document distinguish explicit requirements from proposed targets and
  optional improvements? Current user instructions override an obsolete plan.

Missing information is a finding when it can change execution or acceptance.
Missing a preferred heading, boilerplate principle or trace-ID format is not.

## Work units and dependencies

- Does the order follow real dependencies and lead to a usable result promptly?
- Can a work unit include its related implementation, execution and focused
  verification? Split it only for a useful dependency, ownership, risk or
  independently checkable outcome.
- Are scope and genuine stop conditions clear enough for the assignee to make
  ordinary reversible repairs without repeated approval?
- Do recording, review and supervisor messages support execution, or have they
  become unnecessary prerequisites between every operation?

Combining code and its test is not a defect. More checkboxes are not an
improvement. Initial discovery is required only where proceeding without it
would risk wrong work or harm; do not impose research/design gates universally.

## Verification and evidence

- Are checks proportionate to the change and sufficient for its claimed outcome?
  Add fail-to-pass tests for relevant behavioral changes, not every minor edit.
- Do manual checks state expected observations? Use project-native commands.
- For experiments, identify relevant inputs, resolved settings, evaluation
  split, baseline, selection rule, denominators, exclusions and timing scope.
  Accuracy claims need appropriate independent evidence; unit tests and
  implementation parity alone do not establish real-world accuracy.
- Do changes invalidate only affected evidence? A wording correction should not
  force a model rerun when inputs, implementation and artifacts are unchanged.
- For speed or time-series claims, state the measured stages and relevant
  hardware, warmup, lag or motion effects. Do not demand irrelevant fields.

## Failure handling and records

- Do likely failures have concrete remedies within the assigned scope?
- Do material changes in data, semantics, evaluation or authority require the
  appropriate decision, without turning routine fixes into new approval gates?
- Does an actual blocker stop its affected operation while allowing independent
  authorized work? Preserve explicit stop requests and required authorization.
- Are recorded times derived from logs or the clock, with failures retained?
  Batch records at useful milestones; continuous document edits are not a
  prerequisite unless the user explicitly requests them.

## Completion and progress

- Are requested artifacts present and checked against the user outcome? Plans,
  receipts and smoke tests cannot substitute for the requested full execution.
- Keep unmet quality requirements visible. A failed experiment can satisfy a
  request to run and report it, but cannot satisfy a requirement to improve it.
- Separate plan-only completion from future execution. Report preparation apart
  from usable results; do not derive overall progress from arbitrary checkboxes.
- Use actual run state and throughput for estimates; unknown remains unknown.

## Verdicts

- `PASS`: Executable and consistent with the requested outcome.
- `PASS_WITH_NOTES`: Usable with nonblocking clarifications.
- `REVISE`: Material ambiguities or missing evidence can cause wrong work.
- `FAIL`: The task cannot be meaningfully executed, or contradicts the user goal.

Label findings Blocker/Major/Minor by their actual execution impact. A document
verdict is not new execution authority: identify the affected operation and
repair scope instead of stopping all work because of formatting or audit polish.
