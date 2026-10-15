import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src

SFL = 'https://www.songfacts.com/facts/bill-withers/lovely-day'
AMS = 'https://americansongwriter.com/this-bill-withers-classic-borrowed-its-good-vibes-from-a-famously-jolly-songwriter/'
WLD = 'https://en.wikipedia.org/wiki/Lovely_Day'
OTO = 'https://otonanoweb.jp/s/magazine/diary/detail/10695'
WDT = 'https://ja.wikipedia.org/wiki/DOWN_TOWN_(%E3%82%B7%E3%83%A5%E3%82%AC%E3%83%BC%E3%83%BB%E3%83%99%E3%82%A4%E3%83%96%E3%81%AE%E6%9B%B2)'
JLY = 'https://j-lyric.net/artist/a04ab93/'
SCW = 'https://southerncaliforniawedding.com/flashback-when-your-wedding-is-crashed-by-maroon-5/'
ABC = 'https://abc7news.com/post/watch-maroon-5-crash-real-live-weddings-for-their-music-video/476505/'
WSU = 'https://en.wikipedia.org/wiki/Sugar_(Maroon_5_song)'
UDD = 'https://www.udiscovermusic.com/stories/stevie-wonder-sir-duke-song/'
WSD = 'https://en.wikipedia.org/wiki/Sir_Duke'
BB = 'https://www.billboard.com/music/music-news/bruno-mars-24k-magic-interview-7581250/'
TV = 'https://www.teenvogue.com/story/bruno-mars-vs-show-2016-chunky-performance'
NYL = 'https://www.nylon.com/articles/the-weeknd-lady-gaga-bruno-mars-2016-victorias-secret-performances'
NME = 'https://www.nme.com/news/music/pharrell-williams-25-1214292'
CR = 'https://www.creativereview.co.uk/happy-pharrell-williams/'
H24 = 'https://24hoursofhappy.com/'
RS = 'https://www.rollingstone.com/music/music-news/watch-pharrell-cry-over-happy-inspiration-231769/'
SPOT = 'https://open.spotify.com/playlist/2yL7HHEf409bLqO57CDHBB'

M = dict(
    key='takoukan', file='naze-ongaku-01-takoukan.html', title='人はなぜ音楽を聴くのか 第1回 楽しくなりたいから ― 多幸感ポップス',
    desc='人はなぜ音楽を聴くのか。第1回の答えは「楽しくなりたいから」。Bill Withers、SUGAR BABE、Maroon 5、Stevie Wonder、Bruno Mars、Pharrell Williams。6曲で一日をたどる。',
    hero='ZbZSe6N_BXs', eyebrow='Why do we listen to music? — Report 01 · 6 songs',
    h1='楽しくなりたいから',
    lead='人はなぜ音楽を聴くのか。第1回の答えは、たぶんこれ。<br/>「頑張れ」と説得してこないのに、勝手に口角が上がる6曲。ぜんぶ、このページの中で聴ける。',
    big='人はなぜ音楽を聴くのか。<br/>いちばん最初に浮かぶ答えは、「楽しくなりたいから」。',
    open=['何もしたくない朝から、着替えて出かける夜まで。6曲で、一日をたどってみる。',
          'どの曲にも、楽しさが生まれた現場がある。スタジオにいた一人の楽天家、ボウリング場のあるビルの一室、本物の結婚式、9回ボツをくらった作曲家。'],
    door=f'この6曲の続きは、Spotifyのプレイリスト<a href="{SPOT}" target="_blank" rel="noopener noreferrer">「多幸感ポップス」</a>で。',
    paper=[],
    chapters=[
        dict(no='01', en='目が覚めるだけで、いい日の始まりになる', title='Bill Withers - Lovely Day', year='1977',
             main=dict(id='bEeaS6fuUoA', role='Official Audio 1977', artist='Bill Withers', song='Lovely Day', cap='BillWithersVEVO。1億回以上再生されている'),
             body=[f'1977年のアルバム『Menagerie』から。曲を用意したのはスキップ・スカーボロー、そこにウィザースが言葉を乗せた{src("American Songwriter", AMS)}{src("Songfacts", SFL)}。',
                   f'このスカーボローが、根っからの陽気な人だった。その気分が、そのまま歌詞に入り込んだ{src("American Songwriter", AMS)}。歌の主人公は、つらい朝があることを隠さない。それでも、あなたを見ればいい日になる。',
                   f'ヒットから遠ざかっていたウィザースは、この曲で全米30位に返り咲き、イギリスではトップ10入りした{src("American Songwriter", AMS)}。'],
             say='最後の「デ〜〜イ」、18秒伸ばしてる（Songfacts／Wikipedia）。歯磨き、終わります。',
             bridge='朝をやり過ごしたら、夕方。そろそろ、街へ出よう。'),
        dict(no='02', en='土曜の夕方が、街へのパスポートになる', title='SUGAR BABE - DOWN TOWN', year='1975',
             main=dict(id='n0MHGGN6CFE', role='Official Trailer', artist='SUGAR BABE', song='DOWN TOWN', cap='Sony Music (Japan) 公式のトレーラー'),
             body=[f'1975年4月25日のシングル。詞は伊藤銀次、曲は山下達郎{src("Wikipedia", WDT)}{src("J-Lyric", JLY)}。',
                   f'もとはシュガー・ベイブのための曲ではなかった。ドゥーワップのザ・キング・トーンズのアルバムを作る企画で、伊藤と山下に声がかかった。伊藤の頭にあったのはフォー・トップス、山下はアイズレー・ブラザーズにはまっていて、その要素がイントロに入ってきた。伊藤いわく「『DOWN TOWN』は笹塚で生まれた曲」{src("otonano", OTO)}。',
                   f'1980年、EPOがデビュー曲としてカバーし、フジテレビ『オレたちひょうきん族』のエンディングに使われた。2020年には『レコード・コレクターズ』の「シティ・ポップの名曲ベスト100 1973-1979」で1位に選ばれている{src("Wikipedia", WDT)}。'],
             bridge='街に出ると、知らない誰かの、いちばん大事な一日が始まっていた。'),
        dict(no='03', en='知らない人の結婚式が、ライブ会場になる', title='Maroon 5 - Sugar', year='2015',
             main=dict(id='09R8_2nJtjg', role='Official MV 2015', artist='Maroon 5', song='Sugar', cap='Maroon5VEVO'),
             body=[f'ロサンゼルスの結婚式に、バンドが予告なしで現れて演奏する。監督は映画『ウェディング・クラッシャーズ』のデヴィッド・ドブキン{src("Wikipedia", WSU)}。',
                   f'撮影はグレンデールからマリーナ・デル・レイまで、週末の3日間。バンドは毎日10〜12時間、移動と演奏を繰り返した。アダム・レヴィーンいわく「段取りは本当にストレスだったけど、最高に楽しかった。気に入ってもらえなかったら、完全な大惨事だった」{src("Southern California Wedding", SCW)}。',
                   f'「あんなに大きな反応が返ってくるとは思わなかった。体から魂が抜けるような体験だった」とも語っている{src("ABC7", ABC)}。'],
             say='知ってたのは新郎だけ（ABC7）。花嫁から見たら、人生でいちばん豪華なドッキリ。',
             bridge='そもそも、どうして音楽を聴くとこんな気持ちになるのか。音楽そのものにお礼を言った人がいる。'),
        dict(no='04', en='追悼が、全米1位のお祭りになる', title='Stevie Wonder - Sir Duke', year='1976',
             main=dict(id='ETFvmkIA6S4', role='Official Audio 1976', artist='Stevie Wonder', song='Sir Duke', cap='Stevie Wonder - Topic（公式の音源配信）'),
             body=[f'1974年に亡くなったデューク・エリントンへの捧げもの。アルバム『Songs in the Key of Life』から{src("uDiscover Music", UDD)}{src("Wikipedia", WSD)}。',
                   f'1977年6月、本人はこう話している。「題名は最初から決めていた。でも、自分たちのために何かをしてくれた音楽家たちについての歌にしたかった。彼らは、すぐに忘れられてしまうから」{src("uDiscover Music", UDD)}。歌詞にはカウント・ベイシー、グレン・ミラー、ルイ・アームストロング、エラ・フィッツジェラルドも出てくる{src("Wikipedia", WSD)}。',
                   f'冒頭からたたみかけるホーンは、トランペット2本とアルト、テナーのサックス。1977年5月21日から、全米1位を3週続けた{src("uDiscover Music", UDD)}。'],
             bridge='理屈はもういい。あとは着替えて、出かけるだけ。'),
        dict(no='05', en='部屋で着替えるだけが、ラスベガスの開演前になる', title='Bruno Mars - 24K Magic', year='2016',
             main=dict(id='UqyT8IEBkvY', role='Official MV 2016', artist='Bruno Mars', song='24K Magic', cap='Bruno Mars 公式チャンネル。18億回以上再生されている'),
             body=[f'このアルバムを作るとき、スタジオには服装の決まりがあった。「スウェットで行ったら、スウェットみたいな音になる。だから集めたジュエリーを全部つけて、いちばんいい靴をはいて曲を書いた」{src("Billboard", BB)}。',
                   f'「ライブのことと、自分が開きたいパーティーのことだけを考えた」{src("Billboard", BB)}。表題曲のこのビデオが、その答えだ。',
                   f'同じ2016年、パリで開かれたヴィクトリアズ・シークレットのファッションショーに出たとき、最初に歌ったのは表題曲ではなく、アルバムの「Chunky」だった{src("Teen Vogue", TV)}{src("NYLON", NYL)}。パリのランウェイで、いきなりこれ。'],
             more_label='関連動画 — パリのランウェイで、いきなりこれ',
             more=[dict(id='5kEfq8jPsu4', role='Live 2016', artist='Bruno Mars', song='Chunky (Victoria’s Secret 2016 Fashion Show)', cap='Bruno Mars 公式チャンネル')],
             say='パリのランウェイで、いきなりこれ（笑）。看板の「24K Magic」を後ろに回す度胸。',
             bridge='踊り疲れたところで、最後にこれをどうぞ。'),
        dict(no='06', en='最後に、これをどうぞ', title='Pharrell Williams - Happy', year='2013',
             main=dict(id='ZbZSe6N_BXs', role='Official MV 2013', artist='Pharrell Williams', song='Happy', cap='PharrellWilliamsVEVO'),
             body=[f'映画『怪盗グルーのミニオン危機一発』のために書いた曲。でも最初からハッピーだったわけではない。恋に落ちたグルーの曲を、9回出して9回ボツにされた{src("NME", NME)}。本人いわく「9曲出して『これは違う』。落ち込んだし、プライドはズタズタ。でも10曲目のとき、もう何も残ってなかった」{src("Creative Review", CR)}。',
                   f'そうして生まれたこの曲に、「世界初の24時間ミュージックビデオ」がついた{src("24 Hours of Happy", H24)}。上のはその4分の公式版。',
                   '人はなぜ音楽を聴くのか。第1回の答えが、題名にそのまま書いてある。だから最後に置いた。'],
             say='世界中の人がこの曲で踊る映像を、オプラの番組で見せられて、本人が泣いた。「なんでオプラの前で泣いてるんだ」（Rolling Stone）。ハッピーの作者が、いちばん泣いている。',
        ),
    ],
    close=['人はなぜ音楽を聴くのか。今日の答えは「楽しくなりたいから」。', 'でも、答えはひとつじゃない。', '次回のレポートもお楽しみに。'],
    sources=[('American Songwriter — Lovely Day', AMS), ('Songfacts — Lovely Day', SFL), ('Wikipedia — Lovely Day', WLD), ('otonano — 伊藤銀次が語るシュガー・ベイブ', OTO), ('Wikipedia — DOWN TOWN', WDT), ('J-Lyric — シュガーベイブ', JLY),
             ('Southern California Wedding — Maroon 5 Sugar', SCW), ('ABC7 — Maroon 5 Sugar', ABC), ('Wikipedia — Sugar (Maroon 5 song)', WSU), ('uDiscover Music — Sir Duke', UDD), ('Wikipedia — Sir Duke', WSD),
             ('Billboard — Bruno Mars 24K Magic interview', BB), ('Teen Vogue — Chunky at VS Show 2016', TV), ('NYLON — 2016 Victoria’s Secret performances', NYL),
             ('NME — Pharrell rejected nine times', NME), ('Creative Review — How Pharrell got Happy', CR), ('24 Hours of Happy', H24), ('Rolling Stone — Pharrell cries on Oprah', RS), ('Spotify — 多幸感ポップス', SPOT)],
    note='動画は公式チャンネルの映像です。事実は上の出典で確認できた範囲だけを書いています。歌詞は引用していません。',
)

if __name__ == '__main__':
    print(write(M))
