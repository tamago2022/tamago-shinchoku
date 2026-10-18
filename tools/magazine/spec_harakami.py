import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src

# 2026-10-18 型1018（怒れる人々 vol.1 の型）。9章・吹き出し・静止画6枚（tools/magazine/fuukei.json）・5言語（i18n_harakami.json）。
# 事実は下の出典で確認できたものだけ。本文の出典リンクは src(ラベル, URL)。

W = 'https://ja.wikipedia.org/wiki/%E3%83%AC%E3%82%A4%E3%83%BB%E3%83%8F%E3%83%A9%E3%82%AB%E3%83%9F'
RBMA = 'https://daily.redbullmusicacademy.com/2016/06/rei-harakami-guide'
TOWER = 'https://tower.jp/article/interview/2009/03/19/100041131/100041136'
TOWER1 = 'https://tower.jp/article/interview/2009/03/19/100041131'
TOWER2 = 'https://tower.jp/article/interview/2009/03/19/100041131/100041132'
TOWER3 = 'https://tower.jp/article/interview/2009/03/19/100041131/100041133'
TOWER_SENKO = 'https://tower.jp/article/interview/2009/03/19/100041131/100041134'
TOWER_LUST = 'https://tower.jp/article/interview/2009/03/19/100041131/100041135'
RINGS = 'https://www.ringstokyo.com/rei-harakami-red-curb/'
ELEK = 'https://www.ele-king.net/review/album/001640/'
BARKS = 'https://www.barks.jp/news/?id=1000008310'
ALLAB = 'https://allabout.co.jp/gm/gc/205772/'
ALLAB2 = 'https://allabout.co.jp/gm/gc/205772/2/'
ALLAB3 = 'https://allabout.co.jp/gm/gc/205772/3/'
ALLAB4 = 'https://allabout.co.jp/gm/gc/205772/4/'
YAMAHA = 'https://www.yamahamusic.co.jp/s/ymc/news/detail/1608'
NIEW = 'https://niewmedia.com/series/hosono_house/3_edymm_wrhra/'
WKNC = 'https://wknc.org/2024/03/07/rei-harakamis-lust-makes-for-addictive-listening/'
HH = 'https://ja.wikipedia.org/wiki/HOSONO_HOUSE'
MIRAI = 'https://www.miraikan.jst.go.jp/events/202106262015.html'
CINRA = 'https://www.cinra.net/article/column-202107-reiharakami_ymmtscl'
KYOTO = 'https://www.kyoto-np.co.jp/articles/thekyoto/676859'
KYOTO2 = 'https://www.kyoto-np.co.jp/articles/thekyoto/676562'
YW = 'https://ja.wikipedia.org/wiki/Yanokami'
WSENKO = 'https://ja.wikipedia.org/wiki/%E9%96%83%E5%85%89_(UA%E3%81%AE%E6%9B%B2)'
WTENNEN = 'https://ja.wikipedia.org/wiki/%E5%A4%A9%E7%84%B6%E3%82%B3%E3%82%B1%E3%83%83%E3%82%B3%E3%83%BC'
I18N = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'i18n_harakami.json'), encoding='utf-8'))  # 5言語（訳だけ直すときはこのファイル）

M = dict(
    key='harakami', file='tokushu-rei-harakami.html', title='君はレイ・ハラカミを知っているか',
    desc='Aメロも、Bメロも、サビもない。それなのに、いちど聴いたら耳から離れない。カセットテープ1本で始まったデビュー作『unrest』から、引退を考えながら作った『red curb』、UA「閃光」、くるり「ばらの花」、矢野顕子が「世界遺産」と呼んだ『lust』、プラネタリウムの音楽、そしてyanokamiまで。9章、ページの中で聴きながら辿る。',
    hero='WH0y2GRiHjI', eyebrow='Feature — rei harakami · 9 chapters',
    h1='君はレイ・ハラカミを知っているか',
    lead='Aメロも、Bメロも、サビもない。それなのに、いちど聴いたら耳から離れない。<br/>京都でひとり、小さな機材で鳴らされていた音。ここから9章。',
    big='20年くらい前、はじめて聴いたとき、<br/>「こんな音楽、聴いたことない」と思った。',
    open=['大げさじゃなく、「今まで聴いてた音楽は何だったんだ」とまで思った。歌もない。サビもない。なのに、ずっと聴いていられる。むしろ、止めたくない。',
          f'レイ・ハラカミ。1970年、広島生まれ。18歳のとき学生として京都へ移って一人暮らしを始め、そのまま京都で音を作り続けた人{src("All About", ALLAB)}{src("日本科学未来館", MIRAI)}。本人いわく、京都には今でも「よそもの」という感覚がある{src("All About", ALLAB)}。',
          'カセットテープ1本から始まったデビューから、矢野顕子とのユニットまで。その音がどう広がっていったかを、順番にたどってみる。'],
    door='最後に、ふたりの名前をひとつにしたユニットのライブが待っている。',
    paper=[],
    chapters=[
        dict(no='01', artist='rei harakami', song='unrest', album='アルバム『unrest』', year='1998',
             catch='カセットテープ1本に、返事は一週間で来た',
             main=dict(id='q6-KIxNIscY', role='Debut 1998', artist='rei harakami', song='unrest', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=rei-harakami&song=unrest'),
             body=[f'1998年のデビュー・アルバム『unrest』{src("Red Bull Music Academy", RBMA)}{src("TOWER RECORDS", TOWER)}。その最後に入っている表題曲。後の作品に比べるとテクノ色が強いが、あの深いディレイと、左右に振れる音と、ぬるっと滑る音程は、もうここにある{src("Red Bull Music Academy", RBMA)}。',
                   f'始まりは、カセットテープ1本だった。1996年、ファースト・アルバムの3分の1が入ったデモをSublime Recordsに送ると、一週間もしないうちに「リリースしたい」と返事が来た。数か月後、まだ電話でしか話したことのない相手から「リミックスやってみる？ もちろん良くなかったら没なんだけど」。ダメ元で作ったFlare（Ken Ishiiの別名義）のリミックスが、世に出た最初の仕事になった{src("All About", ALLAB)}。',
                   f'音楽の入り口は、親に通わされたヤマハ音楽教室。楽譜どおりに弾くことに興味が持てなかった（本人いわく「要するにヘタクソだった」）少年の遊びは、マイク付きのカセットレコーダーに音を吹き込むことだった{src("All About", ALLAB)}。',
                   f'アルバムを出しても、反響は「全然ないですよ。けなされもしなかったけど」。これが最後になるかもしれない、と思っていたという{src("TOWER RECORDS", TOWER2)}。水彩画みたいだ、と僕は思った。にじんで、混ざって、輪郭がはっきりしない。なのに、どこを切っても彼の色をしている。'],
             say='デビューしたとき、27歳。本人いわく「リアル・ロッカーなら死んでる歳ですし（笑）」（TOWER RECORDS）。遅咲きの人は、たいてい自分で一番よく分かっている。',
             bridge='その色の正体は、何だったのか。同じアルバムから、もう1曲。',
        ),
        dict(no='02', artist='rei harakami', song='more elbow', album='アルバム『unrest』', year='1998',
             catch='「お父さんが趣味で始める機材」で、ここまで来てしまった',
             main=dict(id='x1kkPf2oBHI', role='unrest 1998', artist='rei harakami', song='more elbow', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=rei-harakami&song=more-elbow'),
             body=[f'使っていた音源は、ローランドのDTM用モジュールSC-88Pro。1996年に出た旧式の機械を2台並べ、内蔵のステレオディレイで音を左右に振る{src("Wikipedia", W)}。本人いわく、それを長年「買い換えてないので、ああなっちゃう」{src("TOWER RECORDS", TOWER1)}。',
                   f'なぜその機材だったのか。「そもそもお金が無かったからです」。スタジオと言えば聞こえはいいが、自分の部屋に機材が置いてあるだけだった{src("All About", ALLAB2)}。93〜94年ごろに使い始め、2、3年たって音色の正体が分かってくると、足し算で曲が組めるようになった{src("TOWER RECORDS", TOWER2)}。',
                   f'「〈お父さんが趣味で始めるDTM〉みたいな、そういう機材で始めちゃったから（笑）。それで飽き足らなくなったら替えればいいやと思ってたら、ここまできちゃった」。もしあのとき買ったのがサンプラーのMPCだったら、まったく別の音楽をやっていたかもしれない、とも{src("TOWER RECORDS", TOWER2)}。',
                   f'新しい機材が新しい表現を生むとは限らない。使い続けている音源でも、組み合わせ次第で十分いろんなことができる——そう考えていた{src("All About", ALLAB2)}。僕の部屋にも、5年前のノートパソコンがある。ひび割れた画面で、この原稿を書いている。'],
             say='DJは、生涯一度もやらなかった。「やっちゃうと知っちゃう感じが。俺の曲はかけにくいだろうな、とわかってしまう」（TOWER RECORDS）。踊らせることを考えなかったから、家で聴ける音になった。',
             bridge='3年後、その音は、本人も形容できないものになる。',
        ),
        dict(no='03', artist='rei harakami', song='cape', album='アルバム『red curb』', year='2001',
             catch='「これを出したら、引退しようかな」と思いながら作った3枚目',
             main=dict(id='WH0y2GRiHjI', role='red curb 2001', artist='rei harakami', song='cape', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=rei-harakami&song=cape'),
             body=[f'僕の音楽観を変えたのは、2001年の3枚目のアルバム『red curb』だった{src("TOWER RECORDS", TOWER)}{src("ele-king", ELEK)}。ポップスで育った耳は、曲を「Aメロ・Bメロ・サビ」で数えてしまう。でもこのアルバムは、そのどれにも当てはまらない。言葉にしようとして、できなかった。いまだに形容できない。',
                   f'本人のコメントが残っている。「3枚目の制作にあたって、もう好きな事ばっかりやろう、というか、好きな事しか出来ないなあ…なんて考えながら作ってました」。そして「ちなみに、このアルバム発表したら、引退しようかなと考えておりましたが、そうはいきませんでした」{src("rings", RINGS)}。',
                   f'作っている最中は「お金なくてどうしよう」。周りの状況もカテゴリーも、踊らせなきゃという義務も、考えるのが面倒になって、「売れなくていいや」と{src("TOWER RECORDS", TOWER3)}。そうやって削ぎ落としたら、世界的な評価を決定づける1枚になった{src("TOWER RECORDS", TOWER)}。',
                   f'ele-kingの野田努は、追悼のレビューにこう書いた。「『レッド・カーブ』は彼が愛したロバート・ワイアットのように美しい作品だが、思い詰めた悲しみというものはない」。レイ・ハラカミの音楽には、バッド・ヴァイブというものがない{src("ele-king", ELEK)}。'],
             pull='「今まで聴いてた音楽は、何だったんだ」',
             bridge='この音を、ほかの人たちも放っておかなかった。最初の大仕事は、UA。',
        ),
        dict(no='04', artist='UA', song='閃光', album='シングル／映画『水の女』主題歌', year='2002.7.24',
             catch='引きこもりの初仕事が、いきなり本物のスタジオだった',
             main=dict(id='eMRTkimQJWM', role='Official MV 2002', artist='UA', song='閃光', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=u-a&song=senko'),
             body=[f'2002年7月24日に出たUAの14枚目のシングル。UAが初めて作曲とプロデュースを手がけた曲で、プロデューサーにはUAとレイ・ハラカミの名前が並び、シングル版の編曲はハラカミ{src("Wikipedia", WSENKO)}。本人が出演した映画『水の女』の主題歌でもある{src("Wikipedia", WSENKO)}。BARKSは「名作『閃光』の共同プロデュース」と書いた{src("BARKS", BARKS)}。',
                   f'「歌以外は完全にハラカミさんの世界ですね」と聞かれて、本人は否定している。「いや、そんなことはなくて、だいぶ彼女の意見が入ってますよ。彼女にとっては久々のソロで、しかも初めての作詞作曲で、『ワーッ!』となってるわけですよ。僕は僕で、ちゃんとしたスタジオで誰かと一緒にやるっていうことに関して、右も左もわかってないですから。それまではただの引きこもりですからね（笑）」{src("TOWER RECORDS", TOWER_SENKO)}。',
                   f'現場には、朝本浩文、ASA-CHANG、鈴木正人という顔ぶれが、侃々諤々やっていた。「俺なんかいなくてもできるじゃん」ぐらいの感じだったという。「一番最初に一番強烈な状況でやったわけですから」{src("TOWER RECORDS", TOWER_SENKO)}。'],
             say='初めての現場で、まわりが全員プロ。僕の初出社も、だいたいこれでした。違いは、ハラカミさんはその現場から「閃光」を持ち帰り、僕は社員証の写真写りの悪さだけを持ち帰ったこと。',
             bridge='人の曲を、自分の音に塗り替える。くるりの曲でも、それをやった。',
        ),
        dict(no='05', artist='くるり', song='ばらの花 ～remixed by Rei Harakami', album='アルバム『ワールズエンド・スーパーノヴァ』', year='',
             catch='会った瞬間、メガネが曇った',
             main=dict(id='Yu3Ch9cNYMA', role='Remix', artist='くるり', song='ばらの花 ～remixed by Rei Harakami', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=quruli&song=bara-no-hana-remixed-by-rei-harakami'),
             body=[f'くるりの『ワールズエンド・スーパーノヴァ』に入っているリミックス。2003年、これを聴いた矢野顕子が、ハラカミの才能をキャッチした。ハラカミのほうは、デビュー・アルバムのころから矢野顕子の音楽を深く敬愛していた{src("ヤマハミュージックコミュニケーションズ", YAMAHA)}。',
                   f'くるりとの縁は、くるりのほうから来た。『red curb』を作っている間、ハラカミはくるりの『図鑑』を愛聴していた。発売後、「コンサートに遊びに来て下さい」と連絡が来て、本当にびっくりしたという。「お会いした時、やはりかけていたメガネが曇りました」{src("All About", ALLAB4)}。日本語のロックにはずっと興味がなかった人が、「日本語で歌詞がいい」と思えた久々の相手が、くるりだった{src("TOWER RECORDS", TOWER3)}。',
                   f'このリミックスは、かなり悩みながら作った。だから矢野顕子に絶賛されたとき、「もう引退してもいいかなと思える瞬間もありました。してませんが」{src("All About", ALLAB3)}。',
                   f'ふたりの交流は、2003年の矢野顕子の恒例コンサート「さとがえるコンサート」のトラック制作を頼まれたところから始まる{src("ヤマハミュージックコミュニケーションズ", YAMAHA)}。原曲を知っている人ほど、最初の数秒で「あ、ハラカミだ」と分かるはず。'],
             more_label='聴きくらべ — 元の「ばらの花」',
             more=[dict(id='baNgL0jFkAs', role='Original', artist='くるり', song='ばらの花', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=quruli&song=%E3%81%AF-%E3%82%89%E3%81%AE%E8%8A%B1')],
             bridge='そして2005年。4年ぶりのアルバムに、矢野顕子がとんでもない肩書きをつける。',
        ),
        dict(no='06', artist='rei harakami', song='come here go there', album='アルバム『lust』', year='2005.5.25',
             catch='世界遺産に決定。文句無し。',
             main=dict(id='CcSOgj-R38g', role='lust 2005', artist='rei harakami', song='come here go there', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=rei-harakami&song=come-here-go-there'),
             body=[f'2005年5月25日、『red curb』から4年ぶりのアルバム『lust』{src("BARKS", BARKS)}。以前共演していた矢野顕子は、このアルバムに「世界遺産に決定。文句無し。」と言葉を寄せた{src("All About", ALLAB)}{src("BARKS", BARKS)}。もちろんユネスコとは関係ない、矢野顕子の独断の認定だ{src("Wikipedia", W)}。僕はずっと yanokami の頃の話だと記憶していたけど、ユニットとしてデビューするより前の言葉だった。',
                   f'4年かかった理由は、はっきりしている。『red curb』のあと、名前を出す仕事の依頼しか来なくなり、責任上、自分の作業が遅くなった。実際に作ったのは、ほぼ前の年の1年間{src("All About", ALLAB2)}。',
                   f'このアルバムで変わったことを、本人はこう言っている。『red curb』の頃はまだ周りの状況に対する「悪意みたいなもの」があって、『lust』ではそれがなくなっている。「いつも思うのは、すごく地味な、すぐ寝れる音楽を作りたいなと（笑）」。出来には納得していて、「いつ遺作になっても問題ない」とまで{src("TOWER RECORDS", TOWER_LUST)}。',
                   f'ジャケットの古い瓦屋根の住宅地は、スズキスキー（元Fantastic Explosion。写真家ではなく音楽家）が個人的に撮った写真。本人は場所を知らない。「京都にこういうロケーションはありそうで、実はあり得ない」{src("All About", ALLAB2)}。'],
             say='2曲目の「joy」は10分を超える。大作を狙ったのかと聞かれて、「作り終わった後に、計ってみたら10分あった、というだけです」（All About）。10分って、カップ麺を3回作れる長さです。',
             bridge='その『lust』には、もうひとつ、誰も予想していなかったものが入っていた。本人の歌声だ。',
        ),
        dict(no='07', artist='rei harakami', song='owari no kisetsu', album='アルバム『lust』', year='2005',
             catch='ウォークマン用のマイクで歌った下書きが、そのまま清書になった',
             main=dict(id='wC1z9sNSaXo', role='lust 2005', artist='rei harakami', song='owari no kisetsu', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=rei-harakami&song=owari-no-kisetsu'),
             body=[f'細野晴臣が1973年の『HOSONO HOUSE』に入れた「終りの季節」{src("Wikipedia", HH)}。それを『lust』でカバーし、歌っているのは本人。ソロ作で声を使ったのは、これが初めてだった{src("Red Bull Music Academy", RBMA)}{src("BARKS", BARKS)}。',
                   f'きっかけは、矢野顕子からの「終わりの季節」をハラカミのアレンジで歌いたい、というオファー。トラックを渡すとき、自分でウォークマン用のマイクで適当に歌ったものを聴かせた。それが発端で、アルバムに入れるかどうかは最後まで考えていなかった。「ちなみにCDに入ってる歌はデモのバージョンのままです」{src("All About", ALLAB3)}。もともと yanokami でカバーするためのデモが、そのままハラカミ版になった{src("NiEW", NIEW)}。',
                   f'自分で作った歌詞と主旋律だったら、冷静に聴けなかっただろう、とも言っている{src("All About", ALLAB3)}。原曲よりさらに抑揚を抑えた、ぶっきらぼうな歌い方に、宅録の人らしさが出ている{src("NiEW", NIEW)}。PVは、本人がカメラを持って撮った{src("BARKS", BARKS)}。',
                   f'細野晴臣のアルバムで一番好きなのは『マーキュリック・ダンス』（1985年）だった、と本人のブログにある{src("NiEW", NIEW)}。2019年の秋には、サム・ゲンデルがヘッドホンで『lust』を聴いていたという話も{src("NiEW", NIEW)}。'],
             say='下書きが、そのまま清書。僕のLINEの下書きも、たまにそのまま送信されます。違いは、こっちは誰にも褒められないこと。',
             bridge='自分の声の次は、人の声と、詩と、星を連れてくる。',
        ),
        dict(no='08', artist='rei harakami', song='yami wa hikari no haha', album='プラネタリウム作品『暗やみの色』', year='2005–2007 上映',
             catch='星の数を数えて、音の数を決めた',
             main=dict(id='N6UmEfJN61o', role='暗やみの色', artist='rei harakami', song='yami wa hikari no haha', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=rei-harakami&song=yami-wa-hikari-no-haha'),
             body=[f'日本科学未来館のドームシアターで、2005年12月から2007年3月まで上映されたプラネタリウム作品『暗やみの色』。その音楽{src("日本科学未来館", MIRAI)}{src("CINRA", CINRA)}。谷川俊太郎が詩「闇は光の母」を書き下ろし、クラムボンの原田郁子がナレーションと朗読を担当した{src("日本科学未来館", MIRAI)}{src("CINRA", CINRA)}。',
                   f'きっかけは1台の投影機だった。元ソニーのエンジニアが個人で開発した「MEGASTAR-II」を、当時の館長・毛利衛が見て「宇宙で見た星空にもっとも近い」と感じたことから、未来館に常設された{src("CINRA", CINRA)}。肉眼では見えない暗い星まで映し出すその機械に合わせて、ハラカミは、投影される星の数と、自分の曲で使う音の数のバランスにこだわり、およそ4か月でサントラを完成させた{src("CINRA", CINRA)}。',
                   f'しかも、音楽が先だった。映像はまだ存在しない。上映時間で決まった尺に合わせて、まだ見ぬプラネタリウムの映像を想像しながら作られた音楽だった。このあと手がけた映画『天然コケッコー』（2007年）のサントラのように、映像に合わせて作ったのではない{src("CINRA", CINRA)}。ちなみにその『天然コケッコー』の音楽で、第62回毎日映画コンクールの音楽賞を受けている{src("Wikipedia", WTENNEN)}{src("日本科学未来館", MIRAI)}。',
                   f'本人は公式ガイドブックに、こう書いている。「『まだ見えていない何かに焦点を当てる』というコンセプトそのものでした。素敵じゃあないですか！」。歳を取るほど「見えないモノ、理解出来ないモノ＝存在しないモノ」という価値観でしか生きていけない、と思わされるフシがある。「この世界を見限ってしまうのか、希望を持つかは、結局その人次第なのですから」{src("日本科学未来館", MIRAI)}。'],
             say='ハラカミには、家庭用のプラネタリウム機も貸し出されていた（CINRA）。部屋の天井に星を出して、音の数を数えていた人。没後10年の2021年に27日間だけ再上映されたとき、見に来たのべ1,159人のうち約8割が初めての鑑賞だった（日本科学未来館）。',
             bridge='ひとりで鳴らしてきた音は、最後に、ふたりの音になる。',
        ),
        dict(no='09', artist='yanokami with U-zhaan', song='終りの季節', album='ライブ「yanokami indoor festival」', year='',
             catch='京都とニューヨーク、MP3の往復で作ったユニット',
             main=dict(id='-MWRM3d1z2Q', role='Live', artist='yanokami with U-zhaan', song='終りの季節 @ yanokami indoor festival', cap='', page='https://joy-relief-station.lovable.app/cover-guide?artist=yanokami&song=owari-no-kisetsu-yanokami-indoor-festival'),
             body=[f'矢野顕子とレイ・ハラカミのユニット、yanokami。2007年8月、ハラカミのプロデュースでアルバム『yanokami』を出し、その年の「Yahoo!ミュージックアワード2007」ベストコラボレーション部門の最優秀賞を獲った{src("ヤマハミュージックコミュニケーションズ", YAMAHA)}{src("Wikipedia", YW)}。',
                   f'作り方が、この人らしい。矢野顕子の歌とピアノをMP3にしてメールで送ってもらい、ハラカミがバックトラックを作って、またMP3で送り返す。最後のミックスダウンだけ東京のスタジオ。「やはり人間の移動が一番お金がかかりますね」{src("All About", ALLAB3)}。小学生のころ、テレビの中でYMOと一緒に飛び跳ねていた人と、初めて会ったときは「かけていたメガネが曇りました」{src("All About", ALLAB3)}。',
                   '07章でハラカミがひとりで歌った「終りの季節」が、ここではふたりの曲になって、U-zhaanのタブラと一緒にライブで鳴っている。',
                   f'2011年、京都とニューヨークでやりとりしながら2枚目を作っている最中に、東日本大震災が起きた。気持ちが疲弊していく様子を感じた矢野顕子は、京都まで会いに行った。JR京都駅ビル2階の喫茶店で、パフェを食べながら。「2〜3時間は話し込んだんじゃないかな」{src("京都新聞", KYOTO2)}。'],
             more_label='もう1本 — yanokami のスタジオ録音',
             more=[dict(id='Sa4pLN2oPwI', role='yanokami 2007', artist='yanokami', song='気球にのって', cap='')],
        ),
    ],
    close=[f'2011年7月27日、脳出血のため、40歳で亡くなった{src("日本科学未来館", MIRAI)}{src("京都新聞", KYOTO)}。', f'直後のライブは、矢野顕子の出演と、ハラカミが遺した打ち込みのデータで、予定どおり行われた。その年の12月14日、2枚目のアルバム『遠くは近い』が出た{src("Wikipedia", YW)}。', '音は、まだ古びていない。', '君はレイ・ハラカミを知っているか。', '最後に、ひとつだけ。知らなかったなら、今日からでいい。'],
    sources=[('Red Bull Music Academy — A Guide to Rei Harakami', RBMA),
             ('TOWER RECORDS — rei harakami インタビュー（2009）(1)', TOWER1),
             ('TOWER RECORDS — インタビュー (2)', TOWER2),
             ('TOWER RECORDS — インタビュー (3)', TOWER3),
             ('TOWER RECORDS — インタビュー (4) 閃光', TOWER_SENKO),
             ('TOWER RECORDS — インタビュー (5) lust', TOWER_LUST),
             ('TOWER RECORDS — DISCOGRAPHIC（2009）', TOWER),
             ('rings — red curb 再発', RINGS),
             ('ele-king — red curb（野田努・2011）', ELEK),
             ('All About — レイ・ハラカミさんに伺う（2005）1/4', ALLAB),
             ('All About — 2/4', ALLAB2),
             ('All About — 3/4', ALLAB3),
             ('All About — 4/4', ALLAB4),
             ('BARKS — 矢野顕子認定、レイハラカミの世界遺産的最新作（2005）', BARKS),
             ('ヤマハミュージックコミュニケーションズ — yanokami 全世界配信', YAMAHA),
             ('NiEW — 『HOSONO HOUSE』再訪', NIEW),
             ('日本科学未来館 — 暗やみの色 リバイバル上映', MIRAI),
             ('CINRA — 暗やみの色', CINRA),
             ('京都新聞 THE KYOTO（2020）', KYOTO),
             ('京都新聞 THE KYOTO — 矢野顕子の証言（2021）', KYOTO2),
             ('Wikipedia — レイ・ハラカミ', W),
             ('Wikipedia — 閃光 (UAの曲)', WSENKO),
             ('Wikipedia — HOSONO HOUSE', HH),
             ('Wikipedia — yanokami', YW),
             ('Wikipedia — 天然コケッコー', WTENNEN)],
    i18n=I18N,
)

if __name__ == '__main__':
    print(write(M))
