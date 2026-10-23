# Harness² 評価の再現手順（公開・合成データ）

この文書は、公開スキル集の改善を **native Harness² ordinary CLI** で再現するための
最小手順である。新しい評価フレームワークを同梱するものではない。実在する公開 fork
[`yuki-inaho/harness2`](https://github.com/yuki-inaho/harness2) の既存 CLI と
`docs/ORDINARY_TASKS.md` の manifest 契約をそのまま使う。

- 対象 fork の固定 commit: `9953226877af0fe742b092a12f8ce4ac3c818a86`
- 上流: Google Research の Harness²（Apache-2.0）。fork の LICENSE と帰属を保持する。
- 公開テストは **モデルを呼ばない**。fake CLI、manifest の `--dry-run`、独立 judge の
  合成ケースだけを検証する。
- 実行時の生成物（run ディレクトリ、raw log、model 応答、cost、session id）は
  すべて非公開であり、commit しない。

この文書と `examples/harness2-skills/` は、clone 直後から「何を準備し、どこを確認し、
何を主張してはいけないか」を再現できるようにするための薄い例である。private な
プロジェクト名・結果・パス・session・設定・実 provider profile は含めない。

関連する公開文書: [README](../README.md) /
[公開スキル方針](PUBLIC_SKILLS_POLICY.md) /
[ワークフロー](workflow.md) /
[ADR 0001](adr/0001-public-portable-skill-boundary.md) /
[ADR 0002](adr/0002-reproducible-validation-and-evaluation.md)。

## 1. 何を再現でき、何を再現しないか

再現できる（公開テストまたは `--dry-run` で確認できる）:

- 3 family（`workdocs` / `coordination` / `specialists`）の準備物の生成。
- c1..c8 OpenCode surface に適合する base harness と、完全な skill snapshot の分離。
- references / assets の `scripts/reference_*` / `scripts/asset_*` への平坦化と、
  `SKILL.md` 内リンクの書き換え。
- schema 1 の ordinary manifest が、実 fork の `--dry-run` を通ること。
- fake `opencode` CLI に対する、正しい answer / 不正 wrapper / case 欠落 / timeout /
  空白を含むパスのテスト。
- occupied / symlink / dangling symlink / 入力との重なり / 既存 receipt を拒否し、
  sentinel と path alias を削除しない負の対照。fresh な native scaffold の保持。
- 独立 judge の gold 一致、常時 `stop` / 常時 `proceed` の負の対照、duplicate /
  missing の unknown 扱い。
- 21 スキル・42 ケース・126 decision field の synthetic fixture と、3 つの mixed
  held-out ケースの分離。

再現しない（この公開物の主張ではない）:

- 実 provider / model の品質、可用性、料金の比較。
- 実 JAX / GPU / WebGL / browser / Docker / MuJoCo / Herdr / agmsg の runtime 動作。
- すべての model や agent runtime で同じ結果になること。
- private workspace で実行した実際の run 結果。
- k=1 の選択が改善であること。k=1 は候補 final の選択であり、base に対する測定された
  改善ではない。

ケースは「workflow の判断プロトコル」を問う合成データである。JAX の実測、WebGL の
描画、GPU の有無、Docker daemon の稼働、provider の提供状况を保証するものではない。

## 2. 前提

- Python 3.12 と `uv`（fork の `.python-version` / `uv.lock` に従う）。
- 公開 fork の checkout。`uv run --locked harness2-ordinary --help` が通ること。
- 実際にインストールされた OpenCode CLI（`opencode --version` が通る）。
- 利用者が実際に serve できる `provider/model#variant`。**model は同梱しない**。
  account 設定、vendor 既定、free fallback は使わない。
- 3 family を比較する場合は、各 family ごとに **fresh な準備先と fresh な run 先**を
  用意する。resume は無い。

```bash
python3 --version
uv --version
opencode --version
```

`opencode` が PATH に無い場合、この例の executor は起動できない。先に CLI の導入と
認証を利用者側で済ませる。この文書は特定の provider を固定しない。

## 3. 公開データの範囲

| family | skills | cases | decision fields |
| --- | ---: | ---: | ---: |
| `workdocs` | 7 | 14 | 42 |
| `coordination` | 7 | 14 | 42 |
| `specialists` | 7 | 14 | 42 |
| 合計 | 21 | 42 | 126 |

- 各スキルに `--positive` と `--boundary` の 2 ケースがある。
- 期待値は `fixtures/expected.json` の 42 キー。`decision` が 2 値の許容集合に
  なっているケースが 2 件ある（`stop` または `inspect`）。
- mixed held-out は 3 ケース（`fixtures/heldout/cases.json` と
  `fixtures/heldout-expected.json`）。task source にはコピーしない。
- 期待値は **model の入力に渡さない**。`oracle/expected.json` は準備先の
  `base/` / `tasks/` / executor workspace の外に置く。

## 4. 準備（非モデル操作）

公開スキル集の checkout で実行する。`--skills-root` の既定値は
`examples/harness2-skills/prepare.py` から `__file__` で計算した repository の
`skills/` であり、private path を埋め込まない。

```bash
cd <public-skills-checkout>

uv run --locked python examples/harness2-skills/prepare.py \
  --family workdocs \
  --model PROVIDER/MODEL#VARIANT \
  --output /tmp/h2-skills-workdocs

uv run --locked python examples/harness2-skills/prepare.py \
  --family coordination \
  --model PROVIDER/MODEL#VARIANT \
  --output /tmp/h2-skills-coordination

uv run --locked python examples/harness2-skills/prepare.py \
  --family specialists \
  --model PROVIDER/MODEL#VARIANT \
  --output /tmp/h2-skills-specialists
```

`PROVIDER/MODEL#VARIANT` は実在する完全な id に置き換える。次の場合は準備が失敗する。

- `--model` が無い、`provider/model` の形で variant が無い。
- `free` / `auto` / `default` / `any` / `best` / `cheapest` / `fallback` などの
  free・自動・fallback id。
- `--output` が既に非空である、`--skills-root` の中にある、または symlink（dangling を
  含む）である。prepare は一時ディレクトリを作り、成功時だけ rename する。既存の
  ファイルやディレクトリを削除して置き換えることはない。

### 4.1 準備先の形

```text
/tmp/h2-skills-workdocs/
  manifest.json                 # ordinary manifest, schema 1
  base/                         # c1..c8 editable OpenCode surface
    systemprompt.md
    guardrails.md
    LongTermMEMORY.md
    tool_descriptions/tool_guidance.md
    skills/<skill>/SKILL.md
    skills/<skill>/scripts/reference_*
    skills/<skill>/scripts/asset_*
  resources/<skill>/            # complete, read-only snapshot
    SKILL.md
    references/...
    assets/...
    scripts/...
    agents/...
  tasks/workdocs-all/
    task.md
    source/cases.json           # selected synthetic cases only
  tools/solve.py                # executor
  tools/judge.py                # independent judge
  oracle/expected.json          # answer key, outside model inputs
  prepare-receipt.json          # hashes and normalization mapping
```

`base/skills/<skill>/SKILL.md` は、元の `references/...` / `assets/...` リンクを
`scripts/reference_...` / `scripts/asset_...` に書き換えたコピーである。元の完全な
スキルは `resources/<skill>/` に残る。executor は両方を workspace に置き、編集済みの
`base` を `resources` の上に重ねる。したがって、baseline に欠けた reference は無い。

SKILL.md が workspace root からの `python3 scripts/<name>.py` を呼ぶ場合、その helper は
`base/scripts/<name>.py` にも mirror する。同名 helper がスキル間で衝突する場合は、その
スキルの参照を `skills/<skill>/scripts/<name>.py` に書き換える。参照先の helper が
baseline に存在しない場合は、 invocation 行を「未同梱なので unknown と報告する」という
正直な注記に置き換え、fake script を同梱しない。これらの適応は
`prepare-receipt.json` の `script_adaptations` に記録する。

`prepare-receipt.json` には次が入る。

- family、model、fork commit、skills 一覧、cases 数、decision fields 数。
- 各 skill の `base_tree_sha256` / `resources_tree_sha256`。
- `normalization`（元の reference/asset パス → 平坦化先）。
- task.md / source cases / expected / manifest の SHA-256。
- `oracle_in_model_inputs: false`。

準備は model を呼ばず、指定した fresh output だけを書く。skills tree は変更しない。

### 4.2 executor の run dir と answer の安全条件

`tools/solve.py` は、既存の実行証跡を消して再利用しない。呼び出し側は次の条件を
満たす fresh な attempt を渡す。

- `--run-dir` は fresh な attempt である。`workspace/`、`agent_events.jsonl`、
  `agent_stderr.log`、`session_api.json`、`trajectory.md`、`executor_receipt.json` の
  いずれかが既にある場合は、削除せず exit 2 で停止する。native core が先に作る
  `run.json` / `input/` / `harness/` は許容するが、executor の receipt がある attempt は
  再利用しない。native 側の retry は、新しい run directory を明示的に用意するか、
  正直に失敗させる。上流 fork が同じ run_dir を先に `rmtree` して再利用する挙動は
  この例の外側で起こるため、再試行では fresh な run_id / run_dir を渡すこと。
- `--out` は既存なら停止し、answer は `O_EXCL` で一度だけ作る。既存ファイルの
  `unlink` や上書きをしない。`--out` 自身が symlink（dangling を含む）なら拒否する。
- `--run-dir` / `--out` は task、task source、harness、resources と重ならない。
  入力側の symlink は解決した実パスで比較し、出力側の symlink は拒否する。
- `workspace/` は `mkdir` で新規作成する。既存の workspace を `rmtree` しない。
- 失敗、timeout、answer 拒否の後も workspace と raw event / stderr は run dir に残す。

これらの検査は path の取り違えを防ぐためのものであり、OS sandbox ではない。同時に
rename される競合や、実行中の任意 code による書込みまで防ぐとは主張しない。

## 5. `--dry-run` で manifest を検証する

実 fork の CLI は、manifest の未知キー、schema、相対パス、argv の placeholder、
`base_harness` / `tasks_dir` の存在を実行前に検証する。`--dry-run` は plan を表示し、
run 先を書かない。

```bash
cd <fork-checkout>

uv run --locked harness2-ordinary \
  --manifest /tmp/h2-skills-workdocs/manifest.json \
  --output /tmp/h2-skills-workdocs-run \
  --k 1 \
  --modes parallel \
  --dry-run
```

期待する plan の要点:

- `tasks` が `["workdocs-all"]`。
- `editor.model` と `executor.declared_model` が、prepare に渡した model と一致する。
- `judge_enabled` が `true`、`k` が `1`、`modes` が `["agg"]`（`parallel` の解決結果）。
- `output` が fresh な `/tmp/h2-skills-workdocs-run`。
- 実行後も `/tmp/h2-skills-workdocs-run` が作られていない（dry-run は書かない）。

coordination / specialists も同じ形で、manifest と output だけを差し替えて確認する。

## 6. 実 run（k=1 / parallel）

モデル呼び出しを含むため、利用者が model と予算を決めてから実行する。1 family につき
**1 回の fresh な ordinary invocation** とする。Library history を持ち越さない。

```bash
cd <fork-checkout>

uv run --locked harness2-ordinary \
  --manifest /tmp/h2-skills-workdocs/manifest.json \
  --output /tmp/h2-skills-workdocs-run \
  --k 1 \
  --modes parallel \
  --tag workdocs-1
```

同様に:

```bash
uv run --locked harness2-ordinary \
  --manifest /tmp/h2-skills-coordination/manifest.json \
  --output /tmp/h2-skills-coordination-run \
  --k 1 --modes parallel --tag coordination-1

uv run --locked harness2-ordinary \
  --manifest /tmp/h2-skills-specialists/manifest.json \
  --output /tmp/h2-skills-specialists-run \
  --k 1 --modes parallel --tag specialists-1
```

- `--output` は毎回 fresh。既存の非空ディレクトリは拒否される。resume は無い。
  executor の `--run-dir` / `--out` も同じ run の下で fresh でなければならない。
- `--k 1` は 1 候補。selection は候補 final の選択であり、改善の測定ではない。
- `--modes parallel` は明示する。timeout は manifest 側で固定されている。
- exit code: `0` は全 task 完了、`1` は未完了または editor 全失敗で degraded、
  `2` は manifest / 引数 / output の misconfiguration。

### 6.1 明示された時間と予算

準備先の manifest は次を固定する。

| 項目 | 値 | 意味 |
| --- | ---: | --- |
| `editor.timeout_s` | 600 | native editor 1 回の wall-clock 上限 |
| `editor.startup_timeout_s` | 90 | 起動待ちの上限（wall とは別） |
| `editor.steps` | 40 | 設定値。installed CLI が強制するとは主張しない |
| `executor.timeout_s` | 300 | executor（この例では OpenCode 呼び出し）の上限 |
| `--timeout-s` (executor argv) | 270 | 内側の CLI wall 上限。manifest の 300 秒より短く固定 |
| `judge.timeout_s` | 120 | 独立 judge の上限 |
| `obs_trunc` | 20000 | 1 observation の表示 budget（下限 10000） |

model の料金は provider 側で決まる。report の `cost` は CLI が
`step_finish.part.cost` を返したときだけ合計し、1 つでも未報告なら
`cost_usd: null` / `cost_source: "unmeasured"` になる。**未測定を 0 として扱わない。**

## 7. 生成物を確認する

run 先は private である。次は読み方の例であり、raw log や model 応答を公開しない。

```bash
python3 -m json.tool /tmp/h2-skills-workdocs-run/preflight.json
python3 -m json.tool /tmp/h2-skills-workdocs-run/report.json
python3 -m json.tool /tmp/h2-skills-workdocs-run/judgment.json
```

確認する項目:

- `report.json` の `tasks[].status`、`tasks[].errors`。
- `editor_health`（run 全体）と `tasks[].integration.editor_health`。
  `all_failed` または editor receipt が無い `ok` は degraded であり、native status を
  editor 成功として読まない。
- `degraded_tasks`、`cost`、`notes`。
- `selection_is_a_measurement: false`（k=1）。
- `executor.declared_model` と `declared_model_verified: false`。

### 7.1 editor と executor の receipt

```bash
find /tmp/h2-skills-workdocs-run/audit/sessions -maxdepth 2 -type f | sort
find /tmp/h2-skills-workdocs-run/runs/executions -name executor_receipt.json -print
```

- `audit/sessions/<label>/start.json`: 起動設定、`env_keys_set`、`xdg_isolation`。
- `audit/sessions/<label>/process.json`: process 情報。
- `audit/sessions/<label>/events.jsonl`: CLI の JSONL event（raw）。
- `audit/sessions/<label>/stderr.log`、`exit.json`: stderr と終了状態。
- `runs/executions/<task>/<run>/run.json`: 展開後 argv、timeout、declared model。
- `runs/executions/<task>/<run>/exit.json`: return code、signal、timeout、answer hash。
- `runs/executions/<task>/<run>/executor_receipt.json`: この例の executor が残す
  CLI version、argv、cwd、session id、cost、answer SHA、前後の snapshot hash。
- `runs/executions/<task>/<run>/answer.json`: 受理された answer。

`executor_receipt.json` の `model_verified` は `false` である。`--model` の argv は
**設定された label** であり、provider が実際にその model を使った証明ではない。
native SDK / session API を別途照会した場合だけ、その事実を別項目として記録できる。

`session_reconciliation` は local OpenCode 2.1.2 の
`GET /api/session/active`（`{"data": {"<sessionID>": {"type": "running"}}}`）を使う。

- 照会するのは、event から得た **exact な session id 1 件**だけである。active map の
  他の entry は receipt にコピーしない。
- その id が `type: "running"` で存在すれば `active`。存在しなければ API の定義どおり
  `inactive`（この OpenCode process で active でない、という意味であり、OS process の
  終了証明ではない）。API が失敗・不正 JSON・未知の値なら `pending` のままにする。
- timeout の場合だけ、exact な id がまだ `active` のときに
  `POST /api/session/<sessionID>/interrupt` を bounded timeout で 1 回呼ぶ。
  `interrupted: true` は interrupt 要求が受け付けられた ack であり、停止の証明ではない。
  ack 後は exact な id だけを最大 10 秒の bounded poll で
  `GET /api/session/active` に照会する。active map から消えたこと（verified inactive）と
  owned frontend の終了の両方を確認した場合だけ `stopped_claimed: true` とする。
  ack 後も active、API が失敗・不正、または frontend の終了を確認できない場合は
  `pending`（停止未確認）のまま workspace を保持する。
  それ以外の id や、API が `pending` の場合は cancel しない。
- `session_api.json` には exact id、状態、request argv、return code、response hash、
  cancellation の結果と bounded poll の観測状態だけを残す。active map 全体、credential、
  server 設定は残さない。

### 7.2 selection と reflection

```bash
find /tmp/h2-skills-workdocs-run/runs -path '*/selection/selection.json' -print
find /tmp/h2-skills-workdocs-run/runs -path '*/reflection/*' -type f -print
```

- `selection/selection.json` は、どの final が選ばれたか、fallback したか、
  `chosen_run_dir` はどこかを記録する。
- `reflection/...` は adoption 後の学習記録である。native の reflection は既存の
  rollout に対して行われる。replay へ読み替えない。
- k=1 では selection は 1 候補の選択であり、base との改善差ではない。

### 7.3 独立 judge

native core は adoption record（`selection/selection.json`）が存在する場合だけ
judge を実行する。judge は task prompt / task source / answer のコピーだけを受け取り、
`oracle/expected.json` を別ファイルとして読む。

```bash
find /tmp/h2-skills-workdocs-run/runs/judge -type f | sort
python3 -m json.tool /tmp/h2-skills-workdocs-run/runs/judge/<task>/<run>/judge.json
python3 -m json.tool /tmp/h2-skills-workdocs-run/runs/judge/<task>/<run>/stdout.log
```

- 3 field（`decision` / `output_target` / `completion`）× 14 case = 42 criteria。
- `criteria[].passed` は boolean。malformed / duplicate / missing は unknown（非ゼロ）
  であり、`0/n` にしない。
- `tie`、`KEEP_BASE`、failure、no observed effect は結果として残す。改善と読み替えない。

judge を手で診断実行する場合も、native の adoption を飛ばして「採用済み」と主張しない。
手動実行は receipt の確認であり、native の judge 記録の代わりではない。

## 8. held-out の扱い

`fixtures/heldout/cases.json` の 3 ケースは、3 family の task source に含まれない。
必要なら adoption 後に、同じ source / model / budget / settings で別の fresh output に
対してだけ replay する。held-out の結果を proposer / composer / executor の入力に
戻さない。1〜2 例の結果から一般化しない。

## 9. この例がしないこと（監査上の限界）

- **permission fence は OS sandbox ではない。** `OPENCODE_PERMISSION` は tool の
  permission policy であり、editor が workspace 外を読めない証明ではない。
- **run dir / out の検査は OS sandbox ではない。** symlink、occupied path、入力との
  重なり、既存 receipt を拒否して不用意な削除・上書きを避けるが、同時 rename や
  実行中 code の任意書込みまで防ぐとは主張しない。
- **upstream の native stage loop は editor を複数回呼び得る。** この例の executor は
  1 回だけ起動し、独自の retry / model 切替 / fallback をしない。quota / auth error の
  後の再試行は upstream の transport 挙動であり、この例は attempt ごとの receipt を
  保証しない。再試行では fresh な run_id / run_dir を渡す。
- **timeout は所有する process group だけを kill する。** `setsid` などで detach した
  子孫は生き残り得る。この例は「停止した」と過大に主張しない。
- **remote session の停止は推測しない。** exact な session id があり local の
  `/api/session/active` が応答する場合だけ、その 1 件を照会する。active map に無い場合は
  `inactive` と記録するが、これは OS process の終了証明ではない。API が失敗・不正なら
  `pending` と記録する。timeout 時に cancel するのは、その id がまだ `active` で、
  interrupt が `interrupted: true` を返した場合だけである。ただし ack は受付の記録で
  あって inactivity の証明ではないため、ack 後に exact id を bounded poll し、active map
  からの消失と owned frontend の終了を確認できるまで `stopped_claimed: true` にしない。
  GUI の idle 表示から remote の生存を推測しない。timeout 後も workspace を削除しない。
- **cost は未測定なら `null`。** 0 と混同しない。
- **`editor.steps` は設定値。** installed CLI が step limit を強制するとは主張しない。
- **`executor.model` は declared label。** 実際の provider / model の証明ではない。
- **公開テストは model を呼ばない。** fake CLI と `--dry-run` の成功は、実モデルの
  品質・provider の可用性・実 runtime の成功を意味しない。
- **生ログは private。** `events.jsonl`、model 応答、session id、cost、answer の実値は
  commit しない。公開するのは合成 fixture と一般化した手順だけである。

## 10. 公開テスト

```bash
cd <public-skills-checkout>

uv run --locked ruff check .
uv run --locked pytest tests/test_harness2_example.py -q
uv run --locked pytest tests -q
uv run --locked python tests/privacy_scan.py
```

実 fork の `--dry-run` もテストする場合だけ、fork の場所を環境変数で渡す（既定では
skip され、private path を source に埋め込まない）:

```bash
HARNESS2_FORK=<fork-checkout> \
  uv run --locked pytest tests/test_harness2_example.py -q
```

公開テストには、occupied / symlink / dangling symlink / 入力との重なり / 既存 receipt を
渡したときに sentinel と path alias が残る負の対照、native core が先に作った scaffold を
保持したまま fresh attempt を実行できる対照、active-session API の exact id 照会と
timeout cancel の対照を含む。fake CLI は model を呼ばない。

`HARNESS2_FORK` を設定しない通常の公開テストは、fake CLI と合成 fixture だけで完結する。
`just` recipe への統合はリポジトリ root 側で行う。それまでは上記の `uv run --locked`
コマンドが契約である。既定の `just check` に外部 fork や実 model の依存を追加しない。
