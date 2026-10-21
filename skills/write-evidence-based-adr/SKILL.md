---
name: write-evidence-based-adr
description: Write or review an architecture decision record grounded in the actual problem, alternatives, observed evidence and implementation status. Use for ADRs or explaining a consequential design choice; ordinary prose edits do not need an ADR.
---

# Write an evidence-based ADR

Make it possible for a later reader to understand why a decision was reasonable, what it commits to, and what remains unproved.

- Read the existing ADR convention and relevant implementation, issue discussion, and measurements. Honor the user's destination, language, and scope; do not impose a repository layout or create an issue merely to fill a template.
- Recover the concrete trigger and constraints. Separate observed behavior, a stakeholder requirement, an interpretation, and a proposed design. Attach source locations to material claims. Preserve stated must-have and desirable requirements. Resolve differences in role, time, or decision status before calling two sources contradictory. If adding acceptance checks or an execution order, label them as your recommendations unless the source actually assigns them to a stakeholder; source silence does not establish approval or refusal.
- Record the decision's actual status. A recommendation is not an accepted decision; an accepted decision is not an implementation; an interface definition or unit test is not evidence that the real consumer uses it.
- Compare plausible alternatives, including retaining the current approach when viable. Tie benefits and costs to the observed problem. Do not treat a design slogan, inheritance count, or fashionable pattern as sufficient justification.
- For a boundary change, identify producer/consumer responsibilities, required information, failure behavior, and external contracts that should remain stable. Check how the contract is exercised in the actual path. Do not prescribe a particular language, protocol system, or architecture to every project.
- Link a design principle to a practical question, the evidence that would answer it, and the next decision that evidence enables. Reuse existing work items where appropriate. Keep structural choices separate from parameters still awaiting measurement.
- State consequences, migration/compatibility concerns, what existing checks establish, and what they do not cover. Label proposed checks as future work. For numerical measurement or comparison claims, retain the population, conditions, and version where relevant; unlike measurements need not imply a winner. State design targets, deadlines, and requirements as such rather than treating them as measured results.

Use the repository's format. Otherwise keep a compact record of context/constraints, status and decision, alternatives with reasons, consequences/verification, and unresolved questions or conditions for revisiting. Give detail only where it changes the decision. A small decision needs a small record.

Before finishing, trace each major conclusion to a source or label it as a recommendation. Check that the requested decision is addressed, implementation is not overstated, and the next evidence-gathering step has a clear purpose. Distinguish your recommendation from a documented organizational decision. Respect existing user authorization without adding new approval steps.
