---
name: tomato-sim2real-pdca
description: Improve Blender tomato scenes for fruit harvesting and leaf-removal perception through evidence-backed PDCA and Harness2 trials. Use for main-stem/petiole/fruit-axis/calyx labels, close RGB-D hand cameras, aisle views, occlusion-changing trajectories, and real-reference visual review. Do not claim sim2real performance from renders alone.
---

# トマト学習用アセットPDCA

## Plan

1. 作業を収穫/葉かき/両方に分け、作業前後を明記する。葉かきでは葉柄基部と主茎の関係を対象にし、葉身だけを納品しない。
2. 実写は器官・遮蔽・支持資材・光の観察に使う。人/道具の除外要求を守る。単眼写真から実寸、隠れた接続、計測済みカメラ姿勢を断定しない。
3. 要求/ADR/作業書に入力境界、器官表、比較条件、合否/unknownを定義する。個体復元と独立手続きモデルを混同しない。
4. [器官と撮影](references/organs-and-cameras.md)を読み、主/手元カメラ、対象点、画像原本、必要サマリーを固定する。

## Do

空シーン生成器へ独自設計と固定種を渡す。代表株の節・葉柄・果房柄・果柄・萼・果実の接続を接写で確認してから増株する。斜行する主茎、複葉の変化、熟度、葉が作業点を隠す状況を含める。

同梱`scripts/policy.json`は初期の造形調整値。対応生成器が実際に読み、名前/版/適用値を記録するときだけ使用する。異なる生成器へ黙って適用しない。未知キー、非有限値、範囲外を拒否する。値を変えただけで改善と呼ばない。

## Check

- 全景/列横、接写、回り込みを保存済み同一版から描画する。果実・萼・果柄・葉柄基部が必要な視点で見えるか画像を開く。
- 浮き、突刺し、萼自己交差、形状反復を列挙する。平均値で一部不良を隠さない。位相水密性と見た目の接続を分ける。
- 視点移動でも器官IDを固定し、対象点の投影・前面深度で可視/遮蔽/画面外を判定する。葉を消して回り込みを達成したことにしない。
- モデル/カメラ/時刻と深度/法線/IDの数値契約を確認する。サマリーと数値原画像を分け、凡例と版対応を付ける。

## Act とHarness²

1. 実失敗を再利用可能な手順か造形値へ反映し、次候補を同入力/種/カメラ/描画条件で試す。
2. Harness²を求められたら固定版のdocs/helpを読み、実Propose–Probe–Composeと選定後判定を使う。概念PDCAをネイティブ実行と呼ばない。
3. 外部編集者なら中核mission/contextを実担当へ渡し、実編集・Blender実行・失敗・費用未計測を記録する。期待答案を提案側へ漏らさない。
4. k=1の選定は改善証明ではない。KEEP_BASE/TIE/REVISE/UNKNOWNを許し、独立の同条件観測から限定した結論を出す。
5. 自己レビューで不足を作業書/DoDへ追加する。未達を記録しただけで品質合格にしない。変更の影響する描画/数値/再現検査を更新する。

実センサー精度、ロボット到達性、実データ学習への効果は別の実証がなければ未検証とする。
