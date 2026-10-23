# tests

公開スキルの契約を、合成データと隔離環境だけで検証する。実ログ・実在の識別子・
ホームパスは使わない。

## 実行方法

依存関係と Python 版は `pyproject.toml` / `uv.lock` / `.python-version` で固定する。
`just` は薄いラッパーで、実体は同じ `uv run --locked` コマンドである。

```bash
uv sync --locked --group dev
uv run --locked pytest tests -q

just check          # 1 コマンド集約: validate + test + privacy + ruff/compile
just lint           # uv run --locked ruff check . + uv run --locked python -m compileall -q skills tests
just test           # uv run --locked pytest tests -q
just validate       # uv run --locked python skills/skill-creator/scripts/validate_skill.py
just privacy        # uv run --locked python tests/privacy_scan.py
just test-contract  # REQUIRE_AGENT_JSONL=1 の専用プロファイル（外部 CLI 必須）
```

`uv sync --locked` / `uv run --locked` は lock と `pyproject.toml` の不一致を検出して
失敗する。`just check` は外部 CLI を必須にしない。外部契約は `just test-contract` または
CI 専用ジョブでだけ必須にする。

CI も同じコマンドを使う。外部契約ジョブだけは、公開リリース
`agent-jsonl-compact` 0.3.1 の `x86_64-unknown-linux-musl` アセットを
`.sha256` と固定ダイジェストで検証してから `REQUIRE_AGENT_JSONL=1` で実行する。

## テスト構成

- `test_public_contract.py` — `skills/*/SKILL.md` を**ファイルシステムから動的発見**し、
  全スキルの frontmatter を同梱 validator と同じ strict YAML 経路で解析する。
  name/ディレクトリ一致、kebab-case、description、同梱物、README の一覧、
  相対リンク、同梱 script 参照を確認する。スキル数の固定値は要求しない。
- `test_skill_creator_validator.py` — colon-space、quoted、folded/block、重複キー、
  非マッピング、frontmatter 欠落、name/description 不正を**実際に失敗する入力**で確認する。
  推奨見出しは警告のみで hard error にしない。
- `test_installer_isolated.py` — `install.sh` を一時ディレクトリへ隔離実行する。
  `codeload.github.com` 以外への取得を拒否する `curl` シムとローカル HTTP サーバを使い、
  全スキルツリーを **recursive tree hash**（scripts/references/assets/LICENSE/agents を含む）
  で比較する。auto-detect / `--dest` / comma list / `--ref` / dry-run / 未知 skill /
  異常アーカイブ配置も確認する。
- `test_agent_jsonl_contract.py` — `agent-jsonl-compact` 0.3.0 以降の CLI 契約を
  合成 JSONL で確認する。通常ローカルでは欠落・旧版を skip するが、
  `REQUIRE_AGENT_JSONL=1` では **skip せず失敗**する。
- `test_herdr_opencode_agmsg.py` — provider planner と cleanup gate の純粋判断を、
  合成 provider ID・合成 catalog・合成 attempt で確認する。実 provider / Herdr /
  agmsg / credential は呼ばない。同梱 catalog は空の neutral template である。
- `test_privacy_scan.py` — `tests/privacy_scan.py` の分類器を合成 canary で確認する。
  正例（合成の home path / email / token / private-key 見出し）と負例（placeholder、
  public URL、`<uuid>`）を使い、レポートが**値ではなく分類とファイル名だけ**を出すことを
  確認する。tracked file と intended new file の両方が走査対象になること、非 Git ルートと
  リポジトリ外へ解決される symlink が再帰走査へフォールバックせず rc2 で拒否されることも
  確認する。`just privacy` の 0 件は安全宣言ではない。
- `test_skill_coverage.py` — `tests/skill_coverage.json` が発見した全スキルを覆い、
  各項目が実在するテストと「証明しないこと」を持つことを確認する。
  `docs/skill-coverage.md` の見出しとも突合する。
- `test_skill_artifacts.py` — 同梱テンプレートの見出し・4 行チェックリスト形式、
  completion/review/audit テンプレート、JAX の false command 除去、handover の最終確認、
  provider-neutral catalog、cleanup gate の警告、空 catalog の明示 stop を確認する。
  これは文書・形式の契約であり、JAX/GPU/ブラウザ実行の証明ではない。

## 証跡の扱い

`just privacy` の出力は**人によるレビューの証跡**であり、公開可否の新しい承認ゲートでは
ない。0 件は安全宣言ではない。分類器は実在の denylist を持たず、一般的なデータ種別だけを
扱う。公開 URL の名前空間は、それ自体では private と判定しない。

スキルごとの「何を検証し、何を証明しないか」は
[`../docs/skill-coverage.md`](../docs/skill-coverage.md) を参照する。
設計判断と検証限界は `../docs/adr/` にある。

`tests/fixtures/` の JSONL・provider listing はすべて合成データである。
