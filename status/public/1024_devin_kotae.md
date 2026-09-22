# 1024 Devinが実測で出した答え（9/22）

※ こちらの見立ては一切渡していない。全部Devinが自分で測って出したもの。
※ 返ってきたPRは中身を見てから扱う。**自動でマージしない。**

（最終更新 2026-09-22 09:39:31・返ってきた本数 6）

## 第1便 A 心臓が死ぬ理由（結論伏せ）（5分）

- セッション: https://app.devin.ai/sessions/0007da7ca7f04ae2870a82e7a0e44e47
- PR: なし

答え：心臓を止めているのは「auto_launcher.py（と command_ingest.py）を **同期で最大45秒ずつ待つ** のに、生存touchは1周に1回・ループ先頭でしかしていない」という heartbeat.sh 自身の構造です。auto_launcher が45秒killに達した周は、touch→touch の間隔が必ず 45＋command_ingest＋相乗り起動＋sleep15 ＝ 60秒超になり、見張り（STALE=60秒）が生きている心臓を kickstart -k で殺します。

■ 根拠（コードの筋道）
1. tools/heartbeat.sh:109 — touch は while ループの先頭で **1周につき1回だけ**。
2. tools/heartbeat.sh:129 と :131 — `run_with_timeout 45 python3 auto_launcher.py` / `command_ingest.py` を **同期（& なし）** で順に待つ。:78 `wait "$cpid"` で親は完全に止まる。上限は 45＋45＝90秒。
3. tools/heartbeat.sh:270 — その後 `sleep 15`。よって auto_launcher が timeout した周の touch 間隔の最小値は 45＋15＝60秒＋α（command_ingest 数秒＋相乗り python 起動 十数本）。実測ログの 68/74/83秒 はちょうどこの範囲。137秒 は auto_launcher と command_ingest の両方が timeout した周（45＋45＋15＋α）。
4. tools/heartbeat_watchdog.py:45 `STALE_SECS = 60`、:86-89 — 60秒を1秒でも超えると即 kickstart。心臓のワーストケース（90〜105秒）より小さく設定されているので、「心臓は正常に動いているのに殺される」が仕様上必ず起きる。ログの「心臓を起動しました」が timeout 行の 40〜60秒後に並んでいるのはこの殺害＋再起動。
5. auto_launcher が45秒を超える中身：tools/auto_launcher.py:1977 `with queue_lock()` の中で :2430/:2436/:2444 `git worktree add`（WT_ADD_TIMEOUT=90、最大3回＝270秒。joy-relief-station は .git 320MB＋worktree 77件で遅いと :2380-2381 に実測記載）、および :2520-2525 の harvest（content_check :431 が URL 1本あたり10秒、直列）。さらに tools/queue_store.py:56 `queue_lock(timeout=180)` は他プロセス（command_ingest/relay_server）が鍵を持っていると最大180秒スピン待ちする。どれも 45秒を超え得る。

■ 02時台・06時台に集中し、03〜06時が静かな理由（コードからの推論・ログには発車行が無いので断定はしません）
上の 5 が走るのは「発車（worktree add）か回収（harvest の実URL検品）がある周」だけです。走行枠が埋まっている／待ち行列が空の間（03〜06時）は _main_impl が :2103-2105 の「見送り」か :1980 の空判定で即 return し、45秒に届かない → 静か。02時台と06時台は仕事が終わって枠が空き、発車＋回収がまとめて発生した時間帯と読めます（06:24→06:40 の約15分周期も「1本発車→走行→回収」の粒度と合います）。同じ構造なので、発車があるたびに同じ往復が起きます。

■ 直し方（最小・1つだけ）：待っている間も心臓が生きていることを見張りへ示す。run_with_timeout の見張り子プロセスが 5秒ごとに .heartbeat_alive を touch する。

```diff
--- a/tools/heartbeat.sh
+++ b/tools/heartbeat.sh
@@ -73,7 +73,11 @@ run_with_timeout() {
   "$@" &
   local cpid=$!
   local killed_flag="$REPO/status/.heartbeat_killed_$$_$cpid"
-  ( sleep "$secs" 2>/dev/null; if kill -0 "$cpid" 2>/dev/null; then : > "$killed_flag"; kill -9 "$cpid" 2>/dev/null; fi ) &
+  # 子を待っている間もループ本体は生きているので、見張り(60秒)に殺されないよう5秒ごとにtouchする
+  ( n=0; while [ "$n" -lt "$secs" ]; do sleep 5 2>/dev/null; n=$(( n + 5 )); touch "$REPO/status/.heartbeat_alive" 2>/dev/null || true; done
+    if kill -0 "$cpid" 2>/dev/null; then : > "$killed_flag"; kill -9 "$cpid" 2>/dev/null; fi ) &
   local watcher=$!
   wait "$cpid" 2>/dev/null
   local rc=$?
```

これで touch 間隔の最大は「5秒＋相乗り起動＋sleep15」≒25秒に収まり、45秒killの仕組みはそのまま残ります（本当に bash ループが固まった時は watcher も止まるので、見張りは従来どおり効きます）。

---

## 第1便 B joy-relief 残りの重さ最大1つ（30分）

- セッション: https://app.devin.ai/sessions/3c39ffc2c4ca497a8d1af203f7ae88e2
- PR: https://github.com/tamago2022/joy-relief-station/pull/455

https://github.com/tamago2022/joy-relief-station/pull/455

補足1行のみ：GitHub Actions が「account payments have failed / spending limit」でジョブ未起動のためCIは赤です（コード起因ではありません）。

---

## 第1便 C リポジトリ肥大の真犯人（111分）

- セッション: https://app.devin.ai/sessions/d61739ebec224075af08cb81f57b1d78
- PR: なし

答え：`share/eagle-k7m2xq9p/` ディレクトリ（PNG/JPG 画像 2,347 ファイル）が、リポジトリ全体 1.44 GB のうち 737 MB（51%）を占めており、これが肥大の最大要因です。

**実測の全体像**（clone 直後、`git count-objects` / `git rev-list --objects --all`）
- pack サイズ 1.40 GiB、オブジェクト 45,706 個（うち blob 26,376 個、blob 合計 1,439 MB）
- 作業ツリー 689 MB、追跡ファイル 4,627、ディレクトリ 118、コミット 4,914
- 拡張子別（share/ 配下の履歴）：png 695 MB、mp4 271 MB、jpg 198 MB、wav 73 MB、m4a 45 MB
- 補足：`git status` 自体は 0.09 秒で速く、体感の遅さは clone（1.4 GB のダウンロード）と 4,000 超の画像・動画ファイルの checkout が主因です。

**上位10件：ディレクトリ／パス別（履歴に残る全バージョンの pack 内サイズ）**

| # | パス | 履歴サイズ | blob 数 | 備考 |
|---|---|---|---|---|
| 1 | share/eagle-k7m2xq9p/ | 736.7 MB | 2,089 | 追跡 2,347 ファイル・作業ツリー 376 MB・2026-09-04 から 117 コミットで急増 |
| 2 | share/check/ | 466.4 MB | 3,172 | 追跡 1,536 ファイル・作業ツリー 261 MB・1,513 コミット（mp4/png） |
| 3 | share/podcast/ | 90.3 MB | 47 | wav/m4a 音声 |
| 4 | status/ | 66.9 MB | 19,057 | うち status/public/queue.json.gz が 228 バージョンで 54.9 MB（小さいがオブジェクト数最多） |
| 5 | share/audio/ | 26.1 MB | 7 | wav |
| 6 | tools/ | 23.0 MB | 1,193 | うち tools/bin/cloudflared バイナリ 20.1 MB |
| 7 | wae_autopost/ | 11.9 MB | 27 | |
| 8 | share/x-search/ | 3.8 MB | 4 | data.json 11.6 MB（.gitignore 済みだが履歴に残存） |
| 9 | share/20-little-phrases/ | 3.1 MB | 30 | |
| 10 | share/nandeyanen/ | 2.5 MB | 15 | |

**単体ファイル上位（参考）**：754-jinbunchi-ai.wav 66.6 MB、tools/bin/cloudflared 39.8 MB、entaku_5nin_aivis.wav 30.6 MB、chashitsu_loop.mp4 16.2 MB、kuroihama_loop.mp4 15.4 MB — いずれも単体では eagle ディレクトリの 1/10 以下です。

**推奨（1つ）：`share/eagle-k7m2xq9p/` の追跡をやめる**（.gitignore に追加し、画像は外部ストレージ／Git LFS へ）。
理由：これ1つで履歴の 51%（737 MB / 1,439 MB）、作業ツリーの 55%（376 MB / 689 MB）、追跡ファイルの 51%（2,347 / 4,627）が対象になります。2位の share/check（466 MB）より 270 MB 大きく、単体ファイル最大の wav（67 MB）の 11 倍。しかも 9/4 以降 117 コミットで積み上がっており、「日に日に重くなる」原因そのものです。なお指示どおり削除・履歴書き換えは一切行っていません（履歴から消すには別途 filter-repo 等が必要で、追跡停止だけでは今後の増加が止まる効果になります）。

---

## 第2便 D YouTube外部追加が時々落ちる（9分）

- セッション: https://app.devin.ai/sessions/79105a170498480ab30568994c6a6bbb
- PR: なし

答え：「毎回ではない」は2つの実測できる差で説明できます。①貼ったYouTube IDのサムネイル有無（IDごとに決定的・404なら必ず落ちる）、②1本追加の1リクエストがWikipedia直列取得（最大22回）＋AI呼び出し複数を含み所要時間が0.7秒〜8秒超まで揺れるため、遅い回だけ端末側／経路側で切られて「落ちた」に見える（かつ同じ動画の二重登録が実際に発生している）。PRは作りませんでした。

■ 経路（ビルド時処理ではなく、管理画面→TanStack Startサーバー関数）
- 入口：`src/components/AdminShelfPanel.tsx` `handleUrlSubmit` / `ensureUrlStockFromInput`（`ShelfCardPriorityMenu.tsx`・`BadgeQuickPicker.tsx`からも同関数を呼ぶ）
- 本体：`src/lib/adminShelves.functions.ts` L1718 `adminAddStockFromUrl`
  - L459 サムネ取得 → L469 判定NG → L1740 で throw（ここが「落ちる」1つ目）
  - L1973 `researchAndResolveArtist`（AI同定＋Wikipedia）→ L2022 `generateVideoCopyFromTitle`（AI）→ L2033 insert
- GitHub Actions（`tamago-daily-ingest-copy-check.yml`）は追加後の監査で、追加経路ではない

■ 実測1：サムネ検証部分（本番と同じ順序・条件で 8 ID × 10回 = 80回）
- 成功 60回／失敗 20回
- 落ちたID：`Yc6G8B8_5gY` 0/10、`k_-RxMOdSWY` 0/10 → 10回とも HTTP 404・本文1097バイト → L469で不合格 → L1740 throw
- 通ったID（`SU1apJTv94o` 等6本）：10/10、HTTP 206・4096バイト、oEmbed 200・約20〜28ms
- 同一IDで結果がぶれた例は0回。つまり入力IDの違いで「通る/落ちる」が決まる（ランダムではない）

■ 実測2：Wikipedia直列取得の所要時間（実物の `getArtistWikiExtract`/`getSongWikiExtract`、10組）
- 0.68秒〜6.6秒、fetch回数 2〜22回（例：Yenlik 6615ms/22回、Stevie Wonder 4426ms/22回、アイナ・ジ・エンド 692ms/4回）
- このあとに AI呼び出し（同定・コピー生成、`ai-copy.server.ts` `callGateway` はタイムアウト無し）が直列に続く。AI鍵はローカルに無いためAI部分の秒数は未計測

■ 実測3：本番DB `admin_stock`（YouTube行252件、読み取りのみ）
- 同一動画の二重登録 4組：時刻差 0ms／1097ms／1733ms／7943ms。つまり1回目が7.9秒経っても insert（L2033）に到達していない間に2回目が投げられ、両方登録された＝1リクエストが8秒以上かかる回が実在する証拠
- 直近59件のうち whisper 空 6件（AI工程が途中で失敗しても行は残る設計）

■ PRを作らなかった理由
- 直す案は「insert を先に行い後からAI結果で update」だが、L2002 で「既存曲と一致したら新規行を作らず既存カードへ合流（duplicate返し）」する既存挙動があり、先に insert すると行の削除が必要になる（既存データ削除・棚の見え方に影響）
- 代替のタイムアウト付与も、遅い回のアーティスト紐づけ・コピーが欠けるため既存の動きが変わる
- 端末側／経路側の打ち切り秒数そのものは本番ログが無く実測できていない（ここは推定）。次に測るなら、L1718直後と各工程の経過msを `console.warn` で残すか、`site_events` に記録する変更が最小です

---

## 第2便 E index.lock取り合いの根本原因（5分）

- セッション: https://app.devin.ai/sessions/a753b0bd20a6419895c73d3eaa5b126d
- PR: なし

読みました。実測を進めて、終わりの合図1通だけ送ります。

---

## 第2便 F 455の後に残る重さ最大1つ（1分）

- セッション: https://app.devin.ai/sessions/30896e6967b8408995b930820d0eb103
- PR: なし

（Devinは一言も書かずに終わりました。枠切れの空振りの可能性があります）
