"""Isolated installer tests with synthetic archives.

The installer fetches from codeload.github.com. A local HTTP server and a curl
shim keep the test offline and reject every non-codeload URL. Every discovered
skill directory is compared by recursive tree hash, not just SKILL.md bytes.
"""

from __future__ import annotations

import hashlib
import http.server
import os
import shutil
import subprocess
import sys
import tarfile
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


def discover_skill_names() -> list[str]:
    return sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, **kwargs) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, *args: object) -> None:  # noqa: D102
        pass


def _serve(directory: Path) -> http.server.ThreadingHTTPServer:
    def handler(*args, **kwargs):
        return _QuietHandler(*args, directory=str(directory), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _make_archive(tmp_path: Path) -> Path:
    archive = tmp_path / "skills-snapshot.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(ROOT / "skills", arcname="skills-snapshot/skills")
    return archive


def _write_curl_shim(bin_dir: Path, base_url: str) -> None:
    shim = bin_dir / "curl"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'url=""\n'
        'out=""\n'
        "while [ $# -gt 0 ]; do\n"
        '  case "$1" in\n'
        '    -o) out="$2"; shift 2 ;;\n'
        '    -*) shift ;;\n'
        '    *) url="$1"; shift ;;\n'
        "  esac\n"
        "done\n"
        '[ -n "$out" ] || { echo "shim: -o required" >&2; exit 2; }\n'
        '[ -n "${SHIM_LOG:-}" ] && printf "%s\\n" "$url" >> "$SHIM_LOG"\n'
        'case "$url" in\n'
        '  https://codeload.github.com/*)\n'
        '    exec "$LOCAL_CURL" -fsSL "$LOCAL_BASE_URL" -o "$out" ;;\n'
        '  *) echo "unexpected url: $url" >&2; exit 22 ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)


def _sandbox_env(tmp_path: Path, base_url: str) -> dict[str, str]:
    real_curl = shutil.which("curl")
    assert real_curl, "テストには curl が必要（シムが実 curl へ委譲する）"
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_curl_shim(bin_dir, base_url)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CLAUDE_HOME": str(home / ".claude"),
            "CODEX_HOME": str(home / ".codex"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "TMPDIR": str(tmp_path / "tmp"),
            "LOCAL_CURL": real_curl,
            "LOCAL_BASE_URL": base_url,
            "SHIM_LOG": str(tmp_path / "curl.log"),
            "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
        }
    )
    (tmp_path / "tmp").mkdir()
    return env


@pytest.fixture()
def local_archive(tmp_path: Path):
    archive = _make_archive(tmp_path)
    server = _serve(tmp_path)
    base_url = f"http://127.0.0.1:{server.server_address[1]}/{archive.name}"
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()


def _run_installer(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _destinations(home: Path) -> dict[str, Path]:
    return {
        "claude": home / ".claude" / "skills",
        "codex": home / ".codex" / "skills",
        "opencode": home / ".config" / "opencode" / "skills",
    }


def test_installs_every_discovered_skill_tree_to_all_agents(
    tmp_path: Path, local_archive: str
) -> None:
    skills = discover_skill_names()
    env = _sandbox_env(tmp_path, local_archive)

    result = _run_installer(env, "--agent", "all")

    assert result.returncode == 0, result.stderr
    assert f"done: {len(skills)} skill(s) -> 3 destination(s)" in result.stdout
    for agent, skills_dir in _destinations(tmp_path / "home").items():
        entries = sorted(path.name for path in skills_dir.iterdir())
        assert entries == skills, f"{agent} の導入結果が discovery と一致しない: {entries}"
        for name in skills:
            expected = _tree_hashes(ROOT / "skills" / name)
            installed = _tree_hashes(skills_dir / name)
            assert installed == expected, f"{agent}/{name} の recursive tree hash が一致しない"


def test_comma_lists_select_agents_and_skills(tmp_path: Path, local_archive: str) -> None:
    skills = discover_skill_names()
    selected = skills[:2]
    env = _sandbox_env(tmp_path, local_archive)

    result = _run_installer(
        env,
        "--agent",
        "claude,codex",
        "--skill",
        ",".join(selected),
    )

    assert result.returncode == 0, result.stderr
    destinations = _destinations(tmp_path / "home")
    assert sorted(path.name for path in destinations["claude"].iterdir()) == selected
    assert sorted(path.name for path in destinations["codex"].iterdir()) == selected
    assert not destinations["opencode"].exists()


def test_auto_detect_uses_existing_agent_home_only(tmp_path: Path, local_archive: str) -> None:
    skills = discover_skill_names()
    selected = skills[0]
    env = _sandbox_env(tmp_path, local_archive)
    (tmp_path / "home" / ".codex").mkdir()

    result = _run_installer(env, "--skill", selected)

    assert result.returncode == 0, result.stderr
    destinations = _destinations(tmp_path / "home")
    assert (destinations["codex"] / selected / "SKILL.md").is_file()
    assert not destinations["claude"].exists()
    assert not destinations["opencode"].exists()


def test_dest_installs_one_selected_tree(tmp_path: Path, local_archive: str) -> None:
    selected = discover_skill_names()[0]
    env = _sandbox_env(tmp_path, local_archive)
    custom = tmp_path / "custom-skills"

    result = _run_installer(env, "--dest", str(custom), "--skill", selected, "--agent", "all")

    assert result.returncode == 0, result.stderr
    assert _tree_hashes(custom / selected) == _tree_hashes(ROOT / "skills" / selected)
    assert not (tmp_path / "home" / ".claude").exists()


def test_dry_run_writes_nothing(tmp_path: Path, local_archive: str) -> None:
    skills = discover_skill_names()
    env = _sandbox_env(tmp_path, local_archive)

    result = _run_installer(env, "--agent", "all", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("would install") == 3 * len(skills)
    assert "dry-run: no files were written" in result.stdout
    home = tmp_path / "home"
    assert not (home / ".claude").exists()
    assert not (home / ".codex").exists()
    assert not (home / ".config").exists()


def test_unknown_skill_fails_without_writing(tmp_path: Path, local_archive: str) -> None:
    env = _sandbox_env(tmp_path, local_archive)

    result = _run_installer(env, "--agent", "all", "--skill", "no-such-skill")

    assert result.returncode != 0
    assert "unknown skill" in result.stderr
    assert not (tmp_path / "home" / ".claude").exists()
    assert not (tmp_path / "home" / ".codex").exists()


def test_ref_is_requested_and_all_fetches_are_codeload(
    tmp_path: Path, local_archive: str
) -> None:
    selected = discover_skill_names()[0]
    env = _sandbox_env(tmp_path, local_archive)

    result = _run_installer(env, "--agent", "opencode", "--skill", selected, "--ref", "test-ref")

    assert result.returncode == 0, result.stderr
    log = Path(env["SHIM_LOG"]).read_text(encoding="utf-8").splitlines()
    assert log
    assert all(url.startswith("https://codeload.github.com/") for url in log)
    assert any("/refs/heads/test-ref" in url for url in log)
    assert "unexpected url" not in result.stderr


def test_unexpected_archive_layout_fails(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tar.gz"
    payload = tmp_path / "payload"
    (payload / "wrong").mkdir(parents=True)
    (payload / "wrong" / "README.md").write_text("not a skill tree\n", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload / "wrong", arcname="bad-snapshot/wrong")
    server = _serve(tmp_path)
    base_url = f"http://127.0.0.1:{server.server_address[1]}/{archive.name}"
    try:
        env = _sandbox_env(tmp_path, base_url)
        result = _run_installer(env, "--agent", "claude")
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode != 0
    assert "unexpected archive layout" in result.stderr


def test_harness_tools_available() -> None:
    assert sys.version_info >= (3, 11)
    assert shutil.which("tar") is not None
    assert shutil.which("bash") is not None
