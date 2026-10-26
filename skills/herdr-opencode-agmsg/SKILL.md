---
name: herdr-opencode-agmsg
description: Coordinate user-visible OpenCode workers in Herdr panes with agmsg messaging, an explicit provider order, evidence-based acceptance, and owned-tab cleanup. Use when the user authorizes this Herdr/OpenCode multi-agent workflow or asks to switch providers inside it. Not for ordinary single-agent tasks or for inspecting Herdr without user authorization.
---

# Herdr + OpenCode + agmsg

Coordinate user-authorized OpenCode workers in visible Herdr panes. The
coordinator owns the plan, review and acceptance; workers own disjoint write
scopes. The user must be able to see instructions, tool activity and results in
the assigned panes.

## When to use

Use when the user asks for a Herdr workspace with OpenCode workers, cross-agent
messaging, one agent per tab, or provider fallback within such a run.

Do not inspect Herdr sessions, panes or agents without explicit user
authorization. A tool process that lacks inherited Herdr variables is not proof
that Herdr is unavailable; it only means this process has no inherited context.

## Prerequisites

1. Read the installed help before controlling anything: `herdr --help`, the
   `herdr pane`/`herdr workspace`/`herdr agent` subcommand help, `opencode run
   --help`, `opencode models --standalone`, and the installed agmsg skill. CLI
   syntax and model catalogs change between versions.
2. Inspect only `HERDR_ENV`, `HERDR_WORKSPACE_ID`, `HERDR_TAB_ID` and
   `HERDR_PANE_ID`. Never dump the whole environment or credential files.
3. Preserve the user's workspace layout, focus, provider/model choice, paused
   work and pre-existing tabs.
4. Use only installed agmsg scripts with the already-established team and
   identity. Do not re-register a known OpenCode worker as a different agent
   type, and do not read or write the message store directly.
5. Read `assets/model_catalog.json` before launching anything. It is the
   editable allowlist of provider order, registry base IDs, supported
   `#variant` values, preferred capabilities and the free-model policy; edit it
   or pass a task copy with `--catalog`. Discovery comes separately from the
   installed model listing, which normally prints base IDs without `#variant`.

## Delegation boundary

Assign a usable outcome with its scope, inputs, end condition and genuine stop
conditions. The initial assignment covers ordinary reversible implementation,
local repairs and required verification within that scope. Do not invent a new
START/GO/READY approval for each substep. Preserve explicit user approval rules.

When supervising another coordinator, let that coordinator manage its workers.
Review artifacts and material milestones; batch nonurgent corrections. Do not
poll for reassurance or send repeated steering that makes receipt handling the
worker's main job. A delayed ACK is not proof of disobedience or a stopped job.
Respect requests for autonomy or no workdoc; roster/log evidence can remain in
the existing task state without a new planning document.

## Procedure

1. **Write the roster first.** For each worker record: agmsg identity and type,
   team, workspace/pane ID, native session ID, actual process ID and start time,
   requested model, write scope, nonce, restrictions, evidence path and end
   condition. Keep worker logs in a private, ignored task directory.
2. **One agent per tab.** Launch each worker in its own tab, label the pane with
   the role and task, and make the run visible. Redirecting output to a file
   without a visible bridge fails the visibility requirement even when the
   process is alive. Record the launch argv, start time and actual exit.
3. **Acknowledge the assignment before editing.** Give each worker a scoped assignment with a
   fresh nonce and require an ACK that states the nonce, identity and scope.
   A sent message is not proof of reading, and an ACK is not proof that the
   work or its verification was completed. This ACK starts the scoped work;
   routine steps and corrections do not require another approval exchange.
4. **Select the provider from the catalog, then use that decision to launch.** Read
   [provider-selection.md](references/provider-selection.md). Select only the
   intersection of the editable catalog, the discovered IDs, the non-free
   policy, the task allowlist/override (narrowing only) and the attempt/quota
   state. Normalize discovery to its base registry ID and build the exact
   `PROVIDER/MODEL#VARIANT` invocation from the catalog; do not require the
   registry listing to contain `#variant`. Prefer a 1017 (or other catalog
   `prefer_capabilities`) entry within a provider when it is discovered. Follow
   the catalog's provider order; the bundled default is Ollama Cloud, then
   OpenCode Go, then OpenRouter, and a task/session override narrows it. When a
   provider is known quota-exhausted, remove every model on that provider and
   move to the next allowed non-free provider without a retry storm and without
   asking again; an unavailable model is candidate-specific. Never select an
   unlisted or free ID and never silently change the model family, version or
   variant. Never edit global auth or default configuration for one run.
   Use `scripts/provider_launch.py` for each attempt (see the provider-selection
   reference). It connects the planner to the actual `--model` argument and bounds
   OpenCode internal retries with a process deadline. It runs one attempt; the
   coordinator classifies, reconciles, updates the request and launches the next
   allowed candidate without asking again when fallback was already authorized.
   Do not replace an authorized fallback order with a single-provider override
   merely because the first provider is preferred. A strict user restriction
   still wins.
5. **Message and poll correctly.** Use
   [coordination-protocol.md](references/coordination-protocol.md). Deliver
   bodies as literal argv lists, read the complete inbox at phase boundaries
   and before READY, and keep the actual recipient and team correct.
6. **Reconcile before falling back.** A timeout, a lost frontend or an HTTP
   error does not prove a remote call stopped. Check owned processes, receipts
   and partial artifacts before retrying; do not start a duplicate writer or
   repeat an external side effect. Preserve every failed attempt with its
   requested model, exit and public error class.
7. **Make execution visible.** Follow
   [visible-lifecycle.md](references/visible-lifecycle.md). Verify the live
   worker, read the actual pane, and save a rendered snapshot. Heartbeats,
   Herdr `idle` state and accepted admissions do not establish completion.
8. **Verify the outcome independently.** Inspect the actual deliverable and
   the checks relevant to its correctness. Use exit codes, structured results,
   input identity or denominators where they support that decision. Reuse valid
   evidence; repeat checks only when a change or failure affects them. A summary,
   `exit 0` or READY alone does not establish the requested outcome. Correcting
   a receipt's wording does not invalidate unchanged artifacts.
9. **Clean up owned resources last.** Close only tabs created by this run,
   after the owned frontend and its jobs have actually exited and the
   completion evidence is collected. Preserve user tabs, servers and unrelated
   agents. Never use broad `pkill`, `killall`, a global reset or a global
   message purge.

## Bounded helpers

Two pure decision helpers and one bounded launcher are bundled. The decision
helpers read a JSON request, print one JSON decision and never touch the network,
credentials, Herdr or global settings.

```bash
python3 scripts/provider_plan.py --input request.json
python3 scripts/provider_plan.py --catalog path/to/model_catalog.json --input request.json
python3 scripts/cleanup_gate.py --input request.json
```

- `provider_plan.py` reads the catalog plus the request, normalizes registry
  base IDs against `#variant` invocations, and applies the allowlist,
  free-model policy, required/preferred capabilities, discovery intersection,
  ordering, bounded attempts and failure classes, and returns `launch`, `retry`,
  `reconcile`, `done`, `fix_same_model`, `inspect` or `stop` with a fixed
  reason code. An unlisted/free override, a free-only catalog or a missing
  required capability stops instead of silently substituting a model.
- `cleanup_gate.py` returns `wait`, `inspect`, `collect_evidence`,
  `refuse_not_owned` or `close` from ownership and exit evidence.

`provider_launch.py` executes one selected attempt in the visible caller pane,
records its PID/exit, and enforces a wall-clock timeout. It does not classify
provider errors, accept work, supervise detached jobs, or automatically repeat
side effects. See the reference for the coordinator loop.

The helpers are advisory gates, not authorization. The coordinator still reads
the actual process, pane and artifact evidence before acting.

## Failure handling

Keep these classes separate; do not convert one into another:

| Class | Next step |
| --- | --- |
| quota or credit exhausted | next allowed non-free candidate, no immediate retry |
| transient 429/5xx/network/timeout | at most a bounded retry that respects Retry-After and the deadline |
| authentication or permission | repair configuration; never copy or expose credentials; do not loop |
| model or variant unavailable | use another explicitly allowed and discovered candidate or report a blocker |
| free or unlisted model | never select it; a catalog that tries to enable free models is rejected |
| provider/account quota exhausted | exclude every candidate on that provider, not just the failed one |
| missing required capability/version | stop and report it; do not downgrade |
| code, test or validation failure | fix with the same model; this is not a provider failure |
| unknown | inspect receipts and processes before any new launch |

After a switch, start a fresh attempt with a fresh scope packet and output
directory; do not reuse the previous provider's native session ID. Carry
forward user constraints, input hashes and accepted results.

A comparison across models run under different conditions is not quality
proof. Keep the evaluation caveat with the result.

## Verification

- The roster matches actual pane, process, start time and native session IDs.
- The ACK nonce, team, sender and recipient are correct, and the inbox was read
  completely before acceptance.
- The selected candidate is in the editable catalog and the discovery output,
  is non-free, satisfies the required capabilities, and uses a catalog-supported
  variant; registry base IDs and `#variant` invocations were normalized, not
  compared literally. The requested model/version/variant is recorded, and any
  switch has a cause, attempt history and fresh-session record.
- Artifacts were inspected directly; failures and partial effects are recorded,
  not hidden by a later success.
- Only owned tabs were closed, with frontend/job exit and completion evidence;
  pre-existing tabs and processes remain.

## Growth log

Append only generic, non-identifying lessons here or in a private log. Never
copy session IDs, host paths, user data or raw provider errors into the public
skill. Prefer a narrow correction to a new universal rule.

## References

- [model_catalog.json](assets/model_catalog.json) — editable provider order,
  exact model IDs/variants, capabilities and free-model policy.
- [provider-selection.md](references/provider-selection.md) — provider order,
  overrides, failure classification and bounded switching.
- [coordination-protocol.md](references/coordination-protocol.md) — agmsg
  delivery, ACK/READY, inbox completeness and report files.
- [visible-lifecycle.md](references/visible-lifecycle.md) — Herdr discovery,
  one-agent-per-tab visibility, roster evidence and cleanup gates.
