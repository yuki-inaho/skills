# Herdr discovery, visibility and owned cleanup

Read when using Herdr panes or deciding whether an owned tab may be closed.

## Authorization and discovery

- Only inspect or control Herdr when the user has authorized the named
  workspace (including earlier instructions in the same task).
- Missing `HERDR_ENV` or pane variables means this tool process lacks inherited
  context. It does not prove that Herdr, the workspace or the parent agent is
  absent. Do not fabricate environment values and do not switch to invisible
  workers based on that observation alone.
- With authorization, locate the executable, read the installed help/skill and
  perform read-only discovery: `herdr status`, `herdr workspace list`,
  `herdr pane list --workspace ACTUAL_ID`, `herdr agent list`. Match the native
  agent session ID and cwd against the live pane.
- Duplicate workspace labels require IDs and session evidence, not sidebar
  order. Record an actual CLI failure separately from missing environment
  variables.
- Normally control from a genuine Herdr pane. If the tool process lacks
  context, use the verified workspace and an already-authorized narrow owned
  controller bootstrap; subsequent worker control runs in that pane. Read-only
  discovery does not authorize typing into an occupied user pane.
- After moving a pane, the existing shell can retain its former workspace/pane
  values. Resolve its current pane by live terminal/shell identity; do not
  treat stale inherited IDs as the current location.

## One agent per tab and visible execution

- Launch each worker in its own tab with a labeled pane. Do not multiplex
  multiple agents in one tab or hide a worker behind file redirection.
- If the worker emits a public event log, run a visible bridge that prints
  public assistant text, tool commands and results, and waiting/exit status.
  Do not expose hidden reasoning or credentials.
- Start the bridge before the next launch. Verify the live worker and read the
  actual visible pane output; save a rendered snapshot. A bridge heartbeat only
  means it is waiting for a public event.
- Do not kill a valid processing job merely to repair its visibility. Repair a
  dead or blank bridge without stopping the job; stop only owned monitors after
  their workers exit.
- Before reusing a tab for a new attempt, retire the previous attempt's monitor
  after verifying its worker exited. Preserve the failed receipt; a stale
  monitor that keeps printing an old `EXIT` line misattributes the new
  attempt's status.
- Record the roster from real values: role, pane, native session, actual process
  ID, start time, model, write scope and evidence path.
- Keep the dispatch pane free and separate from worker tabs. Never type into a
  controller pane while it is busy; use the free dispatch pane or wait. A pane
  label alone does not prove which agent is listening.

## Jobs and receipts

- For long jobs, use an attempt directory per attempt, with exclusive
  stdout/stderr and a real exit receipt. Do not overwrite the first failed
  attempt.
- A launcher returning, an admission receipt or a heartbeat says nothing about
  completion. Inspect the actual job state and artifacts.
- If a detached job continues after its frontend exits, keep the assignment
  active through its required receipt or transfer continuation explicitly with
  `JOB_RUNNING` and the real job state.
- Bound polls to about a minute, then check the inbox before another poll. A
  loop of long sleeps inside one tool call still blocks steering.
- If an exit receipt is absent and both recorder and job are gone, record the
  exit as unknown; do not derive success from file counts.

## Owned cleanup

Close only tabs created by this run, and only after all of the following:

1. the owned frontend has actually exited;
2. every owned job has actually exited;
3. completion or failure evidence has been collected and saved;
4. the tab identity is confirmed as owned by this run;
5. pre-existing user tabs, servers and unrelated agents are identified and left
   untouched.

Use `cleanup_gate.py` as an advisory check, then verify the live topology again.
A partially completed cleanup records which identities already exited before a
retry. Unknown processes or tabs are never closed. Never use broad
`pkill`/`killall`, a global reset or a global message purge.

After an asynchronous pane closes, check the rendered output and residual owned
processes. Final topology and the preserved user identities are part of
acceptance.
