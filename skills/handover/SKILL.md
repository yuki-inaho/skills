---
name: handover
description: Use when the user explicitly asks for a handover, auto-compact handoff, session handoff, work continuation summary, or invokes $handover. Produces a structured Japanese handover document in chat only, without creating files.
---

# Handover

現在の作業状況を分析し、以下のテンプレートに沿って引き継ぎ文書を生成してください。
Auto-Compact時や作業中断時に、次のセッションで円滑に作業を再開できるようにすることが目的です。
ファイルは作成せず、チャット欄に引き継ぎ文書本文だけを出力してください。

## 生成ルール

- 各 `{{変数}}` を現在の作業状況に基づいて適切な内容に置き換えてください
- `{{...}}` はすべて実値に置換し、不明な項目は `TBD` としてください
- ステータスは 🟢（完了/良好）、🟡（進行中/要注意）、🔴（未着手/問題あり）で表現してください
- 作成日は可能なら現在時刻（例: `YYYY-MM-DD HH:MM:SS TZ±HHMM`）を使ってください
- 追加の説明や前置きは不要です。テンプレート本文のみ出力してください

## 出力テンプレート

````markdown
# 引き継ぎ文書（Auto-Compact 用）
作成日: {{date}}
作成者: {{author}}
対象プロジェクト: {{project}}

## 1. 概要
- **目的**: {{purpose}}
- **前回までの進捗要旨**: {{summary}}  <!-- 直近で何を行い、どこまで完了したか -->

## 2. 現状ステータス
| 分類 | 状態 | 補足説明 |
| --- | --- | --- |
| 設計・計画 | {{status_design}} | {{note_design}} |
| 実装 | {{status_impl}} | {{note_impl}} |
| テスト | {{status_test}} | {{note_test}} |
| ドキュメント | {{status_doc}} | {{note_doc}} |

## 3. 完了済みタスク
- {{completed_task1}}
- {{completed_task2}}
- {{...}}

## 4. 残存課題・リスク
### 4.1 ブロッカー（要即時対応）
| 課題 | 影響 | 推奨対応 |
| --- | --- | --- |
| {{blocker1}} | {{impact1}} | {{action1}} |

### 4.2 潜在的リスク
- {{risk1}} : {{mitigation1}}
- {{risk2}} : {{mitigation2}}

## 5. 次アクション（優先順）
1. {{next_step1}}
2. {{next_step2}}
3. {{next_step3}}

## 6. 技術情報
- **重要ファイル/ディレクトリ**:
  - {{path1}} : {{desc1}}
  - {{path2}} : {{desc2}}
- **頻出コマンド**:
  ```bash
  {{command1}}
  {{command2}}
  ```

## 注意事項
{{notes}}
````
