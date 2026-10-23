"""Tests for the whole-tree privacy evidence scanner.

Canaries are synthetic. The report must never echo a matched value, and public
URL namespaces must not be classified as private by themselves. The default
scope is Git-derived and fails closed: non-Git roots and symlinks that escape
the repository are refused instead of being scanned recursively.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import privacy_scan

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "tests" / "privacy_scan.py"

POSITIVE_CANARIES = {
    # Assembled so this public test file does not itself look like a real value.
    "local_absolute_path": "/" + "home/canary-user/example-workspace",
    "email_address": "canary.person" + "@" + "example.com",
    "secret_like_token": "sk-" + "a" * 24,
    "private_key_block": "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
}

NEGATIVE_CANARIES = (
    "~/.config/opencode/skills",
    "/path/to/repo",
    "https://github.com/example-org/example-repo",
    "https://docs.example.dev/reference",
    "<uuid>.jsonl",
    "workdoc_Apr16-2026_example.md",
    "PROVIDER/MODEL#standard",
)


def _git_init(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "example" + "@" + "example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Example"], cwd=root, check=True)


def _run_cli(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), "--root", str(root)],
        capture_output=True,
        text=True,
    )


def test_positive_canaries_are_classified() -> None:
    text = "\n".join(POSITIVE_CANARIES.values())
    categories = {hit.category for hit in privacy_scan.classify_text(text, "canary.txt")}
    assert set(POSITIVE_CANARIES) == categories


def test_negative_canaries_are_not_classified() -> None:
    text = "\n".join(NEGATIVE_CANARIES)
    assert privacy_scan.classify_text(text, "negative.txt") == []


def test_report_names_counts_and_files_but_never_values(tmp_path: Path) -> None:
    _git_init(tmp_path)
    (tmp_path / "positive.txt").write_text(
        "\n".join(POSITIVE_CANARIES.values()), encoding="utf-8"
    )
    subprocess.run(["git", "add", "positive.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    report = privacy_scan.scan(tmp_path)
    rendered = privacy_scan.format_report(report)
    for value in POSITIVE_CANARIES.values():
        assert value not in rendered
    assert "positive.txt" in rendered
    assert "local_absolute_path: 1" in rendered
    assert report["note"] == "evidence only; zero hits is not a safety declaration"


def test_tracked_and_intended_new_files_are_scanned(tmp_path: Path) -> None:
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text("private/\n", encoding="utf-8")
    (tmp_path / "tracked.md").write_text("tracked\n", encoding="utf-8")
    (tmp_path / "intended.md").write_text("intended new file\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01")
    private = tmp_path / "private"
    private.mkdir()
    (private / "ignored.md").write_text("ignored\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "tracked.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    scanned = {
        path.relative_to(tmp_path).as_posix()
        for path in privacy_scan.public_text_files(tmp_path)
    }
    assert {"tracked.md", "intended.md", ".gitignore"} <= scanned
    assert "private/ignored.md" not in scanned
    assert "binary.bin" not in scanned


def test_non_git_root_is_refused_without_recursive_fallback(tmp_path: Path) -> None:
    canary = POSITIVE_CANARIES["email_address"]
    (tmp_path / "leak.txt").write_text(canary + "\n", encoding="utf-8")

    with pytest.raises(privacy_scan.ScanScopeError):
        privacy_scan.public_text_files(tmp_path)

    result = _run_cli(tmp_path)
    assert result.returncode == 2
    assert canary not in result.stdout
    assert canary not in result.stderr
    assert "refusing" in result.stderr.lower()


@pytest.mark.parametrize("tracked", [False, True])
def test_symlink_escaping_repository_is_refused(tmp_path: Path, tracked: bool) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    canary = POSITIVE_CANARIES["secret_like_token"]
    (outside / "secret.txt").write_text(canary + "\n", encoding="utf-8")

    repo = tmp_path / "repo"
    _git_init(repo)
    link = repo / "link.txt"
    link.symlink_to(outside / "secret.txt")
    if tracked:
        subprocess.run(["git", "add", "link.txt"], cwd=repo, check=True)

    with pytest.raises(privacy_scan.ScanScopeError):
        privacy_scan.public_text_files(repo)

    result = _run_cli(repo)
    assert result.returncode == 2
    assert canary not in result.stdout
    assert canary not in result.stderr
    assert "boundary" in result.stderr.lower()


def test_repository_scan_covers_every_public_text_file() -> None:
    files = privacy_scan.public_text_files(ROOT)
    report = privacy_scan.scan(ROOT)
    assert report["scanned_count"] == len(files)
    assert len(report["scanned_files"]) == len(files)
    assert "README.md" in report["scanned_files"]
    assert "pyproject.toml" in report["scanned_files"]
