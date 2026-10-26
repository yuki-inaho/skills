---
name: harness2-portable-workflow
description: >-
  Use when a workflow or skill needs a substantial Harness² Propose–Probe–Compose redesign or self-critique — fix baseline, settings, model and budget, probe candidates, reflect after selection, and report honest evidence. Not for small edits. Triggers: Harness2 で改善を検証する, propose-probe-compose, ワークフロー改善の比較, スキル改善の自己批判, KEEP_BASE 判断, Harness² run の監査.
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

固定した条件は run manifest に残す（値は合成例）:

```text
run    : sample-task-01
source : <commit>
base   : BASE
config : <settings / model / budget を固定値で記録>
artifacts: <receipt の保存先>
```

## Procedure

1. **Fix** — 比較条件を run manifest に固定する。途中で model・budget・base を黙って替えない。
2. **Baseline** — 固定条件で BASE を実行し、receipt（exit code, stderr, timeout, artifacts）を保存する。
3. **Propose** — 候補編集を作る。期待答案は proposer / composer に渡さない。
4. **Probe** — 同じ入力・同じ設定で候補を実行し、BASE と同じ形式の receipt を取る。
5. **Compose** — probe の差分から harness を構成する。ここは**選定**であり、改善の証明ではない。
6. **Reflect（post-selection）** — native の reflection は既存の rollout に対して行われる
   （勝手に replay へ読み替えない）。選ばれた harness の正しさは期待答案側で別途評価する。
   一般化を主張する場合だけ、独立した held-out replay を追加で行う（各タスク必須ではない）。
7. **Decide** — `KEEP_BASE` / tie / failure を正当な結果として残す。1〜2 例で一般化しない。

## Verification

- 各 run に実測 receipt がある（実行していない run を結果として数えない）。
- 比較表が同一条件（revision / base / settings / model / budget）である。
- 正しさの評価が期待答案側で行われ、生成側へ漏れていない。
- 選定（k=1 の選択）だけで「改善」と書いていない。改善主張は同一条件で測った差分に
  基づき、一般化する場合だけ held-out replay を追加する。
- 失敗・timeout・未実行を除外せず、そのまま報告する。

## Failure handling

- runtime 不在/未実装 → 「not executed」と明記する。推論を native Harness² の
  実行結果として書かない。
- フラグ不明 → `--help` と docs を読む。無い機能をでっち上げない。
- timeout / error → receipt を残し、比較から黙って落とさない。
- 条件不一致（入力・設定・model・budget が違う）→ 比較無効としてやり直す。
- 1 例だけの改善 → 一般化しない。追加例を示すか「限定的」と明記する。

## Scope and authorization

- 利用者が指定した対象・範囲・完了条件を守る。スキルの都合で作業範囲を広げない。
- 新しい承認フローを追加しない。既存の権限・安全確認を増減させない。

## Notes

- 公開物には合成タスクと一般化した設定だけを書く。実ログ・実パス・内部名を載せない。
- 上流/fork の実装をコピーせず、この手順は独立に記述する。

## 実タスクと改善実験の境界

- 実成果物の生成が主目的なら、最小の実入力から成果物まで通すことを優先する。通常作業を始める条件としてnative最適化runを追加しない。
- 観測した失敗に対する狭い手順修正は既存文書へ追記できるが、比較実験をしていなければ「運用指示の修正」と報告し、Harness²で改善を実証したとは書かない。
- 準備チェック数ではなく利用者が受け取る成果で評価する。モデル・入力・条件の違う成功例を、過去手順との速度・品質の改善率にしない。
