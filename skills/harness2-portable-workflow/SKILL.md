---
name: harness2-portable-workflow
description: 'Use when a workflow or skill needs a substantial Harness² Propose–Probe–Compose redesign or self-critique — fix baseline, settings, model and budget, probe candidates, reflect after selection, and report honest evidence. Not for small edits. Triggers: Harness2 で改善を検証する, propose-probe-compose, ワークフロー改善の比較, スキル改善の自己批判, KEEP_BASE 判断, Harness² run の監査.'
---

# harness2-portable-workflow

Harness² の task-level recursion を、**比較可能な証跡**として実行・監査する手順。
対象はワークフローやスキルの大幅な改稿であり、小さな修正には使わない。

## 位置づけ（互換性の誤解を避ける）

- この `SKILL.md` は Codex CLI / Claude Code / OpenCode の 3 エージェントで**読み込める**。
  それは「3 つのモデル実行基盤が実装済み」という意味ではない。Harness² の 1 回の run は
  1 つの executor（実行基盤）で動く。
- 実行基盤・CLI は、実際にインストールされた fork の版と docs を確認して従う。
  **`--help` と `docs/ORDINARY_TASKS.md`（提供されていれば）を実際に読み、フラグや
  API を推測で書かない**。機能が無い・未提供なら「未実行」と記録する。
- 出典: fork https://github.com/yuki-inaho/harness2 、上流 Google Research
  https://github.com/google-research/harness2 （Apache-2.0）。上流の LICENSE と帰属を保持する。

## When to use

- ワークフロー/スキルの大きな改稿を、baseline と候補で比較したい。
- Propose–Probe–Compose の結果を、選定後の再評価まで含めて監査したい。
- 「選ばれた候補 = 改善」と主張してよいか判断したい。

使わない: typo 修正、1 ファイルの小さな変更、比較条件を固定できない探索。

## Prerequisites

- fork の checkout と、実行に必要な runtime。
- `docs/ORDINARY_TASKS.md` と `--help` の実出力（無ければ未実装として記録する）。
- 公開する例・fixture・評価ケースは合成データのみ。ローカルで利用者が許可した実タスクは、
  出力と証跡を非公開に保ち、私有物を公開しない限り実行してよい。
- 期待答案は評価側に分離し、proposer / composer に渡さない。
- 比較条件を固定できること: source revision / base / settings / model / budget / environment。
- 比較する snapshot を先に固定する。完全コピーまたは内容を固定した snapshot を使い、
  symlink 等を通じて共有の書き込み可能パスへ依存しない。run 開始後に frozen snapshot を
  編集しない。別途編集した source は次の比較の入力であり、実行中の比較対象ではない。
- この skill や他の skill の source を直すこと自体は、model の比較条件でも改善の証拠でも
  ない。採用は比較結果を見た後、root / 利用者が別に決める。
- 実行可能な例は fork（https://github.com/yuki-inaho/harness2 ）と、共有コレクション
  https://github.com/yuki-inaho/skills の利用 revision にある `examples/harness2-skills/`
  を参照する。これはコレクション側の開発用で、skill 単体には同梱されない。
  runner をこの skill に複製しない。

固定した条件は run manifest に残す（値は合成例）:

```text
run      : sample-task-01
source   : <commit>
base     : BASE
config   : <settings / model / budget を固定値で記録>
env      : <selected interpreter, sys.prefix, cwd>
artifacts: <receipt と artifact の保存先>
```

## Procedure

1. **Fix** — 比較条件を run manifest に固定する。途中で model・budget・base を黙って替えない。
2. **Baseline** — 固定条件で BASE を実行し、receipt（exit code, stderr, timeout, artifacts）を保存する。
3. **Propose** — 候補編集を作る。期待答案は proposer / composer に渡さない。
4. **Probe** — 同じ入力・同じ設定で候補を実行し、BASE と同じ形式の receipt を取る。
5. **Compose** — probe の差分から harness を構成する。ここは**選定**であり、改善の証明ではない。
   k=1 で候補が選ばれたという事実は選好の記録であって、品質差の証拠ではない。
6. **Reflect（post-selection）** — native の reflection は既存の rollout に対して行われる
   （勝手に replay へ読み替えない）。選ばれた harness の正しさは期待答案側で別途評価する。
   一般化を主張する場合だけ、独立した held-out replay を追加で行う（各タスク必須ではない）。
7. **Decide** — `KEEP_BASE` / tie / failure を正当な結果として残す。候補が基準を落とした
   なら `KEEP_BASE` が結論である。1〜2 例で一般化しない。

## Verification

- 各 run に実測 receipt がある（実行していない run を結果として数えない）。
- 比較表が同一条件（revision / base / settings / model / budget / environment）である。
- receipt が、実際に実行した argv・cwd・選択した interpreter と結び付いている。
  transcript 上の path 文字列への regex 一致や、ファイル名の存在だけを実行証拠にしない。
- artifact は実際に開いて確認する（exit code, stderr, 出力 hash, 生成物, 描画結果）。
  summary や READY メッセージを検証の代わりにしない。動的な挙動は実行記録を人手で追う。
- 権限設定の宣言を、実際にアクセスを拒否した証拠としない。tool event の入力・metadata
  は CLI の版に対応して読む。読み込まれた skill の解決先と実内容を確認し、解析できない
  event は未確認として残す。監査側の誤判定も失敗 receipt から消さない。
- 正しさの評価が期待答案側で行われ、生成側へ漏れていない。
- 選定（k=1 の選択）だけで「改善」と書いていない。改善主張は同一条件で測った差分に
  基づき、一般化する場合だけ held-out replay を追加する。
- source を編集しただけで比較をやり直していない場合、model 改善として書かない。
- 失敗・timeout・未実行を除外せず、そのまま報告する。

## Failure handling

- runtime 不在/未実装 → 「not executed」と明記する。推論を native Harness² の
  実行結果として書かない。
- フラグ不明 → `--help` と docs を読む。無い機能をでっち上げない。
- timeout / error → receipt を残し、比較から黙って落とさない。
- 条件不一致（入力・設定・model・budget・snapshot・environment が違う）→ 比較無効としてやり直す。
- 1 例だけの改善 → 一般化しない。追加例を示すか「限定的」と明記する。
- 候補が基準を下回る → `KEEP_BASE`。欠落や失敗を隠して候補を採用しない。
- 実行したコマンドが不明 → artifact から成功を推定しない。argv / cwd / receipt を回収できる
  まで「未確認」と記録する。

## Scope and authorization

- 利用者が指定した対象・範囲・完了条件を守る。スキルの都合で作業範囲を広げない。
- 新しい承認フローを追加しない。既存の権限・安全確認を増減させない。

## Notes

- 公開物には合成タスクと一般化した設定だけを書く。実ログ・実パス・内部名を載せない。
- 上流/fork の実装をコピーせず、この手順は独立に記述する。

## Growth log

日付付きの一般的な学びは [references/growth-log.md](references/growth-log.md) に追記する。
同じ学びが繰り返すか、失敗モードが深刻な場合だけ本文へ昇格する。
