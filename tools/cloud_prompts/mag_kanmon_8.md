joy-relief-station（main）の改善。調べて終わり禁止。PRまで作ること。終わりの合図はPRのURLだけ。質問せず自分で決めて最後までやる。

【実行の作法（重要・承認待ちで止まらないために）】このリポの .claude/settings.json は許可リスト方式。使えるのは npm ci / bun install --frozen-lockfile / npm run <script> / bun run <script> / npx tsx <file> / git（status・diff・log・add・commit・push・switch -c）/ gh pr create / curl -s https://joy-relief-station.lovable.app/* / curl -s https://www.youtube.com/oembed?… 等。`python3`・`node` 直叩き・`git clone`・`npx playwright` は許可に無いので使わない（.mjs も `npx tsx` で動く）。コマンドは1回1つ、&（バックグラウンド）・$()・サブシェル・sleep・多段パイプは使わない（承認待ちになり、無人なので止まる）。依存は最初に `npm ci`（失敗したら `bun install --frozen-lockfile`）。

【ゴール】マガジン8号に載っている曲のうち、関所で落ちた曲（下の一覧・計102件）を全部「独立した曲ページがある・正しいリンク・関連4曲以上（理由の言えるもの）・コピーとメモ（出典つき）」にそろえる。店主の言葉：「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【この環境での読み替え】下の一覧にある工場の道具（python3 tools/magazine/magazine_gate.py・tools/magazine/song_pages.json・deploy_project・Dispatch）はこのリポには無い。やらない。代わりに：曲ページのデータは src/data／coverGuide.ts 系（既存の曲の書き方をそのまま倣う）、関連は src/lib/relatedReason.ts・shelfPicks.ts・moodThreads.ts・coverGuide.ts の relatedProjects、マガジン側の「この曲のページへ →」は public/magazine/<号>.html の該当動画の札に既存の型どおり a.cw-video__page を足す。出典は、動画そのもの（YouTube oEmbed で投稿者・題）とリポ内の記録から言えることに限る（Wikipedia 等は許可が無いので読みに行かない。裏の取れない年号・枚数・受賞は書かない）。
【アーティストの取り違え禁止】曲ページを新しく作るときは、動画の投稿者（oEmbed の author_name）が本人・公式・それに準ずるものかを確かめ、名前の字面一致で別人に紐付けない。確かめられないものは作らず PR 本文に「保留」と書く。名カバーの棚には足さない。
【検査】npx tsc --noEmit／npm run build（prebuild の関所：check-i18n-parity・check-internal-links・check-cover-truth ほか）が通ること。新しい日本語の UI 文言は src/i18n/overlay/{en,zh-Hans,es,ko}.json に同じコミットで訳を足す。
【PR 本文】号ごとに「落ちていた件数→直した件数→保留（理由）」の表。
【禁止】本番DB・Supabaseへの書き込み、秘密情報の出力、他人の未commit変更の巻き込み、既存ファイルの大量書き換え。
━━━━━━ 一覧（工場の関所 2026-10-18 の結果。文中の工場の道具・公開・報告の行は上の読み替えに従う） ━━━━━━
## 122777 マガジンの曲ページ uke-01（26曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/uke-01.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:27:30）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】26曲
- 打首獄門同好会「布団の中から出たくない」（動画 s4DxPeLNVuw） → uchikubi-gokumon-doukoukai/futon-no-naka-kara-detakunai：関連が2曲（4曲以上必要）
- 打首獄門同好会「日本の米は世界一」（動画 BuU2bocSfDo） → uchikubi-gokumon-doukoukai/nihon-no-kome-wa-sekaiichi：関連が2曲（4曲以上必要）
- 打首獄門同好会「島国DNA」（動画 10tju_9D5JI）：曲ページが無い（曲ページが無い）
- 栗コーダーカルテット「帝国のマーチ（ダース・ベイダーのテーマ）」（動画 DHrfi5W5HJE）：曲ページが無い（曲ページが無い）
- やる気のないダース・ベイダーのテーマ「ネットで広がった形」（動画 V1wA3Z7xrq0）：曲ページが無い（曲ページが無い）
- 栗コーダーカルテット「ピタゴラスイッチ オープニングテーマ」（動画 rXApmnPt73w） → kuricorder-quartet/pitagora-switch-op：関連が2曲（4曲以上必要） ／ メモに事実があるのに出典なし
- レキシ「狩りから稲作へ feat. 足軽先生・東インド貿易会社マン」（動画 RN3lMzxsVyc） → rekishi/kari-kara-inasaku-e：関連が2曲（4曲以上必要） ／ コピーなし／メモが短い（22字）
- ザ・フォーク・クルセダーズ「帰って来たヨッパライ」（動画 HgW5KUyJarw）：曲ページが無い（曲ページが無い）
- ボンゾ・ドッグ・ドゥー・ダー・バンド「I'm the Urban Spaceman」（動画 olGXtohOs7c）：曲ページが無い（曲ページが無い）
- 笠置シヅ子「買物ブギー」（動画 Q_tHACJ12kw）：曲ページが無い（曲ページが無い）
- たま「さよなら人類」（動画 1LLsV-myhmQ）：曲ページが無い（曲ページが無い）
- たま「さよなら人類」（動画 iKArF95Z7u0）：曲ページが無い（曲ページが無い）
- ユニコーン「ヒゲとボイン」（動画 Q7ITtfUQ8eU） → unicorn/hige-to-boin：関連が3曲（4曲以上必要） ／ コピーなし／メモが短い（17字）
- POLYSICS「ヒゲとボイン」（動画 oVYfGgN5hLI）：曲ページが無い（曲ページが無い）
- ケロポンズ「エビカニクス」（動画 U9nmGLZUGR4）：曲ページが無い（曲ページが無い）
- ケロポンズ「Ebikanics（英語版）」（動画 GcMZRZqqKMY）：曲ページが無い（曲ページが無い）
- 弘田三枝子「ワンサカ娘'64」（動画 LcWhwiVpeXo）：曲ページが無い（曲ページが無い）
- シルヴィ・バルタン「ワンサカ娘」（動画 E6onW36sOv8）：曲ページが無い（曲ページが無い）
- ハク。（カバー）「かむかもしかもにどもかも！」（動画 J76S5q_ETfo）：曲ページが無い（同じ動画が2曲に入っている：haku/kamu-kamo-shikamo、haku/adana）
- MONO NO AWARE「かむかもしかもにどもかも！」（動画 w9CvXg4jpZU）：曲ページが無い（名前が合う候補（動画は別）：haku/kamu-kamo-shikamo）
- "Weird Al" Yankovic「White & Nerdy」（動画 N9qYF9DZPdw） → weird-al-yankovic/weird-al-yankovic-white-and-nerdy：関連が0曲（4曲以上必要） ／ コピーなし／メモなし
- チャミリオネア feat. クレイジー・ボーン「Ridin'」（動画 CtwJvgPJ9xw）：曲ページが無い（曲ページが無い）
- 亀有ブラザーズ「ビートたけし、ガダルカナル・タカ、つまみ枝豆、グレート義太夫」（動画 5BRTGcA6OGQ）：曲ページが無い（曲ページが無い）
- 亀有ブラザーズ「メドレー」（動画 IYzQYjCg1vY）：曲ページが無い（曲ページが無い）
- 空耳アワー「ナゲット割って父ちゃん」（動画 _OOJDtlBxTQ） → soramimi-award/nugget-watte-touchan：コピーなし／メモに事実があるのに出典なし
- そら耳アワード2016「優勝作品」（動画 F7sQQJxpai0）：曲ページが無い（曲ページが無い）
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only uke-01.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

## 122781 マガジンの曲ページ hikigatari-josh-turner（5曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/hikigatari-josh-turner.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:28:56）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】5曲
- はっぴいえんど「風をあつめて」（動画 kTPw8tJLdtw） → はっひ-いえんと/風をあつめて：コピーなし
- Josh Turner「風をあつめて (Gather the wind) - Happy End Cover」（動画 QeWtMZYjnCE） → josh-turner-guitar/風をあつめて：コピーなし
- Priscilla Ahn「Kaze Wo Atsumete」（動画 SWBVVgLBWvA） → priscilla-ahn/kaze-wo-atsumete：コピーなし／メモに事実があるのに出典なし
- rei harakami「owari no kisetsu」（動画 wC1z9sNSaXo） → rei-harakami/owari-no-kisetsu：コピーなし／メモが短い（19字） ／ 動画が再生できない（隠す表）
- Tahiti 80「風をあつめて」（動画 lp6rkCyAaFc） → tahiti-80/風をあつめて：コピーなし／メモに事実があるのに出典なし
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only hikigatari-josh-turner.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

## 122782 マガジンの曲ページ hito-ga-odoru-01（16曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/hito-ga-odoru-01.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:28:56）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】16曲
- フルリアン・ヒムン(復元演奏)「The Oldest Known Melody (Hurrian Hymn no.6)」（動画 QpxN2VXPMLc）：曲ページが無い（曲ページが無い）
- 徳島・阿波おどり「鳴物と掛け声」（動画 0iGEZkBqRJY）：曲ページが無い（曲ページが無い）
- フラ・カヒコ「メリー・モナーク・フェスティバル 2015年優勝(ウアヒネ部門)」（動画 mPW5LA3zy2Y）：曲ページが無い（曲ページが無い）
- ヨハン・シュトラウス2世「美しき青きドナウ」（動画 sgfs5xajw9A）：曲ページが無い（曲ページが無い）
- チャビー・チェッカー「The Twist」（動画 0f-elp3NkbY）：曲ページが無い（曲ページが無い）
- ジェームス・ブラウン「Sex Machine」（動画 WZdbMlDsZz8）：リンク先のアーティスト「James Brown」がマガジンの表記「ジェームス・ブラウン」と違う
- ジェームス・ブラウン「Cold Sweat」（動画 zx_oxYdzQNA）：曲ページが無い（曲ページが無い）
- ドナ・サマー「I Feel Love」（動画 gHF-w8yGrHI） → donne-summer/i-feel-love：コピーなし
- Disco Demolition Night「コミスキー・パークの記録」（動画 NWCRu-yVEFU）：曲ページが無い（曲ページが無い）
- ブラック・ボックス「Ride on Time」（動画 M0quXl_od3g） → black-box/ride-on-time：コピーなし／メモに事実があるのに出典なし
- ブラック・ボックス「Ride on Time」（動画 cJ_2lm5SDXA）：曲ページが無い（名前が合う候補（動画は別）：black-box/ride-on-time）
- テクノトロニック「Move That Body」（動画 IK_6AZOAsbA） → technotronic/move-that-body：コピーなし／メモが短い（29字）
- キャンディ・ダルファー「Pick Up The Pieces」（動画 rhF5jG8BvgM） → candy-dulfer/pick-up-the-pieces：コピーなし／メモが短い（25字）
- アヴェレッジ・ホワイト・バンド「Pick Up The Pieces」（動画 7Rvk0NPupIU）：曲ページが無い（曲ページが無い）
- メシェル・ンデゲオチェロ「Boyfriend」（動画 JjmYnC3sq3A）：リンク先のアーティスト「Meshell Ndegeocello」がマガジンの表記「メシェル・ンデゲオチェロ」と違う
- メシェル・ンデゲオチェロ「If That's Your Boyfriend (He Wasn't Last Night)」（動画 MsG_VCt5ty4）：曲ページが無い（曲ページが無い）
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only hito-ga-odoru-01.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

## 122783 マガジンの曲ページ hito-wa-naze-tsuki-wo-miru-01（25曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/hito-wa-naze-tsuki-wo-miru-01.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:28:56）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】25曲
- ジェネシス「Dancing with the Moonlit Knight」（動画 4oPA8JUttCw）：曲ページが無い（曲ページが無い）
- 布袋寅泰「DANCING WITH THE MOONLIGHT」（動画 1nqPCbYVGLw） → hotei-tomoyasu/dancing-with-the-moonlight：コピーなし
- ザ・ビートルズ「Mr. Moonlight」（動画 FZQ8nWZJrhA）：曲ページが無い（曲ページが無い）
- ドクター・フィールグッド&ジ・インターンズ「Mister Moonlight」（動画 ZGVCQTRBCiY）：曲ページが無い（曲ページが無い）
- 秋川雅史「荒城の月」（動画 SqyJR7iV3b4）：曲ページが無い（曲ページが無い）
- 十五夜お月さん「日本の歌・唱歌（歌詞付き）」（動画 zKajTGuV9Io）：曲ページが無い（曲ページが無い）
- 月の沙漠「作詞:加藤まさを／作曲:佐々木すぐる」（動画 275DUeC_UMA）：曲ページが無い（曲ページが無い）
- メナヘム・プレスラー（ピアノ）「ドビュッシー「月の光」（ベルガマスク組曲 第3曲）」（動画 -Bxpm0EmOMU）：曲ページが無い（曲ページが無い）
- Rousseau「Debussy - Clair de Lune（演奏可視化）」（動画 WNcsUNKlAKw）：曲ページが無い（曲ページが無い）
- ヴァレンティナ・リシッツァ「ベートーヴェン「月光」ソナタ 第3楽章 プレスト・アジタート」（動画 zucBfXpCA6s）：曲ページが無い（曲ページが無い）
- Rousseau「Beethoven - Moonlight Sonata (3rd Movement)」（動画 BV7RkEL6oRc）：曲ページが無い（曲ページが無い）
- オードリー・ヘプバーン（映画クリップ）「Moon River」（動画 uirBWk-qd9A）：曲ページが無い（曲ページが無い）
- Audrey Hepburn「Moon River」（動画 4zVF_6HW5d0）：曲ページが無い（曲ページが無い）
- エラ・フィッツジェラルド「How High the Moon」（動画 XAwYLQLs3Do） → ella-fitzgerald/how-high-the-moon-epic-scat-live-1966-rity-archi：コピーなし／メモなし
- レス・ポール&メリー・フォード「How High the Moon」（動画 NkGf1GHAxhE）：曲ページが無い（曲ページが無い）
- チェット・ベイカー「Old Devil Moon」（動画 2W7_6rAWd54）：曲ページが無い（曲ページが無い）
- フランク・シナトラ「Old Devil Moon」（動画 -THrCLg0uQU）：曲ページが無い（曲ページが無い）
- フランク・シナトラ「Fly Me to the Moon」（動画 JYuyWrkwpok） → sinatra/fly-me-to-the-moon：コピーなし／メモが短い（9字）
- マイケル・ジャクソン「Billie Jean」（動画 ZXmjhRkPVFc） → mj/billie-jean：メモが短い（20字）
- Michael Jackson「Billie Jean」（動画 CauNjt2j-BM）：曲ページが無い（名前が合う候補（動画は別）：mj/billie-jean）
- LUNA SEA「ROSIER」（動画 DRLkiX-NZzE） → luna-sea/rosier-mv：コピーなし／メモなし
- LUNA SEA「I for You」（動画 MehNUIRekX4） → luna-sea/i-for-you：コピーなし／メモが短い（29字）
- 絢香「三日月」（動画 wHw6W4BznTM） → ayaka/mikazuki：コピーなし
- 玉置浩二 & 絢香「三日月」（動画 u48TUnM9dVE）：曲ページが無い（曲ページが無い）
- 玉置浩二「サザイさん」（動画 00ENc-0Yo4w）：曲ページが無い（曲ページが無い）
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only hito-wa-naze-tsuki-wo-miru-01.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

## 122784 マガジンの曲ページ ikareru-01（3曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/ikareru-01.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:28:56）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】3曲
- Sex Pistols「God Save The Queen」（動画 g-38GX2YQig） → sex-pistols/god-save-the-queen：コピーなし
- 古舘伊知郎チャンネル「忌野清志郎さんの忘れられない話」（動画 uk8PA5A1yk4）：曲ページが無い（曲ページが無い）
- Ado「うっせぇわ」（動画 Qp3b-RXtz4w） → ado/usseewa：コピーなし
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only ikareru-01.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

## 122785 マガジンの曲ページ kimi-wa-hoshi-katsu（14曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/kimi-wa-hoshi-katsu.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:28:56）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】14曲
- モップス「雷舞（LIVE !）大阪・中之島中央公会堂」（動画 o8PEXUTnagw）：曲ページが無い（曲ページが無い）
- 井上陽水「心もよう」（動画 mqlqEb22EUA） → inoue-yousui/心もよう-ライフ-nhkホール-2014-5-22：コピーなし／メモなし
- 井上陽水「氷の世界」（動画 PGkM8FDFsJI） → inoue-yousui/is-the-ice-cream-cold：コピーなし
- 森恵「氷の世界」（動画 qIKvTmMrtl8） → mori-megumi/koori-no-sekai：コピーなし／メモに事実があるのに出典なし
- 忌野清志郎 / RCサクセション「スローバラード」（動画 e6oHTWcA4YA）：リンク先のアーティスト「忌野清志郎 / RCサクセション / ザ・タイマーズ」がマガジンの表記「忌野清志郎 / RCサクセション」と違う
- 来生たかお「夢の途中」（動画 KgVkLLwUP18） → rufus-gumede/yumeno-tochu：コピーなし／メモに事実があるのに出典なし ／ 動画が再生できない（隠す表）
- 来生たかお「夢の途中」（動画 ueF5Lc0oVKQ） → rufus-gumede/yumeno-tochu：コピーなし／メモに事実があるのに出典なし ／ 動画が再生できない（隠す表）
- 来生たかお「セカンド・ラブ」（動画 hEyxari6i-g） → kisugi-takao/second-love：コピーなし／メモなし
- 中森明菜「セカンド・ラブ」（動画 i5U93W19Ays） → akina/second-love：コピーなし
- 安全地帯「ワインレッドの心」（動画 N7w2qGktIFU） → tamaki-koji/wine-red-no-kokoro：コピーなし／メモが短い（25字）
- 上田正樹「悲しい色やね -OSAKA BAY BLUES-」（動画 VKQQruBxWMM） → masaki-ueda/kanashee-iro-yane：動画が再生できない（隠す表）
- 浜田省吾「悲しみは雪のように」（動画 tGzS70EnrEE） → hamada/kanashimi-wa-yuki-no-youni：コピーなし／メモに事実があるのに出典なし
- 坂崎幸之助（テレビ番組）「坂崎幸之助が星勝さんを紹介！井上陽水や小椋佳とも深いつながりが！」（動画 yK1HlQD34mU）：曲ページが無い（曲ページが無い）
- 井上陽水「リバーサイド ホテル」（動画 mOQE4GN7Pl8） → inoue-yousui/リハ-ーサイト-ホテル-1992-sparkling-blue-日本武道館：コピーなし
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only kimi-wa-hoshi-katsu.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

## 122786 マガジンの曲ページ naze-ongaku-01-takoukan（6曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/naze-ongaku-01-takoukan.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:28:56）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】6曲
- Bill Withers「Lovely Day」（動画 bEeaS6fuUoA） → bill-withers/lovely-day：コピーなし
- SUGAR BABE「DOWN TOWN」（動画 n0MHGGN6CFE） → sugar-babe/down-town：コピーなし ／ 動画が再生できない（隠す表）
- Maroon 5「Sugar」（動画 09R8_2nJtjg） → maroon-5/sugar：コピーなし／メモなし
- Stevie Wonder「Sir Duke」（動画 ETFvmkIA6S4） → stevie-wonder/sir-duke：コピーなし／メモが短い（23字）
- Bruno Mars「24K Magic」（動画 UqyT8IEBkvY） → bruno-mars/24k-magic：コピーなし
- Pharrell Williams「Happy」（動画 ZbZSe6N_BXs） → pharrell-williams/happy：コピーなし
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only naze-ongaku-01-takoukan.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

## 122787 マガジンの曲ページ rei-harakami（7曲）
【タスク】マガジン https://joy-relief-station.lovable.app/magazine/rei-harakami.html に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 2026-10-18 17:28:56）
【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。
【落ちた曲】7曲
- rei harakami「more elbow」（動画 x1kkPf2oBHI） → rei-harakami/more-elbow：コピーなし／メモなし
- rei harakami「cape」（動画 WH0y2GRiHjI） → rei-harakami/cape：メモが短い（28字）
- UA「閃光」（動画 eMRTkimQJWM） → u-a/senko：コピーなし／メモなし
- くるり「ばらの花」（動画 baNgL0jFkAs） → quruli/は-らの花：コピーなし／メモなし
- rei harakami「come here go there」（動画 CcSOgj-R38g） → rei-harakami/come-here-go-there：コピーなし／メモなし
- rei harakami「owari no kisetsu」（動画 wC1z9sNSaXo） → rei-harakami/owari-no-kisetsu：コピーなし／メモが短い（19字） ／ 動画が再生できない（隠す表）
- yanokami「気球にのって」（動画 Sa4pLN2oPwI）：曲ページが無い（名前が合う候補（動画は別）：yanokami/kikyu-ni-notte）
【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。
　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。
　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。
　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。
【点検】python3 tools/magazine/magazine_gate.py --only rei-harakami.html で、この号の落ちた曲が0になること。
【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。
【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。

最後の発言はPRのURLのみ。
