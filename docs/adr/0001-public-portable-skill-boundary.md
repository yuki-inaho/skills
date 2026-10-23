# 0001 — Public portable skill boundary

- Status: accepted
- Date: 2026-10-23
- Scope: the shared skill collection in this repository

## Context and trigger

A repository audit before this change found that several shared skills treated one
runtime, vendor or model family as the default. The audit also found that the
repository-wide policy already said generic policy and generic skills must not fix a
provider or model. That is a contradiction between the written boundary and the
artifacts a reader or test would actually see.

The existing policy also requires that no private project name, result, path, session or
user identifier appear in any committed surface (source, tests, docs, ADRs, diagrams,
metadata or commits). The audit above showed a contradiction between that written
boundary and the artifacts. The implementation therefore applies the boundary to all
shared skills and uses provider-neutral defaults, synthetic tests and evidence-based
ADRs.

## Evidence

Public, reproducible evidence at the baseline commit `65a0660`:

- `skills/herdr-opencode-agmsg/assets/model_catalog.json` listed three concrete
  providers and several vendor model IDs as the bundled default.
- `tests/test_herdr_opencode_agmsg.py` asserted those concrete IDs, so changing a
  user's real catalog could break a repository test.
- `tests/fixtures/synthetic_opencode_models.txt` was labelled synthetic but contained
  real vendor IDs.
- `skills/start-work-audit-pattern/assets/start-work-audit-template.md` asked the
  reader to self-identify as one of two runtimes and prescribed model tiers for those
  runtimes.
- `skills/supervisor-orchestration` used one runtime's agent names (`explore`,
  `general`) as if they were universal role names.
- `docs/PUBLIC_SKILLS_POLICY.md` already prohibited fixing a provider or model in
  generic policy or generic skills.

These are facts about the public tree, not private project results. No private value
is reproduced here.

## Decision rationale

The existing policy already prohibited fixing a provider or model in generic policy or
generic skills, and the baseline audit showed that several artifacts contradicted that
boundary. The chosen mechanisms (neutral empty catalog, synthetic provider IDs,
capability-based roles and a new ADR set) follow from that contradiction and the existing
policy. The narrower concrete-catalog option is documented below; this ADR does not claim
it was unreasonable.

## Decision

1. Shared skills are **domain/technical portable**: they may name a tool or a technical
   domain, but must not require a private project, dataset, robot, evaluation or
   organisation.
2. Provider and model choices are **user-owned runtime configuration**, not a shared
   default. The bundled catalog is a neutral empty template. An empty catalog stops with
   `catalog_unconfigured`; there is no vendor or model fallback. Real choices use a
   private `--catalog` file outside the public tree.
3. Role vocabulary is **capability-based** (read-only explorer, executor/writer,
   auditor/reviewer), with runtime-specific mapping left to the environment. The user's
   explicit model, platform, roster and delegation take precedence. Two writers must not
   own the same file scope.
4. The private-data prohibition applies to source, examples, tests, fixtures,
   documentation, diagrams, reports, metadata, commit text and PR text/comments. The
   scanner reports categories and filenames only; it never carries a real denylist. Its
   default scope is Git-tracked plus intended-new files; a non-Git root or a path that
   resolves outside the repository is refused rather than scanned implicitly.
5. The change adds **no new approval flow**. A privacy scan is evidence for human
   review, not a publication gate. Existing user authority and repository policy remain
   the decision procedure.

## Accepted decision vs. implementation

Implemented in this change:

- neutral empty catalog plus a synthetic example;
- synthetic provider IDs in tests and fixtures;
- empty-catalog refusal in `provider_plan.py`;
- capability-based role wording in the audit-pattern and supervisor skills;
- policy wording for project-specific skills, non-inherited project assumptions and
  all public surfaces;
- coverage and ADR documentation.

The public test suite and CI are the evidence for this change. They do not include a
live provider, model, Herdr, OpenCode or agmsg run, and the committed evidence contains
no native Harness² model run. This statement is limited to the public CI/tests; it does
not claim that no native Harness or model call was made elsewhere in the wider
programme.

Not implemented in the public evidence, and not claimed:

- no live provider, model, Herdr, OpenCode or agmsg run in the public tests;
- no proof that a real catalog is complete or that a selected model is available;
- no agent-loader compatibility test beyond strict frontmatter parsing;
- no guarantee that a public URL namespace is private or public by itself.

## Alternatives kept

- **Keep the concrete catalog as a clearly labelled example.** This preserves
  out-of-box convenience. It was not chosen as the default because the shipped tests
  would still encode one vendor's inventory as the expected baseline. A user may still
  adopt such a catalog privately via `--catalog`.
- **Move the whole coordination skill to a private profile.** This removes the
  portability question but discards a reusable workflow. It was rejected.
- **Add a mandatory privacy approval gate.** This would overstate what a heuristic scan
  can prove and would add a new approval step. It was rejected.

## Consequences and verification limits

- Out-of-box convenience is lower: a user must supply a real catalog.
- Tests are stable across catalog changes, but they prove only the planner's decision
  logic on synthetic inputs, not any provider's behavior.
- The empty-catalog stop is intentional. A silent vendor fallback would reintroduce the
  boundary violation this ADR removes.
- Prose skills are verified for structure, links and artifact contracts. That does not
  prove their runtime behavior.
- The privacy scanner reduces some false negatives by scanning the whole public text
  tree, but it is heuristic. Zero hits is not a safety declaration.

## Follow-up

- Keep concrete catalogs and project-specific skills in a private workspace.
- When adding a shared skill, start from the portable boundary and a synthetic scenario;
  do not copy project names, results or assumptions into the public tree.
