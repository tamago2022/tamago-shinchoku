import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src

TW = 'https://totallywiredmag.com/looking-back-oh-bondage-up-yours-and-the-power-of-poly-styrene/'
PKM = 'https://pleasekillme.com/poly-styrene/'
GUARD = 'https://www.theguardian.com/music/2022/nov/28/id-wear-a-mac-on-stage-because-of-all-the-spitting-lora-logic-on-punk-prayer-and-poly-styrene'
WOB = 'https://en.wikipedia.org/wiki/Oh_Bondage_Up_Yours!'
SP23 = 'https://www.sponichi.co.jp/entertainment/news/2023/11/21/kiji/20231121s00041000572000c.html'
TOSPO = 'https://www.tokyo-sports.co.jp/articles/-/343055'
LD = 'https://news.livedoor.com/article/detail/19769824/'
MIY = 'https://miyearnzzlabo.com/archives/12651'
NLAB = 'https://nlab.itmedia.co.jp/cont/articles/3269398/'
WORA = 'https://ja.wikipedia.org/wiki/%E4%BF%BA%E3%82%89%E6%9D%B1%E4%BA%AC%E3%81%95%E8%A1%8C%E3%81%90%E3%81%A0'
WTIM = 'https://ja.wikipedia.org/wiki/THE_TIMERS'
ENC = 'https://encount.press/archives/705209/'
CYZO = 'https://cyzo.jp/culture/post_419074/'
SP25 = 'https://www.sponichi.co.jp/entertainment/news/2025/06/09/kiji/20250609s00041000188000c.html'
BUN = 'https://bunshun.jp/articles/-/75719?page=1'
NAT = 'https://natalie.mu/music/news/455776'
SOL = 'https://www.tfm.co.jp/lock/speciallocks/38998'
RT19 = 'https://rooftop1976.com/interview/190704143000.php?page=3'
RT20 = 'https://rooftop1976.com/interview/200429124722.php'
RS = 'https://realsound.jp/2022/10/post-1153011.html'
ANT = 'https://antenna-mag.com/post-19448/'
GEKI = 'https://gekirock.com/interview/2019/03/uchikubigokumon.php'
SF = 'https://www.songfacts.com/facts/lenny-kravitz/rock-and-roll-is-dead'
WDAME = 'https://ja.wikipedia.org/wiki/%E8%B8%8A%E3%82%8B%E3%83%80%E3%83%A1%E4%BA%BA%E9%96%93'
WLEN = 'https://en.wikipedia.org/wiki/Rock_and_Roll_Is_Dead'
WYOSHI = 'https://ja.wikipedia.org/wiki/%E5%90%89%E5%B9%BE%E4%B8%89'
SP2510 = 'https://www.sponichi.co.jp/entertainment/news/2025/10/23/kiji/20251023s00041000092000c.html'

CAMB = 'https://dictionary.cambridge.org/dictionary/english/up-yours'
WVS = 'https://en.wikipedia.org/wiki/V_sign'
WGOLD = 'https://en.wikipedia.org/wiki/Gold_(Prince_song)'
MYN = 'https://agri.mynavi.jp/2025_07_29_341237/'
WCOV = 'https://ja.wikipedia.org/wiki/COVERS_(RC%E3%82%B5%E3%82%AF%E3%82%BB%E3%82%B7%E3%83%A7%E3%83%B3%E3%81%AE%E3%82%A2%E3%83%AB%E3%83%90%E3%83%A0)'
WUCHI = 'https://ja.wikipedia.org/wiki/%E6%89%93%E9%A6%96%E7%8D%84%E9%96%80%E5%90%8C%E5%A5%BD%E4%BC%9A'

M = dict(
    key='ikareru', file='tokushu-ikareru-01.html', title='怒れる人々 vol.1',
    desc='ロックは怒りや反骨の音楽だった。Ado「うっせぇわ」、THE TIMERSの放送事故、X-Ray Spex、吉幾三、打首獄門同好会、おとぼけビ〜バー。そしてLenny Kravitzの問いかけと、Princeの返事。11曲を、ページの中で聴きながら辿る。',
    hero='Qp3b-RXtz4w', eyebrow='Rock Story — The Angry Ones · vol.1',
    h1='怒れる人々', lead='ロックは、怒りや反骨の音楽だった。<br/>抑圧された若者たちの叫び。ここから11曲。ぜんぶ、このページの中で聴ける。',
    big='やってはいけないことをやる人。<br/>言ってはいけないことを、言ってしまう人。',
    open=['ロックは、怒りや反骨の音楽だった。「ふざけんじゃねえ」「笑わせんじゃねえ」。抑圧された若者たちの叫びが、なぜか何十年も聴き継がれる曲になる。',
          'いちばん新しい叫びから始めて、昔にも怒っていた人たちへさかのぼり、最後にひとつの問いかけと、その返事で締める。'],
    door='最後に、1995年の問いかけと、その返事が待っている。',
    paper=[],
    songs_n=11,
    chapters=[
        dict(no='01', en='優等生がキレた', title='Ado - うっせぇわ', year='2020',
             main=dict(id='Qp3b-RXtz4w', role='Official MV 2020', artist='Ado', song='うっせぇわ', cap='Ado 公式アーティストチャンネル。4億回以上再生されている'),
             body=[f'2020年10月、Adoのメジャーデビュー曲。詞と曲はボカロPのsyudou{src("音楽ナタリー", NAT)}。2021年の新語・流行語大賞でトップテンに入った{src("音楽ナタリー", NAT)}。',
                   f'歌った当時、Adoは高校3年生。社会人の世界はドラマや映画で想像するしかなかった。「簡単に言えば“怒りの感情”みたいな。怒りの感情は学生にも共通している部分はあったので、そこをいかに強く出せるか」{src("SCHOOL OF LOCK!", SOL)}。',
                   f'syudouは「女性の目線にしよう」などは一切考えず、普段通りに書いた。返ってきた答えは「いっさいの直しナシ」。サビで裏声に持っていくあの歌い方も、Ado自身のアイデアだった。「僕が歌のディレクションしたって思われることが多いんですけど、マジでなんもしてないんすよ！」{src("SCHOOL OF LOCK!", SOL)}。'],
             say='デモに返ってきた唯一の注文は「キーを4〜5個上げてください」（SCHOOL OF LOCK!）。優等生、最初から喉でキレる気まんまん。',
             bridge='令和の優等生がキレる、ずっと前。昔にも、怒っている人はいた。'),
        dict(no='02', en='その夜、テレビが事件になった', title='THE TIMERS - FM東京', year='フジテレビ『ヒットスタジオR&N』 1989.10.13',
             main=dict(id='BnU7Yr6tZxU', role='On Air 1989', artist='THE TIMERS', song='FM東京', cap='一般の方の投稿（2014年）。放送の映像。12年で150万回以上再生されている'),
             body=[f'今や伝説の、THE TIMERSの放送事故だ。忌野清志郎に“よく似ている人物”ZERRYが率いる覆面バンド{src("Wikipedia", WTIM)}。',
                   f'火種は前の年。RCサクセションのアルバム『COVERS』は、原発を歌った「サマータイム・ブルース」などが問題にされ、当時の親会社・東芝からの圧力で発売中止になった。新聞広告の文句は「素晴しすぎて発売出来ません」{src("Wikipedia", WCOV)}。その後、別の会社から出たが、FM東京はオンエアを自粛した{src("Wikipedia", WTIM)}。さらに清志郎が詞を書いた「谷間のうた」がFM仙台で放送禁止、タイマーズの「土木作業員ブルース」もFM東京で放送自粛{src("ENCOUNT", ENC)}。',
                   f'1989年10月13日、フジテレビの深夜の音楽番組『ヒットスタジオR&N』――『夜のヒットスタジオ』の派生番組。予定は5曲。2曲目の「偽善者」を歌わず、いきなり始めたのが、FM東京とFM仙台を名指しで罵倒する新曲「FM東京」だった。放送禁止用語つき{src("ENCOUNT", ENC)}。言い出しっぺはギターのTOPPI（三宅伸治）。「何かやらかしましょうか？」。二人で曲を作ったが、清志郎がつけたある歌詞を見て「すげえ。半端な気持ちだった自分とは、覚悟が違った」{src("サイゾー", CYZO)}。',
                   f'司会の古舘伊知郎は、夕方のリハーサルで気づいていた。「歌の中で古舘伊知郎って26回言ったんですよ。本番でそこに違う言葉をはめるんだな、と」。楽屋に乗り込むと、返事は「大丈夫、大丈夫！古舘君、迷惑は掛けないから」。本番、出演者は笑い転げ、「僕だけ青ざめてる」。放送後に文句を言いに行くと、もう楽屋にいなかった。2週間後、西麻布のワインバーで鉢合わせした清志郎は、立ち上がって深々とおじぎし、小さな声で「ごめんなさい、古舘くん」{src("スポニチ", SP25)}。'],
             more_label='関連動画 — 火種になった曲、司会者が振り返るあの夜、ノーカット版',
             more=[dict(id='GpF3hoKLiFY', role='COVERS 1988', artist='RCサクセション', song='サマータイム・ブルース', cap='一般の方の投稿。15年で100万回以上再生されている'),
                   dict(id='uk8PA5A1yk4', role='Witness', artist='古舘伊知郎チャンネル', song='放送禁止用語連発！忌野清志郎さんの忘れられない話', cap='古舘伊知郎の公式チャンネル'),
                   dict(id='JrTQDYVVa7w', role='Uncut', artist='THE TIMERS', song='【完全ノーカット】FM東京事件と今だから語られるその裏側', cap='一般の方の投稿（2026年）。当夜の出演をノーカットで。約17分')],
             say='実はこれ、生放送じゃなかった。ディレクター本人が「実は生じゃなかったんです」。夕方に撮って、そのまま流した。止める時間は、あった（文春）。',
             bridge='日本の深夜のテレビより、さらに12年前。ロンドンでは、ひとりの少女が「くたばれ」と叫んでいた。'),
        dict(no='03', en='束縛なんか、くたばれ', title='X-Ray Spex - Oh Bondage Up Yours!', year='London 1977',
             main=dict(id='DcwdUXZkfTw', role='Punk 1977', artist='X-Ray Spex', song='Oh Bondage Up Yours!', cap='一般の方の投稿（2012年）。字幕つき'),
             body=[f'1977年9月30日、X-Ray Spexのデビュー・シングル。書いて歌ったのは、ポリー・スタイリン{src("Wikipedia", WOB)}。BBCは放送を禁止した{src("Wikipedia", WOB)}。',
                   f'題名の「Up Yours」は、イギリスの悪態だ。ケンブリッジ英英辞典は「offensive（無礼）。相手や、相手の言ったこと・したことが心底嫌いだと示すときに使う」と書く{src("Cambridge Dictionary", CAMB)}。手の甲を相手に向けて二本指を突き上げる、イギリスの侮辱のしぐさとセットで使われ、とくに権威への反抗や軽蔑を表す{src("Wikipedia", WVS)}。日本語なら「くたばれ」「ふざけんな」くらいの強さ。だから題名は「ああ束縛よ、くたばれ！」。',
                   f'ステージに立つ彼女の歯には、矯正器具がはまっていた。小道具ではない、本物だ。ソマリア生まれの父と白人の母のあいだに生まれた{src("PLEASE KILL ME", PKM)}。',
                   f'「ボンデージ」と聞いて、みんなSMの曲だと思った。本人は2008年にこう言っている。「物質世界の束縛から自由になる歌。奴隷制や、鎖でつながれたサフラジェット（女性参政権運動家）のイメージがあった。ヴィヴィアン・ウエストウッドの店でボンデージ・パンツを見たとき、それが私の育ってきたあらゆる“束縛”の象徴に見えた」{src("Totally Wired", TW)}。',
                   f'叫ぶ声に、陽気なサックスがかぶさる。吹いていたローラ・ロジックは、音楽誌の募集広告「Young punks wanted（若いパンク求む）」を見てオーディションに来た{src("The Guardian", GUARD)}。2021年、Rolling Stone誌の「史上最高の500曲」で120位{src("Wikipedia", WOB)}。'],
             bridge='ロンドンの少女が束縛に「くたばれ」と叫んだ7年後。日本の村から、別の怒りが届く。'),
        dict(no='04', en='テレビも無ェ', title='吉幾三 - 俺ら東京さ行ぐだ', year='青森・金木 1984',
             main=dict(id='UzRVEQDxiOo', role='TV', artist='吉幾三', song='俺ら東京さ行ぐだ', cap='一般の方の投稿。11年で2,600万回以上再生されている'),
             body=[f'1984年11月25日のシングル。作詞作曲は吉幾三本人{src("Wikipedia", WORA)}。のちに本人はこう明かしている。「田舎を出てきたときの気持ちを歌にしようと思った。なんにもないのがイヤで出てきたんだよな」{src("ねとらぼ", NLAB)}。',
                   f'売れるまでが長かった。1973年、20歳で「山岡英二」としてデビュー。路線は、なんとアイドル。デビュー曲はヤンマーの船外機のCMソング。ところが同じ時期に郷ひろみ・野口五郎・西城秀樹。「俺を通してくれないんだよ」{src("スポニチ", SP2510)}。1977年に吉幾三と改名し、自作の「俺はぜったい！プレスリー」がヒット。そのあとまた低迷期が来る{src("Wikipedia", WYOSHI)}。',
                   f'あのしゃべるような節回しには、元ネタがある。ニューヨークで板前をしていた先輩が「知らないと思うけど、こんな歌が流行ってる」とレコードを送ってきた。英語でしゃべってるだけ、後ろでズン・ダッタ・ズンとビートが鳴っている。「なんだこれ？ これが歌か？」。それを聴いていたら、ギターで作っているうちにああいうフレーズになった、と本人{src("みやーんZZ", MIY)}。番組では「俺60になるんだけど」と前置きして、カメラに言い放った。「俺、ラッパーだから」{src("みやーんZZ", MIY)}。',
                   f'世に出したのは、演歌の大御所・千昌夫。吉が自作の「津軽平野」を聴かせると、千は「この曲を俺にくれ」。代わりに「お前は『俺ら東京さ行ぐだ』を出せ」と言い、レコーディング費用は「全部俺が出してやる」{src("スポニチ", SP23)}。',
                   f'大ヒットのあと、事務所の電話が鳴りやまなくなる。「生まれたところをバカにすんな！」「おれは青森県から電話しているんだ」。苦情の電話が3本、鳴りっぱなし。本人も受話器を取った{src("東スポ", TOSPO)}。1985年4月の『夜のヒットスタジオDELUXE』では、スタジオに集まった金木町の人たちを後ろに従えて歌っている{src("Wikipedia", WORA)}。'],
             more_label='関連動画 — 公式の、もうひとつの「俺ら東京さ行ぐだ」',
             more=[dict(id='bIV-zcs4VDA', role='Video Cinema', artist='吉幾三', song='俺ら東京さ行ぐだ（ビデオシネマ「純情編」より）', cap='徳間ジャパン 演歌・歌謡曲チャンネル（公式）')],
             say='この曲、最初の題は『離村者』だった（ライブドアニュース）。重すぎる。それが「テレビも無ェ」に化けて、日本中の村から苦情の電話が鳴る事件になる。',
             bridge='村の不満をラップにした人がいれば、ごはんのうまさと、働きたくなさを、重たいギターで叫ぶ人たちもいる。'),
        dict(no='05', en='米と、はたらきたくない', title='打首獄門同好会 - 日本の米は世界一', year='2015',
             main=dict(id='BuU2bocSfDo', role='Official MV 2015', artist='打首獄門同好会', song='日本の米は世界一', cap='打首獄門同好会 公式アーティストチャンネル。11年で1,900万回以上再生されている'),
             body=[f'「生活密着型ラウドロック」を名乗るバンド{src("Wikipedia", WUCHI)}。いちばん知られた曲は、農業を応援しようと作ったわけではない。きっかけは、鮎の塩焼き定食についてきた白米だった{src("マイナビ農業", MYN)}。',
                   f'自分たちのYouTube番組の企画で、原付バイクで東日本を縦断していた途中。新潟県魚沼市でお昼になり、鮎の塩焼きの定食屋に入った。ボーカルの大澤いわく「鮎の塩焼きは当然ながらうまい、ただ主役の鮎がかすむほど、ついてきた白米がおいしかったんです」。スタッフも「米がうまい！うますぎる！」と大騒ぎ。「この感動は歌にしなければ」{src("マイナビ農業", MYN)}。',
                   f'のちに地元の協力で、自分たちで田植えから稲刈りまでやる米作りが始まった。とれた米は「獄ひかり」と名づけて売っている{src("マイナビ農業", MYN)}。',
                   f'もう一曲の「はたらきたくない」は、Nintendo Switchのゲーム『WORK×WORK』のテーマ曲。どんな曲がいいか聞くと、ゲーム会社のほうから「例えば曲のテーマは、はたらきたくないとか……」。バンドは気をつかって「無難な曲」も用意したが、ゲーム会社の人たちは全員で聴き終わると「こっちだね」と「はたらきたくない」を指差した。大澤いわく「ゲーム業界の方も、およそ感覚がおかしいんですよね」{src("激ロック", GEKI)}。'],
             more_label='もう一曲 — 月曜の朝の本音',
             more=[dict(id='GR-mLGV0X1I', role='Official MV 2018', artist='打首獄門同好会', song='はたらきたくない', cap='打首獄門同好会 公式アーティストチャンネル')],
             bridge='日本の中で怒っている人たちがいる一方、その怒りは今、海の向こうでも鳴っている。京都から。'),
        dict(no='06', en='ジジイの反応を待たない', title='おとぼけビ〜バー - ジジイ is Waiting For My Reaction', year='京都 2020',
             main=dict(id='2TzJkX9zweM', role='Official PV 2020', artist='おとぼけビ〜バー', song='ジジイ is Waiting For My Reaction', cap='おとぼけビ〜バー 公式アーティストチャンネル。1分半'),
             body=[f'京都の4人組。曲は1分半。ボーカルのあっこりんりんいわく、「めっちゃイヤな態度出してるのに気づかず口説いてくるおっさんの歌」。「普通メシめっちゃ断られたら脈ないってわかるでしょ？ やつらは『なんで？ ごちそうするのに？』って言うんです。おまえに時間割きながら奢られるメシよりひとりでカップラーメン食ってるほうがうまいねん」。ずっと歌いたかったが、お客さんにオジサマが多いのでビビって作れなかった、とも{src("Rooftop", RT19)}。',
                   f'2016年、初めてのUKツアーは全公演が売り切れた。英語もしゃべれないまま、海の向こうで「ちょっとした騒ぎ」になっていた{src("Real Sound", RS)}。2018年にはアメリカのコーチェラに出演。日本からの出演はX JAPANと彼女たちで、「字面だけでも意味がわからなすぎて『すげーミラクル！』ってみんなでわろてます」{src("ANTENNA", ANT)}。'],
             more_label='関連動画 — 嫁の飯と、海の向こうのスタジオで',
             more=[dict(id='LBz3XJotUHc', role='Official PV', artist='おとぼけビ〜バー', song='あなたわたし抱いたあとよめのめし', cap='おとぼけビ〜バー 公式アーティストチャンネル'),
                   dict(id='MQ8_Cdkyq2s', role='Live', artist='Otoboke Beaver', song='Full Performance (Live on KEXP)', cap='KEXP 公式チャンネル')],
             say='このMV、監督の第一声は「女子高生になってもらいます！」（Rooftop）。ジジイへの返事が、制服で届く。',
             bridge='令和の東京から、1977年のロンドン、青森の村、京都まで。最後に、ひとつの問いかけを置いておく。'),
        dict(no='07', en='ロックは死んだのだろうか', title='Lenny Kravitz - Rock and Roll Is Dead', year='1995',
             main=dict(id='yw8_5OYKQNA', role='Official MV 1995', artist='Lenny Kravitz', song='Rock And Roll Is Dead', cap='LennyKravitzVEVO'),
             body=[f'1995年、アルバム『Circus』からのシングル{src("Wikipedia", WLEN)}。題名だけ聞いて、みんな怒った。でも本人いわく、言いたかったのは別のこと。「イメージが音楽や才能や芸術より優先されている、その上っ面のこと。ロックスターになるために、ヘロインを打ったり決まった振る舞いをしたりする必要はない。自分らしくあれってこと」{src("Songfacts", SF)}。'],
             bridge='この問いかけに、同じ年、返事をした人がいる。'),
        dict(no='08', en='最後に、これをどうぞ', title='Prince - Rock and Roll Is Alive! (And It Lives in Minneapolis)', year='1995',
             main=dict(id='YAxbwQNa15Q', role='Answer 1995', artist='Prince', song='Rock And Roll Is Alive! (And It Lives In Minneapolis)', cap='princevevo（公式）'),
             body=[f'プリンスのシングル「Gold」のB面に入った曲。レニー・クラヴィッツの「Rock and Roll Is Dead」への返事として作られた{src("Wikipedia", WGOLD)}{src("Songfacts", SF)}。',
                   '題名の意味は「ロックンロールは生きてる。ミネアポリスに住んでる」。ミネアポリスは、プリンスの地元だ。'],
        ),
    ],
    close=['ロックは、死んだのだろうか。', 'Adoやおとぼけビ〜バーがいる限り、まだ死んでない。プリンスに言わせれば、住所まである。', '怒れる人々は、まだまだいる。次回もお楽しみに。'],
    sources=[('音楽ナタリー — 流行語大賞', NAT), ('SCHOOL OF LOCK! — Ado × syudou', SOL), ('Wikipedia — THE TIMERS', WTIM), ('Wikipedia — COVERS', WCOV), ('ENCOUNT — FM東京事件', ENC), ('サイゾー — 三宅伸治の証言', CYZO), ('スポニチ — 古舘伊知郎の証言（2025）', SP25), ('文春オンライン — 「実は生じゃなかった」', BUN),
             ('Cambridge Dictionary — up yours!', CAMB), ('Wikipedia — V sign', WVS), ('Wikipedia — Oh Bondage Up Yours!', WOB), ('PLEASE KILL ME — Poly Styrene', PKM), ('Totally Wired — Oh Bondage Up Yours!', TW), ('The Guardian — Lora Logic', GUARD),
             ('ねとらぼ — 「俺ら東京さ行ぐだ」歌詞のウソ・ホント', NLAB), ('みやーんZZ — 吉幾三が語る誕生秘話', MIY), ('スポニチ — 千昌夫とレコーディング費用', SP23), ('東スポ — 苦情の電話', TOSPO), ('ライブドアニュース — 最初のタイトルは『離村者』', LD), ('Wikipedia — 俺ら東京さ行ぐだ', WORA), ('Wikipedia — 吉幾三', WYOSHI), ('スポニチ — 最初は「アイドル」だった（2025）', SP2510),
             ('マイナビ農業 — 「日本の米は世界一」誕生秘話', MYN), ('激ロック — 打首獄門同好会インタビュー', GEKI), ('Wikipedia — 打首獄門同好会', WUCHI),
             ('Rooftop — おとぼけビ〜バー（2019）', RT19), ('Rooftop — おとぼけビ〜バー（2020）', RT20), ('Real Sound — おとぼけビ〜バー', RS), ('ANTENNA — コーチェラ出演', ANT),
             ('Songfacts — Rock and Roll Is Dead', SF), ('Wikipedia — Rock and Roll Is Dead', WLEN), ('Wikipedia — Gold (Prince song)', WGOLD)],
    note='動画は公式チャンネルを基本に、公式より面白いもの（長く残って再生回数の多い一般の方の投稿）や旬の時期の映像も拾っています。事実は上の出典で確認できた範囲だけを書いています。歌詞は引用していません。',
)

if __name__ == '__main__':
    print(write(M))
