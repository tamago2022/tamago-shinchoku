# -*- coding: utf-8 -*-
"""バックナンバー一覧（全マガジン・ジャンル別）を作る（2026-10-16 たまごさん指示）。
本番：https://joy-relief-station.lovable.app/magazine/backnumber.html（＝ public/magazine/backnumber.html）
マガジンを足したら、下の GENRES に1行足して python3 tools/magazine/backnumber.py → put → deploy。
"""
import os, sys, json, html as H
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mag_build as MB

S = 'https://joy-relief-station.lovable.app'
M = S + '/magazine/'
# (ジャンル名, [訳 en, zh, es, ko], [(題, 入口の一言, URL, 英語版URL or None)])
GENRES = [
    ('多幸感ポップス', ('Euphoric pop', '幸福感流行乐', 'Pop eufórico', '다행감 팝스'), [
        ('楽しくなりたいから ― 多幸感ポップス', '人はなぜ音楽を聴くのか 第1回', M + 'naze-ongaku-01-takoukan.html', None),
        ('30年前から届いた未来', 'Jamiroquai「Virtual Insanity」', S + '/feature/virtual-insanity', S + '/feature/virtual-insanity-en'),
        ('知っている曲ほど、知らない旅をしている。', 'Domenico Modugno「Volare」', S + '/feature/volare', None),
        ('まず、聴いてください。— MONKEY MAGIC、48年目の実験', 'MONKEY MAGIC', S + '/feature/monkey-magic', None),
    ]),
    ('ひとりひとりが主役', ('One artist at a time', '每一位都是主角', 'Un artista, una historia', '한 사람 한 사람이 주인공'), [
        ('君は星勝を知っているか', '編曲家・作曲家', M + 'kimi-wa-hoshi-katsu.html', None),
        ('君はレイ・ハラカミを知っているか', 'rei harakami／yanokami', M + 'rei-harakami.html', None),
        ('本人がいなくなっても、旅は続いている。', 'Nujabes', S + '/feature/nujabes-legacy', None),
        ('景色より先に、音楽が旅を連れてくる。', 'Nujabes「The Final View」', S + '/feature/final-view', None),
    ]),
    ('夏と青春の名曲', ('Songs of summer and youth', '夏天与青春的名曲', 'Canciones de verano y juventud', '여름과 청춘의 명곡'), [
        ('1980年の夏は、まだ終わっていない。', '松田聖子「青い珊瑚礁」', S + '/feature/aoi-sangosho', None),
        ('歌は、故郷へ帰ってくる。', 'フジファブリック「若者のすべて」', S + '/feature/wakamono-no-subete', None),
        ('夏は終わる。返事は、来る。', '山下達郎「さよなら夏の日」', S + '/feature/sayonara-natsu-no-hi', S + '/feature/sayonara-natsu-no-hi-en'),
        # （あの日にかえりたい：中身未点検のため 2026-10-16 本番から外した）
    ]),
    ('世界が見つけた日本の歌', ('Japanese songs the world found', '世界发现的日本歌', 'Canciones japonesas que el mundo descubrió', '세계가 발견한 일본의 노래'), [
        ('世界が先に見つけた、日本の夜。', 'シティポップ14曲', S + '/feature/citypop-sekai', None),
        ('日本の若者が知らない曲が、海外を盛り上げている。', 'Midnight Pretenders', S + '/feature/midnight-pretenders-abroad', None),
        ('『これいいね』は国境を越える ― デジタル東方見聞録', '国境を越える「これいいね」', S + '/feature/ekkyo', None),
        ('毎日歌う国に、理由がある。', 'フィリピンとカラオケ', S + '/feature/philippine-voice', None),
    ]),
    ('弾き語りとロック', ('Voice, guitar and rock', '自弹自唱与摇滚', 'Voz, guitarra y rock', '弾き語り와 록'), [
        ('心を震わせる弾き語り', 'Lately から Shape Of You まで', S + '/feature/hikigatari', None),
        ('弾き語り・ジョシュ・ターナー編', 'はっぴいえんど「風をあつめて」から', M + 'hikigatari-josh-turner.html', None),
    ]),
    ('シリーズ「怒れる人々」', ('Series: The Angry Ones', '系列「愤怒的人们」', 'Serie: La gente enfadada', '시리즈 「분노한 사람들」'), [
        ('怒れる人々 vol.1 〜ロックは死んだのか〜', 'Sex Pistols から Ado、Prince まで11曲', M + 'ikareru-01.html', None),
    ]),
    ('シリーズ「月の特集」', ('Series: The Moon', '系列「月亮特辑」', 'Serie: La Luna', '시리즈 「달 특집」'), [
        ('月に吠える 〜月を見て歌う人々〜 月の特集 vol.1', '布袋寅泰から十五夜お月さんまで7曲', M + 'hito-wa-naze-tsuki-wo-miru-01.html', None),
    ]),
    ('シリーズ「人はなぜ踊るのか」', ('Series: Why Do People Dance?', '系列「人为什么跳舞」', 'Serie: ¿Por qué bailamos?', '시리즈 「사람은 왜 춤추는가」'), [
        ('人が踊るとき vol.1 〜人はなぜ踊るのか〜', '1万年前の壁から、ジェームス・ブラウン、ドナ・サマー、モントルーまで11曲', M + 'hito-ga-odoru-01.html', None),
    ]),
]
I18N = {'b_eyebrow': ('Back issues', '往期', 'Números anteriores', '백넘버'),
        'b_h1': ('All back issues', '全部往期', 'Todos los números', '모든 백넘버'),
        'b_lead': ('Every magazine from Gokigen Hokyujo, roughly sorted by mood.', 'ごきげん補給所的全部专题，按大致的风格分类。', 'Todas las revistas de Gokigen Hokyujo, ordenadas a grandes rasgos por estilo.', '고키겐 보급소의 모든 매거진을, 대략 장르별로.'),
        'b_en': ('English edition', '英文版', 'Edición en inglés', '영어판')}


def _auto():
    """即公開（tools/magazine/sokkou.py）で出た号を「新着」に載せる。GENRES に手で足したら自動の側からは消える（二重に載せない）。"""
    p = os.path.join(HERE, 'backnumber_auto.json')
    if not os.path.exists(p):
        return []
    known = {u for _, _, items in GENRES for _, _, u, _ in items}
    items = [(x['title'], x.get('kicker') or '新着', x['url'], None) for x in json.load(open(p, encoding='utf-8')) if x['url'] not in known]
    return [('新着', ('New', '新刊', 'Novedades', '신착'), items)] if items else []


def build():
    global GENRES
    GENRES = _auto() + [g for g in GENRES if g[0] != '新着']
    e = lambda t: H.escape(t, quote=True)
    tr = {l: {} for l in MB._LG4}
    for k, v in I18N.items():
        for l, t in zip(MB._LG4, v): tr[l][k] = t
    secs = []
    n = 0
    for gi, (g, g4, items) in enumerate(GENRES):
        for l, t in zip(MB._LG4, g4): tr[l][f'b_g{gi}'] = t
        lis = []
        for title, kicker, url, en in items:
            n += 1
            extra = f'<a class="cw-bn-en" href="{e(en)}" data-i18n="b_en">英語版</a>' if en else ''
            lis.append(f'<li><a href="{e(url)}"><small>{e(kicker)}</small><b>{e(title)}</b><span aria-hidden="true">→</span></a>{extra}</li>')
        secs.append(f'<section class="cw-other cw-bn"><p class="cw-toc__label" data-i18n="b_g{gi}">{e(g)}</p><ul class="cw-other__grid">{"".join(lis)}</ul></section>')
    css = MB.CW_CSS + MB.EXTRA_CSS + '.cw .cw-bn{margin-top:48px}.cw .cw-bn li{position:relative}.cw .cw-bn-en{display:inline-block;margin:6px 0 0;font-size:12px;color:var(--mute);text-decoration:underline}.cw .cw-bnhead{padding:72px 0 8px}.cw .cw-bnhead h1{font-weight:500;font-size:clamp(28px,7vw,44px);letter-spacing:.06em;margin:10px 0 14px}.cw .cw-bnhead p.lead{color:var(--mute);font-size:15px}'
    h = f'''<!DOCTYPE html><html lang="ja" style="background:#10182a"><head><meta charSet="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>すべてのバックナンバー｜ごきげん補給所</title><meta name="theme-color" content="#10182a"/><meta name="description" content="ごきげん補給所のマガジン、全{n}本をジャンル別に。"/><link rel="canonical" href="{MB.BACKNUMBER_URL}"/><meta property="og:type" content="website"/><meta property="og:title" content="すべてのバックナンバー｜ごきげん補給所"/><meta property="og:description" content="ごきげん補給所のマガジン、全{n}本をジャンル別に。"/><meta property="og:url" content="{MB.BACKNUMBER_URL}"/><meta property="og:image" content="https://joy-relief-station.lovable.app/__l5e/assets-v1/b39d82f5-4c9e-4131-a1ea-faccaec4a5a8/og-four-doors.png"/><meta name="twitter:card" content="summary_large_image"/></head><body><div class="min-h-[100svh] w-full"><main class="cw" lang="ja"><style>{css}</style>
<div class="cw-wrap"><nav class="cw-nav" aria-label="ページ上部"><a href="https://joy-relief-station.lovable.app/">ごきげん補給所</a><span>Magazine Story</span></nav>
<header class="cw-bnhead"><p class="cw-eyebrow" data-i18n="b_eyebrow">バックナンバー</p><h1 data-i18n="b_h1">すべてのバックナンバー</h1><p class="lead" data-i18n="b_lead">ごきげん補給所のマガジンを、ざっくりジャンル別に。</p></header>
{"".join(secs)}<div style="height:72px"></div></div></main></div></body></html>'''
    for l, d in MB.common_i18n().items(): tr[l].update(d)  # 共通部品（シェアの見出し・フォロー）の訳
    h = MB.add_i18n(h, tr, 'backnumber.i18n.json')
    h = MB.unify_look(h)  # 白い枠なし・Magazine Story なし（全マガジン共通）
    t = json.dumps(tr, ensure_ascii=False, separators=(',', ':'))
    for d in ('status/magazine_prod', 'share/check'):
        open(os.path.join(MB.REPO, d, 'backnumber.html'), 'w', encoding='utf-8').write(h)
        open(os.path.join(MB.REPO, d, 'backnumber.i18n.json'), 'w', encoding='utf-8').write(t)
    print('backnumber', n, len(h.encode()))


if __name__ == '__main__':
    build()
