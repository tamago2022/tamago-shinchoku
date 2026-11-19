# -*- coding: utf-8 -*-
"""君は星勝を知っているか：たまごさんの直し（2026-10-17）
1. 森恵「氷の世界」を04章の下に小さく戻す（カバー・2020年『COVERS2 Grace of The Guitar+』＝Wikipedia 氷の世界（曲））／アラン・タム「酒紅色的心」を10章に戻す（広東語カバー事典）
2. King Gnu は外したまま。中森明菜：「セカンド・ラブ」の編曲は萩田光雄、「スローモーション」は船山基紀（Wikipedia）＝星勝の関与なし。明菜版「セカンド・ラブ」は聴きくらべとして置き、編曲者を正しく書く
3. 来生たかお（08・09）を1章に。セカンド・ラブは来生版（編曲：星勝）と明菜版（編曲：萩田光雄）の両方
5. 01の前に、1967年のサイケデリック／ヒッピーの空気（Wikipedia「Summer of Love」「サマー・オブ・ラブ」）と写真2枚、導入の「ロングヘアにベルボトム」に写真1枚（Wikimedia Commons・CC0／CC BY-SA／CC BY）
（4. 締めの長い段落の文字の大きさは mag_build.unify_look が本文と同じにする）
"""
import json, os, re, sys
from bs4 import BeautifulSoup
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
SRC = os.path.join(R, 'share/check/tokushu-hoshi-katsu.html')
BAK = os.path.join(R, 'status/hsk_unify/before-edit10-hoshikatsu.html')
h = open(SRC, encoding='utf-8').read()
if 'data-hk12="1"' in h:
    print('already'); sys.exit(0)
s = BeautifulSoup(h, 'html.parser'); old = BeautifulSoup(open(BAK, encoding='utf-8').read(), 'html.parser')
TRP = os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'); tr = json.load(open(TRP, encoding='utf-8'))
L4 = ['en', 'zh-Hans', 'es', 'ko']


def settr(k, d):
    for l in L4: tr[l][k] = d[l]


def frag(html):
    return BeautifulSoup(html, 'html.parser')


def old_fig(yt, small=True):
    f = old.select_one(f'[data-yt-cover="{yt}"]').find_parent('figure')
    f = BeautifulSoup(str(f), 'html.parser').figure
    if small:
        f['class'] = ['cw-video', 'cw-video--small']
        im = f.select_one('img'); im['src'] = im['src'].replace('maxresdefault', 'hqdefault')
    return f


def setcap(f, key, d):
    c = f.select_one('.cw-video__cap'); c.string = d['ja']; c['data-i18n'] = key; settr(key, d)


# ---- 1. 森恵（04章の下・小さく）
ch04 = s.select_one('#ch04 .cw-wrap')
mori = old_fig('qIKvTmMrtl8')
mori.select_one('.cw-video__role').string = 'Cover 2020'
setcap(mori, 'k126', {'ja': 'カバー（2020年『COVERS2 Grace of The Guitar+』）', 'en': 'Cover (2020, COVERS2 Grace of The Guitar+)', 'zh-Hans': '翻唱（2020年《COVERS2 Grace of The Guitar+》）', 'es': 'Versión (2020, COVERS2 Grace of The Guitar+)', 'ko': '커버 (2020년 『COVERS2 Grace of The Guitar+』)'})
lab = frag('<p class="cw-more__label" data-i18n="h_mori_l">聴きくらべ — 2020年、森恵の「氷の世界」</p>').p
settr('h_mori_l', {'en': 'Listen alongside — Megumi Mori\'s "Koori no Sekai," 2020', 'zh-Hans': '对照聆听 — 2020年，森惠的《冰的世界》', 'es': 'Para comparar — «Koori no Sekai» de Megumi Mori, 2020', 'ko': '비교해서 듣기 — 2020년, 모리 메구미의 「얼음의 세계」'})
grid = s.new_tag('div', attrs={'class': 'cw-more__grid'}); grid.append(mori)
anchor = ch04.select_one('.say') or ch04.select_one('.bridge')
if anchor: anchor.insert_before(lab); lab.insert_after(grid)
else: ch04.append(lab); ch04.append(grid)

# ---- 1. アラン・タム（10章の聴きくらべへ）
alan = old_fig('dgT4nU34uOE')
setcap(alan, 'k124', {'ja': '1984年の広東語カバー', 'en': '1984 Cantonese cover', 'zh-Hans': '1984年粤语翻唱', 'es': 'Versión en cantonés de 1984', 'ko': '1984년 광둥어 커버'})
g10 = s.select_one('#ch10 .cw-more__grid')
g10.insert(0, alan)
settr('k89', {'en': 'Listen alongside — the night that crossed the sea, and one more arranged by Katz Hoshi', 'zh-Hans': '对照聆听 — 渡海的夜晚，和另一首星胜编曲', 'es': 'Para comparar — la noche que cruzó el mar, y otra con arreglos de Katz Hoshi', 'ko': '비교해서 듣기 — 바다를 건넌 밤, 그리고 호시 카츠 편곡 한 곡 더'})
s.select_one('[data-i18n="k89"]').string = '聴きくらべ — 海を渡った夜と、もう1曲の星勝の編曲'

# ---- 3. 来生たかお 08・09 を1章に
c8 = s.select_one('#ch08 .cw-wrap'); sec9 = s.select_one('#ch09'); c9 = sec9.select_one('.cw-wrap')
body8 = c8.select_one('.cw-body')
b76 = c8.select_one('p.bridge[data-i18n="k76"]'); b76.extract(); b76['class'] = []; del b76['class']
body8.append(b76)
for p in list(c9.select_one('.cw-body').children):
    body8.append(p.extract() if hasattr(p, 'extract') else p)
pull = c9.select_one('blockquote.cw-pull')
kisugi2 = c9.select_one('.cw-main figure').extract()
kisugi2['class'] = ['cw-video', 'cw-video--small']; im = kisugi2.select_one('img'); im['src'] = im['src'].replace('maxresdefault', 'hqdefault')
akina = old_fig('i5U93W19Ays')
setcap(akina, 'k120', {'ja': '中森明菜版（編曲：萩田光雄）', 'en': 'Akina Nakamori version (arrangement: Mitsuo Hagita)', 'zh-Hans': '中森明菜版（编曲：萩田光雄）', 'es': 'Versión de Akina Nakamori (arreglos: Mitsuo Hagita)', 'ko': '나카모리 아키나 버전 (편곡: 하기타 미쓰오)'})
g8 = c8.select_one('.cw-more__grid'); g8.append(kisugi2); g8.append(akina)
s.select_one('[data-i18n="k75"]').string = '聴きくらべ — 同じメロディのもうひとつの声と、ふたつの「セカンド・ラブ」'
settr('k75', {'en': 'Listen alongside — the same melody in another voice, and two "Second Love"s', 'zh-Hans': '对照聆听 — 同一旋律的另一个声音，和两版《Second Love》', 'es': 'Para comparar — la misma melodía en otra voz, y dos «Second Love»', 'ko': '비교해서 듣기 — 같은 멜로디의 또 다른 목소리, 그리고 두 개의 「세컨드 러브」'})
if pull: g8.insert_after(pull.extract())
b83 = c9.select_one('p.bridge').extract()
c8.append(b83)
sec9.decompose()
# 章番号を詰める（10→09、11→10）
for old_no, new_no in (('10', '09'), ('11', '10')):
    sec = s.select_one(f'#ch{old_no}'); sec['id'] = f'ch{new_no}'; sec.select_one('.cw-chead__no').string = new_no
toc = s.select_one('.cw-toc__grid')
toc.select_one('a[href="#ch09"]').find_parent('li').decompose()
for old_no, new_no in (('10', '09'), ('11', '10')):
    a = toc.select_one(f'a[href="#ch{old_no}"]'); a['href'] = f'#ch{new_no}'; a.select_one('b').string = f'CHAPTER {new_no}'

# ---- 5. 1967年の空気（01の前）
SOL = 'https://en.wikipedia.org/wiki/Summer_of_Love'
SOLJ = 'https://ja.wikipedia.org/wiki/%E3%82%B5%E3%83%9E%E3%83%BC%E3%83%BB%E3%82%AA%E3%83%96%E3%83%BB%E3%83%A9%E3%83%96'
HOSHI = 'https://ja.wikipedia.org/wiki/%E6%98%9F%E5%8B%9D'
sel = json.load(open(os.path.join(R, 'status/hsk_audit/commons/sel2.json'), encoding='utf-8'))
def ph(i, key, cap, credit, lic):
    o = sel[i]
    settr(key, cap)
    return (f'<figure><img src="{o["thumb"].split("?")[0]}" width="{o["tw"]}" height="{o["th"]}" alt="" loading="lazy" decoding="async"/>'
            f'<figcaption data-i18n="{key}">{cap["ja"]}<br/><span class="cw-credit">写真：<a href="{o["page"]}" target="_blank" rel="noopener">{credit}</a>（{lic}）</span></figcaption></figure>')
CR = {'en': 'Photo: ', 'zh-Hans': '照片：', 'es': 'Foto: ', 'ko': '사진: '}
def capd(ja, d, credit, page, lic):
    return dict({'ja': ja}, **{l: d[l] + f'<br/><span class="cw-credit">{CR[l]}<a href="{page}" target="_blank" rel="noopener">{credit}</a>（{lic}）</span>' for l in L4})
c0 = capd('1967年8月、アムステルダムの「フラワー・パワー」。', {'en': 'August 1967: "Flower Power" in Amsterdam.', 'zh-Hans': '1967年8月，阿姆斯特丹的“花之力”。', 'es': 'Agosto de 1967: «Flower Power» en Ámsterdam.', 'ko': '1967년 8월, 암스테르담의 ‘플라워 파워’.'}, 'Pieter Jongerhuis / Anefo', sel[0]['page'], 'CC0')
c6 = capd('1969年8月、ウッドストック・フェスティバルの若者たち。', {'en': 'August 1969: young people at the Woodstock Festival.', 'zh-Hans': '1969年8月，伍德斯托克音乐节上的年轻人。', 'es': 'Agosto de 1969: jóvenes en el festival de Woodstock.', 'ko': '1969년 8월, 우드스톡 페스티벌의 젊은이들.'}, 'Derek Redmond and Paul Campbell', sel[6]['page'], 'CC BY-SA 3.0')
pre = frag(
    '<section class="cw-interlude" aria-label="写真" data-hk12="1"><div class="cw-wrap">'
    f'<p data-i18n="h_hp1">1967年の夏、アメリカ・サンフランシスコのヘイト・アシュベリーには、最大で10万人の若者が集まったといわれる。長い髪、花、反戦。この夏は「サマー・オブ・ラブ」と呼ばれた<a class="cw-src" href="{SOLJ}" rel="noopener" target="_blank">Wikipedia — サマー・オブ・ラブ</a>。</p>'
    + ph(0, 'h_hp_c0', c0, 'Pieter Jongerhuis / Anefo', 'CC0')
    + f'<p data-i18n="h_hp2">同じ年、日本でデビューしたモップスは、日本のサイケデリック・ロック・バンドと呼ばれた<a class="cw-src" href="{HOSHI}" rel="noopener" target="_blank">Wikipedia — 星勝</a>。</p>'
    + ph(6, 'h_hp_c6', c6, 'Derek Redmond and Paul Campbell', 'CC BY-SA 3.0')
    + '</div></section>')
settr('h_hp1', {'en': 'In the summer of 1967, as many as 100,000 young people are said to have gathered in San Francisco\'s Haight-Ashbury. Long hair, flowers, anti-war. That summer came to be called the "Summer of Love"[[1]].',
                'zh-Hans': '1967年夏天，据说多达10万年轻人聚集在美国旧金山的海特-阿什伯里。长发、鲜花、反战。那个夏天被称为“爱之夏”[[1]]。',
                'es': 'En el verano de 1967, se dice que hasta 100.000 jóvenes se reunieron en Haight-Ashbury, San Francisco. Pelo largo, flores, antibelicismo. Aquel verano se llamó el «Verano del Amor»[[1]].',
                'ko': '1967년 여름, 미국 샌프란시스코의 헤이트애시버리에는 최대 10만 명의 젊은이가 모였다고 한다. 긴 머리, 꽃, 반전. 그 여름은 ‘서머 오브 러브’라 불렸다[[1]].'})
settr('h_hp2', {'en': 'That same year, The Mops debuted in Japan — a band called a Japanese psychedelic rock band[[1]].',
                'zh-Hans': '同一年在日本出道的The Mops，被称为日本的迷幻摇滚乐队[[1]]。',
                'es': 'Ese mismo año debutaron en Japón The Mops, a quienes se llamó banda de rock psicodélico japonés[[1]].',
                'ko': '같은 해 일본에서 데뷔한 더 몹스는 일본의 사이키델릭 록 밴드로 불렸다[[1]].'})
s.select_one('#ch01').insert_before(pre.section)
# 導入の「ロングヘアにベルボトム」の下に1枚
c4 = capd('1975年、フィンランドのロック・フェス「ルイスロック」の観客。', {'en': '1975: the crowd at Ruisrock, a rock festival in Finland.', 'zh-Hans': '1975年，芬兰摇滚节“Ruisrock”的观众。', 'es': '1975: el público de Ruisrock, festival de rock en Finlandia.', 'ko': '1975년, 핀란드 록 페스티벌 ‘루이스록’의 관객.'}, 'Keijo Laajisto / Museovirasto', sel[4]['page'], 'CC BY 4.0')
k19 = s.select_one('[data-i18n="k19"]')
fig = frag('<div class="cw-interlude" style="padding:8px 0 24px">' + ph(4, 'h_hp_c4', c4, 'Keijo Laajisto / Museovirasto', 'CC BY 4.0') + '</div>').div
k19.insert_after(fig)

out = str(s)
out = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', out)
out = MB.unify_look(out)
for p in (SRC, os.path.join(R, 'status/magazine_prod/kimi-wa-hoshi-katsu.html')):
    open(p, 'w', encoding='utf-8').write(out)
json.dump(tr, open(TRP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
t = json.dumps(dict(tr, **{l: dict(tr[l], **MB.common_i18n()[l]) for l in L4}), ensure_ascii=False, separators=(',', ':'))
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, 'kimi-wa-hoshi-katsu.i18n.json'), 'w', encoding='utf-8').write(t)
print('ok', MB.look_check(out), [a['href'] for a in s.select('.cw-toc__grid a')])
