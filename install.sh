#!/usr/bin/env bash
# Install skills from https://github.com/yuki-inaho/skills into
# Claude Code / Codex CLI / OpenCode.
#
# Quick start (no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/yuki-inaho/skills/main/install.sh | bash
#
# Examples:
#   # 特定のエージェントだけに入れる
#   curl -fsSL .../install.sh | bash -s -- --agent claude
#
#   # 特定のスキルだけ / 複数指定
#   curl -fsSL .../install.sh | bash -s -- --agent codex --skill handover --skill write-workdoc-uv
#
#   # インストール先を直接指定（任意のエージェントや別ディレクトリ）
#   curl -fsSL .../install.sh | bash -s -- --dest "$HOME/.claude/skills"
#
# Options:
#   --agent <claude|codex|opencode|all>  繰り返し/カンマ区切り可。既定: 既存を自動検出、無ければ all
#   --skill <name|all>                   繰り返し/カンマ区切り可。既定: all
#   --dest  <dir>                        インストール先を直接指定（--agent より優先）
#   --ref   <branch-or-tag>              取得する ref（既定: main / 環境変数 SKILLS_REF）
#   --dry-run                            書き込まずに実行内容だけ表示
#   -h, --help                           このヘルプ
#
set -euo pipefail

REPO="${SKILLS_REPO:-yuki-inaho/skills}"
REF="${SKILLS_REF:-main}"
AGENTS_RAW=""
SKILLS_RAW=""
DEST=""
DRY_RUN=0

usage() {
    cat <<'EOF'
Install skills from https://github.com/yuki-inaho/skills into Claude Code / Codex CLI / OpenCode.

Quick start:
  curl -fsSL https://raw.githubusercontent.com/yuki-inaho/skills/main/install.sh | bash

Options:
  --agent <claude|codex|opencode|all>  繰り返し/カンマ区切り可。既定: 既存を自動検出、無ければ all
  --skill <name|all>                   繰り返し/カンマ区切り可。既定: all
  --dest  <dir>                        インストール先を直接指定（--agent より優先）
  --ref   <branch-or-tag>              取得する ref（既定: main / 環境変数 SKILLS_REF）
  --dry-run                            書き込まずに実行内容だけ表示
  -h, --help                           このヘルプ

Examples:
  curl -fsSL .../install.sh | bash -s -- --agent claude
  curl -fsSL .../install.sh | bash -s -- --agent codex --skill handover --skill write-workdoc-uv
  curl -fsSL .../install.sh | bash -s -- --dest "$HOME/.claude/skills"
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

note() {
    printf '%s\n' "$*"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --agent)
            [ $# -ge 2 ] || die "--agent requires a value"
            AGENTS_RAW="${AGENTS_RAW}${AGENTS_RAW:+,}$2"
            shift 2
            ;;
        --skill)
            [ $# -ge 2 ] || die "--skill requires a value"
            SKILLS_RAW="${SKILLS_RAW}${SKILLS_RAW:+,}$2"
            shift 2
            ;;
        --dest)
            [ $# -ge 2 ] || die "--dest requires a value"
            DEST="$2"
            shift 2
            ;;
        --ref)
            [ $# -ge 2 ] || die "--ref requires a value"
            REF="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1 (see --help)"
            ;;
    esac
done

command -v curl >/dev/null 2>&1 || die "curl is required"
command -v tar >/dev/null 2>&1 || die "tar is required"

agent_home() {
    case "$1" in
        claude) printf '%s\n' "${CLAUDE_HOME:-$HOME/.claude}" ;;
        codex) printf '%s\n' "${CODEX_HOME:-$HOME/.codex}" ;;
        opencode) printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/opencode" ;;
        *) die "unknown agent: $1" ;;
    esac
}

agent_skills_dir() {
    case "$1" in
        claude) printf '%s\n' "${CLAUDE_SKILLS_DIR:-$(agent_home claude)/skills}" ;;
        codex) printf '%s\n' "${CODEX_SKILLS_DIR:-$(agent_home codex)/skills}" ;;
        opencode) printf '%s\n' "${OPENCODE_SKILLS_DIR:-$(agent_home opencode)/skills}" ;;
        *) die "unknown agent: $1" ;;
    esac
}

# ---- resolve destinations -------------------------------------------------
declare -a DESTS=()
if [ -n "$DEST" ]; then
    DESTS+=("$DEST")
else
    if [ -n "$AGENTS_RAW" ]; then
        agents_csv="${AGENTS_RAW// /}"
        if [ "$agents_csv" = "all" ]; then
            agents_csv="claude,codex,opencode"
        fi
    else
        agents_csv=""
        for candidate in claude codex opencode; do
            if [ -d "$(agent_home "$candidate")" ]; then
                agents_csv="${agents_csv}${agents_csv:+,}${candidate}"
            fi
        done
        if [ -z "$agents_csv" ]; then
            agents_csv="claude,codex,opencode"
            note "note: no existing agent home found; installing to all three defaults"
        fi
    fi
    IFS=',' read -r -a agents_arr <<<"$agents_csv"
    for agent in "${agents_arr[@]}"; do
        [ -n "$agent" ] || continue
        DESTS+=("$(agent_skills_dir "$agent")")
    done
fi
[ "${#DESTS[@]}" -gt 0 ] || die "no destination resolved"

# ---- fetch repository tarball --------------------------------------------
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/skills-install.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

note "fetching ${REPO}@${REF} ..."
tarball="$TMP_DIR/skills.tar.gz"
if ! curl -fsSL "https://codeload.github.com/${REPO}/tar.gz/refs/heads/${REF}" -o "$tarball"; then
    note "  (branch '${REF}' not found; trying tag)"
    curl -fsSL "https://codeload.github.com/${REPO}/tar.gz/refs/tags/${REF}" -o "$tarball" \
        || die "failed to download ${REPO}@${REF}"
fi
tar -xzf "$tarball" -C "$TMP_DIR"
src_dir="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
[ -n "$src_dir" ] && [ -d "$src_dir/skills" ] || die "unexpected archive layout"

declare -a available=()
while IFS= read -r entry; do
    available+=("$(basename "$entry")")
done < <(find "$src_dir/skills" -mindepth 1 -maxdepth 1 -type d | sort)

if [ -n "$SKILLS_RAW" ]; then
    requested_csv="${SKILLS_RAW// /}"
    if [ "$requested_csv" = "all" ]; then
        requested_csv=""
    fi
else
    requested_csv=""
fi

declare -a selected=()
if [ -z "$requested_csv" ]; then
    selected=("${available[@]}")
else
    IFS=',' read -r -a requested_arr <<<"$requested_csv"
    for name in "${requested_arr[@]}"; do
        [ -n "$name" ] || continue
        found=0
        for candidate in "${available[@]}"; do
            if [ "$name" = "$candidate" ]; then
                found=1
                break
            fi
        done
        [ "$found" -eq 1 ] || die "unknown skill: $name (available: ${available[*]})"
        selected+=("$name")
    done
fi
[ "${#selected[@]}" -gt 0 ] || die "no skills selected"

# ---- install --------------------------------------------------------------
for dest in "${DESTS[@]}"; do
    note "destination: ${dest}"
    for name in "${selected[@]}"; do
        target="$dest/$name"
        if [ "$DRY_RUN" -eq 1 ]; then
            note "  [dry-run] would install ${name} -> ${target}"
            continue
        fi
        mkdir -p "$dest"
        rm -rf "$target"
        cp -R "$src_dir/skills/$name" "$target"
        note "  installed ${name} -> ${target}"
    done
done

if [ "$DRY_RUN" -eq 1 ]; then
    note "dry-run: no files were written"
else
    note "done: ${#selected[@]} skill(s) -> ${#DESTS[@]} destination(s)"
    note "restart your agent session to pick up new skills"
fi
