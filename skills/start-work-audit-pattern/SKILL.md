---
name: start-work-audit-pattern
description: Use when the user asks to start or template a plan-driven multi-agent development workflow with a coordinator, worker, and audit agent; when they mention start-work-audit-pattern, 作業監査, 作業エージェント, 監査エージェント, 統括エージェント, workdoc checklist execution, role files under .agents/roles, or step-by-step execution from a workdoc/Plan as the single source of truth. Supports Codex and Claude by bundling reusable prompt and role-file templates.
---

# Start Work Audit Pattern

Run development from a workdoc/Plan as the single source of truth, using three roles: coordinator, worker, and auditor.

This skill is a template and operating pattern. It does not replace local instructions, the active workdoc, repository commands, or user approvals.

## Required Files

Bundled resources:

- `assets/start-work-audit-template.md`: near-verbatim reusable prompt template.
- `assets/roles/coordinator.txt`: coordinator role.
- `assets/roles/worker.txt`: worker role.
- `assets/roles/audit.txt`: audit role.

Before using the pattern in a repository, create role files if missing:

```bash
mkdir -p .agents/roles
cp <skill>/assets/roles/worker.txt .agents/roles/worker.txt
cp <skill>/assets/roles/audit.txt .agents/roles/audit.txt
```

Copy `coordinator.txt` too when the environment supports a coordinator role file:

```bash
cp <skill>/assets/roles/coordinator.txt .agents/roles/coordinator.txt
```

If role files already exist, read them and preserve local customizations unless the user explicitly asks to overwrite them.

## Workflow

1. Identify yourself first: state whether the active agent is Codex, Claude Code, or another runtime.
2. Read local instructions in this order when present: `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, then referenced files.
3. Show the workdoc/Plan path before starting. If no path is given, locate the intended workdoc under `temp/` and state the assumption.
4. Treat the workdoc/Plan as the only source of truth. Do not add scope unless the user updates the Plan.
5. Confirm the timestamp with:

```bash
date "+%Y-%m-%d %H:%M:%S %Z%z"
```

6. Read the checklist and execute the next unchecked `[ ]` item only.
7. For each step, define:
   - what will be done
   - why it is needed
   - completion condition
   - assigned role
   - audit condition
8. Delegate implementation/investigation to the worker role. The coordinator should not do implementation work when real delegation is available.
9. Delegate review to the audit role after each work block.
10. Update the checklist item to `[x]` only after the coordinator accepts the audit result.
11. Immediately append a work record entry to the workdoc after each `[x]` update.
12. Repeat until every checklist item and definition-of-done item is complete.
13. Run final integration checks and summarize evidence.

## Agent Use

Use actual subagents when the runtime provides them and the user has requested an agent team. Keep exactly three conceptual members:

- coordinator: plan control, task breakdown, assignment, audit acceptance, final integration
- worker: implementation, local investigation, narrow verification
- auditor: plan conformance, diff review, verification sufficiency, residual risk

Do not spawn extra agents unless the user explicitly expands the roster.

If the runtime has no subagent feature, emulate the roles in separate labeled blocks while preserving the same handoff and audit gates. State that real subagents are unavailable.

For Codex, prefer available multi-agent tools when present. For Claude Code, use its available subagent/task mechanism. Do not invent tool calls that are not available in the current runtime.

## Workdoc Integration

If the user asks to write a new workdoc, use `write-workdoc-uv` when available.

If the user asks to review a workdoc before execution, use `review-written-workdoc` when available.

When executing an existing workdoc, do not rewrite it wholesale. Only update:

- checklist boxes
- work record rows
- explicit replanning notes when blockers or Plan contradictions are found

## Reminder Rule

Maintain an action count. After every 20 actions, print this exact reminder and reset the count:

> 「では、作業計画書兼記録書のチェックリストを細かく更新し、作業開始前に必ず date "+%Y-%m-%d %H:%M:%S %Z%z" コマンドで現在時刻を確認し、正確な日時を記録してください。詰まった場合は必要に応じてタスクを細分化して作業を再開し、行動カウントと注意事項を注意した上で作業継続してください。チェックリストがすべて埋まるまで作業を続け、表示後には必ず行動カウントをリセットしてください。行動カウントがリフレッシュされるタイミングでかならず作業記録を更新してください（状況報告）。行動カウントは行動のたびに明示的に出力してください。」

Then update the work record with the current status.

## Operating Constraints

- Execute checklist items sequentially from top to bottom.
- Mark `[x]` only after implementation evidence and audit acceptance.
- Keep changes local to Plan scope.
- Preserve traceability: commands, files changed, tests, audit findings, and acceptance decisions must be recorded.
- Use `justfile` targets when they are the project-native path.
- Use `uv` for Python/uv projects. If the project is not uv-based, state that uv is not applicable instead of forcing it.
- Avoid implicit fallback. When a command or dependency is missing, record the blockage and the explicit chosen alternative.
- Follow DRY, KISS, and SOLID.

## Output Templates

Worker completion report:

```markdown
## Worker Report
- 実施内容:
- 変更点:
- 確認方法:
- 残る懸念点:
```

Audit report:

```markdown
## Audit Report
- Plan 整合性:
- 成果物の妥当性:
- 差分の適切さ:
- 検証の十分性:
- 判定: 承認 / 差戻し / 追加確認
- 修正指示:
```

Coordinator step header:

```markdown
## Step N
- 何を行うか:
- なぜ行うか:
- 完了条件:
- 担当:
- 承認条件:
```
