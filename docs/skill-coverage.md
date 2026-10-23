# スキル別カバレッジ

この文書は、現在ツリーに存在する共有スキルごとに「何を変更し、何を検証し、何を
証明しないか」を記録する。スキル一覧は `tests/test_skill_coverage.py` が
`skills/*/SKILL.md` から動的に発見する。ここに書く 21 は執筆時点の件数であり、
テストが固定する恒久定数ではない。

共通の検証:

- **strict YAML**: 全スキルの frontmatter を PyYAML の safe loader（重複キー拒否）で解析する。
- **構造**: name とディレクトリの一致、kebab-case、description、同梱物、相対リンク、
  同梱 script 参照を確認する。
- **installer**: 全スキルツリーを隔離アーカイブから導入し、recursive tree hash を比較する。
- **privacy**: Git-tracked と intended-new の公開テキストを分類し、件数とファイル名だけを
  レポートする。証跡であり承認ゲートではない。非 Git ルートやリポジトリ外へ解決される
  symlink は再帰走査へフォールバックせず拒否する。

どの行も、実データ・実 provider・実 GPU・実ブラウザ・実 Herdr での実行を証明しない。
実行を伴う検証は、明示した専用ジョブまたは利用者環境でだけ行う。

## agent-jsonl-compact-reader

- 判定: 変更（外部契約の実行条件）。
- 変更: `REQUIRE_AGENT_JSONL=1` のとき、バイナリ欠落・0.3.0 未満・version 非対応を
  skip ではなく失敗にする。CI に 0.3.1 の musl アセットを `.sha256` と固定ダイジェストで
  検証して導入する専用ジョブを追加した。
- 検証が示すこと: 合成 JSONL に対する 0.3.1 の version/view/search/pair/partial/retry/cursor
  契約。必須モードの gate 自体も合成 fake でテストする。
- 検証が示さないこと: 0.2.x legacy export、実セッションログ、バイナリ未導入の通常ローカル
  実行。通常 `just test` では 9 件が skip になり得る（CI の専用ジョブは必須）。

## check-finished-workdoc

- 判定: 変更。
- 変更: `rg` が無い環境向けの `find` 代替を明記し、公開サマリへ実パス・識別子・
  セッションログ・private 結果をコピーしない注意を追加した。
- 検証が示すこと: completion summary テンプレートの章構成（8.1〜8.7）と最終判定の形式。
- 検証が示さないこと: 実リポジトリに対する完了照合、チェック済み主張の真偽、証跡の十分性。

## demo-rehearsal

- 判定: 変更。
- 変更: frontmatter を strict YAML 化。スクリーンショット差分をサイズ多様性だけに
  依存せず、内容ハッシュ + ピクセル差分または既知 view state で確認する形へ変更。
  PII/実画面の公開注意を追加。
- 検証が示すこと: frontmatter、リンク、同梱物の構造。
- 検証が示さないこと: 時間設計、headless リハーサル、スクリーンショット取得、聴衆 PDCA。

## grill-me

- 判定: 変更（小）。
- 変更: 本文の打ち切り条件と growth log の最大ラウンド数を 4 に揃えた（3〜4 で収束を試み、
  4 を超えたら未解決として打ち切る）。
- 検証が示すこと: frontmatter、question bank へのリンク、同梱物。
- 検証が示さないこと: 実際の frontier 抽出、事実調査、ユーザー確認、実装前停止。

## handover

- 判定: 変更。
- 変更: 出力前の最終確認（`{{` 残存なし、ファイル未作成、TBD の限定）と、
  セッション内容を公開チャネルへ出す際の private 情報注意を追加。
- 検証が示すこと: 出力テンプレート、`{{date}}` 等のプレースホルダ、最終確認章の存在。
- 検証が示さないこと: 実セッションからの生成、プレースホルダ置換、private 値の判断。

## harness2-portable-workflow

- 判定: 変更（frontmatter のみ）。
- 変更: colon-space を含む description を引用し、strict YAML で読めるようにした。
- 検証が示すこと: frontmatter、リンク、同梱物。
- 検証が示さないこと: baseline/candidate の実行、receipt、比較条件の一致、KEEP_BASE 判断。

## herdr-opencode-agmsg

- 判定: 変更。
- 変更: 公開 catalog を provider/model 既定を持たない空の neutral template に置換し、
  合成 ID の example を別ファイルに分離した。planner は空 catalog を
  `catalog_unconfigured` で明示停止する。テストは合成 provider ID のみを使う。
  cleanup gate のファイル読み込みを `Path.read_text` に変更した。
- 検証が示すこと: 純粋な provider 選択（catalog∩discovery、free 禁止、capability、
  quota、bounded retry、auth stop）と cleanup 判断を合成入力で確認する。
- 検証が示さないこと: 実 Herdr、実 OpenCode、実 provider、実 agmsg、認証・課金・
  保持設定。公開テンプレートは実運用の catalog ではない。

## jax-performance-tuning

- 判定: 変更。
- 変更: frontmatter を strict YAML 化。存在しない `scripts/analyze_trace.py` を削除し、
  公式の `jax.profiler` + TensorBoard trace viewer と公式ドキュメントを案内。
  tool 固有の固定一時パスを `JAX_CACHE_DIR` / `JAX_TRACE_DIR` の利用者指定へ変更。
  実測を伴わない性能数値を削除し、条件・版・日付を記録する形にした。
- 検証が示すこと: false command と tool 固有絶対パスが残っていないこと、公式 trace view
  への参照があること。
- 検証が示さないこと: JAX/GPU 実行、キャッシュヒット、profiler trace、速度改善。
  性能主張は利用者環境の実測なしには行わない。

## mujoco-web-wasm-demo

- 判定: 変更。
- 変更: frontmatter を strict YAML 化。スクリーンショット差分を content hash /
  `__status()` で確認する形へ変更。モデル・ポーズ・画面の公開注意を追加。
- 検証が示すこと: frontmatter、リンク、同梱物。
- 検証が示さないこと: Node/WebGL/ブラウザ実行、MJCF 読み込み、FK、描画、撮影。

## playwright-cli-automation

- 判定: 変更。
- 変更: frontmatter を strict YAML 化。差分確認を content hash へ変更し、サイズは
  前処理に限定。スクリーンショット/console log の公開注意を追加。
- 検証が示すこと: frontmatter、リンク、同梱物。
- 検証が示さないこと: ブラウザ起動、eval、snapshot、console 収集、スクリーンショット比較。

## public-repository-privacy-review

- 判定: KEEP（本文は既に公開境界・差分・例・docs・metadata・PR 本文を対象にしている）。
- 変更: なし。全体スキャナの証跡化と合成 canary テストはリポジトリ側で追加した。
- 検証が示すこと: `tests/privacy_scan.py` が合成 canary を分類し、値を出力しないこと。
  非 Git ルートと外部 symlink を rc2 で拒否し、スコープを暗黙に広げないこと。
- 検証が示さないこと: 人による公開判断、ゼロヒットの安全性、実在 denylist の完全性。
  このスキル自体は承認ゲートを追加しない。

## review-measurement-contract

- 判定: KEEP（prose-first の判断手順で、見出しの rote 化を避ける）。
- 変更: なし。
- 検証が示すこと: frontmatter、リンク、同梱物。
- 検証が示さないこと: 実ベンチマークの分母・母集団・版の照合、再計算、因果判断。

## review-written-workdoc

- 判定: 変更。
- 変更: local instruction 探索に `CLAUDE.md` / `OPENCODE.md` を追加し、公開レビュー時の
  private 情報注意を追加した。
- 検証が示すこと: review rubric の 9 章構成、frontmatter、同梱物。
- 検証が示さないこと: 実 workdoc のレビュー、安全な patch 適用、review-only の遵守。

## skill-creator

- 判定: 変更。
- 変更: validator を regex から PyYAML safe loader（重複キー拒否）へ置換。hard error と
  推奨見出しの advisory warning を分離。colon-space / quoted / folded / block /
  duplicate / non-mapping / frontmatter / name / description の失敗テストを追加。
  PyYAML を `pyproject.toml` の dev 依存に宣言し、PEP 723 metadata で単体 `uv run` も可能に
  した。依存ゼロの記述を更新。template の growth-log リンクは inline code に変更。
- 検証が示すこと: strict YAML の受理・拒否、duplicate key、非マッピング、name 不一致、
  description 欠落、advisory heading が error にならないこと。
- 検証が示さないこと: 各エージェントの loader への登録、スキル作成セッション、公開判断。

## start-with-workdocs

- 判定: 変更。
- 変更: 完了確認の `grep -c` に `|| true` を付け、0 件が rc1 になることと複数 workdoc で
  ファイルごとの出力になることを明記した。
- 検証が示すこと: 完了コマンドの形式（zero-count の扱いを含む）。
- 検証が示さないこと: 実チェックリストの逐次実行、作業記録更新、失敗項目の維持。

## start-work-audit-pattern

- 判定: 変更。
- 変更: description から特定 runtime の限定を外し、strict YAML 化。自己識別を runtime 名 +
  subagent/emulation の別へ変更。役割を能力ラベル（read-only explorer / executor /
  auditor）にし、利用者指定の model/platform/roster を優先、重複 writer を禁止。
  リマインダー既定を兄弟スキルと同じ 40 行動へ揃えた。template の model tier 例を削除。
- 検証が示すこと: 3 役割ファイル、template の役割見出し、40 行動リマインダー、
  vendor/model tier 指示が残っていないこと。
- 検証が示さないこと: coordinator/worker/auditor の実実行、audit 受理、subagent 起動。

## start-work-with-docs

- 判定: KEEP（N=40 の既定と DoD/artifact 確認は既に意図どおり）。
- 変更: なし。
- 検証が示すこと: frontmatter、リンク、同梱物。artifact テストは共通テンプレートを確認する。
- 検証が示さないこと: 逐次実行、失敗項目の `[ ]` 維持、DoD 成果物の実在確認。

## supervisor-orchestration

- 判定: 変更。
- 変更: frontmatter を strict YAML 化。routing table の `explore` / `general` を能力ラベルへ
  置換し、runtime mapping と利用者指定の delegation 優先、単一 writer を明記した。
- 検証が示すこと: routing reference が能力ラベルを使い、特定 runtime の agent 名を
  普遍名として固定していないこと。
- 検証が示さないこと: subagent routing、artifact 検証、並列/直列の実運用、統合判断。

## write-evidence-based-adr

- 判定: KEEP（status / evidence / alternatives / limits の分離が既に本文にある）。
- 変更: なし。
- 検証が示すこと: frontmatter、リンク、同梱物。
- 検証が示さないこと: ADR 作成セッション、証拠の採否、stakeholder approval の有無。

## write-workdoc-docker

- 判定: 変更。
- 変更: `CLAUDE.md` / `OPENCODE.md` を local instruction 探索に追加。作業書へ実 secret・
  private repo 名・絶対 home path・customer data を書かない注意、env/compose log は
  変数名と redacted excerpt だけを記録する注意を追加。
- 検証が示すこと: template の章構成と 4 行チェックリスト形式。
- 検証が示さないこと: Docker build/run、compose 設定の実在、生成 workdoc の内容。

## write-workdoc-uv

- 判定: 変更（小）。
- 変更: `CLAUDE.md` / `OPENCODE.md` を local instruction 探索に追加。作業書へ実 secret・
  private repo 名・絶対 home path・customer data を書かない注意を追加。
- 検証が示すこと: template の章構成と 4 行チェックリスト形式。
- 検証が示さないこと: uv sync/test、生成 workdoc の内容、実 project への適用。
