# Provider selection and bounded switching

Read when choosing an OpenCode provider/model, when a run fails with a provider
error, or when the user authorizes fallback. Provider availability is separate
from task completion and artifact quality.

## The editable catalog is the allowlist

The allowed providers, registry base IDs, supported reasoning variants,
capabilities and free-model policy live in `assets/model_catalog.json`. Edit
that file (or pass another file with `--catalog`) for the task; do not encode
the allowlist only in prose and do not change global auth or defaults for one
run.

```json
{
  "policy_version": 3,
  "provider_order": ["PROVIDER_A", "PROVIDER_B"],
  "default_variant": "high",
  "prefer_capabilities": ["1017"],
  "models": [
    {"id": "PROVIDER_A/MODEL-BUILD", "free": false, "capabilities": ["1017"], "variants": ["high"]},
    {"id": "PROVIDER_A/MODEL", "free": false, "capabilities": [], "variants": ["high"]}
  ]
}
```

The bundled catalog lists the currently allowed DeepSeek V4.1 Flash1017 or
Flash entries as editable defaults for Ollama Cloud, OpenCode Go and OpenRouter,
with `1017` marked as a capability and preferred within its provider. Replace
the entries when the user changes the allowlist. Capability tags are generic
markers such as a build/version requirement; they are not a quality claim.

Selection is the intersection of:

1. the catalog allowlist (the task allowlist may only narrow it);
2. the base IDs returned by the installed model discovery;
3. the unconditional no-free-model prohibition;
4. the requested/supported reasoning variant;
5. the available quota/attempt state.

## Registry IDs vs #variant invocations

`opencode models` normally prints registry base IDs such as
`PROVIDER/MODEL` and may omit a `#variant` suffix. The launch command needs the
exact invocation ID `PROVIDER/MODEL#VARIANT`. Do not intersect the registry
listing literally with the invocation ID: that falsely rejects every candidate.

Normalize discovery by stripping any `#variant` suffix, match it to the catalog
base ID, then build the invocation from `default_variant`, the task variant, or
the per-entry variant. A variant that the catalog entry does not support is not
silently substituted; the request stops with `variant_unsupported`.

`ollama-cloud/...:1017` and `ollama-cloud/...-1017` are model-name build tags,
not free markers. Keep them as the catalog base IDs exactly as discovered.

## Discover, then verify

- Read installed syntax with `opencode run --help` and registered IDs with
  `opencode models --standalone`. Filter the output to relevant names; do not
  print authentication files or environment dumps.
- Discovery and the catalog are inventory, not quota or privacy proof. They do
  not prove credentials, credit, a working inference call or any
  privacy/retention property.
- Do not claim a blanket retention guarantee from a local setting. If the user
  says retention is configured, treat that as user context and do not alter
  auth, ZDR or other global privacy settings as part of this workflow.
- Keep the requested model, version and variant exact, and record the invocation
  actually passed to `--model` in the attempt.

## Free and unlisted models

Free models are forbidden unconditionally, so no setting enables them.
`allow_free_models` may be omitted or set to `false`; any other value is
rejected, and free entries are always excluded. Treat `:free`, `-free`,
`/free` and explicit free metadata as free. Unlisted IDs, including free IDs
that appear in discovery, are never selected. If no non-free allowed candidate
is available, stop and report the policy blocker instead of substituting a free
model.

## Provider-wide quota exhaustion

A quota or credit failure is usually account-wide. Record it explicitly with
request `exhausted_providers: ["PROVIDER"]`, or attach `"scope": "provider"` to a
`quota_exhausted` attempt. Either form excludes **every** catalog candidate on
that provider before trying the next provider. Do not burn through sibling
models on a provider whose account quota is exhausted.

`unavailable_model` is candidate-specific: only that model/version/variant is
skipped, and another model on the same provider may still be tried. An attempt
without a provider scope is candidate-specific; use it only when the failure is
known to be limited to that model.

## Classify failures before switching

| Class | Signals (examples) | Policy |
| --- | --- | --- |
| `quota_exhausted` | credit/quota exhaustion, HTTP 402, explicit "insufficient funds" | Do not retry the unchanged endpoint. Mark the provider exhausted and move to the next allowed non-free provider; keep the error. |
| `transient` | HTTP 429 or 5xx, connection reset, timeout | At most one bounded retry, only while Retry-After fits the remaining deadline. Then move on or stop. |
| `auth_error` | HTTP 401/403, invalid or missing credentials | Repair configuration. No retry loop, no credential copying, no silent provider switch to hide it. |
| `unavailable_model` | model/version/variant absent or rejected | Use another explicitly allowed and discovered candidate or report a blocker. Do not downgrade silently. |
| `code_failure` | failing tests, lint, traceback, validation error | Fix with the same model. This is not provider unavailability. |
| `unknown` | no receipt, truncated error, unclear frontend exit | Inspect processes, receipts and partial output before any launch. |

A monthly credit balance is separate from service connectivity and short-window
rate limits. ECONNREFUSED, ETIMEDOUT, public API failure or a generic 429 are not
evidence of exhausted monthly credits. Mark quota exhaustion only from an
explicit provider/account response. Public API HTTP 200 and a model listing do
not establish successful authenticated inference.

A generic error string does not identify which provider failed. Compare it with
the actual launch argv and the saved receipt before naming a cause.

## Bounded attempt rules

- For a confirmed shared endpoint/network failure, record `transient` with
  `scope: "provider"`. After `provider_transient_limit` failures (default 2),
  skip all sibling models on that provider for this attempt cycle. This is a
  transport budget, not a quota classification. Clear that cycle only after new
  recovery evidence; do not erase the historical receipts.
- One bounded retry is reasonable for a transient failure that respects
  Retry-After and the deadline. Quota exhaustion is not transient.
- Keep one attempt per allowed candidate unless new evidence or user direction
  justifies another. Stop when the allowed candidates are exhausted.
- Do not loop between providers, top up a paid plan, change a plan or edit
  global auth/defaults without a new user decision.
- A timeout in an agent tool call is not a process deadline. If a job has a
  finite deadline, enforce it on the owned process and record the outcome.

## Reconcile live work before fallback

1. Save the failed attempt: requested model, actual argv, native session ID
   when available, start/end clock times, real exit code and public error class.
2. Determine whether the worker or its data job is still alive and whether it
   already wrote artifacts. A lost frontend or timeout is not proof that the
   remote call or a detached job stopped.
3. Check owned process identities, receipts and output hashes. Do not start a
   duplicate writer or repeat an external action that may already have happened.
4. Only after reconciliation, launch the next candidate.

## Fresh attempt after a switch

- Use a new scope packet, new output directory and new native session. Do not
  reuse the previous provider's session ID.
- Carry forward the user constraints, accepted inputs with hashes, current task
  status and completed phases.
- Retire the previous attempt's visible bridge/monitor before reusing its tab,
  and preserve the failed attempt's receipt. An old monitor that keeps printing
  `EXIT 1` after a new attempt starts misattributes the new attempt's status.
- Update the launch title, pane label and receipt together so the visible state
  and the record describe the same attempt.
- For an existing worker identity, keep its agmsg team/name/type and exact
  script paths; do not re-register it under another runtime merely because a
  template shows that runtime.

## Record and verify

Keep `from_model`, `to_model`, authorized order, cause, attempt paths, observed
start/end/exit and a public error excerpt. Keep secrets out of receipts and
public reports. Exit zero, a heartbeat, a model listing or a sent message does
not prove successful inference. Read the pane and inspect the actual result.

When comparing models, state that the runs are not a same-condition quality
comparison unless inputs, settings, repetitions and evaluation criteria match.


## Connect decisions to actual launches

The planner alone does not switch a running OpenCode process. Use the bundled
one-attempt launcher instead of a hard-coded `--model` wrapper. It inherits the
visible pane's stdout/stderr and working directory, uses a fresh native session,
and writes a private decision/receipt without copying the prompt or environment.
Read installed `opencode run --help` first; the launcher uses `run --standalone
--model` and optional `--auto`.

```bash
python3 scripts/provider_launch.py --input private/request.json \
  --assignment private/assignment.txt --attempt-dir private/attempt-01 \
  --timeout 180
```

The assignment contains a fresh nonce, identity, scope and ACK requirement. The
request uses the planner schema plus `live_job_possible: false` (confirmed before
every launch) and `reconciled: true` for subsequent attempts. `--auto` is optional
and only appropriate within previously authorized work. Parent evidence directory
must already exist; each attempt directory must be new. The timeout is a budget
chosen for the work, not a universal 180-second inference limit.

Coordinator loop:

1. Read inventory and the user's authorized provider order. Keep `1017` in
   `prefer_capabilities` when preferred; only set `required_capabilities: ["1017"]`
   when it is actually mandatory. The latter excludes an undated Go model and
   may select OpenRouter's 1017 entry instead. Do not call an undated Go model
   the same snapshot, and do not replace a strict version constraint silently.
2. Prepare the request and a fresh scope packet, register ownership, and run the
   launcher in the worker's visible tab. It refuses blocked planner decisions.
3. Observe live structured message errors while the frontend runs. Internal
   retries can continue without process exit; the launcher enforces the timeout.
   Save native session/model/error evidence before the deadline where possible.
4. Inspect the receipt **and** owned server/jobs/partial artifacts. A killed
   frontend, exit zero, or an expired timer does not prove model success,
   provider failure, or absence of external side effects. Unknown stays unknown.
5. For a confirmed provider error, append the exact candidate/outcome/scope to
   `attempts`, preserve Retry-After, update the remaining deadline and set
   `reconciled: true` only after reconciliation. Run the launcher with a **new**
   assignment and directory. Already-authorized fallback needs no new permission.
   For auth errors repair the configuration; for task/test failures keep the model.
6. Accept results only after the task's independent verification. The launcher
   deliberately leaves receipt `outcome` unknown even on exit zero. Stop when
   planner candidates/deadline are exhausted; never reset attempts to loop.

The launcher terminates only its own process group on timeout/interruption.
Detached private servers/jobs can escape that group and must still be reconciled;
therefore this is coordinator-driven fallback, not an unattended restart daemon.
No global default model, credentials, retention settings or provider account
settings are modified by these helpers.
