---
name: check-finished-workdoc
description: >-
  Check a completed Japanese workdoc against actual repository state and append
  or draft an evidence-based completion analysis chapter. Use when the user says
  check_finished_workdoc, asks to compare 完了の定義 or ゴール要求分析 with reality,
  inspect current status and rationale, record 調査と分析のサマリ, or audit whether
  a workdoc's claimed completion is supported by commands, diffs, tests, logs,
  artifacts, and work records.
---

# Check Finished Workdoc

Compare a workdoc's stated goals and definition of done with the actual project state, then write a traceable Japanese summary chapter. Do not treat an item as complete without evidence.

## Required Reference

Read `references/completion-summary-template.md` before writing the summary. Use it as the canonical chapter structure.

## Workflow

1. Read local repository instructions first, including `AGENTS.md`, `CODEX.md`, and any referenced files. Follow command wrappers such as `rtk` when required.
2. Locate the target workdoc:
   - If the user gives a path, use that file.
   - If no path is given, search `temp/` for `workdoc_*.md` and choose the newest file by modification time when that is a reasonable assumption.
   - If no workdoc is found, stop and state the missing input.
3. Read the whole workdoc and extract:
   - `## 1. 作業目的`
   - ゴール要求分析
   - サブゴール構造
   - トレーサビリティ方針
   - `## 6. 完了の定義`
   - `## 7. 作業記録`
   - any checklist completion marks and verification logs
4. Inspect the actual state needed to verify those claims. Prefer non-destructive checks such as:

```bash
date "+%Y-%m-%d %H:%M:%S %Z%z"
git status --short
git diff --stat
git diff --name-only
git log --oneline -5
rg --files
```

5. Inspect project-specific evidence mentioned by the workdoc: changed files, test files, generated artifacts, command outputs, screenshots, logs, and temp files. If the workdoc references uv or justfile checks, inspect `pyproject.toml`, `uv.lock`, and `justfile` when present.
6. Run only safe verification commands that are needed and reasonable for the current task. Prefer documented `just` targets or uv commands such as `uv run pytest ...`, `uv run ruff check .`, and `uv run ruff format --check .`. If running a command would be expensive, destructive, or underspecified, do not run it; mark the evidence as未確認 and explain why.
7. Compare each goal, subgoal, Trace ID, and definition-of-done item against observed evidence. Classify status as:
   - `達成`: Evidence supports completion.
   - `一部達成`: Some evidence exists, but coverage or scope is incomplete.
   - `未達`: Evidence shows the item is not complete.
   - `未確認`: Evidence is absent or verification was not run.
   - `対象外`: The item is explicitly out of scope or no longer applicable, with rationale.
   For dataset/export goals, separately inspect materialized artifact directories and
   representative counts/pairing keys. A manifest, CSV, or source path alone is not
   evidence that the required data files were produced.
8. Add or draft a chapter titled `## 8. 完了照合・調査分析サマリ` unless the document already uses section 8; if section 8 exists, use the next available number and keep the same title text after the number.
9. Include rationale and current status, not only a verdict. Every status judgment must point to evidence: command, file, diff, log, work record line, or an explicit absence of evidence.
10. Preserve existing workdoc content. If editing the file, append the chapter near the end after `## 7. 作業記録` unless the user requests a different location.

## Evidence Rules

- Do not fabricate completed test results, command output, changed files, or timestamps.
- Use exact command strings and summarize observed results.
- When evidence is missing, write `未確認` and explain what would be needed to confirm it.
- Treat checked checklist boxes as claims, not proof. Cross-check them with actual files, tests, logs, or work records.
- Treat a metadata-only or index-only output as incomplete when the goal requires a
  self-contained dataset. Record the missing artifact paths and the exact command needed
  to verify or produce them.
- Do not silently narrow the user's goal to match what was implemented. Mark the original
  goal `一部達成` or `未達` and explain the scope mismatch.
- If repository state is dirty, distinguish user-existing changes from current verification observations when possible.
- If the workdoc's definition of done is too vague to verify, mark the item `未確認` or `一部達成` and explain the ambiguity.

## Output Behavior

If the user asks to "作って", "追記して", "記録して", or otherwise implies modification, edit the target workdoc directly. If the user asks only to check or summarize, provide the chapter draft in the response without editing.

After editing, report:

- The target workdoc path.
- The appended chapter heading.
- Commands actually run.
- Any items still `未達` or `未確認`.

## Final Verification

Before finishing:

- Confirm the target workdoc still exists.
- Confirm the new chapter exists if editing was requested.
- Confirm every goal/DoD status in the chapter has a rationale.
- Confirm no unknown item was silently marked complete.
