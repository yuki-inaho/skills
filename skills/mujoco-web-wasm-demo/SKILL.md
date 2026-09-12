---
name: mujoco-web-wasm-demo
description: Use when building a browser demo of a MuJoCo model (WASM forward kinematics + three.js rendering), embedding playback poses, exposing automation hooks, and capturing screenshots with playwright-cli. Triggers: MuJoCo ブラウザ, mujoco wasm, three.js で mujoco, Web デモ スクリーンショット.
---

# MuJoCo Web (WASM) Demo

公式 `@mujoco/mujoco` の WebAssembly で **FK/物理**を計算し、`three.js` で描画する。
公式サンプルと同じ分担（MuJoCo は描画を持たない）。操作は `playwright-cli` で自動化できる（→ `playwright-cli-automation`）。

## Prerequisites

```bash
mkdir -p web && cd web
npm init -y && npm install @mujoco/mujoco@3.13.0 three@0.170.0   # CDN を使わず vendoring
```

- モデルは **MJCF 文字列**として用意する（ファイルでも可。`from_xml_string` を使うと FS 操作が不要）。
- 再生させたい場合は **qpos フレーム列**（例: 軌道の各行）を JSON で埋め込む。

## Procedure

1. ページを生成する（自己完結 HTML）。骨子:

```html
<script type="importmap">
{"imports": {"three": "./node_modules/three/build/three.module.js",
             "three/addons/": "./node_modules/three/examples/jsm/"}}
</script>
<script type="module">
import * as THREE from "three";
import loadMujoco from "./node_modules/@mujoco/mujoco/mujoco.js";
const mujoco = await loadMujoco();
const model = mujoco.MjModel.from_xml_string(MJCF);
const data = new mujoco.MjData(model);
// 毎フレーム: data.qpos[i] = frame[i]; mujoco.mj_forward(model, data);
// body の世界姿勢 data.body(name).xpos / .xquat を three のオブジェクトへ適用
window.__appReady = true;
</script>
```

2. 描画の要点（実測で必要になったもの）:
   - MuJoCo は **Z-up**、three.js は **Y-up**。MuJoCo フレームの物体は回転ルート
     （`group.rotation.x = -Math.PI/2`）にまとめて入れる。lookat も `(x, z, -y)` に変換する。
   - body は**フラット**に配置する（入れ子にして世界行列を入れると二重適用で崩れる）。
   - プリミティブは MJCF の geom（sphere/box/cylinder/capsule, `fromto` 対応）から生成する。
3. 自動化フックを公開する: `__appReady` / `__setFrame(i)` / `__play(bool)` / `__setCamera({az,el,dist,lookat})` / `__status()`。
   フックは**即時に再描画**する（次フレーム待ちだとスクリーンショットが更新されない）。
4. HTTP 配信して `playwright-cli-automation` の手順で巡回・撮影する（コンテナでは `PLAYWRIGHT_MCP_SANDBOX=0`、eval は IIFE）。

## Verification

- `window.__appReady === true`、`__status()` に `nq` と body 名一覧、フレーム数が出る。
- 複数ビューのスクリーンショットが**互いに異なる**（サイズ多様性）。同一ならフックが描画を更新していない。
- 目視: リンクが連結して見え、関節を動かすと形が変わる。

## Failure handling

- 画面が黒い: 配信を HTTP にする / カメラの near-far と lookat を確認 / 光源を追加する。
- 形状がバラバラに飛ぶ: Z-up↔Y-up の変換漏れ、または body の入れ子＋世界行列の二重適用。
- 操作が効かない: フック内で再描画を呼んでいない。`requestAnimationFrame` 任せにしない。
- URDF を読みたい場合: MuJoCo の URDF 取り込みは既定で visual を破棄する版がある。MJCF 拡張
  `<mujoco><compiler discardvisual="false"/></mujoco>` を渡せるなら渡す（版差に注意）。
- スクリーンショットが撮れない/ハングする: `playwright-cli-automation` の Failure handling を参照。

## Growth log

- 追記先: [references/growth-log.md](references/growth-log.md)。
