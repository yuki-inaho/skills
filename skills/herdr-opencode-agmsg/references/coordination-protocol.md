# Messaging, steering and report files

Read before sending assignments, steering or acceptance messages.

## Use the installed scripts

Use only the installed agmsg scripts (`join.sh`, `send.sh`, `inbox.sh`,
`team.sh` and other documented helpers). Never read or write the message
database, and never create a parallel messaging setup.

Reuse the established team and identity for an existing worker. New workers get
distinct identities, an explicit team and the same delivery preference as the
rest of the run. Do not rediscover or re-register a joined OpenCode worker as a
different agent type.

## Deliver safely

- Call `send.sh` with a literal argument list, for example through Python
  `subprocess.run([send_script, team, sender, recipient, message], check=True)`.
- When the body contains Markdown, commands, backticks, quotes or `$()`, do not
  interpolate it into shell text or a heredoc. Build the argument list in
  Python, or write the body to a UTF-8 file and pass it as one literal argument
  from a small helper. An interpolated backtick can execute instead of reaching
  the recipient.
- If an interpolation accident happens, preserve stderr and the original
  message, check whether any artifact or command was affected, then resend with
  a literal argument list.
- Run inbox checks as their own bounded tool calls. Do not combine an inbox call
  with a large file dump: the call consumes messages even when the display is
  truncated.

## ACK, steering and READY

- Every assignment includes a fresh nonce, the exact scope, the write boundary,
  the evidence path and the end condition.
- ACK before edits: nonce, identity, scope, material correction. Keep it short;
  do not copy the whole assignment back.
- ACK does not mean that reading or work is complete. A sent message does not
  prove delivery or comprehension.
- Before READY, read the complete inbox. If output was truncated, recover all
  current instructions with `history.sh`; a second empty inbox is not proof that
  hidden messages were read.
- READY states the artifact path, test commands and actual results, failure
  before and success after, limitations, and the same nonce. Sending READY is
  not acceptance; the coordinator verifies the artifact independently.
- For material steering, record the send time and confirm receipt at a tool
  boundary. Delivery alone does not prove the new instruction was consumed.
  Delayed ACKs during an active tool call do not justify replacement or restart.
  Batch nonurgent corrections and let authorized work continue. Explicit stop
  requests or evidence of an unsafe/out-of-scope action require prompt action.
- The initial scoped assignment authorizes its normal steps. ACK receipt of a
  material scope change, not every local fix; do not add a supervisor GO after
  each successful check unless the user actually required that boundary.

## Reports

- Keep worker reports, logs, session IDs and host paths in a private ignored
  directory. Publish only generic, synthetic examples.
- Generate timestamps from the runtime clock, not from memory. Keep reported-at
  distinct from job start/end times.
- Distinguish `sent`, `read`, `ACK`, `job exited`, `artifact verified` and
  `accepted`. Each is separate evidence.
- A missing live process means neither "never started" nor "failed". Reconcile
  launch/start/exit receipts, output paths and process identity before
  reporting status.

## Failure handling

- If a frontend exited before consuming steering, dispatch a new bounded
  assignment after reconciling any remaining job; do not keep resending the
  same unread instruction.
- If evidence shows a worker acting outside its assigned identity or scope,
  reconcile the actual process and affected operation. Interrupt an owned
  process only when needed to stop that violation, honor an explicit stop, or
  recover a confirmed failure. ACK lateness alone is not such evidence. Preserve
  valid work and reconcile remaining jobs before any replacement launch.
- If the inbox contains an incomplete or conflicting instruction, ACK the
  material correction and record the lapse; do not silently reinterpret it.
