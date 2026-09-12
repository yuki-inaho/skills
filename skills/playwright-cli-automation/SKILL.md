---
name: playwright-cli-automation
description: Use when driving a browser autonomously with the global playwright-cli (open, eval, snapshot, screenshot, close), when collecting screenshots of a local page, or when the CLI fails in containers/scripts. Triggers: playwright-cli で操作, ブラウザを自動操作, スクリーンショット収集, playwright cli 動かない.
---

# Playwright CLI Automation

`@playwright/cli`（グローバル）でブラウザを操作し、証跡としてスクリーンショットを集める。

## Prerequisites

```bash
npm install -g @playwright/cli     # playwright-cli が PATH に入る
which playwright-cli
```

- ローカルページは `python3 -m http.server` 等で **HTTP 配信**する（`file://` はモジュール/WebAssembly の制約に当たりやすい）。
- ページ側に**完了フラグ**（例: `window.__appReady`）と**操作フック**（例: `window.__setView(...)`）を用意すると、待機と操作が決定的になる。

## Procedure

```bash
PW=playwright-cli
# 1) 開く（コンテナでは sandbox を無効化）
PLAYWRIGHT_MCP_SANDBOX=0 $PW -s=mysession open http://127.0.0.1:8899/index.html --browser chrome

# 2) 待機（単一式として評価される点に注意）
PLAYWRIGHT_MCP_SANDBOX=0 $PW -s=mysession eval "window.__appReady === true"

# 3) 操作は IIFE（複文をそのまま渡すと SyntaxError）
PLAYWRIGHT_MCP_SANDBOX=0 $PW -s=mysession eval "(() => { window.__setView({az:2.4, dist:2.6}); return 'ok'; })()"

# 4) スクリーンショット
PLAYWRIGHT_MCP_SANDBOX=0 $PW -s=mysession screenshot --filename /abs/out.png --full-page

# 5) 終了
PLAYWRIGHT_MCP_SANDBOX=0 $PW -s=mysession close
```

スクリプトから呼ぶ場合は、次を必ず守る（ハマりどころの実測対策）:

- `stdin=DEVNULL` + 出力キャプチャ（`capture_output=True`）。CLI のデーモンが呼び出し元のパイプを保持して、呼び出しが返らないことがある。
- `cwd` を作業用ディレクトリに固定する（`.playwright-cli/` の snapshot/console がそこに出る）。
- シェルから直接叩く場合も `</dev/null` を付ける。

## Verification

- スクリーンショットが仕様枚数あり、**互いに異なる**（サイズ集合の多様性で機械確認）。
- 重要ページは `.playwright-cli/console-*.log` を確認し、致命的エラーが無いこと（favicon 404 等は無害と切り分ける）。

```bash
python3 - <<'PY'
import glob, os
shots = sorted(glob.glob("out/*.png"))
assert shots and len({os.path.getsize(p) for p in shots}) == len(shots), shots
print("distinct screenshots:", len(shots))
PY
```

## Failure handling

- `Failed to move to new namespace ... Operation not permitted`: コンテナの sandbox 制約。`PLAYWRIGHT_MCP_SANDBOX=0` を付ける。
- `SyntaxError: Unexpected token ';'`: eval は単一式として包まれる。IIFE 形式に直す。
- コマンドが返らない/ハングする: デーモンのパイプ保持。`stdin=/dev/null` と出力キャプチャにする。
- 期待どおり動かないがエラーが出ない: `snapshot` で要素参照を取得して対象を確認する。`console-*.log` を見る。
- ページが真っ黒/無反応: 配信を HTTP にする（file:// を避ける）。WebGL コンテキストロストは初回のみなら正常。

## Growth log

- 追記先: [references/growth-log.md](references/growth-log.md)。
