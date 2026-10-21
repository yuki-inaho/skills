"""install.sh の隔離実行テスト。

installer の取得先は codeload.github.com 固定なので、ローカル HTTP サーバに置いた
アーカイブへ差し替える `curl` シムを PATH 先頭に置く。グローバル導入もネットワーク
公開も行わない。fixture はすべて合成。
"""

from __future__ import annotations

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
SKILL_NAMES = (
    "agent-jsonl-compact-reader",
    "harness2-portable-workflow",
    "public-repository-privacy-review",
)


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
    """repo の skills/ を top-level ディレクトリ付き tar.gz にする。"""
    archive = tmp_path / "skills-snapshot.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(ROOT / "skills", arcname="skills-snapshot/skills")
    return archive


def _write_curl_shim(bin_dir: Path, base_url: str) -> None:
    """codeload への取得だけをローカル配信へ差し替える最小シム。"""
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


def test_installs_only_selected_skills_to_all_agents(tmp_path: Path, local_archive: str) -> None:
    env = _sandbox_env(tmp_path, local_archive)
    selection: list[str] = []
    for name in SKILL_NAMES:
        selection.extend(["--skill", name])

    result = _run_installer(env, "--agent", "all", *selection)

    assert result.returncode == 0, result.stderr
    for name in SKILL_NAMES:
        assert result.stdout.count(f"installed {name}") == 3
    assert f"done: {len(SKILL_NAMES)} skill(s) -> 3 destination(s)" in result.stdout

    home = tmp_path / "home"
    destinations = {
        "claude": home / ".claude" / "skills",
        "codex": home / ".codex" / "skills",
        "opencode": home / ".config" / "opencode" / "skills",
    }
    for agent, skills_dir in destinations.items():
        entries = sorted(path.name for path in skills_dir.iterdir())
        assert entries == sorted(SKILL_NAMES), f"{agent} の導入結果が選択と一致しない: {entries}"
        for name in SKILL_NAMES:
            installed = skills_dir / name / "SKILL.md"
            expected = (ROOT / "skills" / name / "SKILL.md").read_bytes()
            assert installed.is_file(), f"{agent}/{name} に SKILL.md が無い"
            assert installed.read_bytes() == expected, f"{agent}/{name} の内容が一致しない"


def test_dry_run_writes_nothing(tmp_path: Path, local_archive: str) -> None:
    env = _sandbox_env(tmp_path, local_archive)
    selection: list[str] = []
    for name in SKILL_NAMES:
        selection.extend(["--skill", name])

    result = _run_installer(env, "--agent", "all", *selection, "--dry-run")

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("would install") == 3 * len(SKILL_NAMES)
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


def test_local_archive_only_no_external_fetch(tmp_path: Path, local_archive: str) -> None:
    """シムが codeload 以外への取得を拒否するので、外部取得があれば失敗する。"""
    env = _sandbox_env(tmp_path, local_archive)

    selection: list[str] = []
    for name in SKILL_NAMES:
        selection.extend(["--skill", name])
    result = _run_installer(env, "--agent", "opencode", *selection)

    assert result.returncode == 0, result.stderr
    assert "unexpected url" not in result.stderr


def test_harness_tools_available() -> None:
    assert sys.version_info >= (3, 9)
    assert shutil.which("tar") is not None
    assert shutil.which("bash") is not None
