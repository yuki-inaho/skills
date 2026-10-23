# Growth log — herdr-opencode-agmsg

Generic, non-identifying lessons only. No session IDs, host paths, user data,
provider errors or model catalogs.

## 2026-10-23 — visibility and remote-state review

### Findings

- A timeout, a lost frontend, an HTTP error or a cancellation acknowledgement
  did not prove that a remote model call had stopped or become inactive. The
  owned execution-service session's state was the missing evidence before a retry.
- A regex match on a path string in a transcript was treated as proof that a
  command used the intended file, while the actual command operands and cwd
  were different. The executed argv is the evidence, not a string in prose.
- A busy controller pane is not a message inbox. Typing into it interrupts the
  controller's own input loop; a separate free dispatch pane is the safe place
  for control messages.

### Struggles

- Frontend exit and worker inactivity look similar in a pane listing. They are
  different claims and need different receipts.
- A path that exists is easy to mistake for a completed stage; the artifact and
  its producer still have to match.

### Tips

- Reconcile owned remote session state, owned processes, receipts and partial
  artifacts before retrying or starting another writer.
- Capture the actual command operands, cwd, environment, exit code and artifact
  hash. Review the run dynamics manually.
- Keep one dedicated free dispatch pane; never poke a busy controller.
- Treat a cancelled or aborted run as an interrupted attempt, not a comparison.

### Promotion judgment

- Promoted the remote-state and argv checks to Procedure and Verification.
- Promoted the free-dispatch-pane rule to Procedure, the coordination protocol
  and the visibility reference.
- Everything else stays here; no session data or provider error is reproduced.
