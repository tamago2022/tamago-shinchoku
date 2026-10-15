import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src
import json
I18N = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'i18n_ikareru.json'), encoding='utf-8'))  # 5言語（訳だけ直すときはこのファイル）

# 2026-10-16 たまごさんの赤入れ（80点超え）を反映した版。正本は確認ページ（share/check/tokushu-ikareru-01.html）の章立て 00〜10。
# 事実は下の出典で確認できたものだけ（取得物は status/ikareru_v3/src/）。

# 00 Lenny
WLEN = 'https://en.wikipedia.org/wiki/Rock_and_Roll_Is_Dead'
SF = 'https://www.songfacts.com/facts/lenny-kravitz/rock-and-roll-is-dead'
# 01 Sex Pistols
HIS = 'https://www.history.com/this-day-in-history/may-31/the-bbc-bans-the-sex-pistols-god-save-the-queen'
WGSQ = 'https://en.wikipedia.org/wiki/God_Save_the_Queen_(Sex_Pistols_song)'
# 02 X-Ray Spex
WOB = 'https://en.wikipedia.org/wiki/Oh_Bondage_Up_Yours!'
WPOLY = 'https://en.wikipedia.org/wiki/Poly_Styrene'
TW = 'https://totallywiredmag.com/looking-back-oh-bondage-up-yours-and-the-power-of-poly-styrene/'
CAMB = 'https://dictionary.cambridge.org/dictionary/english/up-yours'
WVS = 'https://en.wikipedia.org/wiki/V_sign'
# 03 吉幾三
WORA = 'https://ja.wikipedia.org/wiki/%E4%BF%BA%E3%82%89%E6%9D%B1%E4%BA%AC%E3%81%95%E8%A1%8C%E3%81%90%E3%81%A0'
NLAB = 'https://nlab.itmedia.co.jp/cont/articles/3269398/'
SP2510 = 'https://www.sponichi.co.jp/entertainment/news/2025/10/23/kiji/20251023s00041000092000c.html'
SP23 = 'https://www.sponichi.co.jp/entertainment/news/2023/11/21/kiji/20231121s00041000572000c.html'
TOSPO = 'https://www.tokyo-sports.co.jp/articles/-/343055'
# 04 BOØWY
BOOWY = 'https://21st-century-boowy.com/entry/elite'
# 05 THE TIMERS
WTIM = 'https://ja.wikipedia.org/wiki/THE_TIMERS'
WCOV = 'https://ja.wikipedia.org/wiki/COVERS_(RC%E3%82%B5%E3%82%AF%E3%82%BB%E3%82%B7%E3%83%A7%E3%83%B3%E3%81%AE%E3%82%A2%E3%83%AB%E3%83%90%E3%83%A0)'
ENC = 'https://encount.press/archives/705209/'
CYZO = 'https://cyzo.jp/culture/post_419074/'
SP25 = 'https://www.sponichi.co.jp/entertainment/news/2025/06/09/kiji/20250609s00041000188000c.html'
BUN = 'https://bunshun.jp/articles/-/75719?page=1'
# 06 Bikini Kill
WRG = 'https://en.wikipedia.org/wiki/Rebel_Girl_(Bikini_Kill_song)'
WBK = 'https://en.wikipedia.org/wiki/Bikini_Kill'
WKH = 'https://en.wikipedia.org/wiki/Kathleen_Hanna'
ELLE = 'https://www.elle.com/culture/books/a60631617/kathleen-hanna-rebel-girl-excerpt/'
# 07 打首獄門同好会
WUCHI = 'https://ja.wikipedia.org/wiki/%E6%89%93%E9%A6%96%E7%8D%84%E9%96%80%E5%90%8C%E5%A5%BD%E4%BC%9A'
GEKI = 'https://gekirock.com/interview/2019/03/uchikubigokumon.php'
# 08 Ado
WUS = 'https://ja.wikipedia.org/wiki/%E3%81%86%E3%81%A3%E3%81%9B%E3%81%87%E3%82%8F'
SOL = 'https://www.tfm.co.jp/lock/speciallocks/38998'
# 09 おとぼけビ〜バー
WOTO = 'https://en.wikipedia.org/wiki/Otoboke_Beaver'
RT19 = 'https://rooftop1976.com/interview/190704143000.php?page=3'
ANT = 'https://antenna-mag.com/post-19448/'
# 10 Prince
WGOLD = 'https://en.wikipedia.org/wiki/Gold_(Prince_song)'
WPRI = 'https://en.wikipedia.org/wiki/Prince_(musician)'


def cut(s):
    """出典リンクの付いた一文。"""
    return s


M = dict(
    key='ikareru', file='tokushu-ikareru-01.html', title='怒れる人々 vol.1',
    desc='ロックは死んだのか。1995年のレニー・クラヴィッツの問いから、Sex Pistolsの放送禁止、X-Ray Spexの「くたばれ」、吉幾三の「なんにもない」、BOØWY、THE TIMERSの放送事故、Bikini Killの「女子は前へ」、打首獄門同好会、Ado「うっせぇわ」、おとぼけビ〜バー、そしてPrinceの返事まで。11曲、ぜんぶページの中で聴ける。',
    hero='Qp3b-RXtz4w', eyebrow='Rock Story — The Angry Ones · vol.1',
    h1='怒れる人々', lead='ロックは、怒りや反骨の音楽だった。<br/>抑圧された若者たちの叫び。ここから11曲。ぜんぶ、このページの中で聴ける。',
    big='「ロックは、死んだ」。',
    open=['1995年、レニー・クラヴィッツはそう歌った。じゃあ、本当に死んだのか。確かめに行こう。',
          'ロックは怒りの音楽だった。国に。レールの上を走るエリートに。テレビに。働くことに。押しつけられる「こうあるべき」に。その怒りを、笑いや、踊れるリズムや、大合唱に変えてしまう人たちがいる。1977年のロンドンから、2020年代の京都まで。怒りがどう受け継がれてきたか、順番に追いかけてみる。'],
    door='答えを先に言ってしまうと、まだ死んでいない。多分。',
    paper=[],
    others_skip=['hoshikatsu'],
    map=False,  # 確認ページ（正本）には曲の一覧が無い。目次と重複するので出さない  # 本番がまだ404（2026-10-16 03:23 実測）
    songs_n=11,
    chapters=[
        dict(no='00', artist='Lenny Kravitz', song='Rock and Roll Is Dead', album='アルバム『Circus』', year='1995',
             catch='「ロックは死んだ」と、ロックスターが言った',
             main=dict(id='yw8_5OYKQNA', role='MV 1995', artist='Lenny Kravitz', song='Rock And Roll Is Dead', cap=''),
             body=[f'1995年8月、アルバム『Circus』からの最初のシングル{src("Wikipedia", WLEN)}。題名だけ聞いて、みんな怒った。',
                   f'本人いわく、完全な誤解だった。「みんな、歌詞の中身を聴いてくれなかった。言いたかったのは上っ面のことなんだ。イメージが、音楽や才能や芸術より優先されている。ロックスターになるのに、ヘロインを打つ必要も、決まった振る舞いをする必要もない。自分らしくあれ、ってこと」{src("Songfacts", SF)}。'],
             say='「ロックは死んだ」を、思いきりロックな音で歌う。言ってることと鳴ってることが逆で、ちょっと笑ってしまう。僕も「もう若くないから」と言いながら、夜中の二時にラーメンをすすっている。',
             bridge='その問いの18年前。ロンドンで、国そのものに怒る曲が出る。'),
        dict(no='01', artist='Sex Pistols', song='God Save the Queen', album='シングル', year='1977.5.27',
             catch='放送禁止の、もうひとつの国歌',
             main=dict(id='g-38GX2YQig', role='MV 1977', artist='Sex Pistols', song='God Save The Queen', cap=''),
             body=[f'1977年5月27日発売{src("Wikipedia", WGSQ)}。エリザベス女王の即位25周年を国じゅうが祝う年に、国歌とまったく同じ題名のシングルを出した。もともとの題は「No Future（未来なんかない）」だった{src("Wikipedia", WGSQ)}。',
                   f'4日後の5月31日、BBCは放送を全面禁止した{src("HISTORY", HIS)}。大手のレコード店も扱わなかった。それでも置いた店では、多いときで1日に15万枚売れた。なのに公式チャートは2位。しかもその2位の欄には、曲名すら印刷されず、空白の行が載った{src("HISTORY", HIS)}。音楽紙NMEのチャートでは1位。「チャートは操作された」という疑いは、今も語られている{src("Wikipedia", WGSQ)}。',
                   f'歌ったジョン・ライドンは、30年後にこう振り返っている。「朝飯のテーブルで、ベイクドビーンズを食いながら書いた曲が、国をまっぷたつに割って、ポップカルチャーを変えた。そんな曲は、そう多くない」{src("HISTORY", HIS)}。',
                   '怒りの矛先は、レコード会社でも、親の世代でもなく、国そのものだった。'],
             say='国をまっぷたつに割った曲が、ベイクドビーンズから生まれている。僕の朝ごはんからは、今のところ何も生まれていない。',
             bridge='国を怒った男たちの、4ヶ月後。同じロンドンで、ひとりの少女がデビューする。'),
        dict(no='02', artist='X-Ray Spex', song='Oh Bondage Up Yours!', album='デビュー・シングル', year='1977.9',
             catch='女の子は黙ってろ？ 束縛なんか、まとめてくたばれ',
             main=dict(id='DcwdUXZkfTw', role='Punk 1977', artist='X-Ray Spex', song='Oh Bondage Up Yours!', cap=''),
             body=[f'1977年9月、X-Ray Spexのデビュー・シングル{src("Wikipedia", WOB)}。書いて歌ったのはポリー・スタイリン。セックス・ピストルズのライブを観て、すぐに書いた。1976年の夏、19歳のときだ{src("Wikipedia", WOB)}{src("Wikipedia", WPOLY)}。',
                   f'題名の「Up Yours」は、イギリスの悪態。相手が心底嫌いだと示すときに使う、かなり無礼な言葉だ{src("Cambridge Dictionary", CAMB)}。手の甲を相手に向けて二本指を突き立てる侮辱のしぐさとセットで、とくに権威への反抗を表す{src("Wikipedia", WVS)}。だから題名は「ああ束縛よ、くたばれ！」。',
                   f'何に怒っていたのか。ひとつは、女の子に向けられる「こうあれ」だ。曲は、女の子はおとなしく見られていればいい、口をきくな——そう考える人たちがいる、という静かな前置きで始まる。そして次の瞬間、彼女は題名を絶叫する{src("Wikipedia", WOB)}。',
                   f'もうひとつは、買って、捨てて、また買う暮らしそのもの。芸名の「ポリスチレン（発泡スチロール）」も、使い捨ての文化への皮肉だった。本人いわく「これは解放の呼びかけ。消費のルールにも、自分の欲にも縛られない、ってこと」{src("Wikipedia", WOB)}。「ボンデージ」と聞いて世間はSMの歌だと思ったけれど、本人は「物質の世界の束縛から自由になる歌。奴隷や、鎖につながれたサフラジェット（女性参政権運動家）のイメージがあった」と語っている{src("Totally Wired", TW)}。',
                   f'叫ぶ声に、陽気なサックスがかぶさる。吹いていたローラ・ロジックは、当時16歳{src("Wikipedia", WOB)}。BBCは放送を禁止した{src("Wikipedia", WOB)}。怒りは、最初から少しだけ笑っていた。'],
             say='SMの歌だと思われていたら、中身は「買いすぎ注意」だった。月末にカードの明細を見て震えている僕のために、49年前から叫んでくれていたらしい。',
             bridge='ロンドンの叫びは、海を越える。7年後、日本の村から。'),
        dict(no='03', artist='吉幾三', song='俺ら東京さ行ぐだ', album='シングル', year='1984.11.25',
             catch='田舎者の、魂の叫び。しかも、ほぼ実話',
             main=dict(id='UzRVEQDxiOo', role='TV', artist='吉幾三', song='俺ら東京さ行ぐだ', cap=''),
             body=[f'1984年11月25日のシングル。作詞作曲は吉幾三本人。最初の仮タイトルは『離村者』だった{src("Wikipedia", WORA)}。',
                   f'本人はのちにこう明かしている。「田舎を出てきたときの気持ちを歌にしようと思った。なんにもないのがイヤで出てきたんだよな」。歌っているのは1984年の村ではなく、彼が上京した1968年3月の、ふるさとの姿だった{src("ねとらぼ", NLAB)}。',
                   f'地元の人に聞くと、当時の金木町にもテレビもラジオもあった。ただし吉さんの家は、本人いわく「町一番の貧乏家庭」で、本当にどっちもなかった{src("ねとらぼ", NLAB)}。',
                   f'売れるまでが長かった。1973年、20歳で「山岡英二」としてデビュー。路線は、なんとアイドル。ところが同じ時期に郷ひろみ・野口五郎・西城秀樹。「俺を通してくれないんだよ」{src("スポニチ", SP2510)}。1977年に吉幾三と名を変えて「俺はぜったい！プレスリー」がヒット。そのあと、また長い低迷が来る{src("Wikipedia", WORA)}。',
                   f'この曲はどのレコード会社にも断られた。拾ったのは演歌の大御所・千昌夫。数百万円で原盤権を買い取って、世に出した{src("Wikipedia", WORA)}。のちに吉は、アメリカに渡った知人から送られてきたラップのレコードがヒントだった、と語るようになる{src("Wikipedia", WORA)}。',
                   f'大ヒットのあと、事務所の電話が鳴りやまなくなる。「生まれたところをバカにすんな！」{src("東スポ", TOSPO)}。吉が「子どもの頃はなかっただろうが」と言い返して、けんかになったこともある{src("ねとらぼ", NLAB)}。'],
             more_label='もう1本 — 公式の「俺ら東京さ行ぐだ」',
             more=[dict(id='bIV-zcs4VDA', role='Video Cinema', artist='吉幾三', song='俺ら東京さ行ぐだ（ビデオシネマ「純情編」より）', cap='')],
             say='ちなみにこのレコードのジャケット写真、撮ったのは北海道の増毛町（Wikipedia）。青森の村を飛び出す歌なのに、写真はもう海を渡っている。気が早い。',
             bridge='村から東京へ。で、その東京。レールの上を走るエリートたちを、冷たく笑うバンドがいた。'),
        dict(no='04', artist='BOØWY', song='ELITE', album='アルバム『MORAL』', year='1982.3.21',
             catch='レールの上のエリートに、冷たい一発',
             main=dict(id='sftuJI4P2RY', role='MORAL 1982', artist='BOØWY', song='ELITE', cap=''),
             body=[f'1982年3月21日に出たデビュー・アルバム『MORAL』の4曲目{src("BOØWY資料集", BOOWY)}。作詞作曲は氷室京介。当時のクレジットは「氷室狂介」——狂うの「狂」だった{src("BOØWY資料集", BOOWY)}。',
                   '住宅ローン、かわいい子ども。誰もが描く「幸せ」の設計図を並べてみせて、その上で、同じレールに乗って人を蹴落とす連中を突き放す。怒鳴らない。冷たく笑って、切り捨てる。レールの上を走る側への、短くて鋭い一撃。'],
             say='住宅ローンを組んだ人が聴くと、ちょっと胸が痛い。組めなかった人が聴くと、ちょっと元気が出る。僕はどっちの日もある。',
             bridge='冷たく笑う人がいれば、テレビの電波に乗せて、本当にやらかしてしまう人もいた。'),
        dict(no='05', artist='THE TIMERS', song='FM東京', album='フジテレビ『ヒットスタジオR&N』', year='1989.10.13',
             catch='その夜、テレビが事件になった',
             main=dict(id='JrTQDYVVa7w', role='Uncut 1989', artist='THE TIMERS', song='FM東京', cap=''),
             body=[f'今や伝説の、THE TIMERSの放送事故だ。忌野清志郎に“よく似ている人物”ZERRYが率いる覆面バンド{src("Wikipedia", WTIM)}。',
                   f'火種は前の年。RCサクセションのアルバム『COVERS』は、原発を歌った「サマータイム・ブルース」などが問題にされ、当時の親会社・東芝からの圧力で発売中止になった。新聞広告の文句は「素晴しすぎて発売出来ません」{src("Wikipedia", WCOV)}。その後、別の会社から出たが、FM東京はオンエアを自粛した{src("Wikipedia", WTIM)}。タイマーズの「土木作業員ブルース」もFM東京で放送自粛{src("ENCOUNT", ENC)}。',
                   f'1989年10月13日、フジテレビの深夜の音楽番組『ヒットスタジオR&N』。予定の曲を歌わずに、いきなり始めたのが、FM東京とFM仙台を名指しで罵倒する新曲「FM東京」だった。放送禁止用語つき{src("ENCOUNT", ENC)}。言い出しっぺはギターのTOPPI（三宅伸治）。「何かやらかしましょうか？」。二人で曲を作ったが、清志郎がつけたある歌詞を見て「すげえ。半端な気持ちだった自分とは、覚悟が違った」{src("サイゾー", CYZO)}。',
                   f'司会の古舘伊知郎は、夕方のリハーサルで気づいていた。「歌の中で古舘伊知郎って26回言ったんですよ。本番でそこに違う言葉をはめるんだな、と」。楽屋に乗り込むと、返事は「大丈夫、大丈夫！古舘君、迷惑は掛けないから」。本番、出演者は笑い転げ、「僕だけ青ざめてる」。放送後に文句を言いに行くと、もう楽屋にいなかった。2週間後、西麻布のワインバーで鉢合わせした清志郎は、立ち上がって深々とおじぎし、小さな声で「ごめんなさい、古舘くん」{src("スポニチ", SP25)}。'],
             more_label='関連動画 — 司会者が振り返るあの夜、火種になった曲',
             more=[dict(id='uk8PA5A1yk4', role='Witness', artist='古舘伊知郎チャンネル', song='忌野清志郎さんの忘れられない話', cap=''),
                   dict(id='GpF3hoKLiFY', role='COVERS 1988', artist='RCサクセション', song='サマータイム・ブルース', cap=''),
                   dict(id='BnU7Yr6tZxU', role='1989', artist='THE TIMERS', song='FM東京', cap='')],
             say='実はこれ、生放送じゃなかった（文春オンライン）。もうひとりの司会のGWINKOが16歳で、深夜に働けない。だから夕方に撮って、そのまま流した。ディレクターが「これ流していいですか」と確かめたら、プロデューサーの返事は「いいんじゃない？」。止める時間は、あった。止めなかった。',
             bridge='テレビという最大の拡声器で怒った夜のあと、怒りは、もっと小さな場所で、もっと手作りに鳴り始める。海の向こうの、小さな町で。'),
        dict(no='06', artist='Bikini Kill', song='Rebel Girl', album='シングル（プロデュース：ジョーン・ジェット）', year='1993',
             catch='女子は前へ。「女らしく」は後ろへ',
             main=dict(id='L0oeqAQ1qE8', role='Riot Grrrl 1993', artist='Bikini Kill', song='Rebel Girl', cap=''),
             body=[f'1990年、アメリカ北西部ワシントン州の小さな町オリンピアで結成。ボーカルはキャスリーン・ハンナ{src("Wikipedia", WBK)}。彼女たちが火をつけた動きは「ライオット・ガール」と呼ばれる。フェミニズムを掲げた、パンクの運動だ{src("Wikipedia", WBK)}。',
                   f'何に怒っていたのか。ハンナは回想録にこう書いている。土曜の昼、ダイナーで本を読んでいると、知らない男が勝手に同じテーブルに座ってくる。忙しいと断ったら、本を取り上げられて頭の上に掲げられた。夜、ライブで踊れば男たちに囲まれる。だから、踊るのをやめた。「性差別は私に、家にいろ、世の中に出てくるな、と言っていた」{src("ELLE", ELLE)}。',
                   f'当時のパンクのライブは、最前列のモッシュで、女性がしょっちゅう暴行を受ける場所でもあった{src("Wikipedia", WKH)}。そこでハンナは、ライブで言い始める。「ガールズ・トゥ・ザ・フロント（女子は前へ）」。最前列で男がモッシュしていると、女の子からベースを弾くキャシの手元が見えない。「女の子が楽器を弾くところを見られなかったら、どうやって女の子がバンドを始めるの？」{src("ELLE", ELLE)}。安いスピーカーで歌詞が聞こえないから、ライブの前には女の子たちに歌詞カードを配って回った。野次る男がいれば、客席に飛び込んで自分でつまみ出した{src("ELLE", ELLE)}{src("Wikipedia", WBK)}。',
                   f'返ってきたのは「男嫌い」「逆差別」という罵声。それでも最前列には、いつも5、6人の女の子がいた。バンドは、その子たちのために演奏した{src("ELLE", ELLE)}。',
                   f'「Rebel Girl」は、その場所で鳴った曲だ。歌われているのは、ひとりの女の子への、隠しもしない憧れと恋。男が女を歌うのが当たり前だったラブソングの型をひっくり返して、女の子が女の子をまっすぐ讃える。それがそのまま、女同士の連帯の歌になった{src("Wikipedia", WRG)}。シングル版をプロデュースし、ギターとコーラスで加わったのは、ザ・ランナウェイズ出身のジョーン・ジェット{src("Wikipedia", WRG)}。2021年、Rolling Stone誌の「史上最高の500曲」で296位{src("Wikipedia", WRG)}。2024年に出たハンナの回想録の題名も、『Rebel Girl』だ{src("ELLE", ELLE)}。'],
             say='「女子は前へ」と言われて、男子は後ろへ。僕はたぶん、言われる前から一番後ろで腕を組んでいるタイプだ。それでもこの曲が始まると、腕がほどけて、足だけ前に出ている。',
             bridge='怒りは海を越えて、女子の場所を作った。一方、日本の日常では、怒りは今日も飲み込まれている。たとえば、バイト先のレジの前で。'),
        dict(no='07', artist='打首獄門同好会', song='はたらきたくない', album='ミニ・アルバム『そろそろ中堅』', year='2019',
             catch='「いらっしゃいませ」の奥で煮えていた、本音のマグマ',
             main=dict(id='GR-mLGV0X1I', role='MV', artist='打首獄門同好会', song='はたらきたくない', cap=''),
             body=[f'「生活密着型ラウドロック」を名乗るバンド{src("Wikipedia", WUCHI)}。2019年のミニ・アルバム『そろそろ中堅』の制作は、この曲から始まった{src("激ロック", GEKI)}。',
                   f'きっかけは、ゲーム会社から急に届いた一通のメール。『WORK×WORK』という、働くゲームのテーマ曲の依頼だった。主人公はアルバイト中に、客の王子のいろんな思惑に巻き込まれて、魔王退治をするはめになる。どんな曲がいいかと聞くと、ゲーム会社のほうから「例えば曲のテーマは、はたらきたくないとか……」{src("激ロック", GEKI)}。',
                   f'バンドは気をつかって、無難な曲も用意した。「僕はただのバイトなのに魔王退治で大変だ」という、キャッチーな歌だ。「はたらきたくない」のほうは、遊び半分で1コーラスだけ。ところが全員で聴き終わると、ゲーム会社の人たちは「こっちだね」と「はたらきたくない」を指差した。ボーカルの大澤いわく「ゲーム業界の方も、およそ感覚がおかしいんですよね」{src("激ロック", GEKI)}{src("Wikipedia", WUCHI)}。',
                   f'怒鳴り散らすわけじゃない。重たいギターで、みんながレジの前や満員電車で飲み込んでいる一言を、代わりに鳴らす。大澤いわく「あんなに午前中のツイートが伸びる曲はない」{src("激ロック", GEKI)}。'],
             say='日曜の夜、休みの終わりに聴くのはおすすめしません。月曜の朝の自分が、布団から出てこなくなります。僕が保証します。',
             bridge='ここまで怒ってきたのは、社会に出た側だった。2020年、まだ高校生の側がキレる。'),
        dict(no='08', artist='Ado', song='うっせぇわ', album='配信シングル', year='2020.10.23',
             catch='優等生がキレたら、社会現象になった',
             main=dict(id='Qp3b-RXtz4w', role='MV 2020', artist='Ado', song='うっせぇわ', cap=''),
             body=[f'2020年10月23日に配信された、Adoのメジャー1作目。詞と曲はボカロPのsyudou{src("Wikipedia", WUS)}。2021年の新語・流行語大賞では、トップテンに入った{src("Wikipedia", WUS)}。',
                   f'歌った当時、Adoは高校3年生。社会人の世界は、ドラマや映画で想像するしかなかった。「簡単に言えば“怒りの感情”みたいな。怒りの感情は学生にも共通している部分はあったので、そこをいかに強く出せるか」{src("SCHOOL OF LOCK!", SOL)}。',
                   f'syudouは「女性の目線にしよう」などとは一切考えず、普段どおりに書いた。返ってきたのは「いっさいの直しナシ」。サビで裏声に持っていくあの歌い方も、Ado自身のアイデアだった。「僕が歌のディレクションしたって思われることが多いんですけど、マジでなんもしてないんすよ！」{src("SCHOOL OF LOCK!", SOL)}。',
                   '怒鳴っているのは、もう大人じゃない。押しつけられる側だった世代が、古い「常識」をそのまま投げ返した。社会現象になったのは、みんなどこかで言いたかったからだと思う。'],
             say='デモに返ってきた唯一の注文は「キーを4〜5個上げてください」（SCHOOL OF LOCK!）。優等生、最初から喉でキレる気まんまん。',
             bridge='押しつけられる側がキレる、その前から。京都では、別の怒りが1分半に凝縮されていた。'),
        dict(no='09', artist='おとぼけビ〜バー', song='ジジイ is Waiting For My Reaction', album='京都', year='2020',
             catch='「なんで？ ごちそうするのに？」に、1分半の返事',
             main=dict(id='2TzJkX9zweM', role='PV 2020', artist='おとぼけビ〜バー', song='ジジイ is Waiting For My Reaction', cap=''),
             body=[f'2009年、京都の立命館大学の軽音サークルで結成された4人組{src("Wikipedia", WOTO)}。',
                   f'この曲は、ボーカルのあっこりんりんいわく「めっちゃイヤな態度出してるのに気づかず口説いてくるおっさんの歌」。「普通メシめっちゃ断られたら脈ないってわかるでしょ？ やつらは『なんで？ ごちそうするのに？』って言うんです。おまえに時間割きながら奢られるメシより、ひとりでカップラーメン食ってるほうがうまいねん」。ずっと歌いたかったけれど、お客さんにオジサマが多いのでビビって作れなかった、とも{src("Rooftop", RT19)}。',
                   f'2016年からはイギリスを回り、2018年にはアメリカのコーチェラに出演した{src("Wikipedia", WOTO)}。本人たちいわく「字面だけでも意味がわからなすぎて『すげーミラクル！』ってみんなでわろてます」{src("ANTENNA", ANT)}。',
                   'ロンドンの少女の「くたばれ」も、オリンピアの「女子は前へ」も、京都の1分半も。怒っている相手は、だいたい同じだ。'],
             say='1分半です。カップ麺より早く、ジジイを片付けられます。',
             bridge='国にも、レールにも、テレビにも、ジジイにも、怒ってきた。あの問いの答えは、実は同じ年に出ていた。'),
        dict(no='10', artist='Prince', song='Rock and Roll Is Alive! (And It Lives in Minneapolis)', album='シングル「Gold」B面', year='1995',
             catch='ロックは生きてる。住所は、ミネアポリス',
             main=dict(id='YAxbwQNa15Q', role='Answer 1995', artist='Prince', song='Rock And Roll Is Alive! (And It Lives In Minneapolis)', cap=''),
             body=[f'1995年11月に出たプリンスのシングル「Gold」のB面。レニー・クラヴィッツの「Rock and Roll Is Dead」への、返事の曲だ{src("Wikipedia", WGOLD)}。',
                   f'この頃のプリンスは、名前すら名乗っていない。発音できない記号を名前にしていた{src("Wikipedia", WGOLD)}。そして人前に出るときは、顔に「slave（奴隷）」の文字。「Gold」が入ったアルバム『The Gold Experience』の発売を、所属レコード会社のワーナーが遅らせた。その<a class="cw-inl" href="{WPRI}" target="_blank" rel="noopener noreferrer">契約をめぐる争い</a>への、報復だった。',
                   f'題名は「ロックは生きてる。ミネアポリスに住んでる」。ミネアポリスは、プリンスが生まれて育った街だ{src("Wikipedia", WPRI)}。',
                   '会社に「奴隷」と書いて抗議していた男が、自分の街の名前を胸を張って歌う。「ロックは死んだ？」と聞かれて、自分の家の住所を答えたわけだ。生きてるロックの正体は、たぶん本人だ。'],
             say='「ロックは死んだ」に、「いや、うちにいるけど？」と返す。返事のセンスで、もう勝っている。'),
    ],
    close=['ロックは死んだのか。',
           '1977年の放送禁止が、少女の「くたばれ」が、村の「なんにもない」が、レールへの冷笑が、テレビの放送事故が、「女子は前へ」が、月曜の朝の本音が、優等生のキレが、京都の1分半が。',
           '一本の線でつながっていた。問いが出た1995年、答えも同じ年に歌われていた。怒りは、笑いに、踊りに、憧れに、形を変えながら、まだ鳴っている。',
           'イカれる人は、まだまだいっぱいいる。引き続き、レポートを続けます。次回のレポートもお楽しみに。'],
    sources=[('Wikipedia — Rock and Roll Is Dead', WLEN), ('Songfacts — Rock and Roll Is Dead', SF),
             ('HISTORY — The BBC bans the Sex Pistols’ “God Save the Queen”', HIS), ('Wikipedia — God Save the Queen (Sex Pistols song)', WGSQ),
             ('Wikipedia — Oh Bondage Up Yours!', WOB), ('Wikipedia — Poly Styrene', WPOLY), ('Totally Wired — Oh Bondage Up Yours!', TW), ('Cambridge Dictionary — up yours!', CAMB), ('Wikipedia — V sign', WVS),
             ('Wikipedia — 俺ら東京さ行ぐだ', WORA), ('ねとらぼ — 「俺ら東京さ行ぐだ」歌詞のウソ・ホント', NLAB), ('スポニチ — 最初は「アイドル」だった（2025）', SP2510), ('東スポ — 苦情の電話', TOSPO),
             ('BOØWYの記録 — 『ELITE』', BOOWY),
             ('Wikipedia — THE TIMERS', WTIM), ('Wikipedia — COVERS', WCOV), ('ENCOUNT — FM東京事件', ENC), ('サイゾー — 三宅伸治の証言', CYZO), ('スポニチ — 古舘伊知郎の証言（2025）', SP25), ('文春オンライン — 「実は生じゃなかった」', BUN),
             ('Wikipedia — Rebel Girl (Bikini Kill song)', WRG), ('Wikipedia — Bikini Kill', WBK), ('Wikipedia — Kathleen Hanna', WKH), ('ELLE — Kathleen Hanna『Rebel Girl』抜粋', ELLE),
             ('Wikipedia — 打首獄門同好会', WUCHI), ('激ロック — 打首獄門同好会インタビュー（2019）', GEKI),
             ('Wikipedia — うっせぇわ', WUS), ('SCHOOL OF LOCK! — Ado × syudou', SOL),
             ('Wikipedia — Otoboke Beaver', WOTO), ('Rooftop — おとぼけビ〜バー（2019）', RT19), ('ANTENNA — コーチェラ出演', ANT),
             ('Wikipedia — Gold (Prince song)', WGOLD), ('Wikipedia — Prince (musician)', WPRI)],
    note='',
    i18n=I18N,
)

if __name__ == '__main__':
    print(write(M))
