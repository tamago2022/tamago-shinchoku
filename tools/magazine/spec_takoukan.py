import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src

# 2026-10-18 全開便（120052）：型＝「怒れる人々 vol.1」（10-18確定）にそろえた版。6曲→10曲、章頭の型、吹き出し、つなぎ、5言語。
# 事実は下の出典で本文を確かめたものだけ（wiki_lookup.py で取得・2026-10-18）。Sugar の「本物の結婚式」は両論あるので直した。
_HERE = os.path.dirname(os.path.abspath(__file__))
_I18N_P = os.path.join(_HERE, 'i18n_takoukan.json')
I18N = json.load(open(_I18N_P, encoding='utf-8')) if os.path.exists(_I18N_P) else None  # 5言語（訳だけ直すときはこのファイル）

# 01 Lovely Day
SFL = 'https://www.songfacts.com/facts/bill-withers/lovely-day'
AMS = 'https://americansongwriter.com/this-bill-withers-classic-borrowed-its-good-vibes-from-a-famously-jolly-songwriter/'
WLD = 'https://en.wikipedia.org/wiki/Lovely_Day'
# 02 Here Comes the Sun
WHCS = 'https://en.wikipedia.org/wiki/Here_Comes_the_Sun'
JHCS = 'https://ja.wikipedia.org/wiki/%E3%83%92%E3%82%A2%E3%83%BB%E3%82%AB%E3%83%A0%E3%82%BA%E3%83%BB%E3%82%B6%E3%83%BB%E3%82%B5%E3%83%B3'
# 03 君は天然色
JKT = 'https://ja.wikipedia.org/wiki/%E5%90%9B%E3%81%AF%E5%A4%A9%E7%84%B6%E8%89%B2'
JALV = 'https://ja.wikipedia.org/wiki/A_LONG_VACATION'
# 04 DOWN TOWN
OTO = 'https://otonanoweb.jp/s/magazine/diary/detail/10695'
WDT = 'https://ja.wikipedia.org/wiki/DOWN_TOWN_(%E3%82%B7%E3%83%A5%E3%82%AC%E3%83%BC%E3%83%BB%E3%83%99%E3%82%A4%E3%83%96%E3%81%AE%E6%9B%B2)'
# 05 Sugar
SCW = 'https://southerncaliforniawedding.com/flashback-when-your-wedding-is-crashed-by-maroon-5/'
ABC = 'https://abc7news.com/post/watch-maroon-5-crash-real-live-weddings-for-their-music-video/476505/'
WSU = 'https://en.wikipedia.org/wiki/Sugar_(Maroon_5_song)'
# 06 Sir Duke
UDD = 'https://www.udiscovermusic.com/stories/stevie-wonder-sir-duke-song/'
WSD = 'https://en.wikipedia.org/wiki/Sir_Duke'
# 07 September
WSEP = 'https://en.wikipedia.org/wiki/September_(song)'
SFSEP = 'https://www.songfacts.com/facts/earth-wind-fire/september'
# 08 24K Magic
BB = 'https://www.billboard.com/music/music-news/bruno-mars-24k-magic-interview-7581250/'
TV = 'https://www.teenvogue.com/story/bruno-mars-vs-show-2016-chunky-performance'
NYL = 'https://www.nylon.com/articles/the-weeknd-lady-gaga-bruno-mars-2016-victorias-secret-performances'
# 09 Don't Stop Me Now
WDSM = 'https://en.wikipedia.org/wiki/Don%27t_Stop_Me_Now'
# 10 Happy
NME = 'https://www.nme.com/news/music/pharrell-williams-25-1214292'
CR = 'https://www.creativereview.co.uk/happy-pharrell-williams/'
H24 = 'https://24hoursofhappy.com/'
RS = 'https://www.rollingstone.com/music/music-news/watch-pharrell-cry-over-happy-inspiration-231769/'
SPOT = 'https://open.spotify.com/playlist/2yL7HHEf409bLqO57CDHBB'

M = dict(
    key='takoukan', file='naze-ongaku-01-takoukan.html', title='人はなぜ音楽を聴くのか 第1回 楽しくなりたいから ― 多幸感ポップス',
    desc='人はなぜ音楽を聴くのか。第1回の答えは「楽しくなりたいから」。Bill Withers、The Beatles、大滝詠一、SUGAR BABE、Maroon 5、Stevie Wonder、Earth, Wind & Fire、Bruno Mars、Queen、Pharrell Williams。10曲で一日をたどる。',
    hero='ZbZSe6N_BXs', eyebrow='Why do we listen to music? — Report 01 · 10 songs',
    h1='楽しくなりたいから',
    lead='人はなぜ音楽を聴くのか。第1回の答えは、たぶんこれ。<br/>「頑張れ」と説得してこないのに、勝手に口角が上がる10曲。ぜんぶ、このページの中で聴ける。',
    big='人はなぜ音楽を聴くのか。<br/>いちばん最初に浮かぶ答えは、「楽しくなりたいから」。',
    open=['何もしたくない朝から、着替えて出かける夜まで。10曲で、一日をたどってみる。',
          'どの曲にも、楽しさが生まれた現場がある。会議をさぼった庭、色を失った街、笹塚の部屋、（たぶん）本物の結婚式、意味のない「バディヤ」、9回ボツをくらった作曲家。',
          '楽しい曲は、楽しい人が楽しい日に書いたとは限らない。むしろ逆のことが多い。それを知ってから聴くと、同じ曲が、少し違って聞こえる。'],
    door=f'この10曲の続きは、Spotifyのプレイリスト<a href="{SPOT}" target="_blank" rel="noopener noreferrer">「多幸感ポップス」</a>で。',
    paper=[],
    chapters=[
        dict(no='01', artist='Bill Withers', song='Lovely Day', album='アルバム『Menagerie』', year='1977',
             catch='目が覚めるだけで、いい日の始まりになる',
             main=dict(id='bEeaS6fuUoA', role='Official Audio 1977', artist='Bill Withers', song='Lovely Day', cap=''),
             body=[f'1977年のアルバム『Menagerie』から。曲を用意したのはスキップ・スカーボロー、そこにウィザースが言葉を乗せた{src("American Songwriter", AMS)}{src("Songfacts", SFL)}。',
                   f'このスカーボローが、根っからの陽気な人だった。その気分が、そのまま歌詞に入り込んだ{src("American Songwriter", AMS)}。歌の主人公は、つらい朝があることを隠さない。それでも、あなたを見ればいい日になる。',
                   f'ヒットから遠ざかっていたウィザースは、この曲で全米30位に返り咲き、イギリスではトップ10に入った{src("American Songwriter", AMS)}{src("Wikipedia", WLD)}。',
                   '月曜の朝、目覚ましを3回止めたあとにこれを流す。布団から出る理由にはならないけれど、出てもいいか、くらいにはなる。'],
             say=f'最後の「デ〜〜イ」、18秒伸ばしてる。全米トップ40のヒット曲で、いちばん長く伸ばした一声{src("Wikipedia", WLD)}。歯磨き、終わります。',
             bridge='布団から出たら、カーテンを開ける。その一瞬のための曲が、1969年の春、会議をさぼった庭で書かれていた。'),
        dict(no='02', artist='The Beatles', song='Here Comes the Sun', album='アルバム『Abbey Road』B面1曲目', year='1969.9.26',
             catch='会議をさぼって庭に出たら、太陽が出てきた',
             main=dict(id='GKdl-GCsNJ0', role='2019 Mix', artist='The Beatles', song='Here Comes the Sun', cap=''),
             body=[f'1969年の春。ジョージ・ハリスンは、ビートルズの会社アップルの会議に行くのが心底いやになっていた。本人いわく「ある日、アップルをさぼることにして、エリック・クラプトンの家に行った。あの間抜けな会計士たちに会わなくていい解放感はすばらしかった。エリックのアコースティックギターを1本借りて、庭を歩きながら『Here Comes the Sun』を書いた」{src("Wikipedia", WHCS)}。',
                   f'録音は7月7日、13テイク。ジョン・レノンはこの曲に参加していない。交通事故のけがで療養中だった{src("Wikipedia", WHCS)}{src("Wikipedia", JHCS)}。仕上げは8月19日、ハリスンがカリフォルニアで手に入れたモーグ・シンセサイザーを重ねて完成。2番ではギターの旋律をなぞり、3番では1オクターブ上で別の旋律を歌う{src("Wikipedia", WHCS)}。',
                   f'アルバム『Abbey Road』は1969年9月26日発売。この曲はB面の1曲目に置かれた{src("Wikipedia", WHCS)}。',
                   f'1977年、天文学者のカール・セーガンが、探査機ボイジャーに積む「地球の音楽の盤」にこの曲を入れようとした。ビートルズは乗り気だったが、権利を持っていたのはビートルズではなく、レコード会社。EMIが許可を出さず、太陽の歌は宇宙に行けなかった{src("Wikipedia", WHCS)}{src("Wikipedia", JHCS)}。',
                   f'地球では、ちゃんと届いている。2023年5月、ビートルズの曲で初めて、Spotifyの再生回数が10億を超えた{src("Wikipedia", WHCS)}。'],
             bridge='さぼった庭に太陽が出た。でも、太陽が出ているのに世界に色が無い日もある。1981年の東京に、そんな目で街を見ていた作詞家がいた。'),
        dict(no='03', artist='大滝詠一', song='君は天然色', album='シングル／アルバム『A LONG VACATION』1曲目', year='1981.3.21',
             catch='色を失った街で、「色をつけてくれ」と書いた人',
             main=dict(id='L-hyY-1luHs', role='Official MV (40th Anniversary)', artist='大滝詠一', song='君は天然色', cap=''),
             body=[f'1981年3月21日、大滝詠一の通算7作目のシングル。同じ日に出たアルバム『A LONG VACATION』の1曲目でもある。作詞は松本隆、作曲は大瀧詠一、編曲は多羅尾伴内{src("Wikipedia", JKT)}。',
                   f'聴けば、まぶしい夏の曲だ。でも、詞が書かれたのは、まぶしさとは正反対の場所だった。松本隆は、仲の良かった妹を病気で亡くし、書けなくなっていた。「ほかの作詞家を探してほしい」と頼んだ松本に、大滝は「君の詞じゃないとだめだから半年でも1年でも待つ」と答えた。アルバムの発売は、半年遅れた{src("Wikipedia", JKT)}{src("Wikipedia", JALV)}。',
                   f'そのどん底で見た街の色から、「想い出はモノクローム」という一行が出てきた。続く「色を点けてくれ」について、松本はこう語っている。「人が死ぬと風景は色を失う。だから何色でもいい。染めてほしいとの願いだった」{src("Wikipedia", JKT)}。',
                   dict(say=f'この曲、最初は大滝が須藤薫さんに書いた提供曲の候補だった。「男性向きではないか」という意見で不採用になり、のちに「君は天然色」になった{src("Wikipedia", JKT)}。不採用の曲が、45年後の今もアルバムの1曲目に座っている。履歴書の不採用通知、全部とっておこうと思う。'),
                   f'録音では、サビを全音上に転調する予定だったが、歌入れのとき声に乗らなかった。大滝は「よし、サビだけキーを下げよう」と、ハーモナイザーでサビだけ全音下げた。下がって薄くなった高い音は、パーカッションのベルを重ねて補った{src("Wikipedia", JKT)}。',
                   '夏の歌だと思って聴いていた曲が、誰かの冬から生まれていた。知ってから聴くと、イントロの明るさが、少しだけ違って聞こえる。'],
             bridge='色がついた。じゃあ、街へ出よう。土曜の夕方に。'),
        dict(no='04', artist='SUGAR BABE', song='DOWN TOWN', album='シングル', year='1975.4.25',
             catch='土曜の夕方が、街へのパスポートになる',
             main=dict(id='n0MHGGN6CFE', role='Official Trailer', artist='SUGAR BABE', song='DOWN TOWN', cap=''),
             body=[f'1975年4月25日のシングル。詞は伊藤銀次、曲は山下達郎{src("Wikipedia", WDT)}。',
                   f'もとはシュガー・ベイブのための曲ではなかった。ドゥーワップのザ・キング・トーンズのアルバムを作る企画で、伊藤と山下に声がかかった。伊藤の頭にあったのはフォー・トップス、山下はアイズレー・ブラザーズにはまっていて、その要素がイントロに入ってきた。伊藤いわく「『DOWN TOWN』は笹塚で生まれた曲」{src("otonano", OTO)}。',
                   f'1980年3月21日、EPOがデビュー曲としてカバーし、フジテレビ『オレたちひょうきん族』のエンディングに使われた。デビュー曲になった経緯がいい。EPOがスタジオでデモを録っていたら、作曲者の山下達郎が目の前を歩いていた。その場で「デビュー曲として出したい」と直接かけ合った{src("Wikipedia", WDT)}。',
                   f'2020年、『レコード・コレクターズ』の「シティ・ポップの名曲ベスト100 1973-1979」で1位に選ばれている{src("Wikipedia", WDT)}。笹塚の部屋で生まれた曲が、45年後に1位。'],
             bridge='街に出ると、知らない誰かの、いちばん大事な一日が始まっていた。'),
        dict(no='05', artist='Maroon 5', song='Sugar', album='シングル', year='2015',
             catch='知らない人の結婚式が、ライブ会場になる（たぶん）',
             main=dict(id='09R8_2nJtjg', role='Official MV 2015', artist='Maroon 5', song='Sugar', cap=''),
             body=[f'ロサンゼルスの結婚式に、バンドが予告なしで現れて演奏する。監督は映画『ウェディング・クラッシャーズ』のデヴィッド・ドブキン。言い出したのも監督で、「本物の結婚式に、サプライズのバンドとして現れたらどうだ？」。アダム・レヴィーンは即、乗った{src("Wikipedia", WSU)}。',
                   f'知らせたのは新郎だけ。しかもバンド名は伏せて、「とても人気があって、賞もいくつか取っている」とだけ。撮影が近づくと新郎たちはみんな怖気づいて、やめたいと言い出した。ドブキンは一人ずつ会って、説得した{src("Wikipedia", WSU)}。',
                   f'撮影はグレンデールからマリーナ・デル・レイまで、週末の3日間。バンドは毎日10〜12時間、移動と演奏を繰り返した。レヴィーンいわく「段取りは本当にストレスだったけど、最高に楽しかった。気に入ってもらえなかったら、完全な大惨事だった」{src("Southern California Wedding", SCW)}。「あんなに大きな反応が返ってくるとは思わなかった。体から魂が抜けるような体験だった」{src("ABC7", ABC)}。',
                   f'ただし、全部が本物だったかは、いまも議論がある。『ローリング・ストーン』などは「仕込みで、同じ場所で3日かけて撮った」と報じ、花嫁の両親役を演じたという俳優は「全部仕込みだった」と語った。一方で USA Today の記者は、現場にいた結婚式の写真家に取材して、少なくとも2組は本物だったと書いている{src("Wikipedia", WSU)}。',
                   '本物か、仕込みか。どちらにしても、踊っている人たちの顔は、作りものには見えない。'],
             say='花嫁から見たら、人生でいちばん豪華なドッキリ。僕の披露宴には来てくれなかった。呼んでいないし、披露宴もしていない。',
             bridge='そもそも、どうして音楽を聴くとこんな気持ちになるのか。音楽そのものにお礼を言った人がいる。'),
        dict(no='06', artist='Stevie Wonder', song='Sir Duke', album='アルバム『Songs in the Key of Life』', year='1976',
             catch='追悼が、全米1位のお祭りになる',
             main=dict(id='ETFvmkIA6S4', role='Official Audio 1976', artist='Stevie Wonder', song='Sir Duke', cap=''),
             body=[f'1974年に亡くなったデューク・エリントンへの捧げもの。アルバム『Songs in the Key of Life』から{src("uDiscover Music", UDD)}{src("Wikipedia", WSD)}。',
                   f'1977年6月、本人はこう話している。「題名は最初から決めていた。でも、自分たちのために何かをしてくれた音楽家たちについての歌にしたかった。彼らは、すぐに忘れられてしまうから」{src("uDiscover Music", UDD)}。歌詞にはカウント・ベイシー、グレン・ミラー、ルイ・アームストロング、エラ・フィッツジェラルドも出てくる{src("Wikipedia", WSD)}。',
                   f'スティーヴィーは、憧れの人に先立たれるのが初めてではなかった。ダイナ・ワシントン、ウェス・モンゴメリー。一緒にやろうとした矢先に、二人とも亡くしている。だからエリントンが亡くなったとき、「大事な人たちの名前を歌に残す」と決めた{src("Wikipedia", WSD)}。',
                   f'冒頭からたたみかけるホーンは、トランペット2本とアルト、テナーのサックス。1977年5月21日から、全米1位を3週続けた{src("uDiscover Music", UDD)}。お葬式の歌が、お祭りの歌になった。'],
             bridge='名前を残す歌の次は、意味を残さなかった歌。歌詞に意味が無くても、人は踊れるのか。'),
        dict(no='07', artist='Earth, Wind & Fire', song='September', album='シングル（ベスト盤『The Best of Earth, Wind & Fire, Vol. 1』の新曲）', year='1978.11.18',
             catch='「バディヤ」の意味を聞いたら、「誰が気にする？」',
             main=dict(id='Gs069dndIYk', role='Official HD Video', artist='Earth, Wind & Fire', song='September', cap=''),
             body=[f'1978年11月18日のシングル。書いたのはアリー・ウィリスとモーリス・ホワイト。土台はギターのアル・マッケイが作った音の並び。全米R&Bチャートで1位、Hot 100で8位、イギリスで3位{src("Wikipedia", WSEP)}。',
                   f'ウィリスにとっては、このバンドと書いた最初の曲で、最初の大ヒット。スタジオのドアを開けた瞬間、あのギターのイントロが鳴っていた。「ああ神様、どうかこれが、私と一緒にやりたい曲でありますように。だって、どう聴いてもヒットだったから」{src("Songfacts", SFSEP)}。',
                   f'サビで繰り返される「バディヤ」は、仮の歌詞だった。ウィリスは最後まで本物の言葉に差し替えたくて、ホワイトに「バディヤって、どういう意味なの？」と食い下がった。返事は、要するに「誰が気にする？」。ウィリスはのちに「作詞でいちばん大きな教訓をもらった。歌詞をグルーヴの邪魔にさせるな、ということ」と語っている{src("Wikipedia", WSEP)}{src("Songfacts", SFSEP)}。',
                   f'ベスト盤に「新曲も入っています」と書くためだけに作られた曲だった{src("Wikipedia", WSEP)}。それが2018年、アメリカ議会図書館の「文化的・歴史的に重要な録音」に登録される{src("Wikipedia", WSEP)}。',
                   '意味のない言葉を、意味のある言葉に直さなかった。それで、47年間、世界中が同じところで同じ声を出している。'],
             say=f'「9月21日の夜」に意味はあるのか。ホワイトは生前、ウィリスに「意味はない、歌ったときの響きで選んだ」と言っていた。でも2018年、亡くなったあとで妻のマリリンが明かした。21日は、息子カブランの出産予定日だった（息子は8月1日に早産で生まれた）{src("Songfacts", SFSEP)}。ベースのヴァーディン・ホワイトいわく、いまは9月21日に結婚する人が増えているらしい{src("Songfacts", SFSEP)}。',
             bridge='踊る準備はできた。あとは着替えるだけ。ただし、着替えにも流儀がある。'),
        dict(no='08', artist='Bruno Mars', song='24K Magic', album='アルバム『24K Magic』表題曲', year='2016',
             catch='部屋で着替えるだけが、ラスベガスの開演前になる',
             main=dict(id='UqyT8IEBkvY', role='Official MV 2016', artist='Bruno Mars', song='24K Magic', cap=''),
             body=[f'このアルバムを作るとき、スタジオには服装の決まりがあった。「スウェットで行ったら、スウェットみたいな音になる。だから集めたジュエリーを全部つけて、いちばんいい靴をはいて曲を書いた」{src("Billboard", BB)}。',
                   f'「ライブのことと、自分が開きたいパーティーのことだけを考えた」{src("Billboard", BB)}。表題曲のこのビデオが、その答えだ。',
                   f'同じ2016年、パリで開かれたヴィクトリアズ・シークレットのファッションショーに出たとき、最初に歌ったのは表題曲ではなく、アルバムの「Chunky」だった{src("Teen Vogue", TV)}{src("NYLON", NYL)}。パリのランウェイで、いきなりこれ。',
                   '部屋着で書くと部屋着の音になる、は、たぶん音楽以外にも当てはまる。在宅勤務の日に一度だけ革靴をはいてみたが、メールの文面は変わらなかった。'],
             more_label='関連動画 — パリのランウェイで、いきなりこれ',
             more=[dict(id='5kEfq8jPsu4', role='Live 2016', artist='Bruno Mars', song='Chunky (Victoria’s Secret 2016 Fashion Show)', cap='')],
             say='パリのランウェイで、いきなりこれ（笑）。看板の「24K Magic」を後ろに回す度胸。',
             bridge='着替えて、靴をはいて、玄関を出る。ここから先は、誰にも止められない。'),
        dict(no='09', artist='Queen', song="Don't Stop Me Now", album='シングル（アルバム『Jazz』収録）', year='1979.1.26',
             catch='ギターの人が、いちばん好きじゃなかった曲',
             main=dict(id='HgzGwKwLmgM', role='Official Video 4K', artist='Queen', song="Don't Stop Me Now", cap=''),
             body=[f'1978年のアルバム『Jazz』に入り、1979年1月26日にシングルになった。書いたのはフレディ・マーキュリー。イギリスで9位、アメリカでは86位どまり{src("Wikipedia", WDSM)}。',
                   f'このバンドの中で、この曲をいちばん好きじゃなかったのが、ギターのブライアン・メイだ。当時のフレディの、快楽的で危なっかしい暮らしぶりをそのまま讃えているように聞こえて、怖かった、という{src("Wikipedia", WDSM)}。スタジオ版でブライアンのギターが鳴るのは、ソロのところだけ。ライブでは全部弾いたけれど{src("Wikipedia", WDSM)}。',
                   f'ところがこの曲は、出たときより、あとになって大きくなった。ビルボードの記者は、生き返ったきっかけを2004年の映画『ショーン・オブ・ザ・デッド』に見ている{src("Wikipedia", WDSM)}。2014年にはローリング・ストーン誌の読者投票で、クイーンの曲の3位{src("Wikipedia", WDSM)}。',
                   f'そしてブライアンは、考えを変えた。結婚式で、パーティーで、お葬式で、この曲がかかるのを何度も聞くうちに、これは「大きな喜び」を表す曲なんだ、と受け止めるようになった{src("Wikipedia", WDSM)}。',
                   '書いた本人はもういない。いちばん心配していた人が、いちばん長くこの曲を弾いている。'],
             say=f'イギリスの自動車番組『トップ・ギア』の投票で「史上最高のドライブ曲」に選ばれている{src("Wikipedia", WDSM)}。運転中にかけると、制限速度のことは忘れる。忘れてはいけない。',
             bridge='踊り疲れたところで、最後にこれをどうぞ。'),
        dict(no='10', artist='Pharrell Williams', song='Happy', album='映画『怪盗グルーのミニオン危機一発』サウンドトラック', year='2013',
             catch='最後に、これをどうぞ',
             main=dict(id='ZbZSe6N_BXs', role='Official MV 2013', artist='Pharrell Williams', song='Happy', cap=''),
             body=[f'映画『怪盗グルーのミニオン危機一発』のために書いた曲。でも最初からハッピーだったわけではない。恋に落ちたグルーの曲を、9回出して9回ボツにされた{src("NME", NME)}。本人いわく「9曲出して『これは違う』。落ち込んだし、プライドはズタズタ。でも10曲目のとき、もう何も残ってなかった」{src("Creative Review", CR)}。',
                   f'そうして生まれたこの曲に、「世界初の24時間ミュージックビデオ」がついた{src("24 Hours of Happy", H24)}。上のはその4分版。',
                   '人はなぜ音楽を聴くのか。第1回の答えが、題名にそのまま書いてある。だから最後に置いた。'],
             say=f'世界中の人がこの曲で踊る映像を、オプラ・ウィンフリーの番組で見せられて、本人が泣いた。「なんでオプラの前で泣いてるんだ」{src("Rolling Stone", RS)}。ハッピーの作者が、いちばん泣いている。',
        ),
    ],
    close=['人はなぜ音楽を聴くのか。今日の答えは「楽しくなりたいから」。',
           '会議をさぼった庭。色を失った街。笹塚の部屋。断られ続けた作曲家。楽しい曲の後ろには、だいたい、楽しくなかった日がある。',
           'でも、答えはひとつじゃない。',
           '次回のレポートもお楽しみに。'],
    sources=[('American Songwriter — Lovely Day', AMS), ('Songfacts — Lovely Day', SFL), ('Wikipedia — Lovely Day', WLD),
             ('Wikipedia — Here Comes the Sun', WHCS), ('Wikipedia — ヒア・カムズ・ザ・サン', JHCS),
             ('Wikipedia — 君は天然色', JKT), ('Wikipedia — A LONG VACATION', JALV),
             ('otonano — 伊藤銀次が語るシュガー・ベイブ', OTO), ('Wikipedia — DOWN TOWN', WDT),
             ('Southern California Wedding — Maroon 5 Sugar', SCW), ('ABC7 — Maroon 5 Sugar', ABC), ('Wikipedia — Sugar (Maroon 5 song)', WSU),
             ('uDiscover Music — Sir Duke', UDD), ('Wikipedia — Sir Duke', WSD),
             ('Wikipedia — September (song)', WSEP), ('Songfacts — September', SFSEP),
             ('Billboard — Bruno Mars 24K Magic interview', BB), ('Teen Vogue — Chunky at VS Show 2016', TV), ('NYLON — 2016 Victoria’s Secret performances', NYL),
             ('Wikipedia — Don’t Stop Me Now', WDSM),
             ('NME — Pharrell rejected nine times', NME), ('Creative Review — How Pharrell got Happy', CR), ('24 Hours of Happy', H24), ('Rolling Stone — Pharrell cries on Oprah', RS), ('Spotify — 多幸感ポップス', SPOT)],
    note='',
    i18n=I18N,
)

if __name__ == '__main__':
    print(write(M))
