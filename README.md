# skills

個人のエージェントスキル集（サニタイズ済み・公開可）。
Claude Code / OpenCode / Codex 等のスキル機構で使える `SKILL.md` 形式。

## 収録スキル

| スキル | 用途 |
| --- | --- |
| [`jax-performance-tuning`](skills/jax-performance-tuning/SKILL.md) | JAX のコンパイルキャッシュ・BF16/AMP・micro-batch・remat・プロファイリング・Blackwell/cuDNN9 安定化 |
| [`agent-jsonl-compact-reader`](skills/agent-jsonl-compact-reader/SKILL.md) | 巨大な Codex / Claude Code / OpenCode セッション JSONL を `agent-jsonl-compact` で軽量化し段階的に読む |
| [`write-workdoc-uv`](skills/write-workdoc-uv/SKILL.md) | uv 前提の日本語作業計画書兼記録書（workdoc）を `temp/` に作成（テンプレート付き） |
| [`review-written-workdoc`](skills/review-written-workdoc/SKILL.md) | workdoc を rubric でレビューし、既定で安全な改善を適用 |
| [`handover`](skills/handover/SKILL.md) | Auto-Compact 用の日本語引き継ぎ文書をチャットに出力（ファイルは作らない） |

`write-workdoc-uv` / `review-written-workdoc` / `handover` には Codex 等向けの
`agents/openai.yaml` を同梱。`write-workdoc-uv` と `review-written-workdoc` には
`references/` にテンプレート / rubric を同梱。

## インストール

```bash
# 例: Claude Code の personal skills へ
git clone https://github.com/yuki-inaho/skills.git
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
