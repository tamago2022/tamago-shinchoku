import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src

W = 'https://ja.wikipedia.org/wiki/%E3%83%AC%E3%82%A4%E3%83%BB%E3%83%8F%E3%83%A9%E3%82%AB%E3%83%9F'
RBMA = 'https://daily.redbullmusicacademy.com/2016/06/rei-harakami-guide'
TOWER = 'https://tower.jp/article/interview/2009/03/19/100041131/100041136'
TOWER1 = 'https://tower.jp/article/interview/2009/03/19/100041131'
TOWER_SENKO = 'https://tower.jp/article/interview/2009/03/19/100041131/100041134'
RINGS = 'https://www.ringstokyo.com/rei-harakami-red-curb/'
ELEK = 'https://www.ele-king.net/review/album/001640/'
BARKS = 'https://www.barks.jp/news/?id=1000008310'
ALLAB = 'https://allabout.co.jp/gm/gc/205772/'
YAMAHA = 'https://www.yamahamusic.co.jp/s/ymc/news/detail/1608'
NIEW = 'https://niewmedia.com/series/hosono_house/3_edymm_wrhra/'
WKNC = 'https://wknc.org/2024/03/07/rei-harakamis-lust-makes-for-addictive-listening/'
HH = 'https://ja.wikipedia.org/wiki/HOSONO_HOUSE'
MIRAI = 'https://www.miraikan.jst.go.jp/events/202106262015.html'
CINRA = 'https://www.cinra.net/article/column-202107-reiharakami_ymmtscl'
KYOTO = 'https://www.kyoto-np.co.jp/articles/thekyoto/676859'
KYOTO2 = 'https://www.kyoto-np.co.jp/articles/thekyoto/676562'
YW = 'https://ja.wikipedia.org/wiki/Yanokami'
TOPIC = 'rei harakami - Topic（公式の音源配信）'

M = dict(
    key='harakami', file='tokushu-rei-harakami.html', title='君はレイ・ハラカミを知っているか',
    desc='Aメロも、Bメロも、サビもない。それなのに、いちど聴いたら耳から離れない。デビュー作『unrest』から『red curb』、UA「閃光」、くるり「ばらの花」、矢野顕子の「世界遺産に決定。」、そしてyanokamiまで。8曲を、ページの中で聴きながら辿る。',
    hero='WH0y2GRiHjI', eyebrow='Feature — rei harakami · 8 songs',
    h1='君はレイ・ハラカミを知っているか',
    lead='Aメロも、Bメロも、サビもない。それなのに、いちど聴いたら耳から離れない。<br/>京都でひとり、小さな機材で鳴らされていた音。ここから8曲。',
    big='20年くらい前、はじめて聴いたとき、<br/>「こんな音楽、聴いたことない」と思った。',
    open=['大げさじゃなく、「今まで聴いてた音楽は何だったんだ」とまで思った。歌もない。サビもない。なのに、ずっと聴いていられる。むしろ、止めたくない。',
          f'レイ・ハラカミ。広島で生まれ、18歳で京都へ移り、そのまま京都で音を作り続けた人{src("All About", ALLAB)}{src("Wikipedia", W)}。デビュー作から順に、その音がどう広がっていったかをたどってみる。'],
    door='最後に、ふたりの名前をひとつにしたユニットのライブが待っている。',
    paper=[],
    chapters=[
        dict(no='01', en='デビュー作の表題曲', title='rei harakami - unrest', year='1998',
             main=dict(id='q6-KIxNIscY', role='Debut 1998', artist='rei harakami', song='unrest', cap=TOPIC),
             body=[f'1998年のデビュー・アルバム『unrest』{src("Red Bull Music Academy", RBMA)}{src("TOWER RECORDS", TOWER)}。その最後に入っている表題曲。後の作品に比べるとテクノ色が強いが、あの深いディレイと、左右に振れる音と、ぬるっと滑る音程は、もうここにある{src("Red Bull Music Academy", RBMA)}。',
                   f'使っていた音源は、ローランドのDTM用モジュールSC-88Pro。本人いわく、それを長年「買い換えてないので、ああなっちゃう」{src("TOWER RECORDS", TOWER1)}。',
                   '誰かがこの人の音を「電子の水彩画」と呼んでいた、と僕は記憶している。にじんで、混ざって、輪郭がはっきりしない。なのに、どこを切っても彼の色をしている。'],
             bridge='3年後、その水彩画は、もっと形容できないものになる。'),
        dict(no='02', en='僕の音楽観を変えたアルバム『red curb』から', title='rei harakami - cape', year='2001',
             main=dict(id='WH0y2GRiHjI', role='red curb 2001', artist='rei harakami', song='cape', cap=TOPIC),
             body=[f'僕の音楽観を変えたのは、2001年のアルバム『red curb』だった{src("Wikipedia", W)}{src("TOWER RECORDS", TOWER)}。ポップスで育った耳は、曲を「Aメロ・Bメロ・サビ」で数えてしまう。でもこのアルバムは、そのどれにも当てはまらない。言葉にしようとして、できなかった。いまだに形容できない。',
                   f'本人のコメントが残っている。「3枚目の制作にあたって、もう好きな事ばっかりやろう、というか、好きな事しか出来ないなあ…なんて考えながら作ってました」{src("rings", RINGS)}。',
                   f'ele-kingのレビューは、こう書いた。「彼が愛したロバート・ワイアットのように美しい作品だが、思い詰めた悲しみというものはない」{src("ele-king", ELEK)}。'],
             pull='「今まで聴いてた音楽は、何だったんだ」',
             say='このアルバム、出したら引退するつもりだった、と本人（rings）。辞める気の人が、いちばん自由な音を出してしまった事件。',
             bridge='この音を、ほかの人たちも放っておかなかった。最初の大仕事は、UA。'),
        dict(no='03', en='ハラカミが共同プロデュース', title='UA - 閃光', year='2002',
             main=dict(id='eMRTkimQJWM', role='Official MV 2002', artist='UA', song='閃光', cap='UA 公式アーティストチャンネル'),
             body=[f'UAの「閃光」。ハラカミは共同プロデュースで関わった{src("BARKS", BARKS)}{src("Wikipedia", W)}。',
                   f'本人は、こう振り返っている。「彼女にとっては久々のソロで、しかも初めての作詞作曲で、『ワーッ!』となってるわけですよ。僕は僕で、ちゃんとしたスタジオで誰かと一緒にやるっていうことに関して、右も左もわかってないですから。それまではただの引きこもりですからね（笑）」{src("TOWER RECORDS", TOWER_SENKO)}。'],
             bridge='人の曲を、自分の音に塗り替える。くるりの名曲でも、それをやった。'),
        dict(no='04', en='ハラカミのリミックス', title='くるり - ばらの花 (remixed by Rei Harakami)', year='『ワールズエンド・スーパーノヴァ』より',
             main=dict(id='Yu3Ch9cNYMA', role='Remix', artist='くるり', song='ばらの花 ～remixed by Rei Harakami', cap='Quruli - Topic（公式の音源配信）'),
             body=[f'くるりのアルバム『ワールズエンド・スーパーノヴァ』に入っているリミックス。2003年、これを聴いた矢野顕子が、ハラカミの才能をキャッチした。ハラカミのほうは、デビュー・アルバムのころから矢野顕子の音楽を深く敬愛していた{src("ヤマハミュージックコミュニケーションズ", YAMAHA)}。',
                   f'ふたりの交流は、その年の矢野顕子の恒例コンサート「さとがえるコンサート」のトラック制作を頼まれたところから始まる{src("ヤマハミュージックコミュニケーションズ", YAMAHA)}。原曲を知っている人ほど、最初の数秒で「あ、ハラカミだ」と分かるはず。'],
             more_label='聴きくらべ — 元の「ばらの花」',
             more=[dict(id='baNgL0jFkAs', role='Original', artist='くるり', song='ばらの花', cap='くるり 公式アーティストチャンネル')],
             bridge='そして2005年。今度は自分の声で、人の曲を歌ってしまう。'),
        dict(no='05', en='細野晴臣の「終りの季節」を、本人が歌う', title='rei harakami - owari no kisetsu', year='2005',
             main=dict(id='wC1z9sNSaXo', role='lust 2005', artist='rei harakami', song='owari no kisetsu', cap=TOPIC),
             body=[f'2005年のアルバム『lust』。以前共演していた矢野顕子は、このアルバムに「世界遺産に決定。文句無し。」と言葉を寄せた{src("All About", ALLAB)}{src("BARKS", BARKS)}。もちろんユネスコとは関係ない、矢野顕子の独断の認定だ。僕はずっと yanokami の頃の話だと記憶していたけど、ユニットとしてデビューするより前の言葉だった。',
                   f'その『lust』で、細野晴臣が1973年の『HOSONO HOUSE』に入れた「終りの季節」をカバーしている。歌っているのは本人{src("NiEW", NIEW)}{src("WKNC", WKNC)}{src("Wikipedia", HH)}。抑揚をさらに抑えた、ぶっきらぼうな歌い方に、宅録の人らしさが出ている{src("NiEW", NIEW)}。'],
             say='このハラカミ版、もとは yanokami でカバーするためのデモだった（NiEW）。下書きが、そのまま清書になってしまった事件。',
             bridge='自分の声の次は、人の声と、詩を連れてくる。'),
        dict(no='06', en='谷川俊太郎の詩を、原田郁子が読む', title='rei harakami - yami wa hikari no haha', year='2006',
             main=dict(id='N6UmEfJN61o', role='暗やみの色', artist='rei harakami', song='yami wa hikari no haha', cap=TOPIC),
             body=[f'日本科学未来館のプラネタリウム作品『暗やみの色』の音楽。2005年から2007年まで上映された。谷川俊太郎が詩を書き、クラムボンの原田郁子が朗読した{src("日本科学未来館", MIRAI)}。',
                   f'肉眼では見えない暗い星まで映し出す投影機に合わせて、ハラカミは、映し出される星の数と、自分の曲で使う音の数のバランスにこだわった{src("CINRA", CINRA)}。'],
             say='星の数に合わせて、音の数を決めていた（CINRA）。プラネタリウムで、音まで数えていた人。',
             bridge='ひとりで鳴らしてきた音は、最後に、ふたりの音になる。'),
        dict(no='07', en='最後に、これをどうぞ', title='yanokami with U-zhaan - 終りの季節', year='Live',
             main=dict(id='-MWRM3d1z2Q', role='Live', artist='yanokami with U-zhaan', song='終りの季節 @ yanokami indoor festival', cap='DAX -Space Shower Digital Archives X-'),
             body=[f'矢野顕子とレイ・ハラカミのユニット、yanokami。2007年にアルバム『yanokami』を出している{src("Wikipedia", YW)}{src("ヤマハミュージックコミュニケーションズ", YAMAHA)}。',
                   '05章でハラカミがひとりで歌った「終りの季節」が、ここではふたりの曲になって、U-zhaanのタブラと一緒にライブで鳴っている。',
                   f'2011年の春、震災のあと、矢野顕子は京都まで会いに行った。京都駅ビルの喫茶店で、パフェを食べながら、2〜3時間話し込んだという{src("京都新聞", KYOTO2)}。'],
        ),
    ],
    close=[f'2011年、40歳で亡くなった{src("京都新聞", KYOTO)}。', '音は、まだ古びていない。', '君はレイ・ハラカミを知っているか。知らなかったなら、今日からでいい。'],
    sources=[('Red Bull Music Academy — A Guide to Rei Harakami', RBMA), ('TOWER RECORDS — rei harakami インタビュー（2009）', TOWER1), ('TOWER RECORDS — DISCOGRAPHIC（2009）', TOWER),
             ('rings — red curb 再発', RINGS), ('ele-king — red curb', ELEK), ('All About — レイ・ハラカミさんに伺う（2005）', ALLAB), ('BARKS — 矢野顕子認定、レイハラカミの世界遺産的最新作（2005）', BARKS),
             ('ヤマハミュージックコミュニケーションズ — yanokami 全世界配信', YAMAHA), ('NiEW — 『HOSONO HOUSE』再訪', NIEW), ('WKNC — lust', WKNC), ('日本科学未来館 — 暗やみの色', MIRAI), ('CINRA — 暗やみの色', CINRA),
             ('京都新聞 THE KYOTO（2020）', KYOTO), ('京都新聞 THE KYOTO — 矢野顕子の証言', KYOTO2), ('Wikipedia — レイ・ハラカミ', W), ('Wikipedia — HOSONO HOUSE', HH), ('Wikipedia — yanokami', YW)],
    note='「電子の水彩画」は出典が見つからなかったので、たまごさんの記憶として書いています。動画は公式の配信元です。事実は上の出典で確認できた範囲だけを書いています。',
)

if __name__ == '__main__':
    print(write(M))
