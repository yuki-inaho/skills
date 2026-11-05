# 文章規範の出典と固定版

## 同梱した原典

著者は[k16shikano](https://gist.github.com/k16shikano)、資料名は「日本語技術文書の文章規範」。公開Gistの`SKILL.md`を、以下の版から取得した。

| 項目 | 値 |
|---|---|
| 出典 | [原典Gist](https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d) |
| 固定版 | [`8f2d57610a73efc97d743c9b0b0ecb1002e09fa4`](https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d/8f2d57610a73efc97d743c9b0b0ecb1002e09fa4) |
| 保存先 | [upstream/writing-rules.md](upstream/writing-rules.md) |
| 変更 | ファイル名のみ変更。取得したUTF-8本文は改変していない |
| SHA-256 | `ad350e0e6f5630fd94d8ab98a6aee194053b0096fdc944c23e271d6dfa09ee68` |
| ライセンス | Unlicense。原典のfrontmatterにも記載あり |

これは短い引用ではなく、原典のライセンスに基づく全文の同梱である。上流の文章を本スキルの独自著作として扱わない。

ライセンス本文は、原典が指定する[ライセンスGistの固定版](https://gist.github.com/k16shikano/67625f2a7d96e3bbdfae8d571a936063/1092e6b60296c760071c308624e344469ec345cf)（revision `1092e6b60296c760071c308624e344469ec345cf`）から取得し、[upstream/LICENSE](upstream/LICENSE)へ改変せず保存した。同じGistの`Readme.ja.md`に、著者のpublic GistへUnlicenseを適用する旨が書かれている。

ライセンス本文のSHA-256は`6f9a2fb009225de5cca1c2a24dfed7a68bc22657e455b4a3d63f065258b455d1`。

## 本スキルで追加した方針

[SKILL.md](../SKILL.md)の適用方針・手順・検証項目は、このスキル集で管理する。原典の構成・論証の規範を参考にしつつ、依頼の目的を保つこと、主張の近くに根拠を置くこと、修正後の文章を依頼と照合することを定める。書籍の文体をあらゆる報告へ強制する運用にはしない。

原典は参照資料であり、独立したスキルとして自動読込させない。実行時は同梱版を使い、上流の最新版へ自動で切り替えない。

## 比較に使った関連資料

- [hikimay/japanese-tech-writing・`9f57b2c2902a140741961976cb359815d5c059c0`](https://github.com/hikimay/japanese-tech-writing/tree/9f57b2c2902a140741961976cb359815d5c059c0)：原典を基にチェックリスト等を加えたスキル。
- [nanaism/yomiyasu・`8394e099486aaa2e28cf89992e46f5ebe5ed839d`](https://github.com/nanaism/yomiyasu/tree/8394e099486aaa2e28cf89992e46f5ebe5ed839d)：意味を保持した日本語の推敲スキル。

この二つは比較・参照用のリンクで、本文やコードを同梱していない。実行時の依存先でもない。

## 更新方法

1. 原典の新しいrevisionと現在の固定版を比較し、取り込む理由を判断する。
2. 更新する場合は原典全体をその版から取得し、本文を変更せず保存する。こちらの方針変更は`SKILL.md`へ書く。
3. この文書の固定URL・完全なrevision・SHA-256を更新する。ライセンスの指定が変わった場合は、その本文と適用範囲も確認する。
4. Issue報告や技術説明など用途の異なる短い合成文で、依頼の目的・条件・断定の強さ・根拠が保たれるか見直してから採用する。

固定版とハッシュで追跡するのは参照した規範の内容であり、モデルの出力品質や再実行結果の一致を保証するものではない。
