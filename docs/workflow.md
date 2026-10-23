# ポータブルなワークフロー判断ガイド

この文書は、共有スキル集で使う**判断の流れ**を 1 か所にまとめたものである。
個々の手順の正本は各 `SKILL.md`、公開境界の正本は
[`PUBLIC_SKILLS_POLICY.md`](PUBLIC_SKILLS_POLICY.md)、検証設計の正本は
[ADR 0001](adr/0001-public-portable-skill-boundary.md) と
[ADR 0002](adr/0002-reproducible-validation-and-evaluation.md)、
スキルごとの検証範囲は [`skill-coverage.md`](skill-coverage.md)、
実行コマンドの契約はリポジトリ直下の `justfile` である。

このリポジトリの監査時点で共有スキルは **21 件**である。21 は固定された恒久定数ではなく、
`skills/*/SKILL.md` を動的に発見するテストと `docs/skill-coverage.md` が現在の監査件数として
記録している値である。件数を増減させるときは、カバレッジと検証範囲も同じ変更で更新する。

## 1. 対象と非対象

対象:

- ワークフローやスキルの**大きな改稿**を、baseline と候補で比較する判断。
- 比較条件（revision / base / settings / model / budget / inputs）を固定できる作業。
- 合成データと静的検査で再現できる検証、および明示した外部前提が必要な検証。
- 公開してよい汎用の手順・例・図だけを共有する作業。

非対象:

- typo 修正や 1 ファイルの小さな変更。比較ループを開くほどの不確実性がない。
- 比較条件を固定できない探索。条件が違う run を並べても改善の証拠にならない。
- 実ログ・実データ・実結果・private な識別子を公開物へ持ち込むこと。
- 実 provider / model / GPU / browser / 実機の動作を、静的検査だけで保証すること。
- この文書自身が新しい承認ゲートを作ること。公開可否は利用者と既存ポリシーが決める。

## 2. クイックスタート（uv locked / just check）

検証環境は `pyproject.toml`、`uv.lock`、`.python-version` で固定する。
`just` は薄いラッパーであり、各レシピの実体は `uv run --locked ...` で直接実行できる。

```bash
uv sync --locked --group dev
just check
```

`just check` は次の 4 つを順に実行する集約レシピである。

```text
lint      uv run --locked ruff check .
          uv run --locked python -m compileall -q skills tests
validate  uv run --locked python skills/skill-creator/scripts/validate_skill.py
test      uv run --locked pytest tests -q
privacy   uv run --locked python tests/privacy_scan.py
```

外部 CLI を必須にしない通常のローカル検査はここまでである。外部契約だけを明示的に
確認する場合は、pinned な CLI を用意したうえで次を使う。

```bash
just test-contract
# 実体: REQUIRE_AGENT_JSONL=1 uv run --locked pytest tests/test_agent_jsonl_contract.py -q
```

`just test-contract` は外部 CLI の欠落・旧版・非対応を skip にせず失敗にする。
`just check` は外部 CLI を要求しない。この違いを混同しない。

## 3. 静的・合成と外部前提を分ける

| 検査 | 外部前提 | 示すこと | 示さないこと |
| --- | --- | --- | --- |
| `just lint` / `just validate` | なし | 構文、frontmatter、構造、リンク、同梱物 | 実行時の挙動、外部ツールとの互換性 |
| `just test` | なし（合成 fixture） | 契約、判断ロジック、失敗経路の一部 | 実データ、実 provider、実 GPU、実ブラウザ |
| `just privacy` | なし | 公開テキストの分類レポート | 公開可否。0 件は安全宣言ではない |
| `just check` | なし | 上記の集約 | 外部 CLI・実 runtime の成功 |
| `just test-contract` | pinned な外部 CLI | その版の契約が実際に通ること | 他の版、実運用データ、全ての環境 |
| native Harness² の ordinary run | 実在する fork、manifest、runtime | その run の receipt と比較条件 | manifest が無い場合の実行、一般化 |

外部前提が無い場合は「未実行（not executed）」と記録する。推論や静的検査の結果を、
実行した runtime の証拠として書かない。privacy scan の 0 件も、人による公開判断の
代わりにはならない。

## 4. 判断フロー（15 ステップ）

図の正本は次の 2 ファイルである。どちらも編集可能な mxGraph XML で、SVG は同じ
`.drawio` から書き出した表示用の派生物である。

- [アーキテクチャ（.drawio）](diagrams/skill-workflow-architecture.drawio) /
  [SVG](diagrams/skill-workflow-architecture.svg)
- [シーケンス（.drawio）](diagrams/skill-workflow-sequence.drawio) /
  [SVG](diagrams/skill-workflow-sequence.svg)

1. **User goal** — 比較ループを開く価値のある、非自明なワークフロー/スキル改稿かを確認する。
2. **Workdoc** — 目的、scope、完了の定義（DoD）、原子的なチェックリストを書く。
   作業対象と変更範囲を先に固定する。
3. **Scope & discovery** — 既存の policy、ADR、coverage、現在のコマンドと docs を読む。
   記憶や推測ではなく、その revision の実物を正本にする。
4. **Fixed base / model / inputs** — revision、BASE、settings、model、budget、入力を
   run manifest に固定する。途中で黙って替えない。
5. **External prerequisites** — 外部 CLI、runtime、credential、network、GPU などの
   前提を明示的に確認する。無い場合は未実行として記録する。
6. **Baseline → Propose** — まず固定した BASE を実行し、answer と receipt を保存する。
   その後、期待答案（oracle）を渡さずに候補編集を作る。proposer / solver / executor に
   oracle を持たせない。
7. **Probe** — 同じ入力・同じ設定で候補を実行し、BASE と同じ形式の receipt を取る。
   実行は executor が担い、BASE と probe の条件を途中で替えない。
8. **Compose / select** — probe の差分から native Harness² が harness を構成し、
   候補を選ぶ。これは**選定**であり、改善の証明ではない。`k=1` の自明な選択は別の
   model call ではなく、「品質が上がった証拠」にもならない。
9. **Reflect（post-selection）** — 選ばれた harness について、既存の rollout を対象に
   native 側で振り返る。replay への読み替えを勝手に行わない。oracle は引き続き渡さない。
10. **Independent judge** — 期待答案を持つ独立した judge が、選定後の候補を生成側から
    隔離された状態で評価する。judge の receipt と exit code を保存する。proposer /
    executor は oracle を持たない。
11. **Adopt or KEEP_BASE** — 採用、KEEP_BASE、tie、failure を正当な結果として残す。
    失敗・timeout・tie を比較表から黙って落とさない。新しい承認フローは追加しない。
12. **Command verification** — 採用した状態で実際のコマンドを実行し、rc / stdout / stderr を
    保存する。`uv --locked`、`just check`、必要なら `just test-contract` を使う。
13. **Privacy review + authority** — 既存の公開ポリシーとレビュー手順で公開境界を点検する。
    機械走査は手掛かりであり、承認ゲートではない。公開可否は既存の権限が決める。
14. **Commit / push + source hash** — 公開してよい汎用の面だけを commit / push し、
    対象 revision の source hash を記録する。
15. **Shared install + owned cleanup** — portable な成果物だけを共有先へ導入し、
    自分が起動した renderer / agent / 一時プロセスを終了する。

## 5. シーケンスの役割とガードレール

シーケンス図の参加者は、coordinator、implementation worker、native Harness²、
editor + executor、independent judge、artifact store、repository である。

- **実行順**: 固定した BASE の実行（answer / receipt）→ propose → probe → compose / select →
  native の post-selection reflect（既存 rollout）→ independent judge、の順に進む。BASE の
  実行を propose の後ろへ移さない。compose / select と reflect を飛ばして judge に直結しない。
- **oracle の境界**: 期待答案は independent judge 側だけが持つ。proposer / solver /
  executor / composer の context へ渡さない。
- **選定と証明の分離**: 候補が選ばれたことは、品質が上がったことの証明ではない。
  改善主張は、同じ条件で測った差分と独立した評価に基づける。
- **k=1 の扱い**: 候補が 1 つだけの selection は trivial であり、別の model call ではない。
  選ばれたという事実だけで「品質向上」と書かない。一般化するなら、追加の比較や
  held-out の確認を別に行う。
- **失敗・tie の保持**: failure、timeout、tie、KEEP_BASE はすべて結果である。
  分母から除外したり、成功した run だけを並べたりしない。
- **承認フローの追加禁止**: 既存の権限・承認・安全確認を増やさない。この文書は
  手順と判断材料を提供するだけで、公開や送信の可否を決める新しいゲートを作らない。
- **静的な証拠と実行の証拠**: 静的検査・合成 fixture の成功を、実 runtime の成功として
  書かない。外部前提が無い run は未実行として残す。

## 6. 任意: native Harness² の ordinary CLI

この公開リポジトリは Harness² の fork も manifest も同梱しない。実際にインストールされた
fork があり、実在する manifest を用意できる場合だけ、次の形で任意に実行する。
フラグは記憶で書かず、必ずその環境の `--help` と docs を読む。

```bash
harness2-ordinary --help

# 計画だけを確認する。何も書き込まない。
harness2-ordinary \
  --manifest "<path/to/manifest.json>" \
  --output "<fresh-output-directory>" \
  --k 1 \
  --modes parallel \
  --dry-run

# 実 run。output は fresh な空ディレクトリを指定する。
harness2-ordinary \
  --manifest "<path/to/manifest.json>" \
  --output "<fresh-output-directory>" \
  --k 1 \
  --modes parallel \
  --tag "<tag>"
```

- `--output` は毎回 fresh である。既存ディレクトリは実行前に拒否され、resume は無い。
- `--dry-run` は解決済み plan を表示し、成果物を書かない。
- manifest が無い状態で「実行できる」と pretend しない。manifest / fork / runtime が
  無ければ、その run は未実行である。
- model と budget は manifest 側の固定条件であり、この文書は特定の provider / model を
  固定しない。`python3 -m harness2.cli.ordinary ...` が使える環境では同じ引数を受け付ける。

## 7. 評価文書の扱い

Harness² の評価結果をまとめる `docs/harness2-evaluation.md` は、private workspace 側で
準備中の文書である。この公開リポジトリにはまだ存在しないため、**壊れたリンクを追加しない**。
公開可能な形になった時点で、この節から実在するファイルへリンクする。
それまでは、評価の詳細を公開 docs の主張として書かない。

## 8. 公開前の最小確認

1. [`PUBLIC_SKILLS_POLICY.md`](PUBLIC_SKILLS_POLICY.md) の禁止情報を確認する。
2. `just check` を実行し、lint / validate / test / privacy の結果を保存する。
3. 外部契約を主張する場合は、pinned な CLI を用意して `just test-contract` を実行する。
4. 図は `.drawio` と `.svg` の両方を残し、SVG だけでなく編集可能な source も公開する。
5. 実ログ、実結果、実パス、内部識別子、実 provider 設定、スクリーンショットを公開物へ
   入れていないことを、差分・例・docs・metadata・commit / PR 本文の面で確認する。
6. 公開可否は既存の権限とポリシーで決める。privacy scan の 0 件を安全宣言にしない。
