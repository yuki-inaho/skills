---
name: grill-me
description: 'Use when the user wants to stress-test a plan or design, or invokes grill-me / grilling. Works a design tree round by round: asks the whole settled frontier (up to a user-specified count, default 10) with recommended answers, and never asks what it can look up. Triggers: grill-me, グリルして, 計画を叩いて, stress-test the plan, 設計を詰めて.'
---

# grill-me（frontier 一括グリル）

計画・設計を**設計木（design tree）**として捉え、各決定の前提がすべて確定した質問群
（**frontier**）だけを **1 ラウンドでまとめて**聞く。回答が届くたびに木を更新し、frontier を外へ広げる。

一問ずつ聞かない理由: 往復が増えるうえ、依存関係の全体像がユーザーに見えないまま進む。
frontier をまとめて出すことで、**今決められる決定**と**まだ決められない決定**が同時に見える。

## When to use

- 実装前に計画・設計を叩きたいとき。
- 使わない場面: 単発の質問 1 つで足りるとき（普通に聞く）。

## Prerequisites

- 対象の計画・設計があること（会話中でもファイルでも可）。
- 1 ラウンドの質問数の上限を決める（ユーザー指定。無ければ **10 問**と宣言する）。
- **事実は自分で調べる**。サブエージェントを起動できる環境なら調査を投げる。
  ユーザーに聞いてよいのは**決定**だけ（調べれば分かることを聞かない）。

## Procedure

1. **設計木を描く**: 決定ノードと依存（「A が決まらないと B を聞けない」）を列挙する。
   枝の種は [references/question-bank.md](references/question-bank.md)。
2. **frontier を計算する**: 前提がすべて確定済みのノードだけが「今聞ける」。
   他の未解決ノードに依存する質問は**今回のラウンドに入れない**。
3. **上限 N で優先順位付け**: 上位の決定・ブロッキング・不可逆なものを先に。N を超える分は次ラウンドへ送る。
4. **ラウンドを一括出力**: 番号付き、枝ごとにグループ化。各質問に「なぜ」と「推奨」を付ける。

```text
N 問で出します（上限。変更可）。

【枝: 目的】
Q1: <質問（複数案の比較でもよい）>
  なぜ: <曖昧なままだと何が壊れるか>
  推奨: <推奨回答と、その理由 1 行>

【枝: スコープ】
Q2: ...
```

5. **事実質問はブロックしない**: 環境から調べられるものは調査を起動して先へ進める。
   その事実に依存する下流の質問だけを次ラウンド送りにし、残りの frontier は今聞く。
6. **回答で木を更新**し、frontier を再計算して次ラウンドを出す（前ラウンドの回答を引用して依存の解消を示す）。
7. **収束**: frontier が空になったら「未確定なし」と明示し、**ユーザーの確認を待つ**。
   確認があるまで計画を実行に移さない。

## Verification

- 各質問に「なぜ」と「推奨」が付いている。
- 1 ラウンドの質問数 ≤ 指定数（既定 10）。
- 2 ラウンド目以降は、前ラウンドの回答で**解消した前提**を示し、質問が絞られている。
- 最終ラウンドで frontier 空を宣言し、未解決（あれば）と次のアクションが列挙されている。
- ユーザーの確認前に実装・実行をしていない。

## Failure handling

- 依存が循環する: 片方に仮定を置いて先に確定し、**仮定であることを明記**する。
- 質問が思いつかない: [references/question-bank.md](references/question-bank.md) の枝を順に当てる。
- 答えが好みでしか決まらない: 推奨を必ず添え、影響・コスト・戻しやすさを 1 行で書く。
- 同じ論点が再出現: 前ラウンドの回答を引用して「これで確定か」と 1 問だけ確認する。
- ラウンドが 3〜4 を超える: 打ち切り、残りを「未解決」として次のアクションに落とす。
- 事実が環境に無い: 仮定を明示したうえで質問に含める（事実の捏造をしない）。

## Origin / License

- 着想元: [mattpocock/skills — grill-me / grilling](https://github.com/mattpocock/skills/tree/main/skills/productivity)（MIT License, Copyright (c) 2026 Matt Pocock）。
  本スキルは上流の **design tree / frontier ラウンド方式**に完全整合させた日本語向け再実装（指定数上限・「なぜ/推奨」・
  質問バンクを追加）。
- ライセンス条件に従い、帰属表示と MIT ライセンス全文を `LICENSE` に同梱する。

## Growth log

- 追記先: [references/growth-log.md](references/growth-log.md)。
