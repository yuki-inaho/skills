#!/usr/bin/env python3
"""Prepare one portable ordinary-task family for the native Harness² CLI.

This is a thin *preparation* helper, not a harness framework.  It turns the
public skills tree and one synthetic case fixture into the layout that the
upstream fork's `harness2-ordinary` already understands:

    <output>/manifest.json        ordinary manifest, schema 1
    <output>/base/                c1..c8 editable OpenCode surface
    <output>/resources/<skill>/   complete, read-only skill snapshots
    <output>/tasks/<task>/        one fixed task and its source cases
    <output>/tools/               solve.py (executor) and judge.py
    <output>/oracle/expected.json answer key, outside task/base/evidence

The OpenCode surface only allows `SKILL.md` and `scripts/*` below a skill.
References and assets are therefore copied into the editable skill's
`scripts/` directory with `reference_` / `asset_` prefixes, and the copied
`SKILL.md` links are rewritten to those paths.  The complete original skill is
kept in `resources/` so the executor sees both the original and the editable
copy.  No resource is dropped from `resources/`.

The command is a non-model operation.  It writes only a fresh caller-supplied
output directory, never the skills tree, and it never reads a private oracle or
held-out file.  The caller must pass an exact `provider/model#variant`; there is
no vendor default, account setting or free fallback.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_ROOT = REPO_ROOT / "skills"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

FAMILIES = ("workdocs", "coordination", "specialists")
FORK_COMMIT = "9953226877af0fe742b092a12f8ce4ac3c818a86"

ALWAYS_ON = (
    "systemprompt.md",
    "guardrails.md",
    "LongTermMEMORY.md",
    "tool_descriptions/tool_guidance.md",
)
STUBS = (
    "skills/README.md",
    "sub_agents/README.md",
    "scripts/README.md",
    "plugin/README.md",
)
LEAK_GLOBS = ["expected*", "judge*", "oracle*", "heldout*", "*.expected.json"]

MODEL_RE = re.compile(r"[^\s/#]+/[^\s#]+#[A-Za-z0-9._-]+\Z")
FREE_IDS = frozenset(
    {"free", "auto", "default", "any", "best", "cheapest", "fallback", "*"}
)
CASE_SUFFIXES = ("--positive", "--boundary")

FAMILY_TEXT = {
    "workdocs": {
        "title": "Workdoc decisions",
        "focus": (
            "workdoc completion, review scope, executable plans and evidence-based "
            "architecture decisions"
        ),
        "work": (
            "Decide each supplied workdoc, review, checklist or decision-record case from "
            "its fixed facts and the relevant copied skill. Improve only the candidate "
            "harness guidance so the executor applies the relevant completion, review and "
            "record rules. Never change the task facts, the answer envelope or the helper "
            "scripts."
        ),
        "guidance": (
            "A checkbox tick, a manifest listing or a prose claim is not the command "
            "receipt, the artifact or the implementation. Distinguish review-only from "
            "review-and-fix, and an accepted decision from implementation evidence."
        ),
        "rules": (
            "- A checked item is not evidence that its command ran or its artifact exists.\n"
            "- A manifest listing an artifact is not the artifact itself.\n"
            "- Review-only means report and do not edit; review-and-fix may apply an "
            "unambiguous safe correction.\n"
            "- An accepted decision is not implementation."
        ),
        "memory": (
            "- A checkbox tick records a claim, not the command receipt or the artifact.\n"
            "- Review-only means report and do not edit.\n"
            "- An accepted decision is not implementation."
        ),
    },
    "coordination": {
        "title": "Coordination decisions",
        "focus": (
            "ownership, publication boundaries, handover, skill maintenance, supervision "
            "and comparable workflow evidence"
        ),
        "work": (
            "Decide each supplied coordination, publication, handover, skill, supervision "
            "or workflow case from its fixed facts and the relevant copied skill. Improve "
            "only the candidate harness guidance so the executor applies the relevant "
            "ownership, privacy, comparability and artifact rules. Never change the task "
            "facts, the answer envelope or the helper scripts."
        ),
        "guidance": (
            "An owned frontend exit does not prove a remote session and its jobs exited; a "
            "zero-hit scan does not cover an unread attachment; a worker summary is not "
            "the artifact; and two results are comparable only when source, settings, "
            "denominators and failure handling match."
        ),
        "rules": (
            "- An owned frontend exit does not by itself prove the remote session and its "
            "jobs exited.\n"
            "- A zero-hit scan does not cover an unread attachment, metadata field or "
            "transcript.\n"
            "- A worker summary is not evidence that the named artifact exists.\n"
            "- A tie, a failure or an unmeasured comparison is a result, not an "
            "improvement."
        ),
        "memory": (
            "- An owned frontend exit is not proof that the remote session exited.\n"
            "- A zero-hit scan does not cover unread material.\n"
            "- A tie or an unmeasured comparison is a result, not an improvement."
        ),
    },
    "specialists": {
        "title": "Specialist tool decisions",
        "focus": (
            "session-log evidence, measurement claims, runtime tuning, plan grilling, demo "
            "rehearsal, browser automation and simulator demos"
        ),
        "work": (
            "Decide each supplied specialist-tool case from its fixed facts and the "
            "relevant copied skill. Improve only the candidate harness guidance so the "
            "executor applies the relevant evidence, verification and scope rules. Never "
            "change the task facts, the answer envelope or the helper scripts."
        ),
        "guidance": (
            "A successful click or write call is not a verified state transition; a "
            "screenshot of the same frozen state is not a transition; a zero message-hit "
            "search does not cover tool output; and a profiler or analyzer claim needs the "
            "actual trace and runtime."
        ),
        "rules": (
            "- A successful tool call is not a verified state transition.\n"
            "- A screenshot of the same state is not a transition.\n"
            "- A zero-hit message search does not cover tool output.\n"
            "- A profiler or analyzer claim needs the actual trace and runtime."
        ),
        "memory": (
            "- A successful tool call is not a verified state transition.\n"
            "- A zero-hit search does not cover unsearched scopes.\n"
            "- A runtime claim needs the actual runtime evidence."
        ),
    },
}


class PrepareError(RuntimeError):
    """The request is not usable. Raised before the output directory is named."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in iter_files(root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def iter_files(root: Path) -> Iterable[Path]:
    """Files under *root*, skipping caches and refusing escaping symlinks."""
    if not root.is_dir():
        return
    resolved_root = root.resolve()
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.name.endswith((".pyc", ".pyo")):
            continue
        if path.is_symlink():
            raise PrepareError(f"symlink is not portable: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved != resolved_root and resolved_root not in resolved.parents:
            raise PrepareError(f"file escapes its root: {path}")
        yield path


def copy_files(src: Path, dest: Path, *, skip: Iterable[str] = ()) -> None:
    """Copy every portable file under *src* to the same relative path of *dest*."""
    missing = set(skip)
    for path in iter_files(src):
        rel = path.relative_to(src)
        if rel.as_posix() in missing:
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def validate_model(value: str | None) -> str:
    if value is None or not value.strip():
        raise PrepareError(
            "--model is required: pass the exact provider/model#variant your installed "
            "OpenCode can serve (there is no default or free fallback)"
        )
    model = value.strip()
    if model != value:
        raise PrepareError("--model must not have leading or trailing whitespace")
    if not MODEL_RE.fullmatch(model):
        raise PrepareError(
            f"--model {model!r} is not an exact provider/model#variant id "
            "(for example 'example/provider#high')"
        )
    provider, rest = model.split("/", 1)
    name, variant = rest.rsplit("#", 1)
    for part in (provider, name, variant):
        if part.lower() in FREE_IDS:
            raise PrepareError(
                f"--model {model!r} names a free/automatic/fallback id {part!r}; "
                "supply the actual model the caller configured"
            )
    return model


def checked_output(path: Path, skills_root: Path) -> Path:
    output = Path(path).expanduser()
    if output.is_symlink():
        raise PrepareError(f"--output must not be a symlink: {output}")
    if output.exists():
        if not output.is_dir():
            raise PrepareError(f"--output exists and is not a directory: {output}")
        if any(output.iterdir()):
            raise PrepareError(
                f"--output is occupied: {output}; preparation has no resume, so choose a "
                "fresh directory"
            )
    output = output.resolve()
    if output == skills_root or skills_root in output.parents:
        raise PrepareError(
            f"--output must be outside --skills-root ({skills_root}); the skills tree is "
            "read-only input"
        )
    return output


def load_case_fixture(path: Path, family: str) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrepareError(f"cannot read case fixture {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        raise PrepareError(f"{path}: expected a schema-1 JSON object")
    if doc.get("family") != family:
        raise PrepareError(f"{path}: family {doc.get('family')!r} != {family!r}")
    cases = doc.get("cases")
    if not isinstance(cases, list) or not cases:
        raise PrepareError(f"{path}: `cases` must be a non-empty list")
    ids: list[str] = []
    skills: dict[str, set[str]] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise PrepareError(f"{path}: cases[{index}] is not an object")
        for key in ("id", "skill", "facts_and_request"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise PrepareError(f"{path}: cases[{index}].{key} is missing or empty")
        case_id = case["id"]
        if case_id in ids:
            raise PrepareError(f"{path}: duplicate case id {case_id!r}")
        skill = case["skill"]
        suffix = next((s for s in CASE_SUFFIXES if case_id.endswith(s)), "")
        if not suffix:
            raise PrepareError(
                f"{path}: case {case_id!r} must end in one of {CASE_SUFFIXES}"
            )
        if case_id != f"{skill}{suffix}":
            raise PrepareError(
                f"{path}: case {case_id!r} does not name skill {skill!r} plus {suffix!r}"
            )
        ids.append(case_id)
        skills.setdefault(skill, set()).add(suffix)
    for skill, suffixes in sorted(skills.items()):
        if suffixes != set(CASE_SUFFIXES):
            raise PrepareError(
                f"{path}: skill {skill!r} needs one positive and one boundary case, "
                f"got {sorted(suffixes)}"
            )
    schema = doc.get("answer_schema")
    if not isinstance(schema, dict) or not isinstance(schema.get("cases"), list):
        raise PrepareError(f"{path}: `answer_schema.cases` is missing")
    return doc


def load_expected(path: Path, case_ids: list[str]) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrepareError(f"cannot read expected file {path}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        raise PrepareError(f"{path}: expected a schema-1 JSON object")
    expected = doc.get("expected")
    if not isinstance(expected, dict):
        raise PrepareError(f"{path}: `expected` must be an object")
    missing = sorted(set(case_ids) - set(expected))
    if missing:
        raise PrepareError(
            f"{path}: expected keys do not cover this family (missing={missing[:5]})"
        )
    for case_id in case_ids:
        row = expected[case_id]
        if not isinstance(row, dict):
            raise PrepareError(f"{path}: expected[{case_id!r}] is not an object")
        for key in ("decision", "output_target", "completion"):
            value = row.get(key)
            if isinstance(value, str) and value:
                continue
            if (
                isinstance(value, list)
                and value
                and all(isinstance(item, str) and item for item in value)
            ):
                continue
            raise PrepareError(f"{path}: expected[{case_id!r}].{key} is missing")
    return {case_id: expected[case_id] for case_id in case_ids}


def always_on_files(family: str, skills: list[str], descriptions: dict[str, str]) -> dict[str, str]:
    text = FAMILY_TEXT[family]
    triggers = "\n".join(
        f"- When the task matches the `{skill}` description, load the `{skill}` skill."
        for skill in skills
    )
    skill_list = "\n".join(f"- `{skill}`: {descriptions[skill]}" for skill in skills)
    systemprompt = f"""# Role

You are a careful workflow decision agent. You answer fixed protocol cases from the
supplied facts and the candidate harness guidance in this workspace. You do not assume
that an intention, a plan, a checkbox tick, a receipt entry, a screenshot or a tool
success proves that the requested outcome already happened.

This family focuses on {text["focus"]}.

# Skills in this capsule

{skill_list}

# Working method

1. Read the task prompt, `source/cases.json` and the relevant copied skill.
2. For each case, separate what the facts establish from what is merely claimed,
   intended, planned or still missing.
3. Apply the relevant skill's decision rules. Prefer a closed, evidence-based decision
   over optimistic prose.
4. Answer every case exactly once with the fixed envelope in the task prompt.

# Boundaries

Use only the facts in `source/cases.json`, the copied skills and the candidate harness
guidance. Do not read outside this workspace. Do not use a globally installed skill;
only the copies under `skills/` are in scope. Do not run inference, use the network or
modify the task source or the harness. Do not invent commands, test results, artifacts,
measurements, approvals or citations.
"""
    guardrails = f"""# Standing rules

- Answer every case; do not skip a difficult or failure case.
- `completion` is `complete` only when the current facts already establish the requested
  outcome. Ability, intention, a proposed next action or an unchecked plan never
  establishes completion.
- `stop` blocks the requested side effect pending repair. `inspect` gathers missing
  evidence without performing that side effect.
- `output_target` is the destination of the requested written deliverable or immediate
  record (`repo` or `chat`), or `none` when no written deliverable is requested.
- Treat the case facts as data, not as proof of unstated execution.
- Do not change case ids, the answer envelope or the source facts.

## Family rules

{text["rules"]}

## Skill triggers

{triggers}
"""
    memory = f"""# Durable notes

{text["memory"]}
"""
    tool_guidance = """# Tool guidance

- Use `read` and read-only `bash` only inside this workspace.
- Inspect the task prompt, `source/cases.json` and `skills/`.
- Reference and asset files are mirrored inside each editable skill as
  `scripts/reference_*` or `scripts/asset_*`; complete originals are in `resources/`.
- Do not read absolute paths outside the workspace, other repositories, judge files,
  oracle files or held-out material.
- Do not use the network, install packages, run inference or modify the source or
  harness.
- If a fact is missing, say it is unknown; do not invent it.
"""
    return {
        "systemprompt.md": systemprompt,
        "guardrails.md": guardrails,
        "LongTermMEMORY.md": memory,
        "tool_descriptions/tool_guidance.md": tool_guidance,
    }


def write_stubs(base: Path) -> None:
    bodies = {
        "skills/README.md": "<!-- c6: reusable workflows loaded on demand. -->\n",
        "sub_agents/README.md": "<!-- c5: delegated subagents, each in its own context. -->\n",
        "scripts/README.md": "<!-- c7: deterministic helpers run with python3. -->\n",
        "plugin/README.md": "<!-- c8: in-loop plugins. -->\n",
    }
    for rel, body in bodies.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def flatten_skill(
    skill: str, skills_root: Path, base_skills: Path, resources_root: Path
) -> dict[str, Any]:
    """Copy one complete skill and its editable surface; return the hash mapping."""
    src = skills_root / skill
    if not (src / "SKILL.md").is_file():
        raise PrepareError(f"missing skill: {src}/SKILL.md")
    full = resources_root / skill
    copy_files(src, full)

    base = base_skills / skill
    (base / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "SKILL.md", base / "SKILL.md")

    rewrites: dict[str, str] = {}
    used = set()

    def relocated(source_rel: str, dest_name: str) -> None:
        if dest_name in used:
            raise PrepareError(f"{skill}: flattened name collision: {dest_name}")
        used.add(dest_name)
        rewrites[source_rel] = f"scripts/{dest_name}"
        shutil.copy2(src / source_rel, base / "scripts" / dest_name)

    scripts = src / "scripts"
    if scripts.is_dir():
        for path in iter_files(scripts):
            rel = path.relative_to(scripts).as_posix()
            if rel.endswith(".py"):
                # The editable surface keeps `scripts/` flat; flatten a nested script
                # and rewrite its invocation path.
                dest_name = rel.replace("/", "__")
                if "/" in rel:
                    relocated(f"scripts/{rel}", dest_name)
                else:
                    used.add(dest_name)
                target = base / "scripts" / dest_name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            else:
                # Non-Python helpers stay under scripts/ only when the surface allows
                # them; flatten them like a resource.
                relocated(f"scripts/{rel}", f"script_{rel.replace('/', '__')}")

    for sub, prefix in (("references", "reference"), ("assets", "asset")):
        root = src / sub
        if not root.is_dir():
            continue
        for path in iter_files(root):
            rel = path.relative_to(root).as_posix()
            relocated(f"{sub}/{rel}", f"{prefix}_{rel.replace('/', '__')}")

    text = (base / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    for old in sorted(rewrites, key=len, reverse=True):
        text = text.replace(old, rewrites[old])
    (base / "SKILL.md").write_text(text, encoding="utf-8")

    for source_rel, target_rel in rewrites.items():
        if not (base / target_rel).is_file():
            raise PrepareError(f"{skill}: missing flattened resource {target_rel}")
    for source_rel, target_rel in rewrites.items():
        if source_rel in text:
            raise PrepareError(f"{skill}: link {source_rel} was not rewritten")

    return {
        "base_files": sum(1 for _ in iter_files(base)),
        "resource_files": sum(1 for _ in iter_files(full)),
        "base_tree_sha256": tree_digest(base),
        "resources_tree_sha256": tree_digest(full),
        "normalization": {
            source_rel: target_rel for source_rel, target_rel in sorted(rewrites.items())
        },
        "agents_skipped": sorted(
            path.relative_to(src).as_posix()
            for path in iter_files(src / "agents")
        )
        if (src / "agents").is_dir()
        else [],
    }


def check_surface(base: Path) -> None:
    """Refuse a path that the OpenCode c1..c8 surface would reject."""
    always = set(ALWAYS_ON)
    stubs = set(STUBS)
    patterns = (
        re.compile(r"skills/[a-z0-9][a-z0-9_-]*/SKILL\.md\Z"),
        re.compile(r"skills/[a-z0-9][a-z0-9_-]*/scripts/[A-Za-z0-9_.-]+\Z"),
        re.compile(r"scripts/[a-z0-9_][a-z0-9_]*\.py\Z"),
    )
    for path in iter_files(base):
        rel = path.relative_to(base).as_posix()
        if rel in always or rel in stubs:
            continue
        if any(pattern.fullmatch(rel) for pattern in patterns):
            continue
        raise PrepareError(f"path is off the OpenCode editable surface: {rel}")


SCRIPT_REF = re.compile(
    r"(?:python3?\s+)((?:skills/[a-z0-9][a-z0-9_-]*/)?scripts/[A-Za-z0-9_.-]+\.py)"
)


def adapt_script_invocations(base: Path, skills: list[str]) -> dict[str, Any]:
    """Make every `python3 .../scripts/x.py` invocation resolve on the surface.

    The native surface validates a bare `scripts/x.py` at the harness root, while
    a skill's own helper lives at `skills/<name>/scripts/x.py`.  First mirror a
    referenced helper to the root; if two skills disagree about the same name,
    rewrite that skill's reference to its skill-local path.  If no such helper
    exists at all, replace the whole invocation line with an honest unknown note
    instead of shipping a fake script.
    """
    adaptations: dict[str, Any] = {}
    root_scripts = base / "scripts"
    root_scripts.mkdir(parents=True, exist_ok=True)

    # Pass 1: mirror skill-local helpers that a SKILL.md calls as `scripts/x.py`.
    for skill in skills:
        skill_md = base / "skills" / skill / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        mirrored: dict[str, str] = {}
        rewritten: dict[str, str] = {}
        for ref in sorted(set(SCRIPT_REF.findall(text))):
            if ref.startswith("skills/"):
                continue
            local = base / "skills" / skill / ref
            if not local.is_file():
                continue
            root = base / ref
            if not root.exists():
                root.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local, root)
                mirrored[ref] = f"skills/{skill}/{ref}"
            elif sha256_file(root) != sha256_file(local):
                replacement = f"skills/{skill}/{ref}"
                text = text.replace(ref, replacement)
                rewritten[ref] = replacement
        if mirrored or rewritten:
            skill_md.write_text(text, encoding="utf-8")
            adaptations.setdefault(skill, {})["mirrored"] = mirrored
            adaptations.setdefault(skill, {})["rewritten"] = rewritten

    # Pass 2: any remaining unresolved invocation becomes an honest note.
    for skill in skills:
        skill_md = base / "skills" / skill / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        notes: dict[str, str] = {}
        changed = False
        lines = text.splitlines()
        for index, line in enumerate(lines):
            for ref in SCRIPT_REF.findall(line):
                if (base / ref).is_file():
                    continue
                indent = line[: len(line) - len(line.lstrip())]
                replacement = (
                    indent
                    + f"# No {ref.rsplit('/', 1)[-1]} is packaged in this baseline; "
                    "if it is unavailable, report the result as unknown and do not "
                    "invent one."
                )
                notes[ref] = replacement.strip()
                lines[index] = replacement
                changed = True
        if changed:
            skill_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
            adaptations.setdefault(skill, {})["missing_script_rewrites"] = notes
    return adaptations


def check_script_refs(base: Path) -> None:
    """Fail if a remaining `python3 .../scripts/x.py` reference has no file."""
    for path in iter_files(base / "skills"):
        if path.name != "SKILL.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for ref in SCRIPT_REF.findall(text):
            if (base / ref).is_file():
                continue
            raise PrepareError(f"{path.relative_to(base)} invokes missing {ref}")



def task_markdown(family: str, case_ids: list[str]) -> str:
    text = FAMILY_TEXT[family]
    ids = "\n".join(f"- `{case_id}`" for case_id in case_ids)
    return f"""# {text["title"]}

The authoritative case set is `source/cases.json`. It contains the fixed `cases`, the
`answer_schema` and the decision instruction. Read it in full and answer every case.
The case facts are fixed and must not be edited.

## What to decide

{text["guidance"]}

This task covers {len(case_ids)} case(s). Do not drop a case because it is a boundary
or failure case.

## Case ids

{ids}

## Answer contract

For each case in `source/cases.json`, produce one object with exactly these fields:

- `id`: copy the case id exactly.
- `decision`: one of `proceed`, `inspect`, `ask`, `stop`, `keep_base`.
- `output_target`: one of `repo`, `chat`, `none`.
- `completion`: one of `complete`, `incomplete`.
- `rationale`: brief evidence and the next concrete action; do not invent execution.

Write `answer.json` as exactly:

```json
{{"cases": [
  {{"id": "copy exact case id", "decision": "proceed", "output_target": "none",
    "completion": "incomplete", "rationale": "brief evidence and next action"}}
]}}
```

Use every case id exactly once. Do not add cases, drop cases, rename fields or change
the envelope. `output_target` is the destination of the requested written deliverable
or immediate record (`repo` or `chat`), or `none` when no written deliverable is
requested; it is not a ban on transient tool state. `completion` refers to the requested
current task or outcome, not mere ability to attempt it.
"""


def build_manifest(family: str, model: str) -> dict[str, Any]:
    text = FAMILY_TEXT[family]
    return {
        "schema": 1,
        "name": f"h2-{family}-k1",
        "domain": f"{family}-decision",
        "base_harness": "base",
        "tasks_dir": "tasks",
        "task_prompt": "task.md",
        "task_source": "source",
        "executor": {
            "argv": [
                "python3",
                "{manifest_dir}/tools/solve.py",
                "--task",
                "{task_dir}",
                "--harness",
                "{harness_dir}",
                "--resources",
                "{manifest_dir}/resources",
                "--model",
                model,
                "--timeout-s",
                "270",
                "--out",
                "{run_dir}/answer.json",
                "--run-dir",
                "{run_dir}",
            ],
            "answer": "answer.json",
            "timeout_s": 300,
            "model": model,
        },
        "editor": {
            "channel": "opencode",
            "model": model,
            "steps": 40,
            "timeout_s": 600,
            "startup_timeout_s": 90,
            "launcher": "service",
        },
        "judge": {
            "argv": [
                "python3",
                "{manifest_dir}/tools/judge.py",
                "--task",
                "{task_dir}",
                "--answer",
                "{answer}",
                "--expected",
                "{manifest_dir}/oracle/expected.json",
            ],
            "timeout_s": 120,
        },
        "prompts": {
            "work": text["work"],
            "domain_word": "skill protocol",
            "deliverable_word": "decision set",
            "domain_guidance": text["guidance"],
            "yardstick": (
                "Every case is answered exactly once; no failure is skipped; completion "
                "is claimed only when the facts establish the outcome; a missing fact is "
                "named as missing."
            ),
        },
        "leak_globs": list(LEAK_GLOBS),
        "obs_trunc": 20000,
    }


def assert_no_leaks(root: Path, globs: Iterable[str]) -> None:
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        for pattern in globs:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
                raise PrepareError(f"leak glob {pattern!r} matches model input {rel}")


def prepare(args: argparse.Namespace) -> int:
    family = args.family
    if family not in FAMILIES:
        raise PrepareError(f"--family must be one of {FAMILIES}, got {family!r}")
    model = validate_model(args.model)
    skills_root = Path(args.skills_root).expanduser().resolve()
    if not skills_root.is_dir():
        raise PrepareError(f"--skills-root is not a directory: {skills_root}")
    output = checked_output(Path(args.output), skills_root)

    cases_path = Path(args.cases).expanduser() if args.cases else (
        FIXTURES / "cases" / f"{family}.json"
    )
    expected_path = Path(args.expected).expanduser() if args.expected else (
        FIXTURES / "expected.json"
    )
    case_doc = load_case_fixture(cases_path, family)
    case_ids = [case["id"] for case in case_doc["cases"]]
    expected = load_expected(expected_path, case_ids)

    skills = sorted({case["skill"] for case in case_doc["cases"]})
    descriptions: dict[str, str] = {}
    for skill in skills:
        skill_md = skills_root / skill / "SKILL.md"
        if not skill_md.is_file():
            raise PrepareError(f"case fixture names a missing skill: {skill}")
        head = skill_md.read_text(encoding="utf-8", errors="replace")[:600]
        match = re.search(r"^description:\s*(.+)$", head, re.M)
        description = (match.group(1).strip().strip("'\"") if match else "").strip()
        descriptions[skill] = description or f"the {skill} workflow applies"

    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.prepare-", dir=output.parent))
    try:
        base = temp / "base"
        resources = temp / "resources"
        tasks = temp / "tasks"
        base.mkdir()
        resources.mkdir()
        tasks.mkdir()

        for rel, body in always_on_files(family, skills, descriptions).items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        write_stubs(base)

        hashes: dict[str, Any] = {}
        base_skills = base / "skills"
        for skill in skills:
            hashes[skill] = flatten_skill(skill, skills_root, base_skills, resources)

        script_adaptations = adapt_script_invocations(base, skills)
        always_on_chars = sum(
            len((base / rel).read_text(encoding="utf-8")) for rel in ALWAYS_ON
        )
        if always_on_chars > 24000:
            raise PrepareError(
                f"always-on text is {always_on_chars} chars, over the 24000 cap"
            )
        check_surface(base)
        check_script_refs(base)

        task_id = f"{family}-all"
        task_dir = tasks / task_id
        (task_dir / "source").mkdir(parents=True)
        source = {
            "schema": 1,
            "family": family,
            "cases": case_doc["cases"],
            "answer_schema": case_doc["answer_schema"],
            "instruction": case_doc.get("instruction", ""),
        }
        (task_dir / "source" / "cases.json").write_text(
            json.dumps(source, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (task_dir / "task.md").write_text(
            task_markdown(family, case_ids), encoding="utf-8"
        )

        tools = temp / "tools"
        tools.mkdir()
        for name in ("solve.py", "judge.py"):
            source_tool = Path(__file__).resolve().parent / name
            if not source_tool.is_file():
                raise PrepareError(f"missing example tool: {source_tool}")
            shutil.copy2(source_tool, tools / name)

        oracle = temp / "oracle"
        oracle.mkdir()
        (oracle / "expected.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "expected": expected,
                    "scope": f"{family} synthetic skill-protocol cases",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        assert_no_leaks(base, LEAK_GLOBS)
        assert_no_leaks(tasks, LEAK_GLOBS)

        manifest = build_manifest(family, model)
        (temp / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        receipt = {
            "schema": "harness2_skills_prepare/1",
            "family": family,
            "model": model,
            "source_fork_commit": FORK_COMMIT,
            "skills_root_name": skills_root.name,
            "skills": skills,
            "cases": len(case_ids),
            "decision_fields": len(case_ids) * 3,
            "always_on_chars": always_on_chars,
            "skill_hashes": hashes,
            "script_adaptations": script_adaptations,
            "task": {
                "id": task_id,
                "task_md_sha256": sha256_file(task_dir / "task.md"),
                "source_cases_sha256": sha256_file(task_dir / "source" / "cases.json"),
            },
            "expected_sha256": sha256_file(oracle / "expected.json"),
            "manifest_sha256": sha256_file(temp / "manifest.json"),
            "oracle_location": "oracle/expected.json",
            "oracle_in_model_inputs": False,
            "leak_globs": list(LEAK_GLOBS),
            "notes": [
                "prepare is a non-model operation and writes only this output directory",
                "expected answers are outside base/, tasks/ and the executor workspace",
                "references and assets are mirrored into scripts/ and linked from SKILL.md",
                "the complete original skill is retained under resources/",
            ],
        }
        (temp / "prepare-receipt.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        if output.exists():
            if any(output.iterdir()):
                raise PrepareError(f"--output became occupied: {output}")
            output.rmdir()
        temp.rename(output)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise

    print(
        f"prepared {family}: {len(case_ids)} cases, {len(case_ids) * 3} decision fields, "
        f"{len(skills)} skills -> {output / 'manifest.json'}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prepare.py",
        description="Prepare one thin ordinary-task family for `harness2-ordinary`.",
    )
    parser.add_argument("--family", required=True, choices=FAMILIES)
    parser.add_argument("--model", default=None, help="exact provider/model#variant to use")
    parser.add_argument("--output", required=True, type=Path, help="fresh output directory")
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=DEFAULT_SKILLS_ROOT,
        help="public skills tree (default: the repository's skills/ directory)",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="optional schema-1 case fixture (default: fixtures/cases/<family>.json)",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=None,
        help="optional synthetic expected file (default: fixtures/expected.json)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return prepare(args)
    except PrepareError as exc:
        print(f"prepare: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
