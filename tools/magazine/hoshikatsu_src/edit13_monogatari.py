# -*- coding: utf-8 -*-
"""君は星勝を知っているか：導入を1本の物語に（2026-10-17 たまごさん「ただの情報の羅列は面白くない。正しいより楽しい」）
流れ：知られていない音楽家 → 1967年夏 サンフランシスコ（サマー・オブ・ラブ）→ 同じ年、堀威夫が持ち帰ったサイケデリック → 1967年11月 モップス、19歳の星勝
      → 1969年8月 ウッドストック（約40万人）→ 70年代、オイルショックと高度成長の終わり。情報は増やさず、つなぎ直すだけ。
出典：Wikipedia サマー・オブ・ラブ／ザ・モップス／ウッドストック・フェスティバル／オイルショック、マイナビウーマン（70年代の装い）。
写真：Wikimedia Commons（Anefo CC0・Woodstock redmond stage CC BY-SA 3.0・Ruisrock 1975 CC BY 4.0）
"""
import json, os, re, sys
from bs4 import BeautifulSoup
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
SRC = os.path.join(R, 'share/check/tokushu-hoshi-katsu.html')
h = open(SRC, encoding='utf-8').read()
if 'data-hk13="1"' in h:
    print('already'); sys.exit(0)
s = BeautifulSoup(h, 'html.parser')
TRP = os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'); tr = json.load(open(TRP, encoding='utf-8'))
L4 = ['en', 'zh-Hans', 'es', 'ko']
def settr(k, d):
    for l in L4: tr[l][k] = d[l]

SOLJ = 'https://ja.wikipedia.org/wiki/%E3%82%B5%E3%83%9E%E3%83%BC%E3%83%BB%E3%82%AA%E3%83%96%E3%83%BB%E3%83%A9%E3%83%96'
MOPS = 'https://ja.wikipedia.org/wiki/%E3%82%B6%E3%83%BB%E3%83%A2%E3%83%83%E3%83%97%E3%82%B9'
WOOD = 'https://ja.wikipedia.org/wiki/%E3%82%A6%E3%83%83%E3%83%89%E3%82%B9%E3%83%88%E3%83%83%E3%82%AF%E3%83%BB%E3%83%95%E3%82%A7%E3%82%B9%E3%83%86%E3%82%A3%E3%83%90%E3%83%AB'
OIL = 'https://ja.wikipedia.org/wiki/%E3%82%AA%E3%82%A4%E3%83%AB%E3%82%B7%E3%83%A7%E3%83%83%E3%82%AF'
MYN = 'https://woman.mynavi.jp/article/190307-13/'
def a(u, lab): return f'<a class="cw-src" href="{u}" rel="noopener" target="_blank">{lab}</a>'
CR = {'en': 'Photo: ', 'zh-Hans': '照片：', 'es': 'Foto: ', 'ko': '사진: '}
def fig(key, src, w, hgt, page, credit, lic, ja, d):
    settr(key, {l: d[l] + f'<br/><span class="cw-credit">{CR[l]}<a href="{page}" target="_blank" rel="noopener">{credit}</a>（{lic}）</span>' for l in L4})
    return (f'<div class="cw-interlude" style="padding:12px 0 28px"><figure><img src="{src}" width="{w}" height="{hgt}" alt="" loading="lazy" decoding="async"/>'
            f'<figcaption data-i18n="{key}">{ja}<br/><span class="cw-credit">写真：<a href="{page}" target="_blank" rel="noopener">{credit}</a>（{lic}）</span></figcaption></figure></div>')

# 既存の写真（1967年アムステルダム）を流用
old_il = s.select_one('section.cw-interlude[data-hk12]')
ams = old_il.select('figure')[0]
ams_img = ams.select_one('img'); ams_page = ams.select_one('figcaption a')['href']

P = []
P.append(('h_n1', '話は、1967年の夏から始めたい。海の向こう、サンフランシスコのヘイト・アシュベリーという街に、最大で10万人の若者が集まったといわれる。長い髪に、花。戦争はいやだと言いながら、知らない者同士が肩を寄せ合った。その夏は「サマー・オブ・ラブ」と呼ばれた' + a(SOLJ, 'Wikipedia') + '。',
          {'en': 'I want to start in the summer of 1967. Across the ocean, in a San Francisco neighborhood called Haight-Ashbury, as many as 100,000 young people are said to have gathered. Long hair, flowers. Strangers leaned on each other while saying no to war. That summer was called the "Summer of Love"[[1]].',
           'zh-Hans': '故事想从1967年的夏天讲起。大洋彼岸，旧金山一个叫海特-阿什伯里的街区，据说聚集了多达10万名年轻人。长发，鲜花。一边说着不要战争，一边和陌生人肩并着肩。那个夏天被称为“爱之夏”[[1]]。',
           'es': 'Quiero empezar en el verano de 1967. Al otro lado del océano, en un barrio de San Francisco llamado Haight-Ashbury, se dice que llegaron a juntarse hasta 100.000 jóvenes. Pelo largo, flores. Desconocidos hombro con hombro, diciendo no a la guerra. Aquel verano se llamó el «Verano del Amor»[[1]].',
           'ko': '이야기는 1967년 여름에서 시작하고 싶다. 바다 건너 샌프란시스코의 헤이트애시버리라는 동네에, 최대 10만 명의 젊은이가 모였다고 한다. 긴 머리에 꽃. 전쟁은 싫다고 말하며, 모르는 사람끼리 어깨를 맞댔다. 그 여름은 ‘서머 오브 러브’라 불렸다[[1]].'}))
FIG_AMS = fig('h_hp_c0', ams_img['src'], ams_img.get('width', 1280), ams_img.get('height', 853), ams_page, 'Pieter Jongerhuis / Anefo', 'CC0',
              '1967年8月、アムステルダム。花を髪に挿した若者たち。',
              {'en': 'Amsterdam, August 1967: young people with flowers in their hair.', 'zh-Hans': '1967年8月，阿姆斯特丹。头发上插着花的年轻人。',
               'es': 'Ámsterdam, agosto de 1967: jóvenes con flores en el pelo.', 'ko': '1967년 8월, 암스테르담. 머리에 꽃을 꽂은 젊은이들.'})
P.append(('h_n2', '同じ1967年、ひとりの日本人がアメリカを旅していた。ホリプロの社長、堀威夫。彼はその波を、日本に持ち帰る' + a(MOPS, 'Wikipedia') + '。',
          {'en': 'That same year, 1967, a Japanese man was traveling in America: Takeo Hori, president of Horipro. He brought that wave home to Japan[[1]].',
           'zh-Hans': '同样是1967年，一个日本人正在美国旅行。Horipro的社长，堀威夫。他把那股浪潮带回了日本[[1]]。',
           'es': 'Ese mismo 1967, un japonés viajaba por Estados Unidos: Takeo Hori, presidente de Horipro. Él se llevó aquella ola de vuelta a Japón[[1]].',
           'ko': '같은 1967년, 한 일본인이 미국을 여행하고 있었다. 호리프로의 사장, 호리 다케오. 그는 그 물결을 일본으로 가지고 돌아온다[[1]].'}))
P.append(('h_n3', 'そんな時に出てきたのが、モップスだった。「日本最初のサイケデリック・サウンド」を掲げて、1967年11月にデビューする' + a(MOPS, 'Wikipedia') + '。ギターを抱えていたのは、19歳の星勝だった。',
          {'en': 'That was when The Mops appeared. Billed as "Japan\'s first psychedelic sound," they debuted in November 1967[[1]]. The one holding the guitar was 19-year-old Katz Hoshi.',
           'zh-Hans': '就在那时登场的，是The Mops。打着“日本第一支迷幻之声”的招牌，于1967年11月出道[[1]]。抱着吉他的，是19岁的星胜。',
           'es': 'Fue entonces cuando aparecieron The Mops. Anunciados como «el primer sonido psicodélico de Japón», debutaron en noviembre de 1967[[1]]. El que sostenía la guitarra era Katz Hoshi, de 19 años.',
           'ko': '바로 그때 나타난 것이 더 몹스였다. ‘일본 최초의 사이키델릭 사운드’를 내걸고 1967년 11월에 데뷔한다[[1]]. 기타를 안고 있던 건 19세의 호시 카츠였다.'}))
P.append(('h_n4', '2年後の1969年8月。ニューヨーク州の牧場で開かれたウッドストック・フェスティバルには、約40万人が集まった' + a(WOOD, 'Wikipedia') + '。その3日間は、60年代の若者の文化を象徴する出来事として、いまも語り継がれている。',
          {'en': 'Two years later, in August 1969, about 400,000 people gathered for the Woodstock Festival in rural New York[[1]]. Those three days are still remembered as the event that symbolized the youth culture of the sixties.',
           'zh-Hans': '两年后的1969年8月，在纽约州乡间举办的伍德斯托克音乐节，聚集了约40万人[[1]]。那三天至今仍被当作象征60年代青年文化的事件而流传。',
           'es': 'Dos años después, en agosto de 1969, unas 400.000 personas se reunieron en el festival de Woodstock, en el campo de Nueva York[[1]]. Aquellos tres días se siguen recordando como el símbolo de la cultura joven de los sesenta.',
           'ko': '2년 뒤인 1969년 8월, 뉴욕주 시골에서 열린 우드스톡 페스티벌에 약 40만 명이 모였다[[1]]. 그 사흘은 지금도 60년대 젊은이 문화를 상징하는 사건으로 전해진다.'}))
ST = json.load(open(os.path.join(R, 'status/hsk_audit/commons/stage.json'), encoding='utf-8'))
stg = [p for p in ST['query']['pages'].values() if 'stage' in p['title']][0]['imageinfo'][0]
FIG_WOOD = fig('h_hp_c6', stg['thumburl'].split('?')[0], stg['thumbwidth'], stg['thumbheight'], stg['descriptionurl'], 'Derek Redmond and Paul Campbell', 'CC BY-SA 3.0',
               '1969年8月、ウッドストック・フェスティバルのステージ。',
               {'en': 'August 1969: the stage at the Woodstock Festival.', 'zh-Hans': '1969年8月，伍德斯托克音乐节的舞台。', 'es': 'Agosto de 1969: el escenario del festival de Woodstock.', 'ko': '1969년 8월, 우드스톡 페스티벌의 무대.'})
P.append(('k19', 'そして70年代。1973年10月、第四次中東戦争をきっかけに第一次オイルショックが始まる。翌1974年、物価は23パーセント上がって「狂乱物価」という言葉が生まれ、日本は戦後初めてのマイナス成長を経験した。高度経済成長は、そこで終わる' + a(OIL, 'Wikipedia') + '。それでも若者はロングヘアにベルボトムのジーンズ、絞り染めのTシャツを着て、女性もジーンズをはくようになっていた' + a(MYN, 'マイナビウーマン') + '。明るい曲が売れた時代じゃない。',
          {'en': 'Then came the seventies. In October 1973, the Fourth Arab-Israeli War set off the first oil shock. In 1974 prices jumped 23 percent, the phrase "crazy prices" was born, and Japan saw its first negative growth since the war. That was where the era of high growth ended[[1]]. Even so, young people wore long hair, bell-bottom jeans and tie-dyed T-shirts, and women had started wearing jeans too[[2]]. It wasn\'t an era when bright songs sold.',
           'zh-Hans': '然后是70年代。1973年10月，第四次中东战争引发了第一次石油危机。次年1974年物价上涨23%，诞生了“狂乱物价”一词，日本经历了战后首次负增长。高速经济增长就此结束[[1]]。即便如此，年轻人还是留着长发，穿喇叭牛仔裤和扎染T恤，女性也开始穿牛仔裤[[2]]。那不是明快的歌曲能卖座的时代。',
           'es': 'Y luego llegaron los setenta. En octubre de 1973, la cuarta guerra árabe-israelí desató la primera crisis del petróleo. En 1974 los precios subieron un 23 %, nació la expresión «precios enloquecidos» y Japón vivió su primer crecimiento negativo de la posguerra. Ahí terminó la era del gran crecimiento[[1]]. Aun así, los jóvenes llevaban el pelo largo, vaqueros de campana y camisetas teñidas, y las mujeres también empezaban a llevar vaqueros[[2]]. No era una época en la que vendieran las canciones alegres.',
           'ko': '그리고 70년대. 1973년 10월, 제4차 중동전쟁을 계기로 제1차 오일쇼크가 시작된다. 이듬해 1974년 물가는 23퍼센트 올라 ‘광란 물가’라는 말이 생겼고, 일본은 전후 처음으로 마이너스 성장을 겪었다. 고도 경제성장은 거기서 끝난다[[1]]. 그래도 젊은이들은 긴 머리에 나팔바지 청바지, 홀치기염색 티셔츠를 입었고, 여성들도 청바지를 입기 시작했다[[2]]. 밝은 노래가 팔리던 시대가 아니었다.'}))
P.append(('k20', 'その時代を、ずっと裏側から鳴らし続けた人の話を、19歳のギターの少年から始めよう。',
          {'en': 'Let\'s begin the story of the man who kept that era ringing from behind the scenes — with a 19-year-old boy and his guitar.',
           'zh-Hans': '那个一直在幕后让时代发出声响的人，他的故事，就从19岁抱着吉他的少年开始吧。',
           'es': 'Empecemos la historia del hombre que hizo sonar esa época desde detrás del telón, con un chico de 19 años y su guitarra.',
           'ko': '그 시대를 줄곧 뒤에서 울려 온 사람의 이야기를, 열아홉 살 기타 소년에서부터 시작하자.'}))

op = s.select_one('.cw-open')
k18 = op.select_one('[data-i18n="k18"]')
old_k19 = op.select_one('[data-i18n="k19"]')
ruis = old_k19.find_next_sibling('div', class_='cw-interlude')
k20 = op.select_one('[data-i18n="k20"]')
# 組み直し：k18 の後に n1, 写真, n2, n3, n4, 写真, k19（70年代）, ルイスロック写真, k20
seq = []
def p_html(key, ja, cls=None):
    c = f' class="{cls}"' if cls else ''
    return f'<p data-i18n="{key}"{c}>{ja}</p>'
for key, ja, d in P:
    settr(key, d)
html = (p_html('h_n1', P[0][1]) + FIG_AMS + p_html('h_n2', P[1][1]) + p_html('h_n3', P[2][1]) + p_html('h_n4', P[3][1]) + FIG_WOOD + p_html('k19', P[4][1]))
old_k19.decompose()
frag = BeautifulSoup(html, 'html.parser')
anchor = k18
for el in list(frag.contents):
    anchor.insert_after(el); anchor = el
# ルイスロック写真は k19 の後へ（既に後ろにある）、k20 の文
k20.clear(); k20.append(BeautifulSoup(P[5][1], 'html.parser')); k20['data-hk13'] = '1'
# 01の前にあった写真のかたまりは導入に入れたので外す
old_il.decompose()
# 01章の本文から、導入へ移した「堀威夫…」の一文を外す
k24 = s.select_one('[data-i18n="k24"]')
k24h = k24.decode_contents()
cut = k24h.find('ホリプロ社長の堀威夫')
if cut > 0:
    k24.clear(); k24.append(BeautifulSoup(k24h[:cut], 'html.parser'))
    for l in L4:
        v = tr[l]['k24']; i = v.find('[[1]]')
        if i > 0:
            end = i + 5
            if end < len(v) and v[end] in '.。': end += 1
            tr[l]['k24'] = v[:end]
out = str(s)
out = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', out)
out = MB.unify_look(out)
for p in (SRC, os.path.join(R, 'status/magazine_prod/kimi-wa-hoshi-katsu.html')):
    open(p, 'w', encoding='utf-8').write(out)
json.dump(tr, open(TRP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
t = json.dumps(dict(tr, **{l: dict(tr[l], **MB.common_i18n()[l]) for l in L4}), ensure_ascii=False, separators=(',', ':'))
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, 'kimi-wa-hoshi-katsu.i18n.json'), 'w', encoding='utf-8').write(t)
print('ok', MB.look_check(out))
