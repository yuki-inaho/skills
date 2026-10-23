# 0002 — Reproducible validation and evaluation

- Status: accepted
- Date: 2026-10-23
- Scope: the repository test runner, metadata validation, installer tests, privacy
  evidence and the external JSONL contract

## Context and trigger

The repository claimed Codex/Claude Code/OpenCode compatibility and a synthetic-data
test suite, but its validation could stay green while the metadata was invalid. The
documented runner also depended on an ambient Python package. The concrete scope below
comes from the audit of this public repository. The design records the validation
boundary and its limits in ADRs/rules.

## Evidence

Reproducible observations at the baseline commit `65a0660`:

- Six of 21 `SKILL.md` descriptions used an unquoted colon-space sequence. A strict
  YAML loader raised a scanner error; the repository test and bundled validator used a
  regex and accepted them.
- The structural test parametrized only six skill paths, while the tree contained 21
  `SKILL.md` files. Fifteen skills had no strict frontmatter check.
- The bundled validator returned the literal string `>-` as a description for folded
  descriptions and reported no error for the six invalid files.
- The documented `python3 -m pytest tests -q` failed when pytest was not installed
  globally. There was no `pyproject.toml`, lockfile, `justfile` or CI workflow.
- All nine external contract tests skipped when the installed binary reported 0.2.0 and
  did not support `version --output json`.
- The installer test selected six skills and compared only `SKILL.md` bytes.
- The privacy test scanned a hand-picked subset of files.
- The JAX skill referenced `scripts/analyze_trace.py`, which was not bundled, and
  hard-coded tool-specific temporary paths.

These observations are about this public repository. No private result is needed or
reproduced.

## Decision rationale

The audit showed structural gaps that a minimal runner and short checklist would leave
in place: invalid frontmatter could pass, discovery was incomplete, installer evidence
was shallow and the privacy scope was narrow. The chosen mechanisms (locked uv
environment, strict PyYAML parsing, dynamic discovery, synthetic canaries, a pinned
external CLI and per-skill coverage/ADR records) address those observed gaps. The
minimal-runner option remains a documented alternative; this ADR does not claim the
broader choice was the only reasonable one.

## Decision

1. **uv is the source of truth.** `pyproject.toml`, `uv.lock` and `.python-version`
   declare the dev environment. `just` recipes are thin wrappers; the underlying
   `uv run --locked ...` commands are the contract and are used by CI. `just check` is
   one aggregate command for validate, test, privacy and lint/compile. The locked flag
   makes a stale `uv.lock` fail instead of silently using it.
2. **Strict YAML is part of loadability.** Every `SKILL.md` frontmatter parses with a
   safe YAML loader that rejects duplicate keys and non-mapping values. The repository
   test and the bundled validator share that parse path. Recommended headings remain
   advisory; equivalent operational content is allowed.
3. **Discovery is dynamic.** Tests enumerate `skills/*/SKILL.md`; no fixed skill count
   is asserted. A machine-readable coverage manifest must cover every discovered skill,
   and each entry must name a real test and its verification limit.
4. **Installer evidence is recursive.** A synthetic archive is installed into isolated
   destinations and compared by recursive tree hash, including scripts, references,
   assets, licence and agent metadata. Auto-detect, `--dest`, comma lists, `--ref`,
   dry-run, unknown skills and a bad archive layout are covered.
5. **Privacy scanning is whole-tree evidence with an explicit scope.** The scanner
   covers Git-tracked files plus intended new files, reports category counts and
   filenames only, never values, and is tested with synthetic positive and negative
   canaries. Outside a Git work tree, or with an unreadable index, it refuses instead
   of recursively widening the scope; a candidate that resolves outside the repository
   is refused as well. It is not an approval gate and carries no real denylist. Public
   URL namespaces are not private by themselves.
6. **The external contract is required only where the binary is guaranteed.** Local
   runs may skip a missing or old binary. A dedicated CI job installs the pinned 0.3.1
   `x86_64-unknown-linux-musl` asset, verifies the published `.sha256` and a pinned
   digest, and runs with `REQUIRE_AGENT_JSONL=1`, where missing/old/unsupported fails
   rather than skips.
7. **Execution claims stay separate.** Static and artifact tests prove structure and
   document contracts. They do not prove JAX/GPU, browser/WebGL, Docker, live Herdr,
   provider or agmsg runtime behavior.

## Accepted decision vs. implementation

Implemented:

- `pyproject.toml`, `uv.lock`, `.python-version`, `justfile`;
- strict validator and failing tests for colon-space, quoted, folded/block, duplicate
  keys, non-mapping, missing frontmatter and name/description errors;
- dynamic all-skill structural tests and a coverage manifest;
- recursive installer tests over all discovered skills;
- whole-tree privacy scanner with synthetic canaries, refusing non-Git roots and
  escaping symlinks;
- dedicated agent-jsonl 0.3.1 CI job with checksum verification and required mode;
- CI running the same underlying commands as the `just check` aggregate;
- per-skill `docs/skill-coverage.md` and these ADRs.

The public test suite and CI are the evidence for this change. They do not execute
JAX/GPU, browser/WebGL, Docker, live Herdr, provider or agmsg runtime behavior, and the
committed evidence contains no native Harness² model run. This statement is limited to
the public CI/tests; it does not claim that no native Harness or model call was made
elsewhere in the wider programme.

Not implemented in the public evidence, and not claimed:

- no live provider, model, Herdr, OpenCode or agmsg run in the public tests;
- no provider/model availability or quality comparison;
- no claim that every agent loader accepts every skill, only that strict YAML parses;
- no claim that a zero-hit privacy scan is safe;
- the external 0.3.1 contract runs only in its dedicated job/profile, not in a generic
  local run without the binary.

## Alternatives kept

- **`uvx --from pytest` as the only runner.** This reproduces a run without a
  repository environment but does not pin the Python version, PyYAML, ruff or the
  external contract. It remains a stopgap, not the contract.
- **A regex or hand-written YAML subset parser.** This avoids a dependency but repeats
  the original failure mode and cannot reliably handle folded/block scalars or duplicate
  keys. It was rejected in favour of PyYAML plus PEP 723 metadata.
- **A generic CI job that treats skips as success.** This is the behavior the change
  removes for the explicit required case. A skipped contract job is not evidence.

## Consequences and verification limits

- Contributors need uv. `just` is optional. `just check` aggregates the local required
  checks; it does not require the external CLI.
- `--locked` makes a stale lockfile a visible failure rather than a silent run against
  old pins.
- The main test job honestly reports skips when the external binary is absent; the
  dedicated contract job/profile is the place where absence fails.
- Static tests are cheaper and more stable than full runtime tests, but they cannot
  establish runtime correctness. Coverage text must keep that distinction visible.
- The privacy scan is evidence, not proof. Human review still decides publication.
- The pinned asset is platform-specific; other platforms are not claimed by the CI job.

## Follow-up

- When a runtime claim becomes important, add a dedicated, reproducible job for it
  rather than weakening the static contract or hiding a skip.
- When the external CLI changes, update the pinned version, checksum and contract tests
  together.
- Keep new skills in the dynamic discovery and coverage manifest from the start.
