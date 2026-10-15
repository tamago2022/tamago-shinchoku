# -*- coding: utf-8 -*-
# 2026-10-16：「名前を知らなくても」に誰もが知っている星勝の仕事を足す／スローバラードを名曲としての評価側に厚く
import sys, os, re, json
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
from bs4 import BeautifulSoup

SRC, OUT = sys.argv[1], sys.argv[2]
h = open(SRC, encoding='utf-8').read()
h = re.sub(r'<script>\(function\(\)\{var L=.*?</script>', '', h, flags=re.S)
TR = json.load(open(os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'), encoding='utf-8'))
LG = ['en', 'zh-Hans', 'es', 'ko']
soup = BeautifulSoup(h, 'html.parser')
main = soup.find('main')
def src(l, u): return f'<a class="cw-src" href="{u}" target="_blank" rel="noopener noreferrer">{l}</a>'
W_SB = 'https://ja.wikipedia.org/wiki/%E3%82%B9%E3%83%AD%E3%83%BC%E3%83%90%E3%83%A9%E3%83%BC%E3%83%89'
W_RC = 'https://ja.wikipedia.org/wiki/RC%E3%82%B5%E3%82%AF%E3%82%BB%E3%82%B7%E3%83%A7%E3%83%B3'
TOWER = 'https://tower.jp/article/campaign/2015/10/26/01'
W_OMOIDE = 'https://ja.wikipedia.org/wiki/%E3%81%8A%E3%82%82%E3%81%B2%E3%81%A7%E3%81%BD%E3%82%8D%E3%81%BD%E3%82%8D'
W_TANJO = 'https://ja.wikipedia.org/wiki/%E8%AA%95%E7%94%9F_(%E5%B0%BE%E5%B4%8E%E8%B1%8A%E3%81%AE%E3%82%A2%E3%83%AB%E3%83%90%E3%83%A0)'
W_RIVER = 'https://ja.wikipedia.org/wiki/%E3%83%AA%E3%83%90%E3%83%BC%E3%82%B5%E3%82%A4%E3%83%89%E3%83%9B%E3%83%86%E3%83%AB'
W_HOSHI = 'https://ja.wikipedia.org/wiki/%E6%98%9F%E5%8B%9D'
YT_H2O = 'https://www.youtube.com/watch?v=am9FcU6qhLk'

def put(k, v4):
    for l, t in zip(LG, v4): TR.setdefault(l, {})[k] = t
def setk(k, ja, *v4):
    e = main.find(attrs={'data-i18n': k})
    if e is None: sys.exit('no ' + k)
    e.clear(); e.append(BeautifulSoup(ja, 'html.parser')); put(k, v4)
def frag(x): return BeautifulSoup(x, 'html.parser')

# ---------- 07章：スローバラード ----------
ch = main.find('section', id='ch07')
setk('k65', f'1976年1月21日、RCサクセションが久しぶりに出したシングル。編曲は星勝とRCサクセション。ちょうど日本公演中だったタワー・オブ・パワーのホーン・セクションが録音に加わっている{src("Wikipedia — スローバラード", W_SB)}。',
     'Released January 21, 1976 — RC Succession\'s first single in years. Arranged by Katz Hoshi and RC Succession, with Tower of Power\'s horn section, in Japan on tour, joining the session[[1]].',
     '1976年1月21日，RC Succession时隔多年推出的单曲。编曲是星胜与RC Succession，正在日本巡演的Tower of Power铜管组也加入了录音[[1]]。',
     'Salió el 21 de enero de 1976: el primer sencillo de RC Succession en años. Arreglo de Katz Hoshi y RC Succession, con la sección de vientos de Tower of Power, de gira por Japón, en la grabación[[1]].',
     '1976년 1월 21일, RC 석세션이 오랜만에 낸 싱글. 편곡은 호시 카츠와 RC 석세션. 마침 일본 공연 중이던 타워 오브 파워의 혼 섹션이 녹음에 참여했다[[1]].')
body = ch.find('div', class_='cw-body')
k66 = body.find(attrs={'data-i18n': 'k66'}); k67 = body.find(attrs={'data-i18n': 'k67'}); k68 = body.find(attrs={'data-i18n': 'k68'})
p_tower = frag(f'<p data-i18n="h_sb_tower">いまでは「ロック・バラードの名曲」と呼ばれる曲だ。タワーレコードはRCサクセションのベスト盤を紹介するとき、この曲をそう書いている{src("TOWER RECORDS", TOWER)}。</p>')
put('h_sb_tower', ('Today it\'s called "a classic rock ballad" — that\'s how Tower Records describes it when introducing RC Succession\'s best-of[[1]].', '如今它被称为“摇滚情歌的名曲”。Tower Records介绍RC Succession的精选辑时，就是这样写的[[1]]。', 'Hoy la llaman «una gran balada rock»: así la describe Tower Records al presentar el recopilatorio de RC Succession[[1]].', '지금은 \'록 발라드의 명곡\'으로 불리는 곡이다. 타워레코드는 RC 석세션의 베스트 앨범을 소개할 때 이 곡을 그렇게 적었다[[1]].'))
k65 = body.find(attrs={'data-i18n': 'k65'})
k65.insert_after(p_tower)
# 並べ替え：名曲としての評価 → 当時の話 → 結び
k68.extract(); body.find(attrs={'data-i18n': 'h_sb_tower'}).insert_after(k68)
setk('k66', f'録音の当時は、順風ではなかった。同じ年のアルバム『シングル・マン』はほとんど売れず、いったん廃盤になったが、のちに正式に再発売されている{src("Wikipedia — RCサクセション", W_RC)}。',
     'At the time, things weren\'t easy. The album <i>Single Man</i>, from the same year, barely sold and was soon deleted — and was later officially reissued[[1]].',
     '录音当时并不顺利。同年的专辑《Single Man》几乎没卖出去，一度绝版，后来又被正式再版[[1]]。',
     'En su momento no fue fácil. El álbum <i>Single Man</i>, del mismo año, apenas se vendió y se descatalogó, pero más tarde se reeditó oficialmente[[1]].',
     '녹음 당시는 순탄하지 않았다. 같은 해의 앨범 『싱글 맨』은 거의 팔리지 않아 한때 폐반되었지만, 나중에 정식으로 재발매되었다[[1]].')
p_end = frag('<p data-i18n="h_sb_end">清志郎が「思っていた音と違う」と感じた録音が、半世紀たったいま、「名曲」と呼ばれて歌い継がれている。編曲という仕事の不思議が、この1曲に詰まっている。</p>')
put('h_sb_end', ('A recording Kiyoshiro felt didn\'t sound the way he\'d hoped is now, half a century later, called a classic and still being sung. The strange alchemy of arranging is all packed into this one song.', '清志郎曾觉得“和想要的声音不一样”的那次录音，半个世纪后的今天被称为“名曲”，仍在传唱。编曲这份工作的奇妙，就浓缩在这一首歌里。', 'Una grabación que a Kiyoshiro no le sonó como esperaba hoy, medio siglo después, se considera un clásico y se sigue cantando. Toda la extraña alquimia del arreglo cabe en esta canción.', '기요시로가 \'생각했던 소리와 다르다\'고 느꼈던 녹음이, 반세기가 지난 지금 \'명곡\'으로 불리며 이어 불리고 있다. 편곡이라는 일의 신비가 이 한 곡에 담겨 있다.'))
k67.insert_after(p_end)
setk('k104', '思いどおりにならなかった録音が、名曲として残った。', 'The recording that didn\'t go to plan became a classic.', '没有按设想完成的录音，作为名曲留了下来。', 'La grabación que no salió como se pensaba quedó como un clásico.', '뜻대로 되지 않았던 녹음이, 명곡으로 남았다.')

# ---------- 締め：名前を知らなくても、耳にしているかもしれない仕事 ----------
close = main.find('section', class_='cw-close')
y1 = close.find(attrs={'data-i18n': 'h_yoin1'})
PLAY = MB.PLAY
def fig(id, role, artist, song, cap, keys, page=None):
    ka, ks, kc = keys
    p = f'<a class="cw-video__page" data-i18n="h_pg_{id}" href="{page}">この曲のページへ →</a>' if page else ''
    if page: put(f'h_pg_{id}', ("Go to this song's page →", '前往这首歌的页面 →', 'Ir a la página de esta canción →', '이 곡 페이지로 →'))
    return (f'<figure class="cw-video cw-video--small"><div class="cw-video__frame"><button type="button" class="cw-video__cover" data-yt-cover="{id}" aria-label="ここで再生：{artist}{song}">'
            f'<img src="https://i.ytimg.com/vi/{id}/hqdefault.jpg" alt="" loading="lazy" decoding="async"/><span class="cw-video__role">{role}</span><span class="cw-video__play" aria-hidden="true">{PLAY}</span></button></div>'
            f'<figcaption><span class="cw-video__name"><b data-i18n="{ka}">{artist}</b><i data-i18n="{ks}">{song}</i></span><span class="cw-video__cap" data-i18n="{kc}">{cap}</span>{p}</figcaption></figure>')
RIVER_PAGE = 'https://joy-relief-station.lovable.app/cover-guide?artist=inoue-yousui&song=%E3%83%AA%E3%83%8F-%E3%83%BC%E3%82%B5%E3%82%A4%E3%83%88-%E3%83%9B%E3%83%86%E3%83%AB-1992-sparkling-blue-%E6%97%A5%E6%9C%AC%E6%AD%A6%E9%81%93%E9%A4%A8'
works = (f'<p data-i18n="h_works">たとえば、スタジオジブリの『おもひでぽろぽろ』（1991年）。都はるみが歌う主題歌「愛は花、君はその種子」の編曲は星勝だ{src("Wikipedia — おもひでぽろぽろ", W_OMOIDE)}。'
         f'尾崎豊のアルバム『誕生』（1990年）は全曲の編曲を星勝が手がけ、オリコンで初登場1位になった{src("Wikipedia — 誕生", W_TANJO)}。'
         f'井上陽水「リバーサイド ホテル」も星勝の編曲で{src("Wikipedia — 星勝", W_HOSHI)}、ドラマ『ニューヨーク恋物語』の主題歌として再びヒットした{src("Wikipedia — リバーサイド ホテル", W_RIVER)}。'
         f'H2O「僕等のダイアリー」のクレジットにも、編曲 星勝、プロデュース 多賀英典の名前がある{src("公式配信のクレジット", YT_H2O)}。</p>'
         '<p class="cw-more__label" data-i18n="h_works_lbl">聴きくらべ — 名前を知らなくても、耳を通り抜けているかもしれない</p><div class="cw-more__grid">'
         + fig('viIw3G2bw6I', '1991', '都はるみ', '「愛は花、君はその種子」', 'Harumi Miyako - Topic（映画『おもひでぽろぽろ』の主題歌・公式配信）', ('h_w1a', 'h_w1s', 'h_w1c'))
         + fig('BMatWYmur_M', '1990', '尾崎豊', '「LOVE WAY」', 'Yutaka Ozaki - Topic（アルバム『誕生』の先行シングル・公式配信）', ('h_w2a', 'h_w2s', 'h_w2c'))
         + fig('mOQE4GN7Pl8', '1982', '井上陽水', '「リバーサイド ホテル」', 'kantarokanna（一般投稿・86万回）', ('h_w3a', 'h_w3s', 'h_w3c'), RIVER_PAGE)
         + fig('am9FcU6qhLk', '1980', 'H2O', '「僕等のダイアリー」', 'H2O - Topic（編曲 星勝・公式配信）', ('h_w4a', 'h_w4s', 'h_w4c'))
         + '</div>')
y1.insert_after(frag(works))
put('h_works', ('Take Studio Ghibli\'s <i>Only Yesterday</i> (1991): the theme song sung by Harumi Miyako, "Ai wa Hana, Kimi wa Sono Tane," was arranged by Hoshi[[1]]. Yutaka Ozaki\'s album <i>Tanjo</i> (1990) — every track arranged by Hoshi — entered the Oricon chart at No. 1[[2]]. Yosui Inoue\'s "Riverside Hotel" is a Hoshi arrangement too[[3]], and it became a hit all over again as the theme of the drama <i>New York Koi Monogatari</i>[[4]]. And on H2O\'s "Bokura no Diary," the credits read: arranged by Katz Hoshi, produced by Hidenori Taga[[5]].',
                '比如吉卜力工作室的《岁月的童话》（1991年）。都春美演唱的主题曲《爱是花，你是那颗种子》，编曲就是星胜[[1]]。尾崎丰的专辑《诞生》（1990年）全部由星胜编曲，在Oricon初登场即第一[[2]]。井上阳水的《Riverside Hotel》也是星胜编曲[[3]]，作为电视剧《纽约恋物语》的主题曲再次走红[[4]]。H2O《我们的日记》的署名里，也写着编曲星胜、制作多贺英典[[5]]。',
                'Por ejemplo, <i>Recuerdos del ayer</i> de Studio Ghibli (1991): el tema que canta Harumi Miyako, «Ai wa Hana, Kimi wa Sono Tane», lo arregló Hoshi[[1]]. El álbum <i>Tanjo</i> de Yutaka Ozaki (1990), con todos los arreglos de Hoshi, entró en Oricon directamente en el número 1[[2]]. «Riverside Hotel» de Yosui Inoue también es un arreglo suyo[[3]], y volvió a ser un éxito como tema del drama <i>New York Koi Monogatari</i>[[4]]. Y en «Bokura no Diary» de H2O, los créditos dicen: arreglo de Katz Hoshi, producción de Hidenori Taga[[5]].',
                '예를 들면 스튜디오 지브리의 『추억은 방울방울』(1991년). 미야코 하루미가 부른 주제가 「사랑은 꽃, 너는 그 씨앗」의 편곡이 호시 카츠다[[1]]. 오자키 유타카의 앨범 『탄생』(1990년)은 전곡을 호시 카츠가 편곡했고, 오리콘에 첫 등장 1위를 했다[[2]]. 이노우에 요스이 「리버사이드 호텔」도 호시 카츠의 편곡으로[[3]], 드라마 『뉴욕 사랑 이야기』의 주제가로 다시 히트했다[[4]]. H2O 「우리들의 다이어리」의 크레디트에도 편곡 호시 카츠, 프로듀스 다가 히데노리의 이름이 있다[[5]].'))
put('h_works_lbl', ('Listen alongside — you may have heard these without knowing his name', '对照聆听——就算不知道名字，或许也早已听过', 'Para escuchar a la par — quizá ya las oíste sin saber su nombre', '함께 들어보기 — 이름은 몰라도, 이미 귀를 스쳐 갔을지도 모른다'))
for k, v in {'h_w1a': ('Harumi Miyako', '都春美', 'Harumi Miyako', '미야코 하루미'), 'h_w1s': ('"Ai wa Hana, Kimi wa Sono Tane"', '《爱是花，你是那颗种子》', '«Ai wa Hana, Kimi wa Sono Tane»', '「사랑은 꽃, 너는 그 씨앗」'),
             'h_w1c': ('Harumi Miyako - Topic (theme of <i>Only Yesterday</i>, official)', 'Harumi Miyako - Topic（电影《岁月的童话》主题曲・官方）', 'Harumi Miyako - Topic (tema de <i>Recuerdos del ayer</i>, oficial)', 'Harumi Miyako - Topic(영화 『추억은 방울방울』 주제가・공식)'),
             'h_w2a': ('Yutaka Ozaki', '尾崎丰', 'Yutaka Ozaki', '오자키 유타카'), 'h_w2s': ('"LOVE WAY"', '《LOVE WAY》', '«LOVE WAY»', '「LOVE WAY」'),
             'h_w2c': ('Yutaka Ozaki - Topic (lead single from <i>Tanjo</i>, official)', 'Yutaka Ozaki - Topic（专辑《诞生》先行单曲・官方）', 'Yutaka Ozaki - Topic (sencillo de adelanto de <i>Tanjo</i>, oficial)', 'Yutaka Ozaki - Topic(앨범 『탄생』 선행 싱글・공식)'),
             'h_w3a': ('Yosui Inoue', '井上阳水', 'Yosui Inoue', '이노우에 요스이'), 'h_w3s': ('"Riverside Hotel"', '《Riverside Hotel》', '«Riverside Hotel»', '「리버사이드 호텔」'),
             'h_w3c': ('kantarokanna (fan upload, 860K views)', 'kantarokanna（网友上传・86万次）', 'kantarokanna (subido por un fan, 860 mil vistas)', 'kantarokanna(일반 업로드・86만 회)'),
             'h_w4a': ('H2O', 'H2O', 'H2O', 'H2O'), 'h_w4s': ('"Bokura no Diary"', '《我们的日记》', '«Bokura no Diary»', '「우리들의 다이어리」'),
             'h_w4c': ('H2O - Topic (arranged by Katz Hoshi, official)', 'H2O - Topic（编曲 星胜・官方）', 'H2O - Topic (arreglo de Katz Hoshi, oficial)', 'H2O - Topic(편곡 호시 카츠・공식)')}.items():
    put(k, v)
setk('h_yoin1', '名前を知らなくても、その音は、あなたの耳を通り抜けているかもしれない。',
     'You may not know his name — but his sound may already have passed through your ears.', '就算不知道他的名字，他的声音或许早已穿过你的耳朵。', 'Quizá no sepas su nombre, pero puede que su sonido ya haya pasado por tus oídos.', '이름은 몰라도, 그 소리는 이미 당신의 귀를 스쳐 갔을지도 모른다.')

# ---------- 出典 ----------
ul = main.select_one('.cw-sources ul')
for i, (lab, u, four) in enumerate([
        ('TOWER RECORDS — ゴールデン☆ベスト・シリーズ特集（2015）', TOWER, ('TOWER RECORDS — Golden Best series (2015)', 'TOWER RECORDS — 黄金精选系列特辑（2015）', 'TOWER RECORDS — serie Golden Best (2015)', 'TOWER RECORDS — 골든 베스트 시리즈 특집(2015)')),
        ('Wikipedia — RCサクセション', W_RC, ('Wikipedia (ja) — RC Succession', 'Wikipedia（日文）— RC Succession', 'Wikipedia (ja) — RC Succession', 'Wikipedia(일본어) — RC 석세션')),
        ('Wikipedia — おもひでぽろぽろ', W_OMOIDE, ('Wikipedia (ja) — Only Yesterday', 'Wikipedia（日文）— 岁月的童话', 'Wikipedia (ja) — Recuerdos del ayer', 'Wikipedia(일본어) — 추억은 방울방울')),
        ('Wikipedia — 誕生（尾崎豊のアルバム）', W_TANJO, ('Wikipedia (ja) — Tanjo (Yutaka Ozaki album)', 'Wikipedia（日文）— 诞生（尾崎丰专辑）', 'Wikipedia (ja) — Tanjo (álbum de Yutaka Ozaki)', 'Wikipedia(일본어) — 탄생(오자키 유타카 앨범)')),
        ('Wikipedia — リバーサイド ホテル', W_RIVER, ('Wikipedia (ja) — Riverside Hotel', 'Wikipedia（日文）— Riverside Hotel', 'Wikipedia (ja) — Riverside Hotel', 'Wikipedia(일본어) — 리버사이드 호텔')),
        ('YouTube — H2O「僕等のダイアリー」公式配信のクレジット', YT_H2O, ('YouTube — credits for H2O\'s "Bokura no Diary" (official)', 'YouTube — H2O《我们的日记》官方音源署名', 'YouTube — créditos de «Bokura no Diary» de H2O (oficial)', 'YouTube — H2O 「우리들의 다이어리」 공식 크레디트'))]):
    if u in str(ul): continue
    k = f'h_src9_{i}'
    ul.append(frag(f'<li><a data-i18n="{k}" href="{u}" rel="noopener noreferrer" target="_blank">{lab}</a></li>')); put(k, four)

for l, d in MB.common_i18n().items(): TR.setdefault(l, {}).update(d)
h2 = str(soup)
h2 = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', h2)
h2 = h2.replace('<div aria-hidden="true" class="cw-hero__bg">', '<div class="cw-hero__bg" aria-hidden="true">')
h2 = re.sub(r'(<div class="cw-hero__bg" aria-hidden="true">)<img alt="" decoding="async" src="([^"]+)"/>', r'\1<img src="\2" alt="" decoding="async"/>', h2)
h2 = MB.unify_tail(h2, 'hoshikatsu')
JN = 'kimi-wa-hoshi-katsu.i18n.json'
json.dump(TR, open(os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, JN), 'w', encoding='utf-8').write(json.dumps(TR, ensure_ascii=False, separators=(',', ':')))
h2 = h2.replace('</body>', MB.i18n_script(TR, JN) + '</body>', 1)
open(OUT, 'w', encoding='utf-8').write(h2)
print('ok', len(h2))
