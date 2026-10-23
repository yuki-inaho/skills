"""Whole-tree public text scan.

This is evidence for human review, not a publication approval gate. It reports
category counts and filenames only; matched values are never printed or stored.
It scans every Git-tracked public text file plus intended new files that Git can
see (untracked, non-ignored). Binary files and ignored private work directories
are skipped.

The default scope is explicit: outside a Git work tree, or when the Git index
cannot be read, the scan refuses with exit code 2 instead of recursively widening
the scope. A candidate path that resolves outside the repository (for example a
symlink) is refused for the same reason.

Public URL namespaces (for example a public forge URL) are not classified as
private by themselves. The patterns below are generic data classes, not a list
of real private values.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS: dict[str, re.Pattern[str]] = {
    "local_absolute_path": re.compile(r"(?<![\w~])/(?:home|Users|root)/[\w.@+-]+"),
    "email_address": re.compile(r"\b[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,}\b"),
    "secret_like_token": re.compile(
        r"\b(?:sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{16,})\b"
    ),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


@dataclass(frozen=True)
class Classification:
    category: str
    path: str


class ScanScopeError(RuntimeError):
    """The public scan scope could not be established without guessing."""


def _is_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _resolved_inside(root: Path, path: Path) -> Path:
    """Resolve *path* and refuse anything outside *root* (including symlinks)."""
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ScanScopeError(f"cannot resolve public candidate: {path.name}") from error
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ScanScopeError(
            f"public candidate escapes the repository boundary: {path.name}"
        ) from None
    return resolved


def _git_candidates(root: Path) -> list[Path]:
    """Return tracked and intended-new paths, or refuse without a fallback."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ScanScopeError(
            f"cannot enumerate Git-tracked/intended-new files under {root}; "
            "refusing to fall back to a recursive scan"
        ) from error
    relative = [item for item in result.stdout.decode("utf-8").split("\0") if item]
    return [root / item for item in relative]


def public_text_files(root: Path = ROOT) -> list[Path]:
    """Return Git-tracked plus intended-new text files, sorted for repeatability.

    A missing Git work tree, an unreadable index or a candidate that resolves
    outside the repository raises ``ScanScopeError``; the scope is never widened
    implicitly.
    """
    root = root.resolve()
    files: list[Path] = []
    for path in _git_candidates(root):
        resolved = _resolved_inside(root, path)
        if not resolved.is_file():
            continue
        try:
            data = resolved.read_bytes()
        except OSError as error:
            raise ScanScopeError(f"cannot read public candidate: {path.name}") from error
        if not _is_text(data):
            continue
        files.append(path)
    return sorted(files)


def classify_text(text: str, path: str = "<text>") -> list[Classification]:
    hits: list[Classification] = []
    for category, pattern in PATTERNS.items():
        for _match in pattern.finditer(text):
            hits.append(Classification(category=category, path=path))
    return hits


def scan(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve()
    files = public_text_files(root)
    hits: list[Classification] = []
    for path in files:
        resolved = _resolved_inside(root, path)
        relative = path.relative_to(root).as_posix()
        try:
            text = resolved.read_text(encoding="utf-8")
        except OSError as error:
            raise ScanScopeError(f"cannot read public candidate: {relative}") from error
        hits.extend(classify_text(text, relative))
    categories: dict[str, dict[str, object]] = {
        category: {"count": 0, "files": []} for category in PATTERNS
    }
    for hit in hits:
        bucket = categories[hit.category]
        bucket["count"] = int(bucket["count"]) + 1
        files_list = bucket["files"]
        assert isinstance(files_list, list)
        if hit.path not in files_list:
            files_list.append(hit.path)
    return {
        "scanned_files": [path.relative_to(root).as_posix() for path in files],
        "scanned_count": len(files),
        "categories": categories,
        "note": "evidence only; zero hits is not a safety declaration",
    }


def format_report(report: dict[str, object]) -> str:
    lines = [f"scanned public text files: {report['scanned_count']}"]
    categories = report["categories"]
    assert isinstance(categories, dict)
    for category, bucket in categories.items():
        assert isinstance(bucket, dict)
        files = bucket["files"]
        assert isinstance(files, list)
        shown = ", ".join(files) if files else "none"
        lines.append(f"{category}: {bucket['count']} ({shown})")
    lines.append(str(report["note"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report generic privacy classes in public text.")
    parser.add_argument("--root", default=str(ROOT), help="repository root (default: this repo)")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)
    try:
        report = scan(Path(args.root).resolve())
    except ScanScopeError as error:
        print(f"privacy_scan: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(report))
    # Evidence only: a hit is for human review, never an automatic approval gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
