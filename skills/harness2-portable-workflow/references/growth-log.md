# Growth log — harness2-portable-workflow

一般的で識別情報を含まない学びだけを残す。実ログ、実パス、内部名、session data、
model catalog は書かない。

## 2026-10-23 — frozen comparison review

### 発見（Findings）

- 比較の成否は、base と candidate の snapshot を固定し、run 開始後に
  編集しないことに依存する。共有の書き込み可能パスへの symlink は比較対象を
  実行中に変え得る。完全コピーは、この依存を避ける簡単な方法である。
- 同じに見える比較でも、selected interpreter、`sys.prefix`、cwd が記録されて
  いなければ再現できない。run manifest に environment を残す必要がある。
- k=1 の selection は「候補が選ばれた」という記録であり、base より良いという
  証拠ではない。候補が基準を落とした場合は `KEEP_BASE` が正当な結論になる。
- この skill の source を編集しても、frozen 条件で再比較するまで model の
  改善とは言えない。採用は利用者 / root の別判断である。

### 苦戦（Struggles）

- transcript 上の path 文字列への regex 一致を、コマンドが意図したファイルを
  使った証拠と誤認しやすい。実際の argv と cwd、生成 artifact を確認する必要が
  あった。
- summary や READY は作業の主張であって、artifact の検証ではない。exit code と
  出力 hash、実際の生成物を別に見る必要がある。

### 助言（Tips）

- base と各 family は完全コピーまたは不変 snapshot を使い、freeze 後に編集しない。
- receipt を argv・cwd・interpreter・artifact hash に結び付ける。
- 比較条件が 1 つでも違えば比較無効としてやり直す。
- 「選ばれた」「改善した」「採用した」を別の文として扱う。

### 昇格判断（Promotion judgment）

- Prerequisites に frozen snapshot と environment の記録、Verification に実
  argv / artifact の確認を昇格した。
- k=1 と `KEEP_BASE` の扱いは Procedure と Failure handling に置いた。
- この記録は比較の実行結果ではなく、手順の監査で得た学びである。
