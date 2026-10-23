---
name: write-workdoc-uv
description: >-
  Create detailed Japanese workdoc Markdown files for uv-based development under
  temp/ with filename format workdoc_Apr16-2026_*.md, goal and subgoal analysis,
  phase-separated research, design, implementation, atomic checklist actions,
  TDD expectations, error handling, and traceability. Use when the user says
  write_workdoc_uv, asks to create a workdoc, 作業計画書, 作業記録, 作業書, or UV作業書.
---

# Write Workdoc UV

Create a self-contained Japanese work plan and work record for another agent to execute without missing context. The output is always a Markdown file under `temp/`, designed for uv-based development and audit-friendly traceability.

## Required Reference

Before writing the workdoc, read `references/workdoc-template.md`. Preserve the template structure and the "作業記録"注意事項 unless the user explicitly asks for a different format. Keep the workdoc free of real secrets, private repository names, absolute home paths and customer data; use placeholders or synthetic values.

## Workflow

1. Read local repository instructions first, including `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, `OPENCODE.md`, and any referenced files. Follow command wrappers such as `rtk` when required.
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
8. Separate planning, research, implementation, and verification. Do not mix implementation steps into the research phase.
9. Add a goal requirement analysis section directly under `## 1. 作業目的`. Include the user's intuitive goal, explicit requirements, implicit constraints, subgoal structure, success criteria, non-goals, and traceability IDs.
10. Tie every phase, task, checklist item, command, and definition-of-done item back to the goal analysis or traceability IDs.

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

Every checklist step must be a minimal, single-operation action with this exact Markdown form:

```markdown
### 手順 n: <目的を端的に>
- [ ] 🖐 **操作**: <コマンド／編集内容など>
- [ ] 🔎 **確認**: <期待結果>
- [ ] 🧪 **テスト**: <テストケース名／初期失敗・後成功の確認方法>
- [ ] 🛠 **エラー時対処**: <代表的なエラーと解決策>
```

For each step:

- Make the action atomic and ordered.
- Make completion objectively checkable.
- Include TDD fail-to-pass guidance whenever the task can reasonably be tested.
- Include likely errors and concrete remedies.
- Prefer many small steps over a broad checklist item.

## Verification Before Finishing

Before answering the user, verify:

- The file exists under `temp/` and matches `workdoc_<Mon><DD>-<YYYY>_*.md`.
- The document includes concrete repository context and no unresolved generic placeholders.
- The goal analysis is directly under `## 1. 作業目的`.
- Planning, research, implementation, and verification are phase-separated.
- The checklist uses the required four-line action format for every `### 手順 n`.
- The work record caution notes remain in the document.
