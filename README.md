# skills

個人のエージェントスキル集（サニタイズ済み・公開可）。
Claude Code / OpenCode / Codex 等のスキル機構で使える `SKILL.md` 形式。

## 収録スキル

| スキル | 用途 |
| --- | --- |
| [`jax-performance-tuning`](skills/jax-performance-tuning/SKILL.md) | JAX のコンパイルキャッシュ・BF16/AMP・micro-batch・remat・プロファイリング・Blackwell/cuDNN9 安定化 |
| [`agent-jsonl-compact-reader`](skills/agent-jsonl-compact-reader/SKILL.md) | 巨大な Codex / Claude Code / OpenCode セッション JSONL を `agent-jsonl-compact` で軽量化し段階的に読む（配布元: https://github.com/yuki-inaho/agent-jsonl-compact） |
| [`write-workdoc-uv`](skills/write-workdoc-uv/SKILL.md) | uv 前提の日本語作業計画書兼記録書（workdoc）を `temp/` に作成（テンプレート付き） |
| [`review-written-workdoc`](skills/review-written-workdoc/SKILL.md) | workdoc を rubric でレビューし、既定で安全な改善を適用 |
| [`handover`](skills/handover/SKILL.md) | Auto-Compact 用の日本語引き継ぎ文書をチャットに出力（ファイルは作らない） |
| [`grill-me`](skills/grill-me/SKILL.md) | 計画・設計を叩く質問を**ユーザー指定数まとめて一括**提示（各問に「なぜ」と推奨付き、最大3ラウンド） |
| [`skill-creator`](skills/skill-creator/SKILL.md) | スキルの新規作成・改善（frontmatter の罠、推奨構成、同梱の依存ゼロ検証器、公開前サニタイズ） |
| [`supervisor-orchestration`](skills/supervisor-orchestration/SKILL.md) | 監督エージェントの振り分け・検証・統合（Bloom ルーティング、サブエージェント並列、成長ログ） |
| [`demo-rehearsal`](skills/demo-rehearsal/SKILL.md) | デモの時間設計（説明秒・理解待ち秒）と聴衆エージェント PDCA（汎用ペルソナ付き） |
| [`playwright-cli-automation`](skills/playwright-cli-automation/SKILL.md) | グローバル playwright-cli でブラウザを自律操作しスクリーンショット収集（コンテナ対処込み） |
| [`mujoco-web-wasm-demo`](skills/mujoco-web-wasm-demo/SKILL.md) | MuJoCo をブラウザで（公式 WASM + three.js）。フック公開とスクショ検証 |

`write-workdoc-uv` / `review-written-workdoc` / `handover` / `supervisor-orchestration` /
`demo-rehearsal` / `playwright-cli-automation` / `mujoco-web-wasm-demo` には Codex 等向けの
`agents/openai.yaml` を同梱（`skill-creator` は検証スクリプト `scripts/validate_skill.py` も同梱）。`write-workdoc-uv` と `review-written-workdoc` には
`references/` にテンプレート / rubric を同梱。

## クイックインストール（curl）

`install.sh` が Claude Code / Codex CLI / OpenCode のスキルディレクトリへ導入します。
clone も git も不要です。

```bash
# 既存のエージェント（~/.claude, ~/.codex, ~/.config/opencode）を自動検出して導入
curl -fsSL https://raw.githubusercontent.com/yuki-inaho/skills/main/install.sh | bash

# エージェントを指定（claude / codex / opencode / all）
curl -fsSL https://raw.githubusercontent.com/yuki-inaho/skills/main/install.sh | bash -s -- --agent claude

# スキルを指定（繰り返し指定可。既定は all）
curl -fsSL https://raw.githubusercontent.com/yuki-inaho/skills/main/install.sh | bash -s -- \
  --agent codex --skill handover --skill write-workdoc-uv

# インストール先を直接指定
curl -fsSL https://raw.githubusercontent.com/yuki-inaho/skills/main/install.sh | bash -s -- \
  --dest "$HOME/.claude/skills"

# 何がどこに入るか確認だけ（書き込まない）
curl -fsSL https://raw.githubusercontent.com/yuki-inaho/skills/main/install.sh | bash -s -- --dry-run
```

- `--agent` 省略時は既存ディレクトリを自動検出し、無ければ 3 つすべての既定パスへ導入。
- `--ref <branch-or-tag>` で取得する ref を変更可（既定 `main`）。
- 環境変数: `CLAUDE_HOME` / `CODEX_HOME` / `XDG_CONFIG_HOME`、および
  `CLAUDE_SKILLS_DIR` / `CODEX_SKILLS_DIR` / `OPENCODE_SKILLS_DIR` でパスを上書きできます。

## インストール（手動 / git clone）

```bash
git clone https://github.com/yuki-inaho/skills.git

# 例: Claude Code の personal skills へ
cp -r skills/skills/<skill-name> ~/.claude/skills/

# 例: OpenCode へ
cp -r skills/skills/<skill-name> ~/.config/opencode/skills/

# 例: Codex CLI へ
cp -r skills/skills/<skill-name> ~/.codex/skills/
```

各スキルは `SKILL.md` の YAML frontmatter（`name` / `description`）だけで動作します。
`references/` はスキル本文から参照される補助資料、`agents/openai.yaml` は Codex 系 UI 用メタデータです。

## サニタイズ方針

公開リポジトリのため、配置前に以下を除去・一般化している:

- マシン固有の絶対パス・ユーザー名（`~/` 表記へ）
- private リポジトリ名・プロジェクト固有の内部パス
- API キー・トークン・認証情報・メールアドレス
- 実データ・会話ログ・PII

## 由来

2026-09-12 時点で著者のローカルスキルライブラリから、JAX GPU 学習プロジェクトで
実際に使用したスキルを抽出して配置した。

## ライセンス

特に指定なし（必要なら Issue で連絡）。
