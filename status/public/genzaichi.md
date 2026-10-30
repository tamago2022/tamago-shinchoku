# いまの現在地（10-30 18:55 時点・自動生成・実質30分おき）

⚠️ **今週見たいものを3つ教えてください**（`status/konshu_mitai.json`が空です）

**Dispatchは会話の最初に、返事をする前にこの1枚を読む。ルールではなく『今の状態』がここにある。**

## ★止まっていないか（ここが赤なら他を全部止めてでも直す）
- 🔴 **今日はまだ1本も発車していません**
- 🔴 **メイン不在のカードが棚に出ています：22件（5棚）**
- ✅ 本番に出した 7 件は全部 戻せます（戻れる点 anzen-20260924-1082）
- 🔴 稼ぎ：直近6時間 走った0本（うち空回し0本）→ **取れた0本**
  - 止めているもの：発車待ちは全部お金の確認待ち（直近6時間で990回）
- ✅ 本番(Lovable)：10.6時間前に更新あり
- ✅ 心臓：-0分前に動いた
- ✅ 着火：10分以内に動いている（空回しを含む。産んだ本数は上の「稼ぎ」を見る）
- 🔴 **仕組み系タスク #925「憲法点検：公開リポジトリの1MB超ファイル」が850時間waitingのまま放置されています**
- 🔴 **仕組み系タスク #937「憲法点検：公開リポジトリの1MB超ファイル」が1030時間waitingのまま放置されています**
- 🔴 **仕組み系タスク #1118「憲法点検：未報告の完了が溜まっていないか」が874時間waitingのまま放置されています**
- 🔴 **⚙️発車（auto_launch） が動いていません（2つを別々に見る：①発車係の生死＝status/auto_launch.logのmtime（現在0.3分）②着火の間隔＝status/.last_launch_atのmtime（現在2863.5分沈黙・genzaichi.launch_silence_min()を再利用）。②は空き枠がある時だけ異常とみなす（genzaichi._launch_has_room()を再利用。満員での見送りは正常）。判定：発車係は0.3分前に周回済み・空き枠もあるのに、着火が2863.5分ありません。countTodayはauto_launch.logの本日分『🚀 自動発車』行数）**
- 🔴 **⚙️完了報告の押し出し が動いていません（status/dispatch_outbox.jsonl（typeなし行）とstatus/dispatch_reported.jsonのns突き合わせ：未報告130件・最古348.5時間経過（3時間以内=alive／6時間以内=slow／それ超=dead））**
- 🔴 **確認待ちが578件（10件超）たまっています。鬼監督で仕分けてください**
- 🔴 **7日以上動いていない案件が5935件：16674番「ファイル移動、削除、上書き、大量」(137.7日)・16675番「もしこの画面や設定内に Acce」(137.7日)・16683番「「なぜ雨の日にこれか」の説明は、」(137.6日)・16686番「基本的にバラで出してもらっても構」(137.6日)・16687番「【一覧作成】振られてないんだった」(137.6日)、他5930件**

## 数字
- 走行 **0 / 4**（発車待ち 5092件・うちP1 3094件）
- 今日の完了 **0件**（9/06のピークは60件。20件を切ったら何かが詰まっている）
- 今日の子セッション **0本・合計 $0.00・1本平均 $0.00**
- クレジット 今日 **0.0 / 15.2**・週 **50.0%**
- 今週の残り枠 **49%**（あと4.0日・1日目安14.1%）
- 今週の配分：見たいもの 100% / 裏方 0% / 予備 0%

## 今日 止まっていた時間
- 今日はまだ1本も発車していません

## 今すぐ走っているもの
- **0本**（クレジットが残っているなら、これは異常）

## 次に出る（P1の先頭5件）
- 203897 差し戻し｜判定日赤｜あとはやってもらっていい？
- 203849 差し戻し｜判定日赤｜こういうのも報告してくれていいよ。
- 203126 終わったら、上の依頼のIssueにコメントで結果を返してください（店主に伝言をさせない）。
- 200343 起こし｜白飛びを根元から止める（）
- 200097 判定日赤｜食材単体でも十分な件数が出るように、フィルターの組み合わせロジックを見直してほしい。

## 待っているもの（返事待ち・本人しかできないこと）
- 件数 **558件**（たまごさんの確認・OK待ち）
- 137225 Opus｜シティポップ告知動画3案を85点まで作り直す（122702の続き）
- 125816 Fable｜月の特集 vol.1：7曲・濃く短くに組み直して本番を上書き
- 124961 Fable｜白飛びの解消：ページの切り替えで白い画面を挟まない
- 122709 Fable｜料理：シェフのアーティストページ37人分を充実＋料理を49品→倍に（データだけ）
- 122708 Fable｜サイト全体の見直し：導線・重さ・迷子
- 他 553件（進捗表の『判断待ち』欄で全件見られる）

## まだ渡していない完成品
- img-shutten-1019 公開待ち：壊れた画像6件の修正＋全マガジン・特集の出典を章ごとに（joy-rel
  https://joy-relief-station.lovable.app/feature/citypop-sekai
- toc-smooth-1019 公開待ち：全マガジン・特集 目次から滑らかに飛ぶ＋「押すとそこに飛びます」（jo
  https://joy-relief-station.lovable.app/magazine/ikareru-01.html
- None 公開待ち：LINE共有の直し（全ページ・アプリ起動の確認なし）＋白鳥の湖カードの
  https://joy-relief-station.lovable.app/room/card/marta-swan-lake-alzheimer
- labada-bu-asia-20261021 公開待ち：Labäda Bu「달리기 (Running)」＋アジアのインディー5
  https://joy-relief-station.lovable.app/cover-guide?artist=labada-bu&song=dalligi-running
- tana-shitei-20261021 公開待ち：仕入れの5曲を棚から外す＋棚の関所 check-tana-shitei
  https://joy-relief-station.lovable.app/shelf/music/asia
- gmtn-1022 公開待ち｜George Benson「Give Me the Night」曲ペー
  https://joy-relief-station.lovable.app/cover-guide?artist=george-benson&song=give-me-the-night-2
- gmtn-1022b 公開待ち｜Give Me the Night やり直し（main 5f4c0f6
  https://joy-relief-station.lovable.app/cover-guide?artist=george-benson&song=give-me-the-night
- gmtn-1022c 本番確認済み｜Give Me the Night（投稿カード・元記事ボタン・-2
  https://joy-relief-station.lovable.app/cover-guide?artist=george-benson&song=give-me-the-night

## 未解決の失敗（924番・引き継ぎで見落とすな）
- 未解決 **264件**（うち再発 **63件**）── `python3 tools/failures_ledger.py --list-open`
- F-20261030-ame 飴玉ゼロ率：85.4%（89係中 76係が「走っているのに取れた0」）
- F-20261030-uso 嘘の完了：8件（できもの未検証8件 ＋ 途中で固まった案件0件）
- F-20261030-ochita 落ちた便：1本（24時間：本物0本／空回し0本）

---
*このファイルは tools/genzaichi.py が自動生成する。手で書き換えない。*
