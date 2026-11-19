# ごきげん補給所 — まだ解決してないこと（2026-07-14）

未完了サマリー: 言われたこと 19件 / TODO 27件 / 間違いリスト 128件


## 🗣 言われたこと（未完了 19件）

`saidBacklog.ts`（AI管理の台帳）に残っているオーナー指示。

- **[doing]** 2026-07-05  
  越境同ポジ第一便を仕入れる。日本・アメリカ偏重を解いて、中国・タイ・インドネシア・フィリピン・インド・北欧など世界中の同ポジ才能を並べる。ChatGPTが挙げた15組を優先
  
  ノート: 今回仕入れ：王OK／Phum Viphurit／NIKI／SB19／BUS／LYKN／SANAM／The Rose／Slot Machine／NOAH／JANNABI／Sheila On 7／陳綺貞／AURORA／Laufey（15組・全oEmbed検証済）。導線は「このアーティストが好きなら」に統合、ラベル『越境同ポジ』はUIに出さない。次便：ノルウェー以外の欧州・南米・アフリカ・中東

- **[doing]** 2026-07-05  
  越境同ポジをどんどん続ける。世界中にいっぱいいるはず。ノルウェーがようやくあるくらいで、アジアに固まってる。欧州・南米・アフリカ・中東を厚くして
  
  ノート: 第二〜九便で計47組追加。第九便：Ewa Farna🇵🇱🇨🇿／Iva Bittová🇨🇿／Katie Melua🇬🇪🇬🇧／Nino Katamadze🇬🇪／Fela Kuti🇳🇬／Youssou N'Dour🇸🇳。次便：南米深堀り（アルゼンチン・ペルー）・中央アジア深堀り・南太平洋

- **[todo]** 2026-07-05  
  越境同ポジで仕入れた15組は代表1曲ずつ。憲法通り各人8曲目安まで拡張したい

- **[todo]** 2026-07-05  
  各アーティストページに、自分だけ見える小さな評価ボタンを付ける（十分／足りない／質が低い／もっとライブ入れて 等）。ダッシュボードから飛ぶのは面倒なので、その場でワンタップ
  
  ノート: 誤爆回避のため今回は仕入れと分離。次ターンで実装

- **[doing]** 2026-07-05  
  アイドルの国際色を豊かに。タイ・ベトナム・インドネシア・フランス・ドイツなど、各国の同ポジションのアイドルグループを仕入れる
  
  ノート: 今回：フィリピンSB19／タイBUS・LYKN／インドSANAM を追加。ベトナム・フランス・ドイツはまだ

- **[doing]** 2026-07-05  
  決まったフォーマット（紹介文＋好きなら一曲カード＋別プロジェクト＋代表曲8曲目安＋年号＋カバー往復リンク）を、指示がなくても既存アーティストへ毎ターン数人ずつ反映していく
  
  ノート: 今回: レニー・クラヴィッツ／YMO／森恵／プリンス／Nate James／Galliano。次回以降も継続

- **[doing]** 2026-07-05  
  年号漏れをゼロにする。調べればすぐ出るんだから、入ってたり入ってなかったりはありえない
  
  ノート: ダッシュボードの「年号なし曲数」を毎ターン減らす運用

- **[doing]** 2026-07-04  
  アシッドジャズの棚を作れるくらい仕入れる（Jamiroquai・Incognito・Brand New Heavies だけでは足りない）
  
  ノート: Nate James / Galliano を仕入れ済み。棚の立ち上げはまだ

- **[todo]** 2026-06-28  
  結婚式／お祝いの棚（新規）の立ち上げ

- **[todo]** 2026-06-27  
  ダッシュボードに「+N曲仕入れる」ボタンを付ける

- **[doing]** 2026-06-27  
  動画IDゼロのアーティストの一括補填（残り約248組）
  
  ノート: 毎ターン少しずつ。今回: 乾杯／The Light／Ai No Corrida／French Disko／Luv(sic) Part 3 の5曲補填

- **[todo]** 2026-06-26  
  棚の50件キャップ／「もっと見る」UI。女性ボーカル棚97件は多すぎてカードが見切れる

- **[todo]** 2026-07-04  
  ダッシュボードの「ジャンル別未分類」を埋める（ジャンル×時代のマトリックス）

- **[todo]** 2026-06-25  
  サムネと詳細ページのコピー文を統一する

- **[todo]** 2026-06-25  
  IntersectionObserver で起きる白画面の修正

- **[todo]** 2026-06-25  
  「固定／準候補／除外」バッジUIを目視できるようにする

- **[todo]** 2026-06-24  
  Killing Me Softly 系（Fugees ↔ Roberta Flack ↔ 他カバー）のハブ&スポーク再点検

- **[todo]** 2026-06-24  
  Somebody to Love: Jefferson Airplane と Queen の取り違えがないか全件確認

- **[todo]** 2026-06-28  
  レキシ「きらきら武士」・クラムボン3曲・Brand New Heavies／Arrested Development／Jacob Collier／NAO YOSHIOKA／Tokimeki Records／mime 各1曲の動画ID再挑戦


## 📝 TODO（未完了 27件）

ダッシュボードの TODO タブ。DB `admin_todos` の `status IN (todo, doing, in_progress, reopened)`。

- **[status]** (priority_tag·source) to_char  
  title
  
  詳細: coalesce

- **[todo]** (whenever·ai) 2026-06-28  
  サムネ穴カードのリンク差し替え待ち
  
  詳細: 2026-06-28にサムネ404のため24件を棚から一時下げ。レポート: /mnt/documents/removed-broken-shelf-items-20260628-204245.md。公式/本人/Topic等で確認できる動画に差し替えてから棚へ戻す。

- **[todo]** (whenever·ai) 2026-06-28  
  棚に置く前のYouTube検証を継続
  
  詳細: 棚追加・URL取込・bulk/upload ingest で、YouTubeサムネイルとoEmbed確認を通す。サムネが取れない動画は公開棚に置かない。

- **[todo]** (whenever·ai) 2026-06-27  
  ジャンル別 未分類 7050曲 の手動見直し
  
  詳細: /admin/inventory のジャンル「未分類」を減らす。auto-tag-artists スクリプトで自動推定する案あり（次回実装候補）。

- **[todo]** (whenever·ai) 2026-06-27  
  間違い印システム（admin_card_flags テーブル）
  
  詳細: 巡回中ボタン + 自動検出（重複/コピー短い/ヘッダー乖離） + ダッシュボード「間違いリスト」タブ。ターン2のCで実装予定。

- **[todo]** (whenever·ai) 2026-06-27  
  ダッシュボード「棚タブ」（棚ごとカード縦並び＋一括操作）
  
  詳細: 同一アーティスト連続検出、一括除外ボタン。ターン2のBで実装予定。

- **[todo]** (whenever·ai) 2026-06-27  
  同一アーティスト連続検出（同棚内）
  
  詳細: マライア・キャリーが5連発などの状態を黄色ハイライト → ターン2のBで実装予定。

- **[todo]** (whenever·ai) 2026-06-27  
  未分類自動分類スクリプト auto-tag-artists.ts
  
  詳細: 棚名・既存ARTIST_TAGS・曲名から推定して inventory.functions.ts に追記。残った真の未分類だけ手動。

- **[in_progress]** (whenever·ai) 2026-06-27  
  アーティストTOPで同じ曲が2,3回入っている重複の整理
  
  詳細: youtubeId / songId 重複を間違い印で検出 → 削除（ターン2のC）。

- **[todo]** (whenever·user) 2026-06-27  
  【最優先】サムネはあるのに開くと白紙のカード一掃
  
  詳細: ネットの古典棚「心の底から笑いたい人への、ネットの古典」が代表例。to先のページ／artist/songがcoverGuide.tsに存在しない or 中身が空のカードを全棚スキャンして列挙する。

- **[in_progress]** (whenever·ai) 2026-06-27  
  /room/ のままの音楽系カードを /cover-guide?artist=&song= へ正規化
  
  詳細: 食べ物/かわいい/赤ちゃん系以外で /room/ のまま残ってる音楽カードを移行。

- **[todo]** (whenever·ai) 2026-06-27  
  棚カードのコピー文 < 20文字 を直す
  
  詳細: 「十代の咆哮」「駆け抜ける青春」みたいな短すぎコピーを検出して2〜3行に書き直す。

- **[in_progress]** (whenever·user) 2026-06-27  
  棚ジャンルに合わない推薦見出し文言の修正
  
  詳細: 笑い棚なのに「○○と同じ時代の曲」「○○の他の曲・静かな曲」と出る。world=laugh/cute/foodのときは見出しと文言を切り替える（例:「同じ時代のもの」「他のネタ・別の角度」）。

- **[todo]** (whenever·user) 2026-06-27  
  詳細ページの並び順統一未適用ページの一掃
  
  詳細: 規定順:VideoCard→タグ→つづけてこれはいかが→部屋に戻る→寄り道(next)→記憶の扉→FRIEND TEST。記憶の扉とFRIEND TESTの間に「次の寄り道」が入っていないページを全部直す。

- **[in_progress]** (whenever·ai) 2026-06-27  
  YouTube ID 欠落（グレーの…アイコン）カードの一掃
  
  詳細: 世界観破壊。サムネが出ないカードを検出→補完 or 撤去。

- **[todo]** (whenever·ai) 2026-06-27  
  共有URLが曲直リンクになっていないカードの修正
  
  詳細: getCanonicalCardTo を全カードで確認。

- **[todo]** (whenever·ai) 2026-06-27  
  カバー曲の同 songId 揃え（ハブ＆スポーク不成立検出）
  
  詳細: 同じ曲なのに アーティスト間で songId が違うものを検出→統一。

- **[todo]** (whenever·ai) 2026-06-27  
  アーティストTOPページ未作成アーティストの検出
  
  詳細: 棚にカードはあるが coverGuide.ts に artist がない／曲だけで TOP がないものを洗い出す。

- **[todo]** (whenever·ai) 2026-06-27  
  全棚に対して同アーティスト連続検出を一括実行
  
  詳細: 棚タブの「一括除外」を全棚に対して走らせるバッチ。

- **[todo]** (whenever·ai) 2026-06-27  
  画像なしアーティストにローポリ「ARTIST」タイル
  
  詳細: 空タイル禁止のルール徹底。

- **[todo]** (whenever·ai) 2026-06-27  
  検索ページのマイク絵文字プレースホルダーを削除
  
  詳細: 世界観に合わない。代わりのコピーへ。

- **[open]** (now·user-feedback) 2026-07-09  
  コラボボタン新設（feat./with/×自動配布）
  
  詳細: feat./ft./with/&/× を含む曲を「👥コラボ相手にも貼る」ボタン一撃で相手アーティストの collaborators に自動追加。未登録アーティストはスケルトン＋admin_todos。棚編集パネルに設置。

- **[open]** (now·user-feedback) 2026-07-09  
  年号ボタン即時実効化
  
  詳細: 「年号が入ってない」ボタン押下でAIが即座に年号を推定→ admin_card_flags に保存→ カード表示で優先。今の「情報不十分でした」で終わるのは意味なし。

- **[open]** (anytime·user-feedback) 2026-07-09  
  ヘッダー三点メニューで修正ボタン集約
  
  詳細: カードヘッダー周りに三点メニュー。押すと「タイトル直して/コピー直して/年号入れて/違う」等の修正コマンドが一覧で出る。個別ボタン散らかしを整理。

- **[open]** (little-by-little·user-feedback) 2026-07-09  
  こちらもいかがでしょう 5枚→10枚（全カード）
  
  詳細: scripts/build-recommendations.ts の枠を10枚に。次回まとめ仕入れターンで一括再生成でOK。急がないがずっと放置しない。

- **[open]** (now·user-feedback) 2026-07-09  
  Christmas in Hollis ページの機能しないボタン修正
  
  詳細: Run-D.M.C. / Christmas in Hollis 曲ページに「押しても機能しないボタン」あり（ユーザー指摘）。どのボタンか特定して修正。ボタンあるのに動かないのは絶対NG。

- **[todo]** (slowly·user) 2026-07-09  
  こちらもいかがでしょう」5枚 → 10枚（全カード）


## ⚠️ 間違いリスト（未対応 128件）

ダッシュボードの間違いタブ。DB `admin_card_flags` の `status='open'`。

- **kind** / card=card_id / shelf=coalesce / (source·to_char)
  
  メモ: coalesce

- **needs_normalize** / card=m-singin / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/singin-in-the-rain, music/rainy)

- **needs_normalize** / card=m-rain-song / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/rain-song, music/rainy)

- **needs_normalize** / card=m-purple-rain / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/purple-rain, music/rainy)

- **needs_normalize** / card=m-creedence-rain / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/creedence-rain, music/rainy)

- **needs_normalize** / card=m-norah-jones / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/norah-jones, music/rainy)

- **needs_normalize** / card=m-ame-no-machi / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/ame-no-machi, music/rainy)

- **needs_normalize** / card=m-takanaka / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/takanaka, music/reimport)

- **needs_normalize** / card=m-misia-higher-love / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/misia-higher-love, music/reimport)

- **needs_normalize** / card=m-natsu-no-owari / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/natsu-no-owari, music/summer-end)

- **needs_normalize** / card=m-shounen-jidai / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/shounen-jidai, music/summer-end)

- **needs_normalize** / card=m-nixsa / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/nixsa-uthaipia, music/paradise)

- **needs_normalize** / card=m-benson-breezin / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/benson-breezin, music/paradise)

- **needs_normalize** / card=m-benson-affirmation / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/benson-affirmation, music/paradise)

- **needs_normalize** / card=m-gandhara / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/gandhara, music/paradise)

- **needs_normalize** / card=m-led-zeppelin-dazed / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/led-zeppelin-dazed, music/night)

- **needs_normalize** / card=m-lovely-day / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/lovely-day, music/wake)

- **needs_normalize** / card=m-everybody-loves-the-sunshine / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/everybody-loves-the-sunshine, music/wake)

- **needs_normalize** / card=m-taiyou-ua / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/taiyou-ua, music/wake)

- **needs_normalize** / card=m-you-are-the-sunshine / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/you-are-the-sunshine, music/wake)

- **needs_normalize** / card=x-singin-rain-movie / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/singin-in-the-rain, music/movies)

- **needs_normalize** / card=x-nixsa-uthaipia-asia / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/nixsa-uthaipia, music/asia)

- **needs_normalize** / card=m-imagine / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/imagine, music/farewell)

- **needs_normalize** / card=m-tears-farewell / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/tears-in-heaven, music/farewell)

- **needs_normalize** / card=l-sisonne / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/konto/sisonne, laugh/konto)

- **needs_normalize** / card=l-sandwich / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/konto/sandwichman, laugh/konto)

- **needs_normalize** / card=l-doburock / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/konto/doburock, laugh/konto)

- **needs_normalize** / card=l-robert / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/konto/robert, laugh/konto)

- **needs_normalize** / card=l-kiffness-alugalug / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/music/kiffness-alugalug, laugh/kaigai)

- **needs_normalize** / card=l-doburock-cd / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/konto/doburock, laugh/commute-danger)

- **needs_normalize** / card=l-doburock-naughty / (auto·2026-06-28)
  
  メモ: [overnight-scan] /cover-guide?... へ正規化 (to=/room/konto/doburock, laugh/naughty)

- **short_copy** / card=x-yamashita-sayonara-natsu / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 19文字: "夏の終わりに聴くと、胸のどこかが痛い。"

- **short_copy** / card=x-childish-summer / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 19文字: "夏の終わりの午後三時。この動画がそれ。"

- **short_copy** / card=d-brushy / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 14文字: "弦一本で、世界を踊らせる男。"

- **short_copy** / card=x-yuming-yasashisa-live / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "目にうつる全てのことは、メッセージ。"

- **short_copy** / card=x-aiko-kabutomushi / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "夏の夜の温度が、イントロだけで蘇る。"

- **short_copy** / card=cm-coke-1987-80s / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 11文字: "80年代の夏、丸ごと。"

- **short_copy** / card=cm-xmas-express-80s / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 13文字: "1988年からの伝説CM。"

- **short_copy** / card=cm-caramel-corn-80s / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "袋より先に、子どもの頃の空気が開く。"

- **short_copy** / card=x-faye-wong-dreamlover / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 16文字: "恋なのか、夢なのか、映画なのか。"

- **short_copy** / card=x-brushy-s / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 14文字: "弦一本で、世界を踊らせる男。"

- **short_copy** / card=x-maroon5-sunday-chill / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 15文字: "コーヒーと白いシーツの朝の音。"

- **short_copy** / card=x-ymo-rydeen / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "未来から先に届いた、78年の馬蹄音。"

- **short_copy** / card=x-fuji-keiko-yume / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "18歳の声が、もう全部を知っていた。"

- **short_copy** / card=x-chuck-berry-johnny / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 16文字: "ロックンロールの設計図そのもの。"

- **short_copy** / card=ne-pfc-redemption / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 19文字: "祈りの歌を、地球上の声でつないでいく。"

- **short_copy** / card=f-french-yatai / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "湯気の向こうに、ちゃんと人生がある。"

- **short_copy** / card=f-china-tabearuki / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 16文字: "鼻だけ先に旅してしまう危険地帯。"

- **short_copy** / card=f-turkish-ice-tease / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 14文字: "甘さの前に、軽く人生を学ぶ。"

- **short_copy** / card=f-icecream-baby / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 19文字: "冷たさと幸福が、頭の中で小さくケンカ。"

- **short_copy** / card=f-first-takoyaki / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 14文字: "タイ人が、たこ焼きと初対面。"

- **short_copy** / card=f-baby-lemon / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "顔だけで世界一わかりやすいレビュー。"

- **short_copy** / card=x-kids-taekwondo-dojo / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 17文字: "割れないのに全力。ギャップが正義。"

- **short_copy** / card=l-jinnai / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "一人コントの達人。代表3本まとめて。"

- **short_copy** / card=f-hot-pot-reaction / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 18文字: "熱いって言う前に、顔が温度計になる。"

- **short_copy** / card=x-jack-black-sax-l / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 17文字: "楽器の概念が、今日から変わります。"

- **short_copy** / card=x-wow / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 16文字: "「wow」以外の言葉、いらない。"

- **short_copy** / card=x-monty-python-kaigai / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 19文字: "歩くだけで、国家予算を無駄にする芸術。"

- **short_copy** / card=l-momoume / (auto·2026-06-28)
  
  メモ: [overnight-scan] whisper 8文字: "SNSや職場の\"

- **consecutive_artist** / card=ne-pfc-redemption / (auto·2026-06-28)
  
  メモ: [overnight-scan] 棚 music/net-ensemble で playing for change が 3 連続

- **empty_youtube_id** / card=tatsuro/sparkle / (auto·2026-06-28)
  
  メモ: [overnight-scan] 山下達郎 - SPARKLE (youtubeId 空)

- **empty_youtube_id** / card=tatsuro/kouki-atsu-girl / (auto·2026-06-28)
  
  メモ: [overnight-scan] 山下達郎 - 高気圧ガール (youtubeId 空)

- **empty_youtube_id** / card=tatsuro/magic-ways / (auto·2026-06-28)
  
  メモ: [overnight-scan] 山下達郎 - MAGIC WAYS (youtubeId 空)

- **empty_youtube_id** / card=zard/makenaide / (auto·2026-06-28)
  
  メモ: [overnight-scan] ZARD - 負けないで (youtubeId 空)

- **empty_youtube_id** / card=zard/yureru-omoi / (auto·2026-06-28)
  
  メモ: [overnight-scan] ZARD - 揺れる想い (youtubeId 空)

- **empty_youtube_id** / card=utada/first-love / (auto·2026-06-28)
  
  メモ: [overnight-scan] 宇多田ヒカル - First Love (youtubeId 空)

- **empty_youtube_id** / card=utada/automatic / (auto·2026-06-28)
  
  メモ: [overnight-scan] 宇多田ヒカル - Automatic (youtubeId 空)

- **empty_youtube_id** / card=utada/hikari / (auto·2026-06-28)
  
  メモ: [overnight-scan] 宇多田ヒカル - 光 (youtubeId 空)

- **empty_youtube_id** / card=utada/flavor-of-life / (auto·2026-06-28)
  
  メモ: [overnight-scan] 宇多田ヒカル - Flavor Of Life (youtubeId 空)

- **empty_youtube_id** / card=iwasaki-yoshimi/akogare / (auto·2026-06-28)
  
  メモ: [overnight-scan] 岩崎良美 - あなた色のマノン (youtubeId 空)

- **empty_youtube_id** / card=iwasaki-yoshimi/chelsea-girls / (auto·2026-06-28)
  
  メモ: [overnight-scan] 岩崎良美 - チェルシー・ガールズ (youtubeId 空)

- **empty_youtube_id** / card=ikimono/arigatou / (auto·2026-06-28)
  
  メモ: [overnight-scan] いきものがかり - ありがとう (youtubeId 空)

- **empty_youtube_id** / card=ikimono/yell / (auto·2026-06-28)
  
  メモ: [overnight-scan] いきものがかり - YELL (youtubeId 空)

- **empty_youtube_id** / card=ikimono/sakura-ikimono / (auto·2026-06-28)
  
  メモ: [overnight-scan] いきものがかり - SAKURA (youtubeId 空)

- **empty_youtube_id** / card=yoasobi/yoru-ni-kakeru / (auto·2026-06-28)
  
  メモ: [overnight-scan] YOASOBI - 夜に駆ける (youtubeId 空)

- **empty_youtube_id** / card=yoasobi/idol / (auto·2026-06-28)
  
  メモ: [overnight-scan] YOASOBI - アイドル (youtubeId 空)

- **empty_youtube_id** / card=mrs-green-apple/soranji / (auto·2026-06-28)
  
  メモ: [overnight-scan] Mrs. GREEN APPLE - ソラニン (youtubeId 空)

- **empty_youtube_id** / card=mrs-green-apple/mrs-green-apple-soranji / (auto·2026-06-28)
  
  メモ: [overnight-scan] Mrs. GREEN APPLE - Soranji (youtubeId 空)

- **empty_youtube_id** / card=back-number/kareha / (auto·2026-06-28)
  
  メモ: [overnight-scan] back number - クリスマスソング (youtubeId 空)

- **empty_youtube_id** / card=back-number/happy-end / (auto·2026-06-28)
  
  メモ: [overnight-scan] back number - ハッピーエンド (youtubeId 空)

- **empty_youtube_id** / card=blue-hearts/linda-linda / (auto·2026-06-28)
  
  メモ: [overnight-scan] THE BLUE HEARTS - リンダ リンダ (youtubeId 空)

- **empty_youtube_id** / card=blue-hearts/blue-hearts-theme / (auto·2026-06-28)
  
  メモ: [overnight-scan] THE BLUE HEARTS - ブルーハーツのテーマ (youtubeId 空)

- **empty_youtube_id** / card=blue-hearts/people-without-names / (auto·2026-06-28)
  
  メモ: [overnight-scan] THE BLUE HEARTS - 名もなき義勇軍 (youtubeId 空)

- **empty_youtube_id** / card=mj/my-little-red-book / (auto·2026-06-28)
  
  メモ: [overnight-scan] Michael Jackson / The Jackson 5 - My Little Red Book (youtubeId 空)

- **empty_youtube_id** / card=mj/and-more-again / (auto·2026-06-28)
  
  メモ: [overnight-scan] Michael Jackson / The Jackson 5 - Andmoreagain (youtubeId 空)

- **empty_youtube_id** / card=mj/she-comes-in-colors / (auto·2026-06-28)
  
  メモ: [overnight-scan] Michael Jackson / The Jackson 5 - She Comes in Colors (youtubeId 空)

- **empty_youtube_id** / card=mj/august / (auto·2026-06-28)
  
  メモ: [overnight-scan] Michael Jackson / The Jackson 5 - August (youtubeId 空)

- **empty_youtube_id** / card=bob-marley/could-you-be-loved / (auto·2026-06-28)
  
  メモ: [overnight-scan] Bob Marley - Could You Be Loved (youtubeId 空)

- **empty_youtube_id** / card=bob-james/mardi-gras / (auto·2026-06-28)
  
  メモ: [overnight-scan] Bob James - Mardi Gras (youtubeId 空)

- **empty_youtube_id** / card=bob-james/take-me-to-the-mardi-gras / (auto·2026-06-28)
  
  メモ: [overnight-scan] Bob James - Take Me to the Mardi Gras (youtubeId 空)

- **empty_youtube_id** / card=bon-jovi/livin-on-a-prayer / (auto·2026-06-28)
  
  メモ: [overnight-scan] Bon Jovi - Livin' on a Prayer (youtubeId 空)

- **empty_youtube_id** / card=queen/bohemian-rhapsody / (auto·2026-06-28)
  
  メモ: [overnight-scan] Queen - Bohemian Rhapsody (youtubeId 空)

- **empty_youtube_id** / card=led-zeppelin/kashmir / (auto·2026-06-28)
  
  メモ: [overnight-scan] Led Zeppelin - Kashmir (youtubeId 空)

- **empty_youtube_id** / card=whitney/i-wanna-dance-with-somebody / (auto·2026-06-28)
  
  メモ: [overnight-scan] Whitney Houston - I Wanna Dance with Somebody (youtubeId 空)

- **empty_youtube_id** / card=whitney/run-to-you / (auto·2026-06-28)
  
  メモ: [overnight-scan] Whitney Houston - Run To You (youtubeId 空)

- **empty_youtube_id** / card=whitney/i-wanna-dance-with-somebody-who-loves-me / (auto·2026-06-28)
  
  メモ: [overnight-scan] Whitney Houston - I Wanna Dance With Somebody (Who Loves Me) (youtubeId 空)

- **empty_youtube_id** / card=norah/dont-know-why / (auto·2026-06-28)
  
  メモ: [overnight-scan] Norah Jones - Don't Know Why (youtubeId 空)

- **empty_youtube_id** / card=norah/don-t-know-what-it-means / (auto·2026-06-28)
  
  メモ: [overnight-scan] Norah Jones - Don't Know What It Means (youtubeId 空)

- **empty_youtube_id** / card=coldplay/fix-you / (auto·2026-06-28)
  
  メモ: [overnight-scan] Coldplay - Fix You (youtubeId 空)

- **empty_youtube_id** / card=sinatra/the-way-you-look-tonight / (auto·2026-06-28)
  
  メモ: [overnight-scan] Frank Sinatra - The Way You Look Tonight (youtubeId 空)

- **empty_youtube_id** / card=oasis/champagne-supernova / (auto·2026-06-28)
  
  メモ: [overnight-scan] Oasis - Champagne Supernova (youtubeId 空)

- **empty_youtube_id** / card=oasis/supersonic / (auto·2026-06-28)
  
  メモ: [overnight-scan] Oasis - Supersonic (youtubeId 空)

- **empty_youtube_id** / card=celine-dion/because-you-loved-me / (auto·2026-06-28)
  
  メモ: [overnight-scan] Celine Dion - Because You Loved Me (youtubeId 空)

- **empty_youtube_id** / card=billy-joel/new-york-state-of-mind / (auto·2026-06-28)
  
  メモ: [overnight-scan] Billy Joel - New York State of Mind (youtubeId 空)

- **empty_youtube_id** / card=billy-joel/vienna / (auto·2026-06-28)
  
  メモ: [overnight-scan] Billy Joel - Vienna (youtubeId 空)

- **empty_youtube_id** / card=billy-joel/movin-out / (auto·2026-06-28)
  
  メモ: [overnight-scan] Billy Joel - Movin' Out (Anthony's Song) (youtubeId 空)

- **empty_youtube_id** / card=billy-joel/big-shot / (auto·2026-06-28)
  
  メモ: [overnight-scan] Billy Joel - Big Shot (youtubeId 空)

- **empty_youtube_id** / card=billy-joel/only-the-good-die-young / (auto·2026-06-28)
  
  メモ: [overnight-scan] Billy Joel - Only the Good Die Young (youtubeId 空)

- **empty_youtube_id** / card=billy-joel/shes-always-a-woman / (auto·2026-06-28)
  
  メモ: [overnight-scan] Billy Joel - She's Always a Woman (youtubeId 空)

- **empty_youtube_id** / card=billy-joel/the-longest-time / (auto·2026-06-28)
  
  メモ: [overnight-scan] Billy Joel - The Longest Time (youtubeId 空)

- **empty_youtube_id_summary** / card=_summary / (auto·2026-06-28)
  
  メモ: [overnight-scan] 合計 1752 件の youtubeId 欠落 (上位50件のみ flag 登録)

- **song_id_mismatch** / card=tatsuro/sayonara-natsu-no-hi / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube _paXh_LgwmM に対し songId バラバラ: tatsuro/sayonara-natsu-no-hi, tatsuro-yamashita-ex/say-goodbye-to-day

- **song_id_mismatch** / card=vaundy/odoriko / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube 7HgJIAUtICU に対し songId バラバラ: vaundy/odoriko, imase/odoreru-meiwaku

- **song_id_mismatch** / card=mrs-green-apple/mrs-green-apple-ao-to-natsu / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube m34DPnRUfMU に対し songId バラバラ: mrs-green-apple/mrs-green-apple-ao-to-natsu, mrs-green-apple-ex/ao-to-natsu

- **song_id_mismatch** / card=mrs-green-apple/mrs-green-apple-dance-hall / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube x2rvSf0STBM に対し songId バラバラ: mrs-green-apple/mrs-green-apple-dance-hall, mrs-green-apple-ex/dance-hall

- **song_id_mismatch** / card=mrs-green-apple/mrs-green-apple-bokunokoto / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube xefpHEg5UIA に対し songId バラバラ: mrs-green-apple/mrs-green-apple-bokunokoto, mrs-green-apple-ex/dotabata

- **song_id_mismatch** / card=minami-kosetsu/kanda-gawa / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube JSgyHiKESGw に対し songId バラバラ: minami-kosetsu/kanda-gawa, kousetsu-minami/kandagawa

- **song_id_mismatch** / card=fuji-kaze/nan-nan / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube Nt6ZwuVzOS4 に対し songId バラバラ: fuji-kaze/nan-nan, fujii-kaze/nan-nan-w

- **song_id_mismatch** / card=commodores/all-night-long / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube nqAvFx3NxUM に対し songId バラバラ: commodores/all-night-long, lionel-richie/all-night-long-all-night

- **song_id_mismatch** / card=burnin-spear/slavery-days / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube BpAkVlESkHw に対し songId バラバラ: burnin-spear/slavery-days, burning-spear/burning-spear-slavery-days

- **song_id_mismatch** / card=tetsuji-hayashi/futari-no-summer-monologue / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube PywWtht2HZU に対し songId バラバラ: tetsuji-hayashi/futari-no-summer-monologue, kiyotaka-sugiyama/futari-no-natsu-monogatari

- **song_id_mismatch** / card=juni-ichi-inagaki/christmas-carol-no-koro-ni-wa / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube BGVBlc1LOsg に対し songId バラバラ: juni-ichi-inagaki/christmas-carol-no-koro-ni-wa, toshitaro/christmas-carols-koro

- **song_id_mismatch** / card=juni-ichi-inagaki/bachelor-girl / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube nh7NCWKHDF8 に対し songId バラバラ: juni-ichi-inagaki/bachelor-girl, toshitaro/vampire

- **song_id_mismatch** / card=eiichi-ohtaki/ohtaki-kimi-wa-tennen-shoku / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube L-hyY-1luHs に対し songId バラバラ: eiichi-ohtaki/ohtaki-kimi-wa-tennen-shoku, eiichi-otaki/kimi-wa-tennenshoku, ohtaki-eiichi/kimi-wa-tennenshoku

- **song_id_mismatch** / card=eiichi-ohtaki/ohtaki-kanariya-shoto / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube c6LV06OCPVE に対し songId バラバラ: eiichi-ohtaki/ohtaki-kanariya-shoto, eiichi-otaki/kanariya-island

- **song_id_mismatch** / card=eiichi-ohtaki/ohtaki-koisuru-karen / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube L1SuMI5LikA に対し songId バラバラ: eiichi-ohtaki/ohtaki-koisuru-karen, eiichi-otaki/koigashitai

- **song_id_mismatch** / card=eiichi-ohtaki/shiawase-na-ketsumatsu / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube 5OG5UQ4toCM に対し songId バラバラ: eiichi-ohtaki/shiawase-na-ketsumatsu, eiichi-otaki/happ-end-de-hajimete

- **song_id_mismatch** / card=tony-bennett/body-and-soul / (auto·2026-06-28)
  
  メモ: [overnight-scan] 同 YouTube _OFMkCeP6ok に対し songId バラバラ: tony-bennett/body-and-soul, tony-bennett/body-and-soul-with-amy-winehouse, tony-bennett/body-and-soul
