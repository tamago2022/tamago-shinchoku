import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src, BASE
_D = os.path.dirname(os.path.abspath(__file__))
_I18N_PATH = os.path.join(_D, 'i18n_josh.json')
I18N = json.load(open(_I18N_PATH, encoding='utf-8')) if os.path.exists(_I18N_PATH) else {'en': {}, 'zh-Hans': {}, 'es': {}, 'ko': {}}  # 5言語（訳だけ直すときはこのファイル）

# 2026-10-18 全開便：型＝「怒れる人々 vol.1」（MAGAZINE_KATA_1018）にそろえた版。5曲→11曲。
# 事実は下の出典で本文を確かめたものだけ（wiki_lookup.py・oEmbed・動画の説明文。2026-10-18 取得）。
WKZ = 'https://ja.wikipedia.org/wiki/%E9%A2%A8%E3%82%92%E3%81%82%E3%81%A4%E3%82%81%E3%81%A6_(%E3%81%AF%E3%81%A3%E3%81%B4%E3%81%84%E3%81%88%E3%82%93%E3%81%A9%E3%81%AE%E6%9B%B2)'
REM = 'https://reminder.top/669882129/'
CREA = 'https://crea.bunshun.jp/articles/-/43121'
CINE = 'https://cinemore.jp/jp/erudition/52/article_54_p3.html'
GUA = 'https://www.theguardian.com/music/2024/mar/26/translation-changes-the-original-meaning-how-70s-psych-rockers-happy-end-ended-the-japanese-rock-controversy'
JLT = 'https://joshualeeturner.com/About'
WJLT = 'https://en.wikipedia.org/wiki/Joshua_Lee_Turner'
XM = 'https://x.com/takashi_mtmt/status/1266735609843863553'
YT_KAZE = 'https://www.youtube.com/watch?v=QeWtMZYjnCE'
YT_SOS = 'https://www.youtube.com/watch?v=w5SC1uIxXhk'
YT_GRACE = 'https://www.youtube.com/watch?v=NtYKjQLgnOs'
YT_ANG = 'https://www.youtube.com/watch?v=BOn919FtA8k'
YT_CHAIN = 'https://www.youtube.com/watch?v=9Fdwb62tQkc'
YT_CRAZY = 'https://www.youtube.com/watch?v=An-PQEAxsF8'
YT_OWARI = 'https://www.youtube.com/watch?v=ZPKPNjtNOyI'
WELLE = 'https://en.wikipedia.org/wiki/Elle_Cordova'
CDJ = 'https://www.cdjournal.com/main/cdjpush/priscilla-ahn/1000000796'
BARKS_AHN = 'https://barks.jp/news/676370/'
WNC = 'https://ja.wikipedia.org/wiki/%E3%83%8A%E3%83%81%E3%83%A5%E3%83%A9%E3%83%AB%E3%83%BB%E3%82%AB%E3%83%A9%E3%83%BC%E3%82%BA'
WHH = 'https://ja.wikipedia.org/wiki/HOSONO_HOUSE'
WHCH = 'https://ja.wikipedia.org/wiki/HOCHONO_HOUSE'
NIEW = 'https://niewmedia.com/series/hosono_house/3_edymm_wrhra/'
CINRA_T = 'https://www.cinra.net/article/interview-201502-readaloudtahiti80'
T80 = 'https://tahiti80.com/facts'
TO = 'https://www.timeout.com/tokyo/music/tahiti-80'

M = dict(
    key='josh', file='hikigatari-josh-turner-b.html', title='弾き語り・ジョシュ・ターナー編 ― 終わりの季節から、寄り道して',
    desc='はっぴいえんど「風をあつめて」を起点に、ブルックリンの Josh Turner、Priscilla Ahn、細野晴臣、レイ・ハラカミ、Tahiti 80 へ。日本語のまま海を渡った一曲を、ページの中で聴きながら辿る11曲。',
    hero='QeWtMZYjnCE', eyebrow='Hikigatari — Josh Turner edition · 11 songs',
    h1='弾き語り・ジョシュ・ターナー編',
    lead='終わりの季節から、寄り道して。<br/>「風をあつめて」を一本の糸にして、ブルックリン、ナッシュビル、狭山、ルーアンへ。11曲。',
    big='渋谷の喫茶店のトイレの落書きから、<br/>ブルックリンの部屋まで。',
    open=['1971年の東京で生まれた日本語の歌が、日本語のまま、海の向こうで歌われている。歌っているのは、ブルックリンのアパートでカメラを回す、ひとりのギター弾きだ。',
          'その人は何者なのか。15歳の部屋で始まった動画の話から、ナッシュビルの歌姫、ミネソタのギターの女王、そして1973年の埼玉・狭山の8畳の寝室まで。一曲のカバーを糸にして、寄り道しながらたどってみる。'],
    door='最後は、フランスのバンドで軽く締める。',
    paper=[],
    chapters=[
        dict(no='01', artist='はっぴいえんど', song='風をあつめて', album='アルバム『風街ろまん』', year='1971',
             catch='すべての起点は、喫茶店のトイレの落書き',
             main=dict(id='kTPw8tJLdtw', role='Live 1985', artist='はっぴいえんど', song='風をあつめて', cap=''),
             body=[f'アルバム『風街ろまん』の一曲。詞は松本隆、曲は細野晴臣{src("Wikipedia", WKZ)}。',
                   f'詞のきっかけは、松本が通っていた渋谷の喫茶店「マックスロード」のトイレの壁に書かれていた一行、「てふてふが一匹韃靼海峡を渡って行った」だった{src("CREA", CREA)}。',
                   f'録音はドタバタだった。メロディがレコーディング直前までできていなかったので、大瀧詠一と鈴木茂はスタジオに呼ばれず、松本のドラム以外は全部、細野がひとりで演奏した。ギター、ドラム、ベース、オルガンを重ねても、まだメロディができない。スタジオの廊下でやっとできて、すぐに歌った。だから「起きぬけの」のところは、歌い間違えたまま残っている{src("Re:minder", REM)}。',
                   f'2003年、映画『ロスト・イン・トランスレーション』で使われる。音楽プロデューサーが小山田圭吾に「この映画に合う日本の曲はないか」と尋ね、渡された音源の中から、ソフィア・コッポラと二人で選んだのがこの曲だった{src("CINEMORE", CINE)}。松本隆は2024年にこう話している。「母国語は日本語。翻訳するのはフィルターをかけるようなもの。元の意味が変わってしまう」{src("The Guardian", GUA)}。'],
             say='メロディが完成したのは、スタジオの廊下（Re:minder）。世紀の名曲、意外と立ち話で生まれてる。僕の人生の大事な決断も、だいたい廊下か喫煙所でした。',
             bridge='そして2020年。この日本語の歌を、ブルックリンの若者が、日本語のまま歌った。'),
        dict(no='02', artist='Josh Turner', song='風をあつめて', album='Happy End Cover', year='2020',
             catch='僕が彼を知ったのは、このツイートだった',
             main=dict(id='QeWtMZYjnCE', role='Cover 2020', artist='Josh Turner', song='風をあつめて (Gather the wind) - Happy End Cover', cap=''),
             body=['送りバントの高山さんが「これ最高だから聴いてください」と投げていた。高山さんは、めっちゃ面白い人だ。その人が「最高」と言うんだから、押すしかない。押したら、本当に最高だった。……と書きつつ、正直に言うと、Priscilla Ahn の版を聴いていたのが先だったかもしれない。どっちが先でもいい。たどり着いた先が、この人だった。',
                   f'ブルックリンを拠点にする、ギターも歌も鍵盤もやるミュージシャン。15歳だった2007年にYouTubeチャンネルを始めた。2014年、ポール・サイモン「Graceland」のカバーで『Good Morning America』に出ている{src("公式サイト", JLT)}{src("Wikipedia", WJLT)}。',
                   f'決めごとがある。口パクも、ごまかしも一切なし。聴こえている音を、そのまま弾いて見せる。カバーする曲はアルゴリズムではなく、自分の好奇心で選ぶ{src("公式サイト", JLT)}。',
                   f'この動画で、歌とギターとベースと鍵盤がジョシュ、ドラムともう一本のギターと歌が相棒のカーソン・マッキー{src("本人の動画説明", YT_KAZE)}。公開の4日後、作詞した松本隆本人がこう書いた。「ドラムのフィルまで感じつかんでる。細野さんから、最近アメリカ人が日本語のままカバーしてるよと聞いてたけど、ほんとなんだね」{src("松本隆のX", XM)}。はっぴいえんど、まだ連絡網が生きている。'],
             bridge='ところで、ジョシュ本人は、この歌をどこで知ったのか。答えは、もうひとりの歌い手だった。'),
        dict(no='03', artist='Priscilla Ahn', song='風をあつめて', album='アルバム『ナチュラル・カラーズ』', year='2012',
             catch='ジョシュがこの歌を知った、もうひとつの入口',
             main=dict(id='SWBVVgLBWvA', role='Cover 2012', artist='Priscilla Ahn', song='Kaze Wo Atsumete', cap=''),
             body=[f'ジョシュは動画の説明文に、こう書いている。「この曲を最初に知ったのは、Priscilla Ahn の美しい版だった。日本人の家族ぐるみの友人が、J-POPのコンピレーションをくれて、その中に入っていた」{src("本人の動画説明", YT_KAZE)}。僕と同じ入口だった。',
                   f'Priscilla Ahn はアメリカのシンガー・ソングライター。J-POPのカバー集『ナチュラル・カラーズ』に「風をあつめて」が入っていて、ほとんどの曲を日本語の詞のまま歌っている{src("BARKS", BARKS_AHN)}{src("Wikipedia", WNC)}。',
                   f'選んだのは本人だった。「〈風をあつめて〉は、私からやりたいとリクエストした曲です。映画『ロスト・イン・トランスレーション』のサントラを聴いて、歌詞の内容はまったくわかりませんでしたが、すごく好きになりました。私もバンドの一員として部屋の中にいるような感覚になるんです」{src("CDJournal", CDJ)}。'],
             say='「歌詞の内容はまったくわからなかったけど、すごく好きになった」。分かる。僕も洋楽をそうやって30年聴いてきた。意味を調べた瞬間に恋が冷めた曲、3曲あります。曲名は言いません。',
             bridge='寄り道のつもりが、ここで足が止まる。この人は何者なのか。15歳の部屋まで、さかのぼる。'),
        dict(no='04', artist='Josh Turner', song='Sultans of Swing', album='Dire Straits Cover', year='2012',
             catch='車のデザイナー志望の少年、スマホで名刺を撮る',
             main=dict(id='w5SC1uIxXhk', role='Cover 2012', artist='Josh Turner', song='Sultans of Swing', cap=''),
             body=[f'ジョシュア・リー・ターナー。子どもの頃の夢は、車のデザイナーだった。ギターを始めたのは2006年1月。その約1年後、15歳でYouTubeチャンネルを作った。音楽はあくまで趣味。ところがいくつかの動画が思いがけず注目を集めて、まったく別の道が開く{src("公式サイト", JLT)}{src("Wikipedia", WJLT)}。',
                   f'最初に火がついたのが、2012年のこのダイアー・ストレイツだ。公式サイトいわく、この1本だけで1,400万回以上見られている{src("公式サイト", JLT)}。',
                   f'本人の説明文がいい。「フレーズやソロを完璧になぞるつもりはない。曲の感じが伝わればいい」。ギターはメキシコ製のテレキャスター。そして、カメラは iPhone 4s{src("本人の動画説明", YT_SOS)}。'],
             say='1,400万回の名刺、カメラは iPhone 4s（本人の動画説明）。機材より先に、腕と部屋があった。僕は先に機材を買って、部屋に置いて、眺めて、終わるタイプです。',
             bridge='趣味のはずの動画が、2年後、テレビの朝の番組に本人を連れていく。'),
        dict(no='05', artist='Josh Turner', song='Graceland', album='Paul Simon Cover', year='2014',
             catch='ギター1本で、80年代のドラムの音を出せ',
             main=dict(id='NtYKjQLgnOs', role='Cover 2014', artist='Josh Turner', song='Graceland', cap=''),
             body=[f'インディアナポリスのバトラー大学で音楽を学んでいた2014年、4年生のとき。ポール・サイモンの「Graceland」をひとりで弾いて歌ったこの動画が、アメリカの朝の番組『Good Morning America』に本人を連れていった{src("Wikipedia", WJLT)}{src("公式サイト", JLT)}。',
                   f'本人いわく「アレンジが難しい曲だった。リズムの上でいろんなことが起きている。80年代のドラムの音を、エレキギター1本でどう出すか？」。足で床を踏む音を、専用の板で拾って鳴らしている{src("本人の動画説明", YT_GRACE)}。',
                   f'このカバーは、その後の人生の伏線になる。2018年と2019年は、ツアー公演『The Simon & Garfunkel Story』のキャストとして回り、2019年にはロンドンの O2 シェパーズ・ブッシュ・エンパイアで、『Graceland』をまるごと祝うステージの主役としてポール・サイモンを演じた{src("Wikipedia", WJLT)}{src("公式サイト", JLT)}。'],
             say='「ドラムの音をギター1本で」。うちの会社で言う「人手は増やさず成果は2倍で」と同じ構文です。違うのは、ジョシュは本当にやった。僕は「一旦持ち帰り」ました。',
             bridge='ひとりで全部やる男には、ひとりだけ、ずっと隣にいる相棒がいる。'),
        dict(no='06', artist='The Other Favorites', song='Angelina', album='EP『Fools』', year='2017',
             catch='ブルックリンのアパートが、スタジオ',
             main=dict(id='BOn919FtA8k', role='Original 2017', artist='The Other Favorites', song='Angelina', cap=''),
             body=[f'The Other Favorites は、ジョシュと、長年の相棒カーソン・マッキーのフォーク・デュオ。2017年にEP『Fools』、2018年にオリジナル・アルバム『Naysayer』、2019年にライブ盤『Live in London』、2021年に『Unamericana』{src("Wikipedia", WJLT)}。「風をあつめて」でドラムを叩いていたのも、このカーソンだ{src("本人の動画説明", YT_KAZE)}。',
                   f'「Angelina」は二人で書いたオリジナル。説明文には一行、「自分のアパートで、ライブで録った」{src("本人の動画説明", YT_ANG)}。2016年にニューヨークへ移り、音楽一本で食べていくと決めてからの、部屋の音だ{src("公式サイト", JLT)}。',
                   '大きなスタジオはない。あるのは、部屋と、マイクと、隣の相棒。それで十分だと、この動画が証明している。'],
             bridge='部屋には、友だちも来る。2021年、ジョシュは車で国を横断して、友だちの家を順番に回った。'),
        dict(no='07', artist='Josh Turner feat. Elle Cordova & Toni Lindgren', song='The Chain', album='Fleetwood Mac Cover', year='2024',
             catch='ギターの女王と、鎖の歌',
             main=dict(id='9Fdwb62tQkc', role='Cover 2024', artist='Josh Turner feat. Elle Cordova & Toni Lindgren', song='The Chain', cap=''),
             body=[f'2021年、ジョシュは妻のケリーと車でアメリカを横断し、旧友や新しい友だちと一曲ずつ録っていった。『Among Friends: A Musical Travelogue』と題されたその旅の相手のひとりが、当時「Reina del Cid」と名乗っていた、エル・コルドバだった{src("公式サイト", JLT)}。',
                   f'シンガー・ソングライター。2007年、YouTubeのために「Reina del Cid」という名前を作った。スペインの英雄譚「エル・シッド」から取った名前で、自分のギターにそのあだ名をつけ、その「女王（Reina）」を名乗った。相棒のギタリスト、トニ・リンドグレンと、2013年から2015年までセントポールのバーで毎週月曜の夜に出演を続け、2020年の初めにロサンゼルスへ移った{src("Wikipedia", WELLE)}。',
                   f'二人は毎週、日曜の朝にカバー動画を出し続けてきた。2025年1月、その「Sunday Morning」シリーズを終え、今度は満月のたびに一曲出す「Full Moon Tunes」を始めている{src("Wikipedia", WELLE)}。フリートウッド・マックの「The Chain」を、その二人とジョシュに、ダモン・スミスとジェイソン・バーガーを加えた5人で鳴らす{src("本人の動画説明", YT_CHAIN)}。'],
             say='「Reina del Cid」は、自分のギターに「エル・シッド」とあだ名をつけて、その女王を名乗った芸名（Wikipedia）。ギターの女王、と自称して17年。僕は自分のギターに名前をつける前に、ケースに入れたまま3年が過ぎました。',
             bridge='旅の相手は、もうひとりいる。ナッシュビルで出会った声だ。'),
        dict(no='08', artist='Josh Turner feat. Allison Young', song='Crazy', album='Patsy Cline Cover', year='2018',
             catch='ナッシュビルで、いちばんナッシュビルな曲を',
             main=dict(id='An-PQEAxsF8', role='Cover 2018', artist='Josh Turner feat. Allison Young', song='Crazy', cap=''),
             body=[f'2017年、ジョシュはネットでアリソン・ヤングと知り合う{src("Wikipedia", WJLT)}。翌2018年、ツアーでナッシュビルに寄ったとき、「ずっと声に憧れていた」彼女に動画を一緒に撮らないかと頼んだ。返事は、イエス。それなら「ナッシュビルらしさの極みを」と彼女が提案したのが、ウィリー・ネルソンが書いてパッツィ・クラインで広まった「Crazy」だった{src("本人の動画説明", YT_CRAZY)}。',
                   f'その一本が、二人の歌の始まりになる。2022年にはオリジナルのEP『May 9-12』を出してツアーを回り、2023年にはバンド「The Bygones」を結成。バワリー・ボールルームやトルバドールといった名物の会場に立ち、2024年には The Wood Brothers のツアーの前座も務めた{src("公式サイト", JLT)}。',
                   f'2025年2月、二人は The Bygones の活動を続けないと発表した{src("Wikipedia", WJLT)}。それでもこの3分24秒には、始まりの夜の空気が、そのまま残っている。'],
             say='「ナッシュビルらしい曲を」と言われて、ウィリー・ネルソンがすっと出る人。「日本らしい曲を」と言われて、考え込んだ末に「さくらさくら」しか出ない僕。どっちも正解です。たぶん。',
             bridge='部屋で録った歌の話を、もうひとつ。時計を1973年の、埼玉・狭山まで巻き戻す。'),
        dict(no='09', artist='細野晴臣', song='終りの季節', album='アルバム『HOCHONO HOUSE』（原曲は1973年『HOSONO HOUSE』）', year='2019',
             catch='8畳の寝室で録った、終わりの歌',
             main=dict(id='ZPKPNjtNOyI', role='Remake 2019', artist='細野晴臣', song='終りの季節', cap=''),
             body=[f'「風をあつめて」を作曲した細野晴臣は、1972年の秋、埼玉県狭山市の通称「アメリカ村」に移り住んだ。1973年の最初のソロ・アルバム『HOSONO HOUSE』は、その自宅で録られている。リビングに16トラックの卓を置き、演奏は8畳ほどの寝室。狭い部屋の音の回り込みが、このアルバム特有の音になった。録音は2月15日から3月16日まで、毎日午後に5時間ほど、3日に1日休むペースで{src("Wikipedia", WHH)}。',
                   f'「終りの季節」はその4曲目。作詞の「宇野もんど」は細野の変名で、前の年に斉藤任弘に提供した曲のセルフカバーだ{src("Wikipedia", WHH)}。',
                   f'それから46年。活動50周年の2019年、細野はこのアルバムをまるごと作り直した。題して『HOCHONO HOUSE』。演奏も歌もプログラミングも録音も編集も、全部ひとりで。曲順は、元のアルバムと逆{src("Wikipedia", WHCH)}。ここで聴けるのは、その2019年の「終りの季節」だ{src("公式の音源", YT_OWARI)}。',
                   'ブルックリンのアパートで、ひとりで全部の楽器を重ねる男の、ちょうど半世紀前。寝室で録った歌が、ここにもあった。'],
             bridge='この歌を、自分の声で歌い直した人がいる。'),
        dict(no='10', artist='rei harakami', song='owari no kisetsu', album='アルバム『lust』', year='2005',
             catch='寄り道の、さらに寄り道',
             main=dict(id='wC1z9sNSaXo', role='lust 2005', artist='rei harakami', song='owari no kisetsu', cap=''),
             body=[f'細野晴臣が1973年の『HOSONO HOUSE』に入れた「終りの季節」を、レイ・ハラカミが本人の声でカバーした{src("NiEW", NIEW)}。',
                   f'この人の話は長くなるので、特集「<a class="cw-inl" href="{BASE}rei-harakami.html">君はレイ・ハラカミを知っているか</a>」にまとめた。'],
             bridge='最後は、フランスから。日本と縁の深いバンドで締める。'),
        dict(no='11', artist='Tahiti 80', song='Heartbeat', album='アルバム『Puzzle』', year='1999',
             catch='最後に、これをどうぞ',
             main=dict(id='K3SezDMPpVM', role='Official MV', artist='Tahiti 80', song='Heartbeat', cap=''),
             body=[f'フランス・ルーアンの大学で結成されたバンド{src("公式サイト", T80)}。1999年、当時のマネージャーがフランスでコーネリアスのマネジメントも担当していて、デモを小山田圭吾に渡せた。小山田はそのデモ版「Heartbeat」を自分のコンピレーションに入れた{src("CINRA", CINRA_T)}{src("Time Out Tokyo", TO)}。メンバーいわく「本当に幸運だった」{src("CINRA", CINRA_T)}。',
                   f'デビュー・アルバム『Puzzle』は日本でゴールドディスクになり、その中でいちばん成功したシングルが「Heartbeat」だった{src("公式サイト", T80)}。',
                   '実は Tahiti 80 も「風をあつめて」をカバーしている。それも良かった。でも最後はこっち。これだけは絶対に紹介したかった。'],
             more_label='関連動画 — Tahiti 80 の「風をあつめて」',
             more=[dict(id='lp6rkCyAaFc', role='Cover', artist='Tahiti 80', song='風をあつめて', cap='')],
             say='バンド名は、ボーカルの父親が1980年にもらったお土産のTシャツから（公式サイト）。Tシャツ1枚で、バンドの名前が決まった事件。',
        ),
    ],
    close=['一曲のカバーを追いかけたら、知らない人に会えた。',
           '渋谷の喫茶店のトイレの落書きが、狭山の寝室を通り、ロサンゼルスのスタジオを通り、ブルックリンのアパートで、日本語のまま鳴っていた。部屋で録った歌は、海を渡る。',
           'トイレの落書きから始まった歌は、まだ旅の途中だ。次回の弾き語りもお楽しみに。'],
    sources=[('Wikipedia — 風をあつめて', WKZ), ('CREA — 松本隆と「風街」', CREA), ('Re:minder — 「風をあつめて」誕生', REM), ('CINEMORE — ロスト・イン・トランスレーション', CINE), ('The Guardian — Happy End', GUA),
             ('Joshua Lee Turner 公式サイト', JLT), ('Wikipedia — Joshua Lee Turner', WJLT), ('松本隆（X・2020年5月30日）', XM),
             ('Josh Turner Guitar — 風をあつめて（動画の説明文）', YT_KAZE), ('Josh Turner Guitar — Sultans of Swing（動画の説明文）', YT_SOS), ('Josh Turner Guitar — Graceland（動画の説明文）', YT_GRACE),
             ('Josh Turner Guitar — Angelina（動画の説明文）', YT_ANG), ('Josh Turner Guitar — The Chain（動画の説明文）', YT_CHAIN), ('Josh Turner Guitar — Crazy（動画の説明文）', YT_CRAZY),
             ('Wikipedia — Elle Cordova', WELLE),
             ('CDJournal — Priscilla Ahn インタビュー', CDJ), ('BARKS — ナチュラル・カラーズ', BARKS_AHN), ('Wikipedia — ナチュラル・カラーズ', WNC),
             ('Wikipedia — HOSONO HOUSE', WHH), ('Wikipedia — HOCHONO HOUSE', WHCH), ('細野晴臣 — 終りの季節（公式の音源）', YT_OWARI), ('NiEW — 『HOSONO HOUSE』再訪', NIEW),
             ('CINRA — Tahiti 80', CINRA_T), ('Tahiti 80 公式サイト', T80), ('Time Out Tokyo — Tahiti 80', TO)],
    note='',
    i18n=I18N,
)

if __name__ == '__main__':
    print(write(M))
