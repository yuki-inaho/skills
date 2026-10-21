---
name: write-evidence-adr
description: Create and maintain evidence-backed design decision records under repository docs. Use to record design and artistic rationale, update ADRs during iterative work, preserve superseded decisions, connect requirements to validation, and maintain requested commit/push/git-notes checkpoints.
---

# 証拠に基づくADR作成・更新

## 調べる

1. 指示、要求、作業書、最新引き継ぎ、docs/adrの一覧と関連ADRを読む。既存命名と番号を守り、別担当の追加番号を再利用しない。
2. 要求、観察、仮定、制作提案、実測を分ける。コードや画像を未確認のまま前担当の成功報告を確定事項へ変えない。
3. 判断が必要な問題と利用者が得たい結果を一文で記す。視覚作品では構図・形・素材・印象の狙いも残す。

## 記す

[最小構成](references/adr-template.md)に沿ってdocs/adr以下へ独立して読めるADRを書く。

- 採用案、実際に検討した代案、理由、交換条件を記す。
- 由来、版、単位、入出力、性能予算、評価条件を必要な範囲で固定する。
- 提案閾値・利用者要求・実測を区別する。調整前に条件を固定し、変更するなら理由と旧条件を残す。
- 旧判断の上書き範囲を示し、旧ADRから新ADRへ参照を付ける。失敗/未達を消さない。
- 新要件に応じて要求/作業書/DoD/実装の対応を更新する。成功に合わせてDoDを狭めない。

## 検証・保存

ソース、試験、実記録、画像、保存物を照合する。設計採用・実装・検証合格を別状態にする。未確認リンクや存在しないコマンドを完成入口にしない。

凍結候補、後続実装、提出版の証拠を分ける。後続版で取得したメタデータを古い試行の成功理由にしない。最適化器の採択後に制約を満たすため修正した場合、選定済み候補を保存し、修正理由・変更量・再評価範囲を別の決定として記す。寸法や画像の目標未達は測定値と閾値を残し、再現性の成功で置き換えない。

作業書へ判断と次の検証を追記する。文章だけの訂正なら無関係な実験を繰り返さず、形状/契約変更なら影響する証拠を更新する。

提出直前の重大不具合は新しい判断記録にし、発見した見た目、数値による切分け、旧版の採用撤回、修正の不変条件、再検証範囲を結ぶ。旧試験が何を保証し何を検査していなかったかを明記し、過去のPASSを削除したり全面合格へ拡張したりしない。失敗版と修正版のmodel/source/camera hashを保持し、未完了の修正を完了と記さない。

利用者指定の節目で対象差分だけcommitし、許可されたremote/branchへpushし、commitへgit notesを付ける。notesは判断/検証/残課題/証拠に絞る。ローカルnotesとremote refs/notesの保存を別確認する。任意refが接続で扱えない場合は制限と復元可能な保存経路を明記する。Markdown文書をgit notesとして報告しない。

秘密や私有ログを汎用スキルへ埋め込まず個別の私有プロジェクトに置く。

## Number reservations

Inspect both existing ADR filenames and the index or handoff documents for reserved but unpublished numbers. Allocate a number beyond those reservations. If a collision is found before publication, rename the new ADR and update its index, successor links, and current workdoc. Preserve the review history and record the renumbering reason.
