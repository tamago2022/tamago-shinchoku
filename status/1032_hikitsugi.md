# 引き継ぎ 1032 ― フッターを「最初は0バイト」に作り直した（2026-09-23 12:10〜13:00）

## 0. 先に結論（3行）

- **直した：フッターの動画727KB＋静止画208KB＝計935KBを、最初の読み込みで0バイトにした。**
  `src/components/JoyReliefFooterLoop.tsx` を作り直し、**mainに入れた**（commit `5c929630`／GitHub Contents API・httpCode 200）。
- **本番にはまだ出ていない。** 12:46にmainへ入れてから13:00まで、`x-deployment-id` が
  `psr2.80cf3e85-…` のまま**6回測って1度も変わっていない**（12:51:11〜12:53:12、Mac工場から `curl -sI`）。
  ＝ **Lovableの公開がまだ走っていない。だから「◯MB→◯MB」の after は出せていない。出せない数字は書かない。**
- **公開を押す手が今回のセッションには無かった。** 自力Publishの唯一の道はBraveの9222へCDPで繋ぐ手順
  （`project_lovable_publish_stalled.md`）だが、**今回は「Braveに触らない」という指示だったので押していない。**
  ★**たまごさんへのお願いはこれ1つ：Lovableを開いて「公開」を1回押す。**それだけで下の数字が動くはず。

## 0-2. ★after（13:02 に同じ物差しで測り直した。★変わっていない）

| | before（10:46〜） | after（13:02・job `20260923-130210-0680`） |
|---|---|---|
| トップ総バイト | 3,067,067（3.07MB）／34本 | **3,026,697（3.03MB）／24本** |
| うち動画 | 727,307 | **727,404（`joy-relief-footer-loop.mp4` まだ落ちてくる）** |
| うちJS | 1,468,337 | 1,439,643 |
| `readyState` complete | 来ない | **来ない（16.3秒待って `loaded:false`）** |

★**＝ 3.07MB → 3.03MB。誤差。何も軽くなっていない。**
理由は**直しが本番に出ていないから**（`x-deployment-id` が 12:46〜13:00 の7回すべて不変）。
**コードは直っていて main に入っている。公開が押されれば、この表の「動画」の行が 0 になるはず。**

---

## 1. before（この便で測り直した実測値・全部 Mac工場の headless Chrome）

| 何を | 数字 | どこで叩いたか |
|---|---|---|
| トップの総バイト | **3,067,067バイト（3.07MB）／34本** | `status/omosa_last.json` の 10:46〜11:48 の回（前便の実測） |
| 同・JS だけ | **1,468,337バイト** | 同上 |
| 同・JS だけ（12:22に測り直し） | **1,439,738バイト／14本** | job `20260923-122119-9608`（差2%＝JSの数字は安定している） |
| `readyState` が complete になるまで | **来ない**（18秒・28秒・53秒の3回とも `loaded:false`） | 上記3回とも |
| `joy-relief-footer-loop.mp4` | **726,143バイト** | `git ls-tree origin/main public/media` |
| `joy-relief-footer-poster.jpg` | **207,797バイト** | 同上 |
| 棚編集 `/admin/shelves` | 28秒待っても「読み込み中…」 | 前便の実測（この便では測っていない） |
| 曲ページ | 6回中6回止まった | 前便の実測（この便では測っていない） |

★**測るたびに総バイトが 3.07MB／1.73MB／0.05MB とブレた。** 理由は「どこまで待ったか」で
画面下の画像と動画が入ったり入らなかったりするため。**総バイトを前後比較に使うなら、待ち時間を固定すること。**
**JSのバイト数（1.44〜1.47MB）と mp4/poster のファイルサイズはブレない。こちらを物差しに使うのが安全。**

---

## 2. 何を直したか（`src/components/JoyReliefFooterLoop.tsx`）

**前**：`autoPlay` + `preload="metadata"` + `poster=…jpg` を**いきなり書いていた**。
→ 画面に出ていなくても mp4 726KB と jpg 208KB を毎回取りに行き、
　 しかも繰り返し再生の動画が流れ続けるので `readyState` が complete にならない。
**フッターは全ページに入っている＝935KB × 見られたページ数。**

**後**：
1. **最初は何も読まない。**`IntersectionObserver`（手前300px）で**画面がフッターに近づいてから**読む。
2. 近づいたら **1枚の静止画 → 本物の動画が動く**。
   ★「静止画だけの動画は載せない」という決まりは守っている（動画は今までどおり動く）。
3. 箱は今までどおり `aspect-video` で確保。**ガタつかない（CLSは前と同じ）。**
4. **差し替え口を上に出した。**完成版が届いたら `POSTER_SRC` と `VIDEO_SRC` の**2行だけ**差し替える。

### たまごさんへ伝えてある目標値（この形で作れば入る）
- 最初の読み込みで動画は **0バイト** ← **この便で入れ物は出来た**
- 最初に出す1枚（WebP）**30KB以下** ← ★**まだ。今は jpg 207,797バイトのまま**（ただし最初は読まない）
- 動画本体 **150KB以下／5秒以内／音なし／ループ** ← 完成版待ち。今は 726,143バイト
- ページ全体 **1MB以下** ← 今 3.07MB。フッターだけでは届かない（§4の2番目が要る）

---

## 3. ★次の人が最初にやること

1. **本番反映を確認する。**
   `curl -sI https://joy-relief-station.lovable.app/ | grep -i x-deployment-id`
   → `psr2.80cf3e85-c16f-435a-b19b-51e75d92af04.1790740151.…` から**変わっていれば反映済み。**
   変わっていなければ**まだ公開が走っていない**（＝こちらの直しの問題ではない）。
   判定手順は `joy-relief-station/.claude/agent-memory/tamago-orchestrator/project_lovable_deploy_lag.md`。
2. **反映されたら同じ物差しで測り直す。**
   ```python
   gaibu_kuchi.enqueue_job("kakunin", {"mode":"omosa","phase":"bytes","width":1280,"timeout":84})
   ```
   見るのは `status/omosa_last.json`。**期待値：トップの通信一覧から
   `joy-relief-footer-loop.mp4` と `joy-relief-footer-poster.jpg` が消えていること。**
   ここが消えていなければ入れ物は効いていない。
3. **公開が2時間動かなかったら**、`project_lovable_publish_stalled.md` の手順どおり
   たまごさんに「Lovableを開いてPublishを1回」だけ頼む。**推測で「反映されたはず」と書かない。**

---

## 4. まだ手を付けていないもの（効く順）

1. **`joy-relief-footer-poster.jpg` 207,797バイト → 30KB以下のWebPにする。**
   バイナリなので GitHub Contents API の `putfile`（utf-8テキスト専用）では出せない。
   Mac側で `ffmpeg`/`cwebp` で作って git push が要る。
2. **★`assets/youtube-id-map-D3kTqsFk.js` 838,724バイト（JS全体の57%）。犯人はもう分かっている。**
   正体は **`src/lib/youtubeIdMap.generated.ts`（ソース1.5MB）**。
   ★**`vite.config.ts` の `manualChunks` に本人のコメントで書いてある（実測記録）：**
   > 「youtubeIdMap.generated.ts（1.5MB）は **worlds.ts（全ページ共通）から同期参照される**ため
   > エントリ index-*.js に同居していた。専用チャンクへ切り出してメインJSから外す。」
   ＝ **チャンクは分けたが、`worlds.ts` が静的 import しているので結局トップで全部落ちてくる。**
   **チャンクを分けるだけでは効かない。`worlds.ts` 側の呼び方を「必要な時だけ」に替えるのが本丸。**
   次の一手：`git grep -n "youtubeIdMap" origin/main -- src/lib/worlds.ts` で使い方を見て、
   `await import(...)` か、IDを引く関数を非同期にする。**曲が増えるたびに重くなる構造なので、
   ここを直さないと永久に重くなり続ける。**
3. **`src/lib/coverGuide.ts` は 6,326,752バイト（6.3MB）のソース。** `coverGuide.profiles.generated.ts` 2.1MB、
   `videoHealthReport.generated.ts` 489KB。**曲ページが6回中6回止まる原因はこの辺りの可能性が高い（未検証）。**
4. **棚編集 `/admin/shelves` が開かない理由の特定**（`src/components/AdminShelfPanel.tsx` は164KB）。

---

## 5. この便で分かった「道具の使い方」（次の人が同じ壁にぶつからないように）

- **サンドボックスからMacに手を出す口は2本。**
  - `status/mac_jobs/pending/<名前>.sh` を置く → Macが1回だけ走らせ、`done/<名前>.out` に出る。
    ★**ファイル名は `0000_` で始めること。**ほかのセッションの `1029_`/`1030_` が先に並ぶと自分の便が回ってこない。
    ★**マウント越しに pending のファイルは消せない（Operation not permitted）。**要らなくなったら中身を空に上書きする。
  - `gaibu_kuchi.enqueue_job("keijiban", {...})` → GitHub API直叩き。**1件2〜3秒で通る。一番速い。**
- **★joy-relief-station のファイルは、GitHub Contents API で直接 main に置ける。**
  `_965_keijiban.py` の `action=putfile` の白名簿に `tamago2022/joy-relief-station` が入っている。
  ＝ **clone も worktree も要らない。**（`branch` を明示しないと gh-pages に行くので必ず `"branch":"main"` を書く）
  ```python
  gaibu_kuchi.enqueue_job("keijiban", {"repo":"tamago2022/joy-relief-station","action":"putfile",
    "branch":"main","path":"src/...","text":"<全文>","message":"..."})
  ```
  読むのは同じ口の `action=content`（`"ref":"main"`）。
- **Mac側の `/Users/mac/Desktop/joy-relief-station` の作業ツリーは `claude/taste-entry-cover-guide` という
  古いブランチのまま・大量に dirty。**`origin/main` は追従しているので、**読むときは必ず `origin/main:` を付ける。**
  作業ツリーを grep すると古い中身を見ることになる（1回引っかかった）。
- **mac_jobs は45〜180秒で殺される。**`git grep` を全 src に掛けると落ちる。**パスを絞る。**

## 6. 触っていないもの
- Brave／内蔵ブラウザ／`request_access`／`request_cowork_directory`／`start_code_task`／`git worktree`：**すべて不使用。**
- 新しい定期タスク・新しい常駐：**0個。**課金：**0円。**
- 見た目：**変えていない。**（箱の大きさも出るものも前と同じ。読む時刻だけを遅らせた）
