---
name: public-repository-privacy-review
description: 'Use when something is about to be published in a public repository or public PR, and the change needs a privacy review across the publication boundary, diff, examples, fixtures, docs, metadata, commit text, and PR title/body/comments. Triggers: 公開前レビュー, public repo review, public-before-publish, 公開リポジトリに入れてよいか, PR本文の個人情報確認, 内部名が残っていないか. Not for ordinary private-only edits or internal-only changes.'
---

# public-repository-privacy-review

公開リポジトリへ出る直前の「何が公開されるか」を点検する手順。このスキルは単体で完結し、
`~/.codex/skills` などへコピーした環境でも本文だけで同じ手順を実行できる。由来は公開スキル集の
`docs/PUBLIC_SKILLS_POLICY.md`（§3 禁止情報・§4 合成データ・§6 権限・§7 公開前チェック）だが、
これは出典であって実行時の前提でも唯一の根拠でもない。無い環境では本文と、利用者・組織の
既存ポリシーに従う。

これは承認ゲートではない。公開可否の決定権は利用者と既存ポリシーにあり、この手順は判断材料を揃えるだけ。
新しい承認や許可を要求せず、既に許可された修正を止めるものでもない。private なローカル作業は
private な文脈のままでよく、公開物へ持ち出さなければよい。

## When to use

- public リポジトリへの commit / PR / release / README 例の追加の直前。
- public PR の title・body・コメント・レビュー返信を書く、または直すとき。
- 「この差分や例は公開してよいか」を点検するとき。

使わない: private リポジトリ内だけの通常編集、公開境界に触れない内部レビュー。
公開前点検の依頼が無いコードレビューへ、この手順を勝手に足さない。

## Prerequisites

- 公開境界を先に固定する。**どのリポジトリ・どの ref・どの差分・どの成果物が公開されるか**を
  1 行で言えること（例: `git diff --cached`、`git diff origin/main...HEAD`、`git show <commit>`、
  PR の本文とコメント）。
- 公開の有無と再掲の必要性を分ける。公開済みであることは、氏名や私的文脈の詳細を
  再掲してよい理由にならない。公開アカウント名は、公開参照に必要な範囲だけ残す
  （必要最小限。不要なら一般化・省略する）。
- 実在の名前一覧（denylist）を公開ソースへ持ち込まない。判断は都度、文脈で行う。
- このスキルは既存の承認・権限・手続きを増減させない。許可済みの作業をやり直させない。

## Procedure

1. **公開される面を列挙する**（差分だけで終わらせない）: コード / テストと fixture / 例とサンプル出力 /
   docs と README / frontmatter や `agents/*.yaml` などの metadata / commit message /
   PR の title・body・コメント / 添付画像やログ。
2. **各候補に 3 つを問う**: 公開読者が再現・理解するのに必要か。内部の人物・案件・場所を特定させるか。
   一般化・合成値・省略で意味を保てるか。必要でない固有値は置換または削除する。
3. **人物の文脈を分ける**: 公開アカウント名（上流の maintainer、公開 Issue の投稿者、公開ドキュメントの著者）は、
   公開参照として必要な範囲で残してよい。内部の人名・通称・チャンネル名・顧客名は内部文脈であり、
   公開物では合成名か役割名（例: `reviewer`, `maintainer`）へ置き換えるか省略する。
   名前の有無だけで機械的に決めず、**その名前が公開情報で、かつ再掲が必要か**を基準にする。
4. **置換は意味を保つ**: `/path/to/repo`、`~/.codex/sessions`、`<uuid>.jsonl` のような一般化、
   または合成の識別子を使う。**元の private な文字列を、テスト・fixture・commit message・
   レビュー報告へそのまま写さない**（削除した証拠としても写さない）。削除は
   「内部の実パス 1 件を一般化」のように種別で書く。
5. **機械走査は手掛かりとしてだけ使う**（任意。0 件は安全宣言ではない）。ヒットは確認候補で、
   無ヒットは「見落としが無い」ことを意味しない。差分の外（PR 本文・コメント・metadata・画像）は別に見る。
   `rg` が無い環境では `grep -nE` などで代替してよい。

   ```bash
   git diff --cached --stat
   # 絶対パスらしき文字列
   git diff --cached -U0 | rg -n '(^|[^[:alnum:]~])/([[:alnum:]_.-]+/){2,}' || true
   # メールアドレスらしき文字列
   git diff --cached -U0 | rg -n '[[:alnum:]._%+-]+@[[:alnum:]-]+\.' || true
   # 秘密情報らしき語
   git diff --cached -U0 | rg -ni '(secret|token|password|api[_-]?key|authorization)' || true
   # URL のホストを目視
   git diff --cached -U0 | rg -o 'https?://[^/ )"]+' | sort -u
   ```

6. **由来を確認する**: 上流由来のコード・文書は license と帰属を保持し、一般化した独自変更を上流へ混ぜない。
   例が private 文脈から適応されたものなら、公開版が一般化されているかを確認する。
7. **記録する**: 見た面と、実害のあるプライバシー候補（公開読者に内部の人物・案件・場所を
   同定させうるもの、秘密情報）についてだけ keep / generalize / omit と理由を残す。
   すべての文字列やトークンを列挙しない。報告自体が公開物になる場合は、報告にも固有値を書かない。

## Verification

- 公開境界（repo / ref / 差分 / PR 本文など）を列挙し、各面を実際に読んだ。
- 各候補について keep / generalize / omit の判断と理由がある（列挙は実害のある候補に絞る）。
- fixture・例・テストが合成データで、実行して再現できる（該当する場合）。
- 機械走査を「手掛かり」として解釈し、0 件のみを根拠に「公開可」と結論していない。
- private な文字列が、公開物のどこにも（レポートや削除メモにも）コピーされていない。

## Failure handling

- 走査は 0 件だが違和感が残る: 差分と PR 本文を人手で読み直す。0 件を根拠に打ち切らない。
- 内部情報か公開情報か判断できない: 公開物からは一般化・省略を既定にし、値が本質的な場合だけ所有者へ確認する。
- 公開してよいか迷う: このスキルは承認も拒否もしない。判断は利用者・既存ポリシー・組織の手続きに残す。
- ローカルで private な検証が必要: 非公開のまま実行してよい。公開物へ持ち出さない。
- 公開済みの漏えいを見つけた: 既に許可された修正はそのまま進めてよい。履歴改変のような
  不可逆な操作だけ、既存の権限・ポリシーに従う。影響範囲は一般化して報告する。

## Growth log

- 同じ判断の迷いが繰り返し出たら、固有値を含めない形で本スキルへ追記する（追加する例は合成値のみ）。
