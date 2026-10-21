# tests

公開スキルの契約を、合成データと隔離環境だけで検証する。実ログ・実在の識別子・
ホームパスは使わない。

```bash
python3 -m pytest tests -q
```

- `test_public_contract.py` — 公開物の構造だけを見る（各 `SKILL.md` の frontmatter が
  name/description として成立し、ディレクトリ名と一致する、README が方針と各スキルを
  参照している、同梱物が想定内）。加えて、変更した公開ファイルに実在パス・メール・
  秘密情報・外部 URL が無いことを走査する。文言の一致は検証しない（表現を固定して
  しまうため）。
- `test_installer_isolated.py` — `install.sh` を一時ディレクトリへ隔離実行する。
  installer は取得先が `codeload.github.com` 固定なので、テスト内でローカル HTTP
  サーバに置いたアーカイブへ向ける `curl` シムを PATH の先頭に置く。
  ネットワーク公開・グローバル導入は行わない。`--agent all` で 3 エージェント ×
  選択したスキルが入り、内容が byte 一致すること、選択外が入らないこと、
  dry-run が書かないこと、未知 skill が失敗することを確認する。
- `test_agent_jsonl_contract.py` — `agent-jsonl-compact` 0.3.0 以降の CLI 契約を
  合成 JSONL で確認する（version probe、除外対象、根拠の byte 位置、tool pair 状態、
  partial/retry、出力予算、append cursor）。バイナリは `AGENT_JSONL_COMPACT` か PATH
  から探し、無ければ skip（旧版 0.2.x も skip。スキル側は legacy フォールバックを
  案内する）。PATH に旧版が入っている環境では、`AGENT_JSONL_COMPACT` で**対象
  バイナリを固定**してから実行する（旧版の `version` サブコマンドは未対応なので skip）。

`tests/fixtures/` の JSONL はすべて合成データである。
