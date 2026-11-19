# -*- coding: utf-8 -*-
"""月の特集 vol.1「月に吠える 〜月を見て歌う人々〜」（2026-10-19・125816番・7曲・濃く短く）
10-19 たまごさん：曲は7曲（布袋／ビートルズ／マイケル・ジャクソン／グレン・ミラー／Moon River／三日月／十五夜お月さん）。
聴き比べは載せない（Mr. Moonlight の原曲・三日月の玉置浩二版は曲ページで）。落とした曲は status/tsuki_dai2dan_kouho.json。
前の版（17章・122703番）は git の履歴にある。型＝怒れる人々 vol.1（mag_build）。事実は下の出典で確かめたものだけ。
ヘッダーは店主指定の「月の写真」（assets/tsuki01/hero.webp・hero-og.jpg）。章の合間の絵は Grokボットとたまごさんの月の絵（fuukei.json）。
使い方: python3 tools/magazine/spec_tsuki01.py   → share/check と status/magazine_prod に書く
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mag_build as MB
from mag_build import src

HERE = os.path.dirname(os.path.abspath(__file__))
_i18n_path = os.path.join(HERE, 'i18n_tsuki01.json')
I18N = json.load(open(_i18n_path, encoding='utf-8')) if os.path.exists(_i18n_path) else None

# ---- 出典（本文に出るものは全部ここ） ----
WAPOLLO = 'https://en.wikipedia.org/wiki/List_of_Apollo_astronauts'
WCONSP = 'https://en.wikipedia.org/wiki/Moon_landing_conspiracy_theories'
WTSUKI = 'https://ja.wikipedia.org/wiki/%E6%9C%88%E3%81%AB%E5%90%A0%E3%81%88%E3%82%8B_(%E8%90%A9%E5%8E%9F%E6%9C%94%E5%A4%AA%E9%83%8E%E3%81%AE%E8%A9%A9%E9%9B%86)'
WSAKU = 'https://ja.wikipedia.org/wiki/%E8%90%A9%E5%8E%9F%E6%9C%94%E5%A4%AA%E9%83%8E'
WHOTEI = 'https://ja.wikipedia.org/wiki/DANCING_WITH_THE_MOONLIGHT'
WGH = 'https://ja.wikipedia.org/wiki/GUITARHYTHM'
WMRM = 'https://en.wikipedia.org/wiki/Mr._Moonlight_(song)'
WLUNATIC = 'https://en.wikipedia.org/wiki/Lunatic'
WWERE = 'https://en.wikipedia.org/wiki/Werewolf'
WLUNAR = 'https://en.wikipedia.org/wiki/Lunar_effect'
WTHR = 'https://en.wikipedia.org/wiki/Michael_Jackson%27s_Thriller_(music_video)'
WM25 = 'https://en.wikipedia.org/wiki/Motown_25:_Yesterday,_Today,_Forever'
WMW = 'https://en.wikipedia.org/wiki/Moonwalk_(dance)'
WMS = 'https://en.wikipedia.org/wiki/Moonlight_Serenade'
WGM = 'https://en.wikipedia.org/wiki/Glenn_Miller'
WGMJ = 'https://ja.wikipedia.org/wiki/%E3%82%B0%E3%83%AC%E3%83%B3%E3%83%BB%E3%83%9F%E3%83%A9%E3%83%BC'
WMOONR = 'https://en.wikipedia.org/wiki/Moon_River'
WMIKA = 'https://ja.wikipedia.org/wiki/%E4%B8%89%E6%97%A5%E6%9C%88_(%E7%B5%A2%E9%A6%99%E3%81%AE%E6%9B%B2)'
WMOTO = 'https://ja.wikipedia.org/wiki/%E6%9C%AC%E5%B1%85%E9%95%B7%E4%B8%96'
WNOGU = 'https://ja.wikipedia.org/wiki/%E9%87%8E%E5%8F%A3%E9%9B%A8%E6%83%85'
WTSUKIMI = 'https://ja.wikipedia.org/wiki/%E6%9C%88%E8%A6%8B'
WFULL = 'https://en.wikipedia.org/wiki/Full_moon'
HERO_PAGE = 'https://commons.wikimedia.org/wiki/File:Supermoon,_September_28,_2015_(UTC),_Osaka,_Japan.jpg'

W = lambda u: src('Wikipedia', u)

M = dict(
    key='tsuki01', file='hito-wa-naze-tsuki-wo-miru-01.html', title='月に吠える 〜月を見て歌う人々〜 月の特集 vol.1',
    desc='月に行ったことがある人は、まだ12人。それでも人は月を見上げて、話しかけてきた。布袋寅泰、ビートルズ、マイケル・ジャクソン、グレン・ミラー、オードリー・ヘプバーン、絢香、そして「十五夜お月さん」。7曲、ぜんぶページの中で聴ける。',
    hero='1nqPCbYVGLw',  # 組むときの仮。write() の中で店主指定の月の写真（assets/tsuki01/hero.webp）に差し替える
    eyebrow='Series — The Moon · vol.1',
    h1='月に吠える<br/><span class="cw-hero__sub">〜月を見て歌う人々〜</span>',
    lead='月の特集 vol.1。<br/>人はなぜ月を見るのか。月に話しかけてきた人たちの歌を7曲、ぜんぶこのページの中で。',
    big='月には、行ったことがある人が、まだ12人しかいない。',
    open=[f'1969年から1972年まで、アポロ計画で月面を歩いたのは12人{W(WAPOLLO)}。それきり、誰も行っていない。「本当は行っていない」と言う人も、いまだにいる{W(WCONSP)}。それはそれとして。',
          '人はなぜ月を見るのか。行けもしないのに見上げて、祈った。恋しい人を思った。月明かりの下で恋をした。ぼーっと眺めて、お団子を食べて、季節を知った。人は、月に話しかけてきた。',
          f'題は、萩原朔太郎が1917年に出した最初の詩集『月に吠える』から借りた{W(WTSUKI)}。月に話しかけた人たちの歌を7曲。まず、月あかりで踊った男から。'],
    door='順番は年代順ではありません。まず、ギターを置いて歌った男から。',
    paper=[],
    others_skip=[],
    map=False,
    songs_n=7,
    chapters=[
        # 01 布袋
        dict(no='01', artist='布袋寅泰', song='DANCING WITH THE MOONLIGHT', album='アルバム『GUITARHYTHM』', year='1988.10.5',
             catch='ギターを置いて、月あかりで踊った',
             main=dict(id='1nqPCbYVGLw', role='GUITARHYTHM 1988', artist='布袋寅泰', song='DANCING WITH THE MOONLIGHT', cap=''),
             body=[f'1988年、ソロ1作目のアルバム『GUITARHYTHM』の1曲{W(WHOTEI)}{W(WGH)}。BOØWYが終わった年に、布袋寅泰が最初にやったことのひとつが「月あかりと踊る」だった。',
                   f'録音はロンドンのアビー・ロード・スタジオ、それも第2スタジオ。ビートルズが使った部屋だ{W(WGH)}。翌年イギリスで12インチを出したが、ほとんど売れずに早々と廃盤になった{W(WHOTEI)}。',
                   f'代々木の初披露で、布袋はこの曲だけギターを持たず、歌だけでステージに立った{W(WHOTEI)}{W(WGH)}。ギターの神様みたいな人が、月の前では手ぶらになる。'],
             bridge='ビートルズの部屋で録った男の、24年前。リバプールの4人は、レコードの裏側で月を拾っていた。'),
        # 02 Beatles
        dict(no='02', artist='The Beatles', song='Mr. Moonlight', album='アルバム『Beatles for Sale』', year='1964.12.4',
             catch='B面で拾った月に、前奏なしで叫ぶ',
             main=dict(id='FZQ8nWZJrhA', role='Beatles for Sale 1964', artist='The Beatles', song='Mr. Moonlight', cap=''),
             body=[f'もとは1962年、アトランタのドクター・フィールグッド＆ジ・インターンズのシングルのB面{W(WMRM)}。ビートルズはその裏面を拾って、ライブでやり始めた{W(WMRM)}。1962年の原曲は、この曲のページで聴ける。',
                   f'ライブではよく1曲目だった。ジョンが前奏なしで、いきなり「ミスター！」と叫ぶ。何もないところから正しい音を出さなければならなかった、とロードマネージャーのニール・アスピノールが振り返っている{W(WMRM)}。',
                   f'ところが評論家には、「あのアルバムで、たいていの人がいちばん嫌いな曲」とまで書かれた{W(WMRM)}。月に本気で叫ぶ人は、だいたい笑われる。'],
             say='月に向かって、前奏なしで「ミスター！」。会社の朝礼でこれをやると、翌日から朝礼に呼ばれなくなる。ジョンだから許された。',
             bridge='叫ぶ月があるなら、吠える月もある。英語で「月」は、昔から「狂う」と隣り合わせだった。'),
        # 03 MJ
        dict(no='03', artist='Michael Jackson', song='Thriller', album='ミュージック・ビデオ／監督：ジョン・ランディス', year='1983.12.2',
             catch='狼男だと思っていたら、猫だった',
             main=dict(id='sOnqjkJTMaA', role='Short film 1983', artist='Michael Jackson', song='Thriller', cap=''),
             body=[f'英語の lunatic（狂人）は、ラテン語の「月に打たれた」から来ている。月が狂気を起こすと、本気で信じられていた{W(WLUNATIC)}。詩集『月に吠える』を「変態心理の代表作」扱いされた朔太郎も、「少しく不愉快です」と書いている{W(WSAKU)}。月に吠えると、人は勝手にこちらを病気にする。',
                   f'狼男の話も古い。紀元60年ごろのローマの小説『サテュリコン』に、もう狼に変わる男が出てくる。満月の夜に変身する姿が定番になったのは、主に今の映画や小説の中だ{W(WWERE)}。',
                   f'潮の満ち引きは、本当に月のせいだ。でも「満月の夜は事件や出産が増える」は、たくさんの研究で関係が見つかっていない。月の周期と月経の周期が近いのも、偶然らしい{W(WLUNAR)}。つまり、俗説だ。',
                   f'マイケル・ジャクソンは映画『狼男アメリカン』を見て、その監督ジョン・ランディスに短編を頼んだ。ところが特殊メイクのリック・ベイカーは「狼男はもう作りたくない」と、彼を猫人間にした。冒頭には「オカルトを信じるものではない」という断り書きまで付いている{W(WTHR)}。2009年、ミュージック・ビデオとして初めてアメリカ国立フィルム登録簿に選ばれた{W(WTHR)}。',
                   f'同じ年の春、モータウン25周年の特番で、彼は初めて人前でムーンウォークをした{W(WM25)}。動きそのものは「バックスライド」と呼ばれた古いもので、マイケルがやったのは発明ではなく、命名だった{W(WMW)}。月を歩いた人は12人。月を歩く真似をした人は、数えきれない。'],
             more_label='もう1本 — 1983年3月、初めて人前でムーンウォークした夜',
             more=[dict(id='CauNjt2j-BM', role='Motown 25 / 1983', artist='Michael Jackson', song='Billie Jean', cap='')],
             say='満月で事件が増える、は俗説。ただ、満月の夜に「今日だけ」とコンビニでアイスを2個買う僕の事件は、毎月起きている。',
             bridge='狂った月の話は、ここまで。ムーンウォークの44年前、月明かりの下では、みんなゆっくり踊っていた。'),
        # 04 Glenn Miller
        dict(no='04', artist='Glenn Miller & His Orchestra', song='Moonlight Serenade', album='作曲：グレン・ミラー／作詞：ミッチェル・パリッシュ', year='1939',
             catch='「日の出」の相方として、月明かりになった',
             main=dict(id='9Ws6DdrDtyo', role='Bluebird 1939', artist='Glenn Miller & His Orchestra', song='Moonlight Serenade', cap=''),
             body=[f'グレン・ミラー楽団は、この曲に名前が付く前から、テーマ曲として演奏していた。もとは1935年の「Now I Lay Me Down to Weep」で、題名は何度も変わった{W(WMS)}。',
                   f'最後の名前を決めたのは出版社だった。ミラーが「Sunrise Serenade（日の出のセレナーデ）」を録音すると知って、日の出の相方なら月明かりだろう、と{W(WMS)}。1939年4月4日にニューヨークで録音、全米3位{W(WMS)}。',
                   f'1944年12月15日、少佐になっていたミラーを乗せた飛行機は、イングランドからフランスへ向かう途中、英仏海峡の上で消えた。原因は、はっきりしていない{W(WGM)}{W(WGMJ)}。テーマ曲だけが残って、いまも月明かりの下で鳴っている。'],
             say='1943年、アメリカの陸軍省はこの曲を兵隊向けのレコード「V-Disc」にしている。戦地にも、月明かりのセレナーデは配給された。',
             bridge='戦争の前の、ダンスホールの月。戦争が終わって16年後、ニューヨークの非常階段で、月は川と並べられた。'),
        # 05 Moon River
        dict(no='05', artist='Audrey Hepburn', song='Moon River', album='映画『ティファニーで朝食を』／作曲：ヘンリー・マンシーニ／作詞：ジョニー・マーサー', year='1961',
             catch='「私の死体を越えてからにして」。重役が切ろうとした歌',
             main=dict(id='uirBWk-qd9A', role='Film 1961', artist='Audrey Hepburn', song='Moon River', cap=''),
             body=[f'1961年の映画『ティファニーで朝食を』。マンシーニとマーサーは、ヘプバーンが歌うためにこの曲を書いた。アカデミー歌曲賞{W(WMOONR)}。',
                   f'マーサーの最初の題は「Blue River」。ジョージア州サバンナで、夏にハックルベリーを摘んだ記憶を重ねて書いた{W(WMOONR)}。月をぼーっと眺めながら、ここではないどこかへ行きたくなる歌だ。',
                   f'試写の反応が鈍く、パラマウントの重役がこの曲を切ろうと言い出した。ヘプバーンの返事は証言によって幅があるが、「私の死体を越えてからにして！」から、もっと激しい言い回しまで伝わっている{W(WMOONR)}。'],
             bridge='旅立ちの月の次は、置いてきた人を思う月。この特集でいちばん新しい月が、いちばん欠けている。'),
        # 06 絢香
        dict(no='06', artist='絢香', song='三日月', album='4枚目のシングル／作詞：絢香／作曲：西尾芳彦・絢香', year='2006.9.27',
             catch='欠けている月の方を、人は長く見ている',
             main=dict(id='wHw6W4BznTM', role='Single 2006', artist='絢香', song='三日月', cap=''),
             body=[f'テーマは遠距離恋愛。大阪を離れて上京することが現実になり始めた頃、地元の大切な人たちを思って書いた{W(WMIKA)}。',
                   f'「三日月」は、携帯電話の形の比喩でもある{W(WMIKA)}。2006年の携帯は、まだ折りたたみ。閉じると、三日月に似ている。',
                   f'初のオリコン週間1位。その年、レコード大賞の最優秀新人賞。紅白でもこの曲を歌った{W(WMIKA)}。2018年からはマクドナルドの月見バーガーのCMで流れた{W(WMIKA)}。会えない人を思う歌が、月見の季節の合図になった。',
                   '玉置浩二が歌う「三日月」は、この曲のページで。'],
             bridge='遠い人を思う月は、100年前の子どもの歌にもいた。最後は、日本の秋の月へ。'),
        # 07 十五夜お月さん
        dict(no='07', artist='ひばり児童合唱団', song='十五夜お月さん', album='作詞：野口雨情／作曲：本居長世', year='1920（大正9）',
             catch='月にあいさつしてから、いない人の話をする',
             main=dict(id='WVOZhpksvpU', role='1920 / 童謡', artist='ひばり児童合唱団', song='十五夜お月さん', cap=''),
             body=[f'1920年、本居長世が発表した童謡。歌ったのは長世の長女・みどりで、この曲で一躍有名になり、童謡歌手の第1号、レコード吹き込みの第1号になった{W(WMOTO)}。作詞は「七つの子」の野口雨情{W(WNOGU)}。',
                   '歌は、月にあいさつするところから始まる。あいさつをしてから、いなくなった人の話をする。月は何も言わない。言わないから、話せる。',
                   f'十五夜の月見は、中国から平安時代の貴族に伝わった。文献には、859年の宴が記されている{W(WTSUKIMI)}。団子が広まったのは江戸時代、すすきが全国に広まったのは明治から。とれたての里芋を供えるので「芋名月」とも呼ぶ{W(WTSUKIMI)}。',
                   f'同じ秋の満月を、西洋では「ハーベスト・ムーン（収穫の月）」と呼ぶ。秋分にいちばん近い満月のことで、この呼び名は18世紀の初めから記録がある{W(WFULL)}。東は団子を供え、西は名前をつけた。どちらも、実りの夜に月を見上げている。'],
             say='旧暦の8月15日は、暦の上でかならず仏滅。だから「仏滅名月」とも呼ぶ。いちばんきれいな月の日が、いちばん縁起が悪い。お団子は、たぶん慰めでもある。'),
    ],
    close=['布袋は月あかりで踊った。ジョンは月に叫んだ。マイケルは月を歩いた。グレン・ミラーは月明かりで人を踊らせ、ヘプバーンは月の川を眺め、絢香は欠けた月に遠い人を重ね、子どもたちは十五夜の月にあいさつをした。',
           '人は昔から色んな思いを月に馳せてきた。けれど、誰も月から返事をもらったことはない。',
           'それでも人は、今でも月を眺める。帰りのコンビニの袋を提げたまま、今夜も。次回もお楽しみに。'],
    sources=[('Wikipedia — List of Apollo astronauts（月面を歩いた12人）', WAPOLLO), ('Wikipedia — Moon landing conspiracy theories', WCONSP),
             ('Wikipedia — 月に吠える（萩原朔太郎の詩集）', WTSUKI), ('Wikipedia — 萩原朔太郎', WSAKU),
             ('Wikipedia — DANCING WITH THE MOONLIGHT', WHOTEI), ('Wikipedia — GUITARHYTHM', WGH),
             ('Wikipedia — Mr. Moonlight (song)', WMRM),
             ('Wikipedia — Lunatic', WLUNATIC), ('Wikipedia — Werewolf', WWERE), ('Wikipedia — Lunar effect', WLUNAR),
             ("Wikipedia — Michael Jackson's Thriller (music video)", WTHR), ('Wikipedia — Motown 25: Yesterday, Today, Forever', WM25), ('Wikipedia — Moonwalk (dance)', WMW),
             ('Wikipedia — Moonlight Serenade', WMS), ('Wikipedia — Glenn Miller', WGM), ('Wikipedia — グレン・ミラー', WGMJ),
             ('Wikipedia — Moon River', WMOONR), ('Wikipedia — 三日月 (絢香の曲)', WMIKA),
             ('Wikipedia — 本居長世', WMOTO), ('Wikipedia — 野口雨情', WNOGU), ('Wikipedia — 月見', WTSUKIMI), ('Wikipedia — Full moon（Harvest moon）', WFULL),
             ('ヘッダー写真 — Laitche「Supermoon, September 28, 2015, Osaka」（CC BY-SA 4.0 / Wikimedia Commons）', HERO_PAGE)],
    note='',
)
if I18N:
    M['i18n'] = I18N

# ヘッダー＝店主指定の月の写真（差し替えは assets/tsuki01/hero.webp と hero-og.jpg の2ファイルを置き換えるだけ）
HERO_IMG = 'assets/tsuki01/hero.webp'
HERO_OG = MB.BASE + 'assets/tsuki01/hero-og.jpg'


def moon_hero(h):
    yt = f'https://i.ytimg.com/vi/{M["hero"]}/maxresdefault.jpg'
    h = h.replace(f'<link rel="preload" as="image" href="{yt}"/>', f'<link rel="preload" as="image" href="{HERO_IMG}"/>')
    h = h.replace(f'content="{yt}"', f'content="{HERO_OG}"')
    h = h.replace('<meta property="og:image:width" content="1280"/><meta property="og:image:height" content="720"/>', '<meta property="og:image:width" content="1200"/><meta property="og:image:height" content="630"/>')
    import re as R
    h = R.sub(r'(<div class="cw-hero__bg" aria-hidden="true">)<img [^>]*?src="' + R.escape(yt) + r'"[^>]*/>',
              lambda q: q.group(1) + f'<img src="{HERO_IMG}" data-hero-by="tamago" width="1600" height="1198" alt="" decoding="async"/>', h, count=1)
    assert 'data-hero-by="tamago"' in h and HERO_OG in h, 'ヘッダーの差し替えが当たらない'
    return h


def dedupe_src(h):
    """同じ段落の中で同じ出典リンクが2回以上出たら、2回目以降を消す（送る量を増やさない・読みやすい）。"""
    import re as R
    def one(m):
        seen = set()
        def a(q):
            if q.group(1) in seen:
                return ''
            seen.add(q.group(1)); return q.group(0)
        return R.sub(r'<a class="cw-src" href="([^"]+)"[^>]*>[^<]*</a>', a, m.group(0))
    return R.sub(r'<p\b[^>]*>.*?</p>|<div class="say__bub">.*?</div>', one, h, flags=R.S)


def unquote_wiki(h):
    """出典リンクの ja.wikipedia の %E3%81… を日本語のまま書く（送る量 −1KB。ブラウザが送るときに同じ形に戻す）。"""
    import re as R
    from urllib.parse import unquote
    return R.sub(r'href="(https://ja\.wikipedia\.org/wiki/[^"]+)"', lambda q: 'href="' + unquote(q.group(1)).replace('"', '%22') + '"', h)


def write(m):
    """mag_build.write と同じ（確認ページ＋本番の写し＋訳のJSON）。ヘッダーだけ月の写真にしてから書く。"""
    h = MB.build(m)
    h = moon_hero(h)
    h = dedupe_src(h)
    h = h.replace('" target="_blank" rel="noopener">', '" target="_blank">')  # rel=noopener は target=_blank の既定（軽く）
    h = unquote_wiki(h)
    MB.kanmon(m, h)
    p = os.path.join(MB.REPO, 'share/check', m['file'])
    open(p, 'w', encoding='utf-8').write(h)
    d = os.path.join(MB.REPO, 'status/magazine_prod'); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, MB.PROD[m['key']]), 'w', encoding='utf-8').write(h)
    if m.get('i18n'):
        tr = json.loads(json.dumps(m['i18n']))
        tr.pop('_bytext_keep', None)  # 訳の当て直し用の控え（tsuki01_i18n.py）。本番には送らない
        for l, dd in MB.common_i18n().items():
            tr.setdefault(l, {}).update(dd)
        t = json.dumps(tr, ensure_ascii=False, separators=(',', ':'))
        for dd in (os.path.join(MB.REPO, 'share/check'), d):
            open(os.path.join(dd, MB.i18n_name(m)), 'w', encoding='utf-8').write(t)
    return p


if __name__ == '__main__':
    print(write(M))
