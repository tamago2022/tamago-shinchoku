# いまの現在地（11-28 06:32 時点・自動生成・実質30分おき）

⚠️ **今週見たいものを3つ教えてください**（`status/konshu_mitai.json`が空です）

**Dispatchは会話の最初に、返事をする前にこの1枚を読む。ルールではなく『今の状態』がここにある。**

## ★止まっていないか（ここが赤なら他を全部止めてでも直す）
- 🟡 今日 止まっていた：**364分**（本物 29 本／空回し 0 本）
- 🔴 **メイン不在のカードが棚に出ています：22件（5棚）**
- ✅ 本番に出した 7 件は全部 戻せます（戻れる点 anzen-20260924-1082）
- 🔴 稼ぎ：直近6時間 走った27本（うち空回し0本）→ **取れた27本**
  - 止めているもの：Claudeの週次利用上限（weekly limit）に達しています。resumeAt=2026-11-28T06:39:23+09:00 まで新規発車を止めます（過ぎたら自動で外します）。検知時刻:2026-11-28 05:39
- 🔴 **本番(Lovable)：78時間 更新なし** ← コードを直しても画面は変わらない。最優先で復旧
- ✅ 心臓：-0分前に動いた
- 🔴 **発車：54分 沈黙**（見つけて直しました：心臓は生きていたので、5分便(machine-status)へ蹴り直しを依頼しました／no_launch.flagが残っています（内容：Claudeの週次利用上限（weekly limit）に達しています。resumeAt=2026-11-28T06:39:23+09:00 まで新規発車を止めます（過ぎたら自動で外します）。検知時刻:2026-11-28 05:39）。正当な理由か人の目で確認してください）
- 🔴 **仕組み系タスク #925「憲法点検：公開リポジトリの1MB超ファイル」が1534時間waitingのまま放置されています**
- 🔴 **仕組み系タスク #937「憲法点検：公開リポジトリの1MB超ファイル」が1713時間waitingのまま放置されています**
- 🔴 **仕組み系タスク #1118「憲法点検：未報告の完了が溜まっていないか」が1557時間waitingのまま放置されています**
- 🔴 **⚙️発車（auto_launch） が動いていません（2つを別々に見る：①発車係の生死＝status/auto_launch.logのmtime（現在8.0分）②着火の間隔＝status/.last_launch_atのmtime（現在54.3分沈黙・genzaichi.launch_silence_min()を再利用）。②は空き枠がある時だけ異常とみなす（genzaichi._launch_has_room()を再利用。満員での見送りは正常）。判定：発車係は8.0分前に周回済み・空き枠もあるのに、着火が54.3分ありません。countTodayはauto_launch.logの本日分『🚀 自動発車』行数）**
- 🔴 **⚙️Lovable公開 が動いていません（status/deploy_history.jsonのat基準（x-deployment-idが変わった時刻）：現在78.2時間更新なし（24時間以内=alive／48時間以内=slow／それ超=dead）。ネットワークは叩かずこのファイルの記録だけで判定する（0円））**
- 🔴 **⚙️完了報告の押し出し が動いていません（status/dispatch_outbox.jsonl（typeなし行）とstatus/dispatch_reported.jsonのns突き合わせ：未報告165件・最古1032.1時間経過（3時間以内=alive／6時間以内=slow／それ超=dead））**
- 🔴 **確認待ちが759件（10件超）たまっています。鬼監督で仕分けてください**
- 🔴 **7日以上動いていない案件が7338件：16674番「ファイル移動、削除、上書き、大量」(166.2日)・16675番「もしこの画面や設定内に Acce」(166.2日)・16683番「「なぜ雨の日にこれか」の説明は、」(166.1日)・16686番「基本的にバラで出してもらっても構」(166.1日)・16687番「【一覧作成】振られてないんだった」(166.1日)、他7333件**

## 数字
- 走行 **0 / 測定できていません**（発車待ち 6018件・うちP1 3939件）
- 今日の完了 **0件**（9/06のピークは60件。20件を切ったら何かが詰まっている）
- 今日の子セッション **29本・合計 $0.00・1本平均 $0.00**
- クレジット 今日 **0.0 / 15.3**・週 **25.0%**
- 今週の残り枠 **74%**（あと3.5日・1日目安14.1%）
- 今週の配分：見たいもの 93% / 裏方 7% / 予備 0%

## 今日 止まっていた時間
- 今日の発車 **29本**（本物 29本／空回し 0本）・最初 00:09／最後 05:38
- ★**止まっていた合計：364分（6.1時間）**
- 10分以上あいた所：
  - 00:10 → 01:11　**61分**
  - 01:16 → 02:18　**62分**
  - 02:20 → 03:22　**62分**
  - 03:27 → 04:30　**63分**
  - 04:30 → 05:32　**61分**
  - 05:38 → いま　**55分（まだ止まっています）**

## 今すぐ走っているもの
- **0本**（クレジットが残っているなら、これは異常）

## 次に出る（P1の先頭5件）
- 272435 判定日赤｜ある分だけでいいので、その情報を共有してほしい。
- 272434 判定日赤｜既存の構造的ブロッカー（launchd退役＋CDP未常駐＋起動禁止）から変化なし
- 272433 判定日赤｜gh CLI無し、WebFetchは非公開リポ・Lovable管理画面いずれも認証なし
- 272432 判定日赤｜GitHub Issue本文自体も、このworktree環境ではghコマンドが使えず（
- 272431 判定日赤｜これさ、もうちゃんと裏取りやってほしいな。

## 待っているもの（返事待ち・本人しかできないこと）
- 件数 **705件**（たまごさんの確認・OK待ち）
- 247604 空カード埋め｜キリンジ（2/2）
- 247409 空カード埋め｜リー・スクラッチ・ペリー（2/2）
- 246318 GH1047 店主の推し曲ページ作成（10/24 店主指名）
- 215150 共有URLを短く統一（/v/<ID>・OGP残す・旧URL転送）
- 205559 空カード埋め｜Donald Fagen（2/2）
- 他 700件（進捗表の『判断待ち』欄で全件見られる）

## まだ渡していない完成品
- tana-shitei-20261021 公開待ち：仕入れの5曲を棚から外す＋棚の関所 check-tana-shitei
  https://joy-relief-station.lovable.app/shelf/music/asia
- gmtn-1022 公開待ち｜George Benson「Give Me the Night」曲ペー
  https://joy-relief-station.lovable.app/cover-guide?artist=george-benson&song=give-me-the-night-2
- gmtn-1022b 公開待ち｜Give Me the Night やり直し（main 5f4c0f6
  https://joy-relief-station.lovable.app/cover-guide?artist=george-benson&song=give-me-the-night
- gmtn-1022c 本番確認済み｜Give Me the Night（投稿カード・元記事ボタン・-2
  https://joy-relief-station.lovable.app/cover-guide?artist=george-benson&song=give-me-the-night
- dispatch-1113-0 GH1159 おふとんレディオ5周年 → 睡眠用BGM棚ほか：本番の中身で確認済
  https://joy-relief-station.lovable.app/cover-guide?artist=funnymovie&song=namimiko-ofuton-radio-5th
- dispatch-1113-1 GH1164 SHOW-GO → 口芸・ビートボックス棚：本番の中身で確認済み
  https://joy-relief-station.lovable.app/cover-guide?artist=show-go&song=jasmine-gbb2021
- dispatch-1113-2 猫の棚の初回ちらつき修正：本番の中身で確認済み
  https://joy-relief-station.lovable.app/
- yomikuchi 新しい連携の候補 10件（読み口の見直し）
  https://tamago2022.github.io/tamago-shinchoku/share/check/furiwake.html#yomikuchi

## 未解決の失敗（924番・引き継ぎで見落とすな）
- 未解決 **308件**（うち再発 **65件**）── `python3 tools/failures_ledger.py --list-open`
- F-20261128-ame 飴玉ゼロ率：85.6%（90係中 77係が「走っているのに取れた0」）
- F-20261128-uso 嘘の完了：8件（できもの未検証8件 ＋ 途中で固まった案件0件）
- F-20261128-ochita 落ちた便：5本（24時間：本物75本／空回し0本）

---
*このファイルは tools/genzaichi.py が自動生成する。手で書き換えない。*
