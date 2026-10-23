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
5. Read the catalog before launching anything. `assets/model_catalog.json` is a
   neutral empty template with no provider or model defaults; copy
   `assets/model_catalog.example.json` to a private, non-committed catalog or
   pass one with `--catalog`. The catalog is the editable allowlist of provider
   order, registry base IDs, supported `#variant` values, preferred capabilities
   and the free-model policy. An empty or unconfigured catalog stops clearly
   with `catalog_unconfigured`; it never falls back to a vendor or model.
   Discovery comes separately from the installed model listing, which normally
   prints base IDs without `#variant`.

## Procedure

1. **Write the roster first.** For each worker record: agmsg identity and type,
   team, workspace/pane ID, native session ID, actual process ID and start time,
   requested model, write scope, nonce, restrictions, evidence path and end
   condition. Keep worker logs in a private, ignored task directory.
2. **One agent per tab.** Launch each worker in its own tab, label the pane with
   the role and task, and make the run visible. Redirecting output to a file
   without a visible bridge fails the visibility requirement even when the
   process is alive. Record the launch argv, start time and actual exit. Keep a
   dedicated **free dispatch pane** for control; never type or `poke` into a
   controller pane while it is busy. A controller's prompt is its own input
   loop, not a message channel. If the dispatch pane is occupied, wait or use
   another owned free pane.
3. **Acknowledge before editing.** Give each worker a scoped assignment with a
   fresh nonce and require an ACK that states the nonce, identity and scope.
   A sent message is not proof of reading, and an ACK is not proof that the
   work or its verification was completed.
4. **Select the provider from the catalog.** Read
   [provider-selection.md](references/provider-selection.md). Select only the
   intersection of the editable catalog, the discovered IDs, the non-free
   policy, the task allowlist/override (narrowing only) and the attempt/quota
   state. Normalize discovery to its base registry ID and build the exact
   `PROVIDER/MODEL#VARIANT` invocation from the catalog; do not require the
   registry listing to contain `#variant`. Prefer an entry carrying the
   catalog's `prefer_capabilities` tags within a provider when it is discovered.
   Follow the catalog's provider order from the user-provided catalog; the
   bundled template defines no order. A task/session override narrows it. When a
   provider is known quota-exhausted, remove every model on that provider and
   move to the next allowed non-free provider without a retry storm and without
   asking again; an unavailable model is candidate-specific. Never select an
   unlisted or free ID and never silently change the model family, version or
   variant. Never edit global auth or default configuration for one run.
5. **Message and poll correctly.** Use
   [coordination-protocol.md](references/coordination-protocol.md). Deliver
   bodies as literal argv lists, read the complete inbox at phase boundaries
   and before READY, and keep the actual recipient and team correct.
6. **Reconcile before falling back.** A timeout, a lost frontend, an HTTP error
   or a cancellation acknowledgement does not prove a remote call stopped or
   became inactive. When the provider exposes its own session/run state, check
   that state for the session this run owns; a closed frontend, silence or an
   ACK is not an inactivity receipt. Check owned processes, receipts and
   partial artifacts before retrying; do not start a duplicate writer or repeat
   an external side effect while the remote state is unknown. A cancelled or
   aborted call is also not a quality comparison. Preserve every failed attempt
   with its requested model, exit and public error class.
7. **Make execution visible.** Follow
   [visible-lifecycle.md](references/visible-lifecycle.md). Verify the live
   worker, read the actual pane, and save a rendered snapshot. Heartbeats,
   Herdr `idle` state and accepted admissions do not establish completion.
8. **Verify independently.** Check actual artifacts, exit codes, hashes and
   positive denominators. Parse structured outputs. A worker's summary,
   `exit 0`, a model listing or a READY message is a claim, not verification.
   Tie each artifact to the actual command operands (argv), cwd and selected
   environment that produced it; a regex hit on a path string in a transcript
   or log is not command evidence, and a file merely existing is not a
   completed stage. Read the run dynamics manually — launch, exit, artifact
   production — instead of trusting static patterns alone.
9. **Clean up owned resources last.** Close only tabs created by this run,
   after the owned frontend and its jobs have actually exited and the
   completion evidence is collected. Preserve user tabs, servers and unrelated
   agents. Never use broad `pkill`, `killall`, a global reset or a global
   message purge.

## Bounded helpers

Two pure decision helpers are bundled. They read a JSON request, print one JSON
decision and never touch the network, credentials, Herdr or global settings.

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
  reason code. An empty catalog stops with `catalog_unconfigured`. An
  unlisted/free override, a free-only catalog or a missing required capability
  stops instead of silently substituting a model.
- `cleanup_gate.py` returns `wait`, `inspect`, `collect_evidence`,
  `refuse_not_owned` or `close` from ownership and exit evidence.

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
- Each accepted artifact is tied to the actual argv, cwd, selected environment
  and exit receipt. A path-string regex hit, a file's existence or a summary is
  not substituted for that evidence.
- Where the execution service exposes session state, remote inactivity was confirmed
  there for the owned session; a cancellation ACK, timeout or closed frontend
  was not treated as proof.
- Control messages were typed only into a free dispatch pane; no keystroke was
  injected into a busy controller pane.
- Only owned tabs were closed, with frontend/job exit and completion evidence;
  pre-existing tabs and processes remain.

## Growth log

Append only generic, non-identifying lessons to
[references/growth-log.md](references/growth-log.md). Never copy session IDs,
host paths, user data or raw provider errors into the public skill. Prefer a
narrow correction to a new universal rule.

## References

- [model_catalog.json](assets/model_catalog.json) — neutral empty template;
  [model_catalog.example.json](assets/model_catalog.example.json) — synthetic
  shape example only, not a provider recommendation.
- [provider-selection.md](references/provider-selection.md) — provider order,
  overrides, failure classification and bounded switching.
- [coordination-protocol.md](references/coordination-protocol.md) — agmsg
  delivery, ACK/READY, inbox completeness and report files.
- [visible-lifecycle.md](references/visible-lifecycle.md) — Herdr discovery,
  one-agent-per-tab visibility, roster evidence and cleanup gates.
