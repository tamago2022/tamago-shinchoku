# 1024 Devinを遊ばせない（9/22・18時まで）引き継ぎ

たまごさんは外出中。質問はしない。止まってよいのは不可逆な4つだけ
（作り直せないデータ削除／課金／外部公開／パスワード入力）。

## 絶対に触らないもの
- **オンデマンド残高。** `Purchase on-demand usage` / `Configure auto-reload settings` /
  `Manage billing` は**見るだけ。クリック禁止。**有料プラン契約・追加購入は厳禁。
- Brave（`88704cda-...`）には触らない。Chromeは `7d965dae-...`。
- `joy-relief-station` を公開リポジトリにしない。
- 返ってきたPRを**自動でマージしない。**

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

## 第2便（tools/devin_1by1_922b.py）待ち行列＝6本
D→E→F→G→H→I の順に、**1本ずつ**投げる（前が終わるまで次を投げない）。

| | 題材 | 投げ先 | 返し方 |
|---|---|---|---|
| D | 外部からのYouTube追加が時々落ちる | joy-relief-station | PR か 本文 |
| E | `.git/index.lock` 取り合いの根本原因 | tamago-shinchoku | 本文＋diff（403でpush不可） |
| F | PR#455 の後に残る重さ最大1つ | joy-relief-station | PR か 本文 |
| G | 待ち行列132件が減らない理由 | tamago-shinchoku | 本文＋diff |
| H | `status/` を太らせている出所 | tamago-shinchoku | 本文＋diff |
| I | Pages が404のままになる条件 | tamago-shinchoku | 本文＋diff |

## Devin に投げるときの型（実測で2回とも当てた形）
- **「こちらの前提が正しいか、実測で確かめてくれ」＋こちらの結論を先に見せない。**
- 依頼文に必ず埋める：
  - 「返事を書くな。終わりの合図は【終わりの合図】の1通だけ。」
  - 「詰まったら聞かずに別の手を試せ。手を5つ試すまで止まるな。」
  - 「依頼主は外出中で、誰も答えられません。」
- **向かない（投げない）：** 見た目の判断／範囲が曖昧な掃除／本番まで通す必要がある仕事。
- **1本ずつ。** 3本同時は枠が30分で空になる（実測）。
- **APIは枠が空でも200で受理する。受理≠動いている。**30分後に `403 out_of_quota`。

## 次の人がやること
1. `status/devin_922b.json` の `thrown` と `returned` を見る。
   **「投げた>0 なのに 返り=0」なら赤。** ticker が死んでいないか確認する。
2. 返ってきたPRは**中身を見てから**扱う。自動マージ禁止。
3. 待ち行列（D〜I）が空になったら、同じ型で題材を足す。
4. 20分に1回、たまごさんに3行で報告する
   （1行目＝投げ数と返り数／2行目＝当てた一番大きいもの／3行目＝枠の残りと次の1本）。
