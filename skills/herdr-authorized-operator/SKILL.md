---
name: herdr-authorized-operator
description: Inspect an existing Herdr workspace, tab and agent; identify the correct pane, enter or submit prompts, and answer context questions within user authorization. Includes explicitly authorized operation from outside Herdr. Use when steering an existing visible agent, not when launching a worker fleet.
---

# Herdr の承認に基づく操作（非公式）

ユーザーが指定した既存の Herdr エージェントを特定し、状況の確認、プロンプトの入力・送信、情報待ちへの回答を行う。Herdr 公式スキルの改変版ではなく、利用者の承認範囲を扱う独自の補助手順である。

## 承認と対象範囲

- 会話から、対象と許可された操作を確認する。「読む」「入力欄に置く」「送信する」「情報待ちに回答して続行させる」を区別する。既に許可された操作について承認を取り直さない。
- Herdr 外からの操作には、その操作をユーザーが明示的に認めた根拠が必要。公式スキルの `HERDR_ENV=1` 条件と異なる運用であることを明示する。このスキルを読んだだけでは承認にならない。
- 実行環境を偽装するために `HERDR_ENV` や呼び出し元 ID を設定しない。使える既存接続で対象を調べる。システム・開発者の制約や実際のアクセス制御は別途守る。
- 対象の agent、model、作業ディレクトリ、ユーザーの表示位置を維持する。起動・切替・割り込み・終了・公開操作は、既存エージェントへの指示送信とは別の作業として扱う。

## 1. 接続先と CLI を確認する

コマンドの正本はインストール済み CLI。以下は Herdr 0.9.4 で確認した構文例であり、版が違う場合はその場の help を優先する。例は `rtk proxy` を使う環境向け。RTK を使わない環境ではこの接頭辞だけを外す。

```bash
rtk proxy herdr --version
rtk proxy herdr status
rtk proxy herdr --skill
rtk proxy herdr --help
rtk proxy herdr workspace
rtk proxy herdr tab
rtk proxy herdr pane
rtk proxy herdr agent
```

同じ作業内で読んだ help を繰り返し取得する必要はない。裸の `herdr` は TUI を起動するので探索に使わない。`create` などの変更コマンドを引数なしで試さない。

ローカル・名前付きセッション・SSH 接続先を混同しない。既存の名前付きセッションを指定する場合は `herdr session` の help と `herdr session list` で存在を確かめる。リモートを指定された場合は `herdr machine` の help と `herdr machine list --json` で保存済み接続先を確認する。以降の全操作で同じ `--session` または `--machine` 指定を保つ。両者を併用しない。

接続不能や版不一致なら、その状態を報告する。調査のためにサーバーを停止・更新したり、新しい接続先を作ったりしない。

## 2. ワークスペース → タブ → ペイン → エージェントを対応付ける

```bash
rtk proxy herdr workspace list
```

返された ID を選んでから、次へ進む。以下の `<...>` は一覧で得た実値に置換する。

```bash
herdr_target_workspace='<workspace-id-from-list>'
rtk proxy herdr tab list --workspace "$herdr_target_workspace"
rtk proxy herdr pane list --workspace "$herdr_target_workspace"
```

ユーザーのいう「スペース」は workspace、「タブ」は tab、「実際の入力先」は pane として照合する。表示番号から ID を組み立てない。タブには複数ペインがあり得るため、タブ名だけで入力先を決めない。

依頼された仕事と、ペインの agent 種別、cwd、タイトル、会話 ID、表示内容を照合する。同じ cwd に複数セッションがある場合は cwd だけでは特定できない。識別が足りなければ候補ペインの内容を読む。なお曖昧なら入力せず、候補を短く示して対象を尋ねる。

ローカルの作業メモには次の対応だけを残せばよい。実値を汎用スキルや公開資料へコピーしない。

| 接続先 | workspace 名 / ID | tab 名 / ID | pane ID | agent / 会話 ID | cwd / 対象作業 | 確認時刻 |
|---|---|---|---|---|---|---|
| 調査した接続先 | 一覧の値 | 一覧の値 | 一覧の値 | 取得できた値 | 依頼との対応 | タイムゾーン付き |

会話 ID、terminal ID、pane ID は別物。入力には pane ID または一意な live agent 名を使う。移動・再起動・セッション切替後や、後日の再操作時には対応を取り直す。

## 3. 状態と実際の表示を読む

```bash
herdr_target_pane='<pane-id-from-list>'
rtk proxy herdr agent get "$herdr_target_pane"
rtk proxy herdr pane read "$herdr_target_pane" --source visible --lines 40
rtk proxy herdr agent read "$herdr_target_pane" --source recent-unwrapped --lines 100
```

状態が表示内容と食い違う場合は `herdr agent explain "$herdr_target_pane" --json` と、必要に応じて `herdr pane process-info --pane "$herdr_target_pane"` を使う。

| 観測 | 判断・対応 |
|---|---|
| `working` でツール出力や成果物が進む | 作業中。通常は指示を重ねず、区切りを待つ。 |
| `idle` / `done` | 入力待ちの可能性。最後の回答と作業書を読み、完了・単なる区切り・指示待ちを分ける。 |
| `blocked` | 現在の質問・承認画面を読む。一瞬の表示だけでは、ユーザーの判断が必要とは決めない。 |
| `unknown` / agent が見つからない | 前面がシェル・別プロセス・別エージェントになっていないか調べる。未特定の入力欄へ送らない。 |

既存の入力文がある場合は勝手に消したり、追記してまとめて送信したりしない。ユーザーの下書きか、こちらが直前に入力した文かを確認する。

長い会話が画面から読めなければ、対応する会話 ID を使ってエージェントの export またはログを読む。`agent-jsonl-compact-reader` が利用できればその手順に従う。export はスナップショットなので、古い export を現在の進捗と混同しない。

## 4. 入力と送信を分ける

**送信まで許可され、対象エージェントの通常の入力欄だと確認できた場合**は、agent 向けの送信を優先する。

```bash
rtk proxy herdr agent prompt "$herdr_target_pane" '最新版の作業書の未完了項目から作業を開始してください。検証結果を記録し、完了条件を満たすまで進めてください。'
```

**入力欄に置くだけ**なら、送信しない。

```bash
rtk proxy herdr pane send-text "$herdr_target_pane" 'ここに確認用の指示文を置く。'
```

その文を送信するよう依頼されたら、前面のエージェント・入力文・入力欄が変わっていないことを読んで確認し、`herdr pane send-keys "$herdr_target_pane" enter` を使う。既に入力済みの文に対して `agent prompt` で同じ文を送り直さない。

長文やコードを含む指示はシェル文字列へ直接埋め込まず、手元の UTF-8 ファイルを読み、引数配列として渡す。ファイル名とペイン ID は実値に置換する。

```bash
rtk proxy python3 - "$herdr_target_pane" /path/to/private/prompt.txt <<'PY'
from pathlib import Path
import subprocess
import sys

subprocess.run(
    ["rtk", "proxy", "herdr", "agent", "prompt", sys.argv[1],
     Path(sys.argv[2]).read_text(encoding="utf-8")],
    check=True,
)
PY
```

送信の成功応答は、相手の読了・着手・完了を意味しない。送信直後と、依頼された待ち時間後に状態・表示を読み、送った内容への応答または作業開始を確認する。待機は短く区切り、進捗を伝える。無期限の `--wait` は使わない。タイムアウト時も送信済みの可能性があるため、再送前に画面と会話を確認する。

## 5. 情報待ち・指示待ちに対応する

ユーザーから「待っていたら補足して続けさせて」と依頼されていれば、会話と資料から答えられる質問にはこちらで回答して送信する。毎回ユーザーへ差し戻さない。

1. **何を待っているかを読む。** 相手の具体的な質問、止まった手順、必要な判断を拾う。
2. **根拠を調べる。** ユーザーの直近の指示、正本の作業書、現行ファイルを確認する。過去の要約より新しい明示指示を優先する。
3. **再開に必要な分だけ答える。** 根拠の場所と、次の作業・完了条件を短く伝える。推定をユーザーの決定として伝えない。
4. **本当に不足している情報を切り分ける。** 記録者しか知らない事実や新たな範囲・権限の判断は捏造しない。ユーザーへその一点を尋ね、独立して進められる項目があれば先へ進むよう伝える。

補足プロンプトの型：

```text
待っている点への回答：<具体的な回答>。
根拠：<ユーザーの指示、作業書の節、確認したファイルと版>。
次に行うこと：<未完了項目と必要な入力>。
完了条件：<成果物と検証方法>。
この範囲の通常の修正・検証は継続してください。未解決の点があれば記録し、
依存しない項目を進めてください。
```

`agent prompt` が `agent_blocked` を返したら、同じ送信を繰り返さない。質問フォームなら、実際の選択肢と入力欄を見て承認範囲内の回答を行う。権限の承認画面なら、既に許可された操作かを照合し、新しい権限を勝手に認めない。画面の意味が分からないまま Enter や Escape を押さない。

## 6. 作業書と目標を渡して継続させる

「内容を確認して」とだけ伝えると、要約して止まることがある。実行依頼なら「作業を開始し、完了条件まで進める」と明記する。

- 作業書の実パス、正本の版、今回のゴール、着手順、変更範囲を渡す。
- `start-with-workdocs` の利用を求められた場合は、対象エージェントから読める実在のスキルを指定する。使えないスキルを使ったことにしない。
- 自己レビューで問題を見つけたら、必要な手順と完了条件を作業書へ追加し、修正・検証・再レビューを続けさせる。チェックは証拠を確認してから付ける。
- `/goal` 等を依頼されたら、対象製品・セッションでの対応を確かめる。別製品のコマンドを存在する前提で入力しない。設定結果で新しい目標を確認し、古い `goal met` 表示を成功の根拠にしない。非対応なら作業書に目標を記録して実作業を続ける。
- 作業中のファイルを別エージェントから同時編集しない。追加事項はまず指示として渡す。

## 完了の伝え方

「対象」「送信した要点」「最後に観測した反応」を短く伝える。入力のみ、送信済み、相手の着手確認、成果物の検証済みを区別する。進捗の数値は作業書や成果物で確かめ、相手の自己申告しか読んでいなければその旨を添える。

この手順だけで常時監視は始まらない。依頼された時間内の確認を終えたら最終確認時刻を伝え、実際に動いている監視手段なしに「今後も自動監視する」と約束しない。

## 由来と保守

Herdr の配布元は [herdr.dev](https://herdr.dev/)。構文・状態の意味はインストール済み `herdr --skill` と各 help を参照する。本手順は 2026-11-10 に Herdr 0.9.4 の CLI を参照して独自に記述した。公式文書の転載や、Herdr による承認・保証を意味しない。

新しいワーカー群の起動・provider 切替・agmsg による調整が必要なら、利用可能な `herdr-opencode-agmsg` を別途参照する。本スキルの利用から、その追加作業の許可を推定しない。
