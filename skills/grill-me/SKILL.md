---
name: grill-me
description: 'Use when the user wants to stress-test a plan or design with a batch of hard questions, or invokes grill-me / grilling. Asks a user-specified number of questions all at once (default 10). Triggers: grill-me, グリルして, 計画を叩いて, stress-test the plan, 設計を詰めて.'
---

# grill-me（一括グリル）

計画・設計の穴を、**ユーザー指定数の質問を 1 回でまとめて**投げて潰す。
一問ずつ聞くと往復が多く、論点の全体像が見えないまま進む。まとめて出すことで**優先順位と依存関係**を
ユーザー自身が同時に見られる。

## When to use

- 実装前に計画・設計を叩きたいとき。
- 使わない場面: 単純な質問 1 つで足りるとき（普通に聞く）。

## Prerequisites

- 対象の計画・設計・作業書があること（会話中でもファイルでも可）。
- 質問数を決めておくこと。指定が無ければ **10 問**を既定とし、冒頭で「N 問で出します（変更可）」と宣言する。

## Procedure

1. 対象を読み、**枝（論点カテゴリ）**を洗い出す（推奨: 目的 / スコープ / データ / 失敗時 / 運用 / 成功指標 / リスク / 代替案）。
2. コードベースや資料から答えられる質問は**自分で調べてから**、本当にユーザー判断が要るものだけを残す。
3. **指定数 N の質問を一括で**出力する。各質問は次の 3 点を 1 セットにする:

```text
Q<番号>（枝）: <質問>
  なぜ: <ここが曖昧だと何が壊れるか>
  推奨: <あなたの推奨回答>
```

4. 出力は番号付き・枝ごとにグループ化し、1 質問あたり 3 行以内に収める（長文の前置きを書かない）。
5. ユーザーの回答後、**未回答・矛盾・新たに露出した依存だけ**を抽出し、2 回目のバッチ（前回より少ない数）を出す。
6. 最大 3 ラウンドで収束させる。収束しない論点は「未解決」として明記し、判断を次アクションに落とす。

## Verification

- 各質問に「なぜ」と「推奨」が付いている。
- 1 回目のバッチ数 = ユーザー指定数（または既定 10）。2 回目以降は減っている。
- ラウンドは 3 回以内で、最後に「未解決の論点」と「次のアクション」が列挙されている。

## Failure handling

- 質問が思いつかない: [references/question-bank.md](references/question-bank.md) の枝を順に当てる。
- 答えがユーザーの好みでしか決まらない: 推奨を必ず添え、判断材料（影響・コスト・戻しやすさ）を 1 行で書く。
- 同じ論点が再出現: 前ラウンドの回答を引用して「これで確定か」と 1 問だけ確認する。
- ユーザーが数を指定できない: 10 問で出し、「増減は言ってください」と添える。

## Origin / License

- 着想元: [mattpocock/skills — grill-me / grilling](https://github.com/mattpocock/skills/tree/main/skills/productivity)（MIT License, Copyright (c) 2026 Matt Pocock）。
  上流の現行版は「設計木（design tree）の frontier をラウンドで一括質問」する方式で、本スキルの一括バッチ方針はこれに沿っている。
- 本スキルは**日本語環境向けに再構成した独自実装**（指定数の一括出力・「なぜ/推奨」必須・最大 3 ラウンド・質問バンク）。
  ライセンス条件に従い、帰属表示と MIT ライセンス全文を `LICENSE` に同梱する。

## Growth log

- 追記先: [references/growth-log.md](references/growth-log.md)。
