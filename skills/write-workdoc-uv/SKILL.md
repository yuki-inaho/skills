---
name: write-workdoc-uv
description: >-
  Create detailed Japanese workdoc Markdown files for uv-based development under
  temp/ with filename format workdoc_Apr16-2026_*.md, goal and subgoal analysis,
  dependency-aware work units, relevant verification, error handling, and
  evidence of the requested outcomes. Use when the user says
  write_workdoc_uv, asks to create a workdoc, 作業計画書, 作業記録, 作業書, or UV作業書.
---

# Write Workdoc UV

Create a self-contained Japanese work plan and work record for another agent to execute without missing context. The output is always a Markdown file under `temp/`, designed for uv-based development and audit-friendly traceability.

## Required Reference

Read `references/workdoc-template.md` as a starting point. Scale its detail to the requested handoff; omit inapplicable sections rather than manufacturing work. A current request for no workdoc overrides an earlier workflow preference. Do not create or review a document as a prerequisite to already-authorized execution unless the user requires it.

## Workflow

1. Read local repository instructions first, including `AGENTS.md`, `CODEX.md`, and any referenced files. Follow command wrappers such as `rtk` when required.
2. Confirm the current timestamp with:

```bash
date "+%Y-%m-%d %H:%M:%S %Z%z"
```

3. Determine the filename date token with the English three-letter month:

```bash
LC_TIME=C date "+%b%d-%Y"
```

Use `temp/workdoc_<date-token>_<slug>.md`, for example `temp/workdoc_Apr16-2026_api_refactor.md`. The slug must be short, lowercase, and task-specific.
4. Determine the working directory and repository name. Prefer `git rev-parse --show-toplevel` when inside a Git repository. If the directory is not a Git repository, do not silently fall back; state that it is not a Git repository in the document and use the current working directory as the explicit working directory.
5. Inspect the project enough to make the document executable by another agent: repository layout, uv files such as `pyproject.toml` and `uv.lock`, tests, `justfile`, entry points, and relevant source modules.
6. Create `temp/` if needed and write the workdoc there.
7. Fill every placeholder with concrete information. Do not leave bracket placeholders like `[ファイル名]` unless the user explicitly requested a blank template.
8. Order work by actual dependencies and the path to a usable result. A coherent unit may include implementation, execution and its focused verification; do not create approval gates between these by default.
9. State the user's goal, required artifacts, success criteria, constraints and material assumptions near the start. Distinguish required outcomes from optional improvements.
10. Connect each work unit to a requested outcome and evidence. Use trace IDs only when they help a complex handoff; a compact plan need not assign an ID to every command.

## Outcome And Evidence Boundaries

When a task includes measurable quality, accuracy, stability, or speed, make those user outcomes explicit acceptance items. Working code, saved artifacts, passing unit tests, and a document review do not by themselves establish those outcomes. If a run misses a quality target, retain the unmet item; do not redefine success as merely recording the failure. For a research/plan-only request, distinguish the completed planning deliverable from the still-unexecuted implementation and outcome gates. State which thresholds are user requirements, proposed engineering targets, or measurements, and freeze evaluation conditions before tuning.

For data-dependent experiments, specify the baseline and input/source identity, evaluation split, sample-selection rule, denominator, exclusions, units, and timing scope. Include failure/unknown cases and a control that could disprove the claimed improvement (for example, a constant output can reduce apparent jitter). Use independent observations for accuracy claims; implementation parity and residuals over only accepted correspondences are narrower evidence.

For evolving artifacts, distinguish current results from dated intermediate snapshots. Identify the source/config/input for each result and invalidate only checks affected by a subsequent change. Do not require full reruns for a wording correction when the underlying implementation and artifacts are unchanged.

## uv And Command Policy

- Use uv commands for Python workflows, for example `uv sync`, `uv run pytest`, `uv run ruff check`, and `uv run python ...`.
- If a `justfile` exists, inspect it and prefer documented `just` targets when they are more project-native than raw commands.
- Do not invent implicit fallback behavior. If a command, dependency, file, or assumption is unavailable, document the exact blockage and the explicit alternative chosen.
- Keep commands copy-pasteable from the repository root unless a step says otherwise.

## Checklist Policy

Use one checkable outcome per work unit, with enough commands, paths, expected
results and likely failure handling for the recipient to execute it. Combine
related edits and their verification. Split only when dependencies, ownership,
risk or independent acceptance make the split useful. More checkboxes are not
more progress. Include regression tests when the change warrants them; do not
invent a fail-to-pass exercise for every reversible edit.

Identify what genuinely blocks execution and what the assignee can fix within
existing authorization. Record milestone results using actual logs/timestamps;
do not make continuous document updates a prerequisite to the next operation.

## Verification Before Finishing

- The requested document exists at the agreed path (default `temp/workdoc_<Mon><DD>-<YYYY>_*.md`).
- Context, deliverables, dependencies, commands and completion criteria are concrete.
- Every retained work unit contributes to the requested outcome; optional improvements do not block it.
- Checks are proportionate and relevant; changed evidence is distinguished from still-valid evidence.
- Unknowns, failures and genuine decision boundaries are explicit. No invented results or generic placeholders remain.
