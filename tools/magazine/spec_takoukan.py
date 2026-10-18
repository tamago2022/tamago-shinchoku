import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src

# 2026-10-18 全開便（120052番）：確定した型（怒れる人々 vol.1）にそろえた版。6曲 → 11曲、吹き出し・写真・5言語・出典の裏取りし直し。
# 事実は下の出典で確認できたものだけ（取得物は作業中 /private/tmp/q120052/src/ に置き、最後に消す）。
_HERE = os.path.dirname(os.path.abspath(__file__))
_I18N = os.path.join(_HERE, 'i18n_takoukan.json')
I18N = json.load(open(_I18N, encoding='utf-8')) if os.path.exists(_I18N) else {'en': {}}  # 5言語（訳だけ直すときはこのファイル）

# 01 Bill Withers
SFL = 'https://www.songfacts.com/facts/bill-withers/lovely-day'
AMS = 'https://americansongwriter.com/this-bill-withers-classic-borrowed-its-good-vibes-from-a-famously-jolly-songwriter/'
WLD = 'https://en.wikipedia.org/wiki/Lovely_Day'
# 02 Katrina and the Waves
WOS = 'https://en.wikipedia.org/wiki/Walking_on_Sunshine_(Katrina_and_the_Waves_song)'
WKW = 'https://en.wikipedia.org/wiki/Katrina_and_the_Waves'
# 03 大滝詠一
WTEN = 'https://ja.wikipedia.org/wiki/%E5%90%9B%E3%81%AF%E5%A4%A9%E7%84%B6%E8%89%B2'
WALV = 'https://ja.wikipedia.org/wiki/A_LONG_VACATION'
# 04 SUGAR BABE
OTO = 'https://otonanoweb.jp/s/magazine/diary/detail/10695'
WDT = 'https://ja.wikipedia.org/wiki/DOWN_TOWN_(%E3%82%B7%E3%83%A5%E3%82%AC%E3%83%BC%E3%83%BB%E3%83%99%E3%82%A4%E3%83%96%E3%81%AE%E6%9B%B2)'
JLY = 'https://j-lyric.net/artist/a04ab93/'
# 05 Maroon 5
SCW = 'https://southerncaliforniawedding.com/flashback-when-your-wedding-is-crashed-by-maroon-5/'
ABC = 'https://abc7news.com/post/watch-maroon-5-crash-real-live-weddings-for-their-music-video/476505/'
WSU = 'https://en.wikipedia.org/wiki/Sugar_(Maroon_5_song)'
# 06 Earth, Wind & Fire
WSEP = 'https://en.wikipedia.org/wiki/September_(song)'
# 07 Stevie Wonder
UDD = 'https://www.udiscovermusic.com/stories/stevie-wonder-sir-duke-song/'
WSD = 'https://en.wikipedia.org/wiki/Sir_Duke'
# 08 Bruno Mars
BB = 'https://www.billboard.com/music/music-news/bruno-mars-24k-magic-interview-7581250/'
TV = 'https://www.teenvogue.com/story/bruno-mars-vs-show-2016-chunky-performance'
W24 = 'https://en.wikipedia.org/wiki/24K_Magic_(song)'
# 09 Queen
WDS = 'https://en.wikipedia.org/wiki/Don%27t_Stop_Me_Now'
# 10 Daft Punk
WGL = 'https://en.wikipedia.org/wiki/Get_Lucky_(Daft_Punk_song)'
# 11 Pharrell Williams
NME = 'https://www.nme.com/news/music/pharrell-williams-25-1214292'
CR = 'https://www.creativereview.co.uk/happy-pharrell-williams/'
H24 = 'https://24hoursofhappy.com/'
RS = 'https://www.rollingstone.com/music/music-news/watch-pharrell-cry-over-happy-inspiration-231769/'
WHAP = 'https://en.wikipedia.org/wiki/Happy_(Pharrell_Williams_song)'
SPOT = 'https://open.spotify.com/playlist/2yL7HHEf409bLqO57CDHBB'

M = dict(
    key='takoukan', file='naze-ongaku-01-takoukan.html', title='人はなぜ音楽を聴くのか 第1回 楽しくなりたいから ― 多幸感ポップス',
    desc='人はなぜ音楽を聴くのか。第1回の答えは「楽しくなりたいから」。Bill Withers、Katrina and the Waves、大滝詠一、SUGAR BABE、Maroon 5、Earth, Wind & Fire、Stevie Wonder、Bruno Mars、Queen、Daft Punk、Pharrell Williams。11曲で、朝から夜明けまでの一日をたどる。',
    hero='ZbZSe6N_BXs', eyebrow='Why do we listen to music? — Report 01 · 11 songs',
    h1='楽しくなりたいから',
    lead='人はなぜ音楽を聴くのか。第1回の答えは、たぶんこれ。<br/>「頑張れ」と説得してこないのに、勝手に口角が上がる11曲。ぜんぶ、このページの中で聴ける。',
    big='人はなぜ音楽を聴くのか。<br/>いちばん最初に浮かぶ答えは、「楽しくなりたいから」。',
    open=['何もしたくない朝から、着替えて出かける夜、そして夜明けまで。11曲で、一日をたどってみる。',
          'どの曲にも、楽しさが生まれた現場がある。スタジオにいた一人の楽天家。ボウリング場のあるビルの一室。本物の結婚式。9回ボツをくらった作曲家。妹を亡くして、街の色を失った作詞家。楽しい曲ほど、裏側はそう簡単じゃない。'],
    door=f'この11曲の続きは、Spotifyのプレイリスト<a href="{SPOT}" target="_blank" rel="noopener noreferrer">「多幸感ポップス」</a>で。',
    paper=[],
    map=False,
    songs_n=11,
    chapters=[
        dict(no='01', artist='Bill Withers', song='Lovely Day', album='アルバム『Menagerie』', year='1977',
             catch='目が覚めるだけで、いい日の始まりになる',
             main=dict(id='bEeaS6fuUoA', role='Official Audio 1977', artist='Bill Withers', song='Lovely Day', cap=''),
             body=[f'1977年のアルバム『Menagerie』から。曲を用意したのはスキップ・スカーボロー。そこにウィザースが言葉を乗せた{src("American Songwriter", AMS)}{src("Wikipedia", WLD)}。',
                   f'このスカーボローが、根っからの陽気な人だった。その気分が、そのまま歌詞に入り込んだ{src("American Songwriter", AMS)}。歌の主人公は、つらい朝があることを隠さない。それでも、あなたをひと目見れば、今日はいい日になる。',
                   f'ヒットから遠ざかっていたウィザースは、この曲で全米30位に返り咲き、イギリスでは7位まで上がった{src("American Songwriter", AMS)}{src("Wikipedia", WLD)}。',
                   'ぼくの朝は、目覚ましを3回止めるところから始まる。4回目の代わりに、この曲をかける。歯磨きの途中で、だいたい口角が上がっている。'],
             say='終盤でウィザースが伸ばす一声、長さ18秒。全米トップ40に入った曲の中で、いちばん長い（Wikipedia／Songfacts）。歯磨きは、ちょうどこのロングトーンで終わります。',
             bridge='一日が始まった。玄関を開けたら、外は晴れ。背中を押す曲が、もう一曲要る。'),
        dict(no='02', artist='Katrina and the Waves', song='Walking on Sunshine', album='アルバム『Katrina and the Waves』', year='1985.4',
             catch='陽気じゃない4人が作った、いちばん陽気な曲',
             main=dict(id='iPUmE-tne5U', role='Official MV', artist='Katrina and the Waves', song='Walking on Sunshine', cap=''),
             body=[f'1983年に一度レコードになり、録り直した版が1985年4月にシングルとして出た。全米9位、イギリス8位{src("Wikipedia", WOS)}。',
                   f'書いたのはギターのキンバリー・リュー。本人いわく「玄関を出たら彗星が見えてひらめいた、みたいな話にできればいいんだけど、ただの単純で楽しい曲。僕らは飛び抜けて陽気な人間じゃなかった。不安で、悲観的で、典型的な若いバンド。ドイツのフェスで二番手に出る程度のポップバンド。でも、この曲だけはあった」{src("Wikipedia", WOS)}。',
                   f'ほかのメンバーは、最初この曲が好きではなかった。ボーカルのカトリーナは「私たちらしくない」、ベースのヴィンスは「イライラする」{src("Wikipedia", WOS)}。',
                   f'そのイライラする曲が、バンドを食べさせた。出版権を自分たちで持ち続けたので、CMや映画で使われるたびに4人に印税が入る。元EMIの社員いわく「EMIのカタログの中の、王冠の宝石」。2015年8月、リューとバンドの曲はまとめて1000万ポンドで買い取られた{src("Wikipedia", WOS)}。',
                   f'2005年、ハリケーン・カトリーナがアメリカ南部を襲ったとき、ニュース番組が報道の題名を「カトリーナ・アンド・ザ・ウェイヴス」にした。本人は新聞の見出しで「カトリーナ、9人を殺す」を見て「ちょっとショックだった」。それでも「この曲の本当の精神が勝ってほしい」と言った{src("Wikipedia", WOS)}。',
                   '玄関を出るたびに、頭の中でこの曲が勝手に鳴っている。ぼくはたぶん、世界でいちばん長く、この曲を無料で使っている。'],
             bridge='外に出た。街を歩く。ところで、きょうの街は何色だろう。'),
        dict(no='03', artist='大滝詠一', song='君は天然色', album='アルバム『A LONG VACATION』', year='1981.3.21',
             catch='色を失った街に、色をつけてくれと頼んだ歌',
             main=dict(id='L-hyY-1luHs', role='Official MV (40th)', artist='大滝詠一', song='君は天然色', cap=''),
             body=[f'1981年3月21日、アルバム『A LONG VACATION』の1曲目。同じ日にシングルとしても出た{src("Wikipedia", WTEN)}{src("Wikipedia", WALV)}。作詞は松本隆、作曲は大滝詠一。',
                   f'明るい曲に聞こえる。でも、詞が生まれた場所はどん底だった。松本隆は、仲の良かった妹を病気で亡くし、詞が書けなくなっていた。「他の作詞家を探してほしい」と頼んだ松本に、大滝は「君の詞じゃないとだめだから、半年でも1年でも待つ」と返した。アルバムの発売は、半年遅れた{src("Wikipedia", WTEN)}{src("Wikipedia", WALV)}。',
                   f'妹を失った松本の目に、街は色を失って見えた。人が死ぬと、風景は色を失う。だから何色でもいい、染めてほしい。その願いが、歌い出しの一節になった{src("Wikipedia", WTEN)}。知ってから聴くと、サビの明るさの意味が変わる。',
                   f'大滝のほうにも、忘れられない瞬間があった。レコーディングで初めてイントロの演奏を聴いたとき、「『これだよこれ』って。あの瞬間はいまだに忘れられないね。あれ以上に至福の時はなかった」。何年も研究してきたフィル・スペクターの音が、ようやく自分のものになった、と{src("Wikipedia", WTEN)}。'],
             say='サビは本当は、もう一つ高いキーで録るはずだった。歌入れで違和感があって、サビだけ機械で全音下げた（Wikipedia）。いちばん明るく聞こえる場所が、いちばん手を入れた場所。',
             bridge='街に色がついた。日が傾いてきた。土曜の夕方、行き先はひとつ。'),
        dict(no='04', artist='SUGAR BABE', song='DOWN TOWN', album='アルバム『SONGS』', year='1975.4.25',
             catch='土曜の夕方が、街へのパスポートになる',
             main=dict(id='n0MHGGN6CFE', role='Official Trailer', artist='SUGAR BABE', song='DOWN TOWN', cap=''),
             body=[f'1975年4月25日のシングル。詞は伊藤銀次、曲は山下達郎{src("Wikipedia", WDT)}{src("J-Lyric", JLY)}。',
                   f'もとはシュガー・ベイブのための曲ではなかった。ドゥーワップのザ・キング・トーンズのアルバムを作る企画で、伊藤と山下に声がかかった。伊藤の頭にあったのはフォー・トップス、山下はアイズレー・ブラザーズにはまっていて、その要素がイントロに入ってきた。デモを録ったのは、事務所があったビル、いまもボウリング場が入っているビルの一室。伊藤いわく「『DOWN TOWN』は笹塚で生まれた曲」{src("otonano", OTO)}。',
                   f'1980年3月21日、EPOがデビュー曲としてカバーし、フジテレビ『オレたちひょうきん族』のエンディングに使われた。デビュー曲になった経緯がいい。EPOがスタジオでデモを録っていたら、目の前を作曲者の山下達郎が歩いていて、「デビュー曲として出したい」と直接かけ合った{src("Wikipedia", WDT)}。',
                   f'2020年、『レコード・コレクターズ』の「シティ・ポップの名曲ベスト100 1973-1979」で1位に選ばれている{src("Wikipedia", WDT)}。',
                   '金曜の夜より、土曜の夕方のほうが浮かれている。宿題はまだある。でも、まだ見ないことにしている。'],
             bridge='街に出ると、知らない誰かの、いちばん大事な一日が始まっていた。'),
        dict(no='05', artist='Maroon 5', song='Sugar', album='アルバム『V』', year='2015',
             catch='知らない人の結婚式が、ライブ会場になる',
             main=dict(id='09R8_2nJtjg', role='Official MV 2015', artist='Maroon 5', song='Sugar', cap=''),
             body=[f'ロサンゼルスの結婚式に、バンドが予告なしで現れて演奏する。監督は映画『ウェディング・クラッシャーズ』のデヴィッド・ドブキン{src("Wikipedia", WSU)}。',
                   f'始まりは一通のメール。2014年、ドブキンは自分の映画の試写でローマにいて、そこにアダム・レヴィーンから連絡が来た。打ち合わせで出たのが「本物の結婚式に、サプライズのバンドとして現れたら？」。レヴィーンは即座に気に入った{src("Wikipedia", WSU)}。',
                   f'撮影はグレンデールからマリーナ・デル・レイまで、週末の3日間。バンドは毎日10〜12時間、移動と演奏を繰り返した。レヴィーンいわく「段取りは本当にストレスだったけど、最高に楽しかった。気に入ってもらえなかったら、完全な大惨事だった」{src("Southern California Wedding", SCW)}。',
                   f'「あんなに大きな反応が返ってくるとは思わなかった。体から魂が抜けるような体験だった」とも語っている{src("ABC7", ABC)}。'],
             say='知ってたのは新郎だけ（ABC7）。花嫁から見たら、人生でいちばん豪華なドッキリ。ぼくの結婚式に来るのは、たぶん親戚のカラオケ。',
             bridge='知らない人の結婚式で踊ったら、次はちゃんとしたパーティーだ。9月21日の夜のこと、覚えているだろうか。'),
        dict(no='06', artist='Earth, Wind & Fire', song='September', album='『The Best of Earth, Wind & Fire, Vol. 1』', year='1978.11.18',
             catch='「意味なんて、誰が気にする」で、世界が踊った',
             main=dict(id='Gs069dndIYk', role='Official HD Video', artist='Earth, Wind & Fire', song='September', cap=''),
             body=[f'1978年11月18日のシングル。書いたのはモーリス・ホワイトと、作詞家のアリー・ウィリス。ギターのアル・マッケイが作った進行をもとに、1ヶ月かけて仕上げた{src("Wikipedia", WSEP)}。',
                   f'ウィリスは最初、曲のあちこちにホワイトが入れた、意味のない「バディヤ」が気になって仕方なかった。「『バディヤって、どういう意味なの』って聞いたら、彼の答えは要するに『誰が気にするんだ』。作詞人生でいちばん大事な教訓を、彼から学んだ。歌詞を、グルーヴの邪魔にさせるな」{src("Wikipedia", WSEP)}。',
                   f'歌詞に出てくる「9月21日」を、ホワイト本人は「歌ったときの響きで選んだだけ」と言っていた。ところが2019年、妻のマリリンがウォール・ストリート・ジャーナルに明かした。9月21日は、二人の息子の出産予定日だった。初めて曲を聴いたとき「体じゅうが笑顔になった。私たちと息子だけの、秘密のメッセージみたいだった」{src("Wikipedia", WSEP)}。',
                   f'全米R&Bチャート1位、総合8位、イギリス3位。2018年、アメリカ議会図書館の「国家録音登録簿」に入った{src("Wikipedia", WSEP)}。',
                   'ぼくの9月21日は、たぶん何もなかった。でもこの曲が鳴ると、何かあった気がしてくる。'],
             say='「意味なんて、誰が気にする」。会議で3時間かけて直した資料の一文、だいたい誰も気にしてない。モーリス・ホワイトは1978年の時点で、それを知っていた。',
             bridge='踊りながら、ふと思う。そもそも、どうして音楽でこんな気持ちになるのか。音楽そのものにお礼を言った人がいる。'),
        dict(no='07', artist='Stevie Wonder', song='Sir Duke', album='アルバム『Songs in the Key of Life』', year='1976',
             catch='追悼が、全米1位のお祭りになる',
             main=dict(id='ETFvmkIA6S4', role='Official Audio 1976', artist='Stevie Wonder', song='Sir Duke', cap=''),
             body=[f'1974年に亡くなったデューク・エリントンへの捧げもの。アルバム『Songs in the Key of Life』から{src("uDiscover Music", UDD)}{src("Wikipedia", WSD)}。',
                   f'ワンダーはそれまでにも、憧れの2人、ダイナ・ワシントンとウェス・モンゴメリーと組もうとしたところで、相手を亡くしている{src("Wikipedia", WSD)}。1977年6月、本人はこう話した。「題名は最初から決めていた。でも、自分たちのために何かをしてくれた音楽家たちについての歌にしたかった。彼らは、すぐに忘れられてしまうから」{src("uDiscover Music", UDD)}。歌詞にはカウント・ベイシー、グレン・ミラー、ルイ・アームストロング、エラ・フィッツジェラルドも出てくる{src("Wikipedia", WSD)}。',
                   f'冒頭からたたみかけるホーンは、トランペット2本とアルト、テナーのサックス。1977年5月21日から、全米1位を3週続けた{src("uDiscover Music", UDD)}。',
                   '追悼の曲なのに、聴き終わると口笛を吹いている。本人が一番、そうなることを望んでいたと思う。'],
             bridge='理屈はもういい。あとは着替えて、出かけるだけ。'),
        dict(no='08', artist='Bruno Mars', song='24K Magic', album='アルバム『24K Magic』', year='2016.10.7',
             catch='部屋で着替えるだけが、ラスベガスの開演前になる',
             main=dict(id='UqyT8IEBkvY', role='Official MV 2016', artist='Bruno Mars', song='24K Magic', cap=''),
             body=[f'2016年10月7日、アルバム『24K Magic』の先行シングル{src("Wikipedia", W24)}。このアルバムを作るとき、スタジオには服装の決まりがあった。「スウェットで行ったら、スウェットみたいな音になる。だから集めたジュエリーを全部つけて、いちばんいい靴をはいて曲を書いた」{src("Billboard", BB)}。',
                   f'「ライブのことと、自分が開きたいパーティーのことだけを考えた」{src("Billboard", BB)}。表題曲のこのビデオが、その答えだ。',
                   f'同じ2016年、パリで開かれたヴィクトリアズ・シークレットのファッションショーに出たとき、最初に歌ったのは表題曲ではなく、アルバムの「Chunky」だった{src("Teen Vogue", TV)}。パリのランウェイで、いきなりこれ。'],
             more_label='関連動画 — パリのランウェイで、いきなりこれ',
             more=[dict(id='5kEfq8jPsu4', role='Live 2016', artist='Bruno Mars', song='Chunky (Victoria’s Secret 2016 Fashion Show)', cap='')],
             say='パリのランウェイで、いきなりこれ（笑）。看板の「24K Magic」を後ろに回す度胸。ぼくは出かける前に、鏡の前で3回着替えて、結局いつもの黒。',
             bridge='ラスベガスの夜は、止まらない。「止めないでくれ」と歌った人が、1979年にもいた。'),
        dict(no='09', artist='Queen', song="Don't Stop Me Now", album='アルバム『Jazz』', year='1979.1.26',
             catch='ギタリストが嫌いだった、バンドいちばんの多幸感',
             main=dict(id='HgzGwKwLmgM', role='Official Video', artist='Queen', song="Don't Stop Me Now", cap=''),
             body=[f'1978年のアルバム『Jazz』から、1979年1月26日にシングル。書いたのはフレディ・マーキュリー。1978年8月、南フランスの山のスタジオで録った{src("Wikipedia", WDS)}。',
                   f'ブライアン・メイは、この曲が好きではなかった。マーキュリーの快楽的で危なっかしい生き方を祝う歌に聞こえて、怖かった。歌詞にも引っかかりを感じていた{src("Wikipedia", WDS)}。スタジオ版でメイのギターが鳴るのは、ソロの部分だけ{src("Wikipedia", WDS)}。',
                   f'出た当時は、クイーンの曲の中では地味なほうと見られていて、ライブで演奏されたのは1979年だけ。それが2004年の映画『ショーン・オブ・ザ・デッド』で生き返り、2014年にはローリング・ストーン誌の読者投票で、クイーンの曲の3位になった{src("Wikipedia", WDS)}。イギリスの車番組『トップ・ギア』の投票では「史上最高のドライブ曲」{src("Wikipedia", WDS)}。',
                   '金曜の帰り道にこれが鳴ると、歩くのが速くなる。信号は、ちゃんと守っている。'],
             bridge='止まらないまま、夜が深くなる。空が白むまで、あと少し。'),
        dict(no='10', artist='Daft Punk', song='Get Lucky', album='アルバム『Random Access Memories』', year='2013.4.19',
             catch='ロボットとギターの神様が、朝日を待つ曲',
             main=dict(id='5NV6Rdv1a3I', role='Official Audio 2013', artist='Daft Punk', song='Get Lucky (feat. Pharrell Williams, Nile Rodgers)', cap=''),
             body=[f'2013年4月19日、ダフト・パンク最後のアルバム『Random Access Memories』の先行シングル。歌はファレル・ウィリアムス、ギターはシックのナイル・ロジャース{src("Wikipedia", WGL)}。',
                   f'ダフト・パンクとロジャースが出会ったのは1997年、デビュー作『Homework』の試聴会。友だちになったのに、すれ違いが続いて組めないまま、ようやくニューヨークのエレクトリック・レディ・スタジオで実現した。最初、曲はウーリッツァーの電気ピアノを中心にした粗い形だった。デモを聴いたロジャースは、ドラム以外を全部外してくれ、と頼んだ{src("Wikipedia", WGL)}。',
                   f'ファレルいわく、題名は「うまくいく」だけの意味じゃない。会いたい人に会えた、という幸運のことでもある。この音から浮かんだのは、南の島の、桃色の夜明け{src("Wikipedia", WGL)}。',
                   f'2014年のグラミー賞で、最優秀レコード賞。授賞式のステージには、スティーヴィー・ワンダーも並んだ{src("Wikipedia", WGL)}。1976年の章の主役が、2013年の章に顔を出す。'],
             say='ロボット2体と、ギターの神様と、この次に出てくる「9回ボツの男」。朝まで踊る布陣として、これ以上はない。ぼくは終電で帰ります。',
             bridge='桃色の夜明けにいたファレルは、同じ年、もう一曲作っていた。最後に、これをどうぞ。'),
        dict(no='11', artist='Pharrell Williams', song='Happy', album='映画『怪盗グルーのミニオン危機一発』サウンドトラック', year='2013',
             catch='最後に、これをどうぞ',
             main=dict(id='ZbZSe6N_BXs', role='Official MV 2013', artist='Pharrell Williams', song='Happy', cap=''),
             body=[f'映画『怪盗グルーのミニオン危機一発』のために書いた曲。でも最初からハッピーだったわけではない。恋に落ちたグルーの曲を、9回出して9回ボツにされた{src("NME", NME)}。本人いわく「9曲出して『これは違う』。落ち込んだし、プライドはズタズタ。でも10曲目のとき、もう何も残ってなかった」{src("Creative Review", CR)}。',
                   f'そうして生まれたこの曲は、2013年11月21日、「世界初の24時間ミュージックビデオ」と一緒にシングルになった{src("Wikipedia", WHAP)}{src("24 Hours of Happy", H24)}。上のはその4分の公式版。翌2014年、世界でいちばん売れた曲になった{src("Wikipedia", WHAP)}。',
                   '人はなぜ音楽を聴くのか。第1回の答えが、題名にそのまま書いてある。だから最後に置いた。'],
             say='世界中の人がこの曲で踊る映像を、オプラの番組で見せられて、本人が泣いた。「なんでオプラの前で泣いてるんだ」（Rolling Stone）。ハッピーの作者が、いちばん泣いている。',
        ),
    ],
    close=['人はなぜ音楽を聴くのか。今日の答えは「楽しくなりたいから」。',
           '朝の18秒から、桃色の夜明けまで。楽しい曲の裏側には、陽気じゃなかったバンドも、妹を亡くした作詞家も、9回ボツをくらった男もいた。それでも曲は、楽しいほうを向いていた。',
           'でも、答えはひとつじゃない。次回のレポートもお楽しみに。'],
    sources=[('American Songwriter — Lovely Day', AMS), ('Songfacts — Lovely Day', SFL), ('Wikipedia — Lovely Day', WLD),
             ('Wikipedia — Walking on Sunshine (Katrina and the Waves song)', WOS), ('Wikipedia — Katrina and the Waves', WKW),
             ('Wikipedia — 君は天然色', WTEN), ('Wikipedia — A LONG VACATION', WALV),
             ('otonano — 伊藤銀次が語るシュガー・ベイブ', OTO), ('Wikipedia — DOWN TOWN', WDT), ('J-Lyric — シュガーベイブ', JLY),
             ('Southern California Wedding — Maroon 5 Sugar', SCW), ('ABC7 — Maroon 5 Sugar', ABC), ('Wikipedia — Sugar (Maroon 5 song)', WSU),
             ('Wikipedia — September (song)', WSEP),
             ('uDiscover Music — Sir Duke', UDD), ('Wikipedia — Sir Duke', WSD),
             ('Wikipedia — 24K Magic (song)', W24), ('Billboard — Bruno Mars 24K Magic interview', BB), ('Teen Vogue — Chunky at VS Show 2016', TV),
             ('Wikipedia — Don’t Stop Me Now', WDS),
             ('Wikipedia — Get Lucky (Daft Punk song)', WGL),
             ('NME — Pharrell rejected nine times', NME), ('Creative Review — How Pharrell got Happy', CR), ('Wikipedia — Happy (Pharrell Williams song)', WHAP), ('24 Hours of Happy', H24), ('Rolling Stone — Pharrell cries on Oprah', RS),
             ('Spotify — 多幸感ポップス', SPOT)],
    note='',
    i18n=I18N,
)

if __name__ == '__main__':
    print(write(M))
