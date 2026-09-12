---
name: skill-creator
description: 'Use when creating or updating an agent skill (SKILL.md), fixing frontmatter/YAML failures, or deciding what belongs in a skill. Triggers: create skill, new skill, skill を追加, SKILL.md を直す, frontmatter エラー.'
---

# skill-creator (meta)

スキルは「非自明な手順」を再利用可能にするためのもの。**能力の説明ではなく、判断を変える情報だけ**を書く。

## When to use

- 新しいスキルを `skills/<name>/SKILL.md` として追加するとき。
- 既存スキルの frontmatter・検証・構成を直すとき。
- 使わない場面: 一度きりの手順（スキル化しない）。

## Prerequisites

- 追加する手順を**実際に 1 回実行**し、コマンドと期待出力を確認しておくこと（未実行の手順を書かない）。
- 対象エージェントの skills ディレクトリを把握しておくこと（例: `~/.claude/skills`, `~/.codex/skills`, `~/.config/opencode/skills`）。

## Procedure

1. 名前は kebab-case。`name` は**ディレクトリ名と一致必須**。
2. frontmatter を書く:
   - `description` は `Use when ...` と `Triggers: ...` を含める。**`:` を含むので引用符で囲む**（YAML 破断の実例あり）。
   - 任意で `metadata`、UI 向けに `agents/openai.yaml`（display_name / short_description / default_prompt / policy）。
3. 本文の推奨構成（読み手が実行できる形にするための 6 見出し）:

```text
## When to use        # いつ使うか。使わない場面も 1 行
## Prerequisites      # 前提。無ければ先に何をするか
## Procedure          # 実行可能なコマンド（コードブロック必須）
## Verification       # 何をもって完了か（コマンド + 期待値 + 証跡）
## Failure handling   # 症状 -> 原因 -> 対処（fail-closed）
## Growth log         # 使用記録の追記先
```

4. 本文に書くこと / 書かないこと:
   - 書く: 非自明な落とし穴、検証コマンドと期待値、失敗時の切り分け、スコープ境界。
   - 書かない: 一般論、重複した方針、未確認の推測、**秘密情報・社内固有のパスや名称**（公開前に必ず除去）。
5. 検証する（同梱の依存ゼロ検証器）:

```bash
python3 skills/skill-creator/scripts/validate_skill.py            # 既定: 同コレクションの skills/
python3 skills/skill-creator/scripts/validate_skill.py skills/handover
```

6. 使ったら `references/growth-log.md` に「日付 / 何をした / 学び / 昇格判断」を追記。
   **同じ学びが 3 回で SKILL.md へ昇格**（1〜2 回はログ止まりで YAGNI）。

## Verification

- `validate_skill.py` が hard error 0 で終了（警告は内容を確認して取捨）。
- 追加したスキルの `## Verification` が実コマンドと期待値で書かれている。
- 公開先へ入れる前に、秘密情報・固有パスの走査（例: `grep -rniE "(secret|password|token|/home/|<internal-name>)"`）を 1 回実行する。

## Failure handling

- YAML パースエラー: `description` をシングルクォートで囲み、内部の `'` を 2 重化する。
- `name` 不一致: ディレクトリ名と同じにする（リネームはスキル名の互換性に影響）。
- 検証器が `missing recommended section` を警告: 実行可能性に必要なら見出しを追加、不要なら理由を本文に書く。
- description が長い/曖昧: 実際の能力と適用条件を 1〜2 文に絞る（列挙をやめる）。

## Growth log

- 追記先: [references/growth-log.md](references/growth-log.md)。
