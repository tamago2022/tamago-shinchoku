# 1024 Devinを遊ばせない（9/22・18時まで）引き継ぎ

たまごさんは外出中。質問はしない。止まってよいのは不可逆な4つだけ
（作り直せないデータ削除／課金／外部公開／パスワード入力）。

## 絶対に触らないもの
- **オンデマンド残高。** `Purchase on-demand usage` / `Configure auto-reload settings` /
  `Manage billing` は**見るだけ。クリック禁止。**有料プラン契約・追加購入は厳禁。
- Brave（`88704cda-...`）には触らない。Chromeは `7d965dae-...`。
- `joy-relief-station` を公開リポジトリにしない。
- 返ってきたPRを**自動でマージしない。**

## ★いちばん大事な実測（2026-09-22 09:28）：**枠が尽きた**
```
HTTP 403 {'detail': 'Your organization has a billing error. Error: out_of_quota'}
```
- **オンデマンドには一切触っていない。**購入・自動チャージ・請求の画面はクリックしていない。
- 枠が戻るまで Devin は動かせない。ticker が60秒ごとに叩き続けるので、
  **戻った瞬間に自分で投げ直す。**人が並べ直す必要はない。

## ★数え方の落とし穴（今日3回間違えた。次の人は間違えないで）
1. 「messagesが2通以上＝返ってきた」→ **嘘。**Eは「読みました。実測を進めます」という
   **返事だけ**書いて寝た。それも2通になる。
2. 「最後の1通に『答え：』がある＝返ってきた」→ **嘘。**枠切れの空振りは
   **こちらの依頼文だけ**が messages に入って戻る。依頼文の中に「答え：」の字がある。
3. 「type != user_message がDevinの発言」→ **嘘。**こちらの依頼文の type は
   **`initial_user_message`**（username=`TAMAGO`）。
4. **正解：`type == "devin_message"` の最後の1通に「答え：」があるか、PRのURLがあるか。**
   これだけを返りに数える。`tools/devin_1by1_922b.py` にそう直した。

## いま動いているもの（2026-09-22 09:20 時点）
- **`tools/devin_ticker_922b.sh`** が Mac のうしろで走っている。
  - 60秒ごとに `tools/devin_1by1_922b.py` を1回叩く。叩くたびに1歩進む（様子見 or 次を投げる）。
  - **18:00になったら自分で終わる。**待ち行列が空になっても終わる。
  - 止め方：`status/.devin_922b_stop` を作る。生死：`status/.devin_922b_ticker.lock`。
  - ログ：`status/devin_922b_ticker.log`
  - 台帳：`status/devin_922b.json`（`thrown` と `returned` を両方数えている）
- 起動のしかた（もし死んでいたら）：`status/mac_jobs/pending/` に置く札に
  `nohup bash tools/devin_ticker_922b.sh > /dev/null 2>&1 &` と書くだけ。

## 実測でわかっていること（今日の分）
- **サンドボックス（Cowork の bash）からは `api.devin.ai` に届かない**
  （`Tunnel connection failed: 403 Forbidden`）。Devin を叩くのは必ず **Mac側**、
  `status/mac_jobs/pending/<名前>.sh` に札を置く経路から。
- **枠そのものは API では測れない。** `/v1/enterprise/consumption` は
  `{"detail":"Contact support to enable the consumption API"}` を返す。
  `/v1/usage` `/v1/account` `/v1/me` は 404。
  → 測れるのは「一覧に走行中が何本あるか」と「30分後に `403 out_of_quota` が出るか」だけ。
- `gh` コマンドは Mac に入っていない。PRを読むときは
  `git fetch origin pull/<n>/head:<枝>` で取ってきて読む（マージはしない）。
- `status/` 直下は `.gitignore:39` で除外。**残したい紙は `status/public/` に置く。**

## 第1便（tools/devin_1by1_922.py）結果：投げた3／返った3
| | 題材 | 時間 | 返り |
|---|---|---|---|
| A | 心臓が死ぬ理由 | 5分 | 本文で回答（行番号つき＋diff） |
| B | joy-relief トップの重さ | 30分 | **PR #455** |
| C | リポジトリ肥大の真犯人 | 111分 | 本文で回答（上位10件の表） |

- **Cの答え：** `share/eagle-k7m2xq9p/`（PNG/JPG 2,347ファイル）が
  リポジトリ 1.44GB のうち **737MB（51%）**。次が `share/check/` 466MB。
- **Aの答え：** 心臓が `auto_launcher.py` と `command_ingest.py` を**同期で最大45秒ずつ待つ**のに、
  生存 touch は1周に1回しかしていない。見張りの `STALE_SECS=60` より心臓のワーストケース
  （90〜105秒）が大きいので、**生きている心臓が必ず殺される。**

## 第2便（tools/devin_1by1_922b.py）結果：投げた3／**本物の返り1**
| | 題材 | 時間 | 返り |
|---|---|---|---|
| D | 外部からのYouTube追加が時々落ちる | 9分 | **本物**（実測80回＋DB252行） |
| E | index.lock 取り合いの根本原因 | 5分 | ✗「読みました」だけ書いて寝た → 待ち行列に戻した |
| F | #455の後に残る重さ最大1つ | 1分 | ✗ 枠切れの空振り（Devinは一言も書いていない） |

### Dの答え（たまごさんの見立てとは別物だった）
> 答え：「毎回ではない」は2つの実測できる差で説明できる。
> ①貼ったYouTube IDのサムネイル有無（IDごとに決定的・404なら必ず落ちる）
> ②1本追加の1リクエストが Wikipedia直列取得（最大22回）＋AI呼び出し複数を含み、
> 0.7秒〜8秒超まで揺れるため、遅い回だけ端末側／経路側で切られて「落ちた」に見える

- 実測：8ID×10回=80回 → 成功60／失敗20。
  落ちたIDは `Yc6G8B8_5gY` と `k_-RxMOdSWY` で **10回とも HTTP 404**（本文1097バイト）。
  **同じIDで結果がぶれた例は0回＝ランダムではなく入力で決まる。**
- 落ちる場所：`src/lib/adminShelves.functions.ts` L459 サムネ取得 → L469 判定NG → L1740 throw
- 遅さの正体：`getArtistWikiExtract`/`getSongWikiExtract` が 0.68〜6.6秒・fetch 2〜22回（直列）。
  そのあとAI呼び出しが**直列で**続く（`ai-copy.server.ts` `callGateway` はタイムアウト無し）。
- 証拠：本番 `admin_stock` の YouTube行252件に **同じ動画の二重登録が4組**。
  登録時刻の差 0ms／1097ms／1733ms／**7943ms** ＝1回目が7.9秒経っても insert に届いていない。
- PRを作らなかった理由も書いてある（先に insert する案は L2002 の「既存曲に合流」挙動と
  ぶつかり、行の削除が必要になる＝データを消すことになるので採らなかった）。

### 待ち行列の残り（E→F→G→H→I→J→K→L の8本）
**1本ずつ**投げる（前が終わるまで次を投げない）。枠が戻れば ticker が勝手に E から再開する。

| | 題材 | 投げ先 | 返し方 |
|---|---|---|---|
| D | 外部からのYouTube追加が時々落ちる | joy-relief-station | PR か 本文 |
| E | `.git/index.lock` 取り合いの根本原因 | tamago-shinchoku | 本文＋diff（403でpush不可） |
| F | PR#455 の後に残る重さ最大1つ | joy-relief-station | PR か 本文 |
| G | 待ち行列132件が減らない理由 | tamago-shinchoku | 本文＋diff |
| H | `status/` を太らせている出所 | tamago-shinchoku | 本文＋diff |
| I | Pages が404のままになる条件 | tamago-shinchoku | 本文＋diff |
| J | 同じ動画が棚に2枚並ぶ | joy-relief-station | PR か 本文 |
| K | 壊れている確認ページの件数 | tamago-shinchoku | 本文＋diff |
| L | queue.json.gz が228版ある理由 | tamago-shinchoku | 本文＋diff |

## Devin に投げるときの型（実測で2回とも当てた形）
- **「こちらの前提が正しいか、実測で確かめてくれ」＋こちらの結論を先に見せない。**
- 依頼文に必ず埋める：
  - 「返事を書くな。終わりの合図は【終わりの合図】の1通だけ。」
  - 「詰まったら聞かずに別の手を試せ。手を5つ試すまで止まるな。」
  - 「依頼主は外出中で、誰も答えられません。」
- **向かない（投げない）：** 見た目の判断／範囲が曖昧な掃除／本番まで通す必要がある仕事。
- **1本ずつ。** 3本同時は枠が30分で空になる（実測）。
- **APIは枠が空でも200で受理する。受理≠動いている。**30分後に `403 out_of_quota`。

## PR #455 の中身（**まだマージしていない**）
- Devinのコミット：「速さ: トップ初回ロードから youtube-id-map（839KB gz）を外す —
  head/beforeLoad の worlds.ts 参照を loader へ移動」
- 規模：12ファイル / +186 / −97。触っているのは
  `src/routes/__root.tsx` `hub.$hubId.tsx` `shelf.$worldId.$shelfId.tsx` `world.$worldId.tsx`
  `room.*` `vite.config.ts` `components/ShareButton.tsx`。
  やり方は「静的 import を `await import()` / loader へ移す」。
- **CIは赤だが、コード起因ではない。**Devinの補足：
  GitHub Actions が「account payments have failed / spending limit」で**ジョブ自体が起動していない。**
  → ここは課金の話なので**触っていない。**たまごさんの判断待ち。
- Macでの読み方（`gh` は入っていない）：
  `cd ~/Desktop/joy-relief-station && git fetch origin pull/455/head:pr455-readonly`
  → `git diff $(git merge-base origin/main pr455-readonly) pr455-readonly`

## 次の人がやること
1. `status/devin_922b.json` の `thrown` と `returned` を見る。
   **「投げた>0 なのに 返り=0」なら赤。** ticker が死んでいないか確認する。
2. 返ってきたPRは**中身を見てから**扱う。自動マージ禁止。
3. 待ち行列（D〜I）が空になったら、同じ型で題材を足す。
4. 20分に1回、たまごさんに3行で報告する
   （1行目＝投げ数と返り数／2行目＝当てた一番大きいもの／3行目＝枠の残りと次の1本）。
