# -*- coding: utf-8 -*-
# 2026-10-16 夜：事実の点検と共通の型（09章の編曲者・注記を出さない・参考動画の位置・字幕/表記のズレ）
# 入力：share/check/tokushu-hoshi-katsu.html（data-i18n 付き）＋ tools/magazine/i18n_hoshikatsu.json
import sys, os, re, json
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
from bs4 import BeautifulSoup

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(R, 'share/check/tokushu-hoshi-katsu.html')
h = open(SRC, encoding='utf-8').read()
TR = json.load(open(os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'), encoding='utf-8'))
LG = ['en', 'zh-Hans', 'es', 'ko']
# 古い多言語スクリプトを外す（あとで入れ直す）
h = re.sub(r'<script>\(function\(\)\{var L=.*?</script>', '', h, flags=re.S)
soup = BeautifulSoup(h, 'html.parser')
main = soup.find('main')

def src(label, url):
    return f'<a class="cw-src" href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'

W_KISUGI = 'https://ja.wikipedia.org/wiki/%E6%9D%A5%E7%94%9F%E3%81%9F%E3%81%8B%E3%81%8A'
W_SAILOR = 'https://ja.wikipedia.org/wiki/%E3%82%BB%E3%83%BC%E3%83%A9%E3%83%BC%E6%9C%8D%E3%81%A8%E6%A9%9F%E9%96%A2%E9%8A%83_(%E6%9B%B2)'
W_SECOND = 'https://ja.wikipedia.org/wiki/%E3%82%BB%E3%82%AB%E3%83%B3%E3%83%89%E3%83%BB%E3%83%A9%E3%83%96_(%E6%9B%B2)'
W_HOSHI = 'https://ja.wikipedia.org/wiki/%E6%98%9F%E5%8B%9D'
YT_SECOND = 'https://www.youtube.com/watch?v=hEyxari6i-g'
YT_YUME = 'https://www.youtube.com/watch?v=ueF5Lc0oVKQ'

def el(k):
    e = main.find(attrs={'data-i18n': k})
    if e is None:
        sys.exit('no key ' + k)
    return e

def setk(k, ja, en, zh, es, ko, e=None):
    e = e if e is not None else el(k)
    e.clear(); e.append(BeautifulSoup(ja, 'html.parser'))
    e['data-i18n'] = k
    for l, v in zip(LG, [en, zh, es, ko]):
        TR.setdefault(l, {})[k] = v

NEW = [2000]
def newk():
    NEW[0] += 1; return f'k{NEW[0]}'

def frag(x):
    return BeautifulSoup(x, 'html.parser')

PLAY = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5.5v13l11-6.5z"></path></svg>'
def fig(id, role, artist, song, cap, size='small', page=None, keys=None, q='hqdefault'):
    """keys = (artistKey, songKey, capKey, roleKey or None, pageKey or None)"""
    ka, ks, kc, kr, kp = keys
    r = f'<span class="cw-video__role"{f" data-i18n={chr(34)}{kr}{chr(34)}" if kr else ""}>{role}</span>'
    p = f'<a class="cw-video__page" data-i18n="{kp}" href="{page}">この曲のページへ →</a>' if page else ''
    return (f'<figure class="cw-video cw-video--{size}"><div class="cw-video__frame"><button aria-label="ここで再生：{artist}{song}" class="cw-video__cover" data-yt-cover="{id}" type="button">'
            f'<img alt="" decoding="async" src="https://i.ytimg.com/vi/{id}/{q}.jpg"/>{r}<span aria-hidden="true" class="cw-video__play">{PLAY}</span></button></div>'
            f'<figcaption><span class="cw-video__name"><b data-i18n="{ka}">{artist}</b><i data-i18n="{ks}">{song}</i></span><span class="cw-video__cap" data-i18n="{kc}">{cap}</span>{p}</figcaption></figure>')

def put(k, v4):
    for l, v in zip(LG, v4):
        TR.setdefault(l, {})[k] = v

ART_KISUGI = ('Takao Kisugi', '来生隆夫', 'Takao Kisugi', '키스기 다카오')
ART_AKINA = ('Akina Nakamori', '中森明菜', 'Akina Nakamori', '나카모리 아키나')
S_YUME = ('"Yume no Tochu"', '《梦的途中》', '«Yume no Tochu»', '「꿈의 도중」')
S_SECOND = ('"Second Love"', '《Second Love》', '«Second Love»', '「세컨드 러브」')
S_SLOW = ('"Slow Motion"', '《Slow Motion》', '«Slow Motion»', '「슬로 모션」')
PAGE_TXT = ("Go to this song's page →", '前往这首歌的页面 →', 'Ir a la página de esta canción →', '이 곡 페이지로 →')

# ---------- 08章：来生たかお - 夢の途中（星勝の編曲がクレジットで確かめられる曲に） ----------
ch = main.find('section', id='ch08')
setk('k71', '姉弟の歌を、ふたつの声で', "The siblings' song, in two voices", '姐弟的歌，两种声音', 'La canción de los hermanos, en dos voces', '남매의 노래를, 두 개의 목소리로')
setk('k9', '来生たかお - 夢の途中', 'Takao Kisugi - Yume no Tochu', '来生隆夫 - 梦的途中', 'Takao Kisugi - Yume no Tochu', '키스기 다카오 - 꿈의 도중')
ch.find('p', class_='cw-chead__year').string = '1981'
mainfig = ch.find('div', class_='cw-main')
ka, ks, kc = newk(), newk(), newk()
mainfig.clear(); mainfig.append(frag(fig('KgVkLLwUP18', 'Live', '来生たかお', '「夢の途中」', '白米部長。（一般投稿・1725万回）', 'main', keys=(ka, ks, kc, None, None))))
put(ka, ART_KISUGI); put(ks, S_YUME); put(kc, ('白米部長。(fan upload, 17.25M views)', '白米部長。（网友上传・1725万次）', '白米部長。(subido por un fan, 17,25 M de vistas)', '白米部長。(일반 업로드・1725만 회)'))
setk('k72', f'作詞は姉の来生えつこ、作曲は弟の来生たかお。姉弟のソングライター・コンビだ{src("Wikipedia — 来生たかお", W_KISUGI)}。1976年のデビュー・アルバム『浅い夢』から、星勝はアレンジャーとして加わっていた{src("Wikipedia — 来生たかお", W_KISUGI)}。',
     'Lyrics by his older sister Etsuko Kisugi, music by Takao Kisugi — a brother-and-sister songwriting team[[1]]. From his 1976 debut album <i>Asai Yume</i>, Katz Hoshi was there as an arranger[[2]].',
     '作词是姐姐来生悦子，作曲是弟弟来生隆夫——一对姐弟词曲搭档[[1]]。从1976年的出道专辑《浅梦》开始，星胜就以编曲者身份参与其中[[2]]。',
     'Letra de su hermana mayor, Etsuko Kisugi; música de Takao Kisugi: un dúo de compositores hermanos[[1]]. Desde su álbum debut de 1976, <i>Asai Yume</i>, Katz Hoshi estuvo ahí como arreglista[[2]].',
     '작사는 누나 키스기 에츠코, 작곡은 동생 키스기 다카오. 남매 송라이터 콤비다[[1]]. 1976년 데뷔 앨범 『얕은 꿈』부터 호시 카츠는 편곡자로 함께했다[[2]].')
setk('k73', f'1981年、来生たかおは「夢の途中」を歌う。薬師丸ひろ子が歌った映画の主題歌「セーラー服と機関銃」と同じメロディの曲で、どちらも編曲は星勝。シンプルなアルペジオとドラムスで始まる音が耳に残る{src("Wikipedia — セーラー服と機関銃（曲）", W_SAILOR)}。来生版はオリコン集計で40.6万枚を売った{src("Wikipedia — セーラー服と機関銃（曲）", W_SAILOR)}。',
     'In 1981, Takao Kisugi sang "Yume no Tochu." It shares its melody with "Sailor Fuku to Kikanju," the film theme sung by Hiroko Yakushimaru — and Hoshi arranged both. That sound, opening on a simple arpeggio and drums, stays with you[[1]]. Kisugi\'s version sold 406,000 copies by Oricon\'s count[[2]].',
     '1981年，来生隆夫唱了《梦的途中》。它与药师丸博子演唱的电影主题曲《水手服与机关枪》是同一段旋律，两首的编曲都是星胜。以简单的琶音和鼓声开场的声音，让人久久难忘[[1]]。来生的版本按Oricon统计卖出40.6万张[[2]]。',
     'En 1981, Takao Kisugi cantó «Yume no Tochu». Comparte melodía con «Sailor Fuku to Kikanju», el tema de la película que cantó Hiroko Yakushimaru, y Hoshi arregló las dos. Ese sonido que arranca con un arpegio sencillo y batería se queda contigo[[1]]. La versión de Kisugi vendió 406.000 copias según Oricon[[2]].',
     '1981년, 키스기 다카오는 「꿈의 도중」을 부른다. 야쿠시마루 히로코가 부른 영화 주제가 「세일러복과 기관총」과 같은 멜로디의 곡으로, 둘 다 편곡은 호시 카츠. 단순한 아르페지오와 드럼으로 시작하는 소리가 귀에 남는다[[1]]. 키스기 버전은 오리콘 집계로 40.6만 장이 팔렸다[[2]].')
setk('k74', f'来生たかおは、控えめで都会的、ノスタルジックな作風で、ほとんどビブラートを掛けない歌い方は「来生節」と呼ばれる{src("Wikipedia — 来生たかお", W_KISUGI)}。その声を、星勝はどう鳴らしたか。',
     'Takao Kisugi\'s style — understated, urban, nostalgic, sung with almost no vibrato — is known as "Kisugi-bushi"[[1]]. How did Hoshi make that voice ring?',
     '来生隆夫的风格克制、都会、带着怀旧，几乎不用颤音的唱法被称为“来生节”[[1]]。星胜是怎样让这副嗓音响起来的？',
     'El estilo de Takao Kisugi —contenido, urbano, nostálgico, casi sin vibrato— se conoce como «Kisugi-bushi»[[1]]. ¿Cómo hizo Hoshi sonar esa voz?',
     '키스기 다카오는 절제되고 도회적이며 향수 어린 작풍으로, 비브라토를 거의 쓰지 않는 창법을 \'키스기부시\'라고 부른다[[1]]. 그 목소리를 호시 카츠는 어떻게 울렸을까.')
setk('k75', '聴きくらべ — 1981年の音源と、同じメロディのもうひとつの声', 'Listen alongside — the 1981 recording, and the same melody in another voice', '对照聆听——1981年的音源，与同一旋律的另一个声音', 'Para escuchar a la par — la grabación de 1981 y la misma melodía en otra voz', '함께 들어보기 — 1981년 음원, 그리고 같은 멜로디의 또 다른 목소리')
grid = ch.find('div', class_='cw-more__grid')
ka, ks, kc = newk(), newk(), newk()
grid.insert(0, frag(fig('ueF5Lc0oVKQ', '1981', '来生たかお', '「夢の途中」', 'Takao Kisugi - Topic（1981年の音源・編曲 星勝・公式配信）', keys=(ka, ks, kc, None, None))))
put(ka, ART_KISUGI); put(ks, S_YUME); put(kc, ('Takao Kisugi - Topic (1981 recording, arranged by Katz Hoshi, official)', 'Takao Kisugi - Topic（1981年音源・编曲 星胜・官方）', 'Takao Kisugi - Topic (grabación de 1981, arreglo de Katz Hoshi, oficial)', 'Takao Kisugi - Topic(1981년 음원・편곡 호시 카츠・공식)'))
setk('k76', 'そして1982年、姉弟の曲は中森明菜に渡る。', "And in 1982, the siblings' songs pass to Akina Nakamori.", '然后在1982年，姐弟的歌交到了中森明菜手里。', 'Y en 1982, las canciones de los hermanos pasan a Akina Nakamori.', '그리고 1982년, 남매의 곡은 나카모리 아키나에게 건너간다.')

# ---------- 09章：来生たかお - セカンド・ラブ（明菜版の編曲は萩田光雄。星勝が編んだのは本人の録音） ----------
ch = main.find('section', id='ch09')
setk('k77', '同じ歌を、作った本人の声で', 'The same song, in the voice of the man who wrote it', '同一首歌，用作者本人的声音', 'La misma canción, en la voz de quien la escribió', '같은 노래를, 만든 본인의 목소리로')
setk('k10', '来生たかお - セカンド・ラブ', 'Takao Kisugi - Second Love', '来生隆夫 - Second Love', 'Takao Kisugi - Second Love', '키스기 다카오 - 세컨드 러브')
ch.find('p', class_='cw-chead__year').string = '1983'
old_akina = ch.find('div', class_='cw-main').find('figure').extract()
old_kisugi = ch.find('button', attrs={'data-yt-cover': 'hEyxari6i-g'}).find_parent('figure').extract()
old_kisugi['class'] = ['cw-video', 'cw-video--main']
old_kisugi.find('img')['src'] = 'https://i.ytimg.com/vi/hEyxari6i-g/maxresdefault.jpg'
r = old_kisugi.find('span', class_='cw-video__role'); r.string = '1983'; del r['data-i18n']
setk('k122', 'Takao Kisugi - Topic（プロデュース 多賀英典・編曲 星勝・公式配信）', 'Takao Kisugi - Topic (produced by Hidenori Taga, arranged by Katz Hoshi, official)', 'Takao Kisugi - Topic（制作 多贺英典・编曲 星胜・官方）', 'Takao Kisugi - Topic (producción de Hidenori Taga, arreglo de Katz Hoshi, oficial)', 'Takao Kisugi - Topic(프로듀스 다가 히데노리・편곡 호시 카츠・공식)', e=old_kisugi.find(attrs={'data-i18n': 'k122'}))
ch.find('div', class_='cw-main').append(old_kisugi)
old_akina['class'] = ['cw-video', 'cw-video--small']
old_akina.find('img')['src'] = 'https://i.ytimg.com/vi/i5U93W19Ays/hqdefault.jpg'
ch.find('div', class_='cw-more__grid').insert(0, old_akina)
setk('k82', '聴きくらべ — 中森明菜が歌った「セカンド・ラブ」と、デビュー曲', 'Listen alongside — Akina Nakamori\'s "Second Love," and her debut single', '对照聆听——中森明菜演唱的《Second Love》，与她的出道曲', 'Para escuchar a la par — la «Second Love» de Akina Nakamori y su sencillo debut', '함께 들어보기 — 나카모리 아키나가 부른 「세컨드 러브」, 그리고 데뷔곡')
setk('k78', f'1982年11月10日、中森明菜の3枚目のシングル「セカンド・ラブ」が出る。作詞は来生えつこ、作曲は来生たかお、編曲は萩田光雄{src("Wikipedia — セカンド・ラブ（曲）", W_SECOND)}。',
     'On November 10, 1982, Akina Nakamori released her third single, "Second Love." Lyrics by Etsuko Kisugi, music by Takao Kisugi, arrangement by Mitsuo Hagita[[1]].',
     '1982年11月10日，中森明菜的第三张单曲《Second Love》发行。作词来生悦子，作曲来生隆夫，编曲萩田光雄[[1]]。',
     'El 10 de noviembre de 1982, Akina Nakamori publicó su tercer sencillo, «Second Love». Letra de Etsuko Kisugi, música de Takao Kisugi, arreglo de Mitsuo Hagita[[1]].',
     '1982년 11월 10일, 나카모리 아키나의 세 번째 싱글 「세컨드 러브」가 나온다. 작사는 키스기 에츠코, 작곡은 키스기 다카오, 편곡은 하기타 미츠오[[1]].')
setk('k79', f'オリコン週間1位を通算6週。1983年度の年間8位、およそ77万枚で、明菜のシングルでいちばん売れた曲になった{src("Wikipedia — セカンド・ラブ（曲）", W_SECOND)}。もとは、大橋純子に渡すつもりで作られた曲だった{src("Wikipedia — 来生たかお", W_KISUGI)}。',
     'Six weeks in total at No. 1 on the Oricon weekly chart, 8th for the 1983 year, around 770,000 copies — her best-selling single[[1]]. It had originally been written with Junko Ohashi in mind[[2]].',
     'Oricon周榜累计6周第一，1983年度年榜第8，约77万张，成为明菜销量最高的单曲[[1]]。这首歌原本是打算写给大桥纯子的[[2]]。',
     'Seis semanas en total en el número 1 semanal de Oricon, 8.ª del año 1983, unas 770.000 copias: su sencillo más vendido[[1]]. En origen se había escrito pensando en Junko Ohashi[[2]].',
     '오리콘 주간 1위 통산 6주. 1983년도 연간 8위, 약 77만 장으로 아키나의 싱글 중 가장 많이 팔린 곡이 되었다[[1]]. 원래는 오하시 준코에게 주려고 만든 곡이었다[[2]].')
setk('k80', f'星勝が編んだのは、作った本人が歌うほうの「セカンド・ラブ」だ。来生たかおの録音のクレジットには、プロデューサー多賀英典、編曲 星勝と並んでいる{src("公式配信のクレジット", YT_SECOND)}{src("Wikipedia — 星勝", W_HOSHI)}。',
     'The "Second Love" Hoshi arranged is the one sung by the man who wrote it. On Takao Kisugi\'s recording, the credits read: producer Hidenori Taga, arranger Katz Hoshi[[1]][[2]].',
     '星胜编曲的，是作者本人演唱的那版《Second Love》。来生隆夫录音的署名里，并列着制作人多贺英典、编曲星胜[[1]][[2]]。',
     'La «Second Love» que arregló Hoshi es la que canta su autor. En la grabación de Takao Kisugi, los créditos dicen: producción, Hidenori Taga; arreglo, Katz Hoshi[[1]][[2]].',
     '호시 카츠가 편곡한 것은, 만든 본인이 부르는 쪽의 「세컨드 러브」다. 키스기 다카오 녹음의 크레디트에는 프로듀서 다가 히데노리, 편곡 호시 카츠가 나란히 적혀 있다[[1]][[2]].')
setk('k81', '同じメロディでも、編曲と声が変われば、歌の景色が変わる。17歳の明菜の歌と、ほとんどビブラートを掛けない作者の歌。聴きくらべてみてほしい。',
     'Same melody — but change the arrangement and the voice, and the whole landscape of the song changes. Seventeen-year-old Akina, and the writer who sings with almost no vibrato. Listen to them side by side.',
     '同样的旋律，编曲和声音一变，歌的风景也就变了。17岁的明菜，和几乎不用颤音的作者。请对照听听看。',
     'La misma melodía; cambia el arreglo y la voz, y cambia todo el paisaje. Akina con diecisiete años, y el autor que canta casi sin vibrato. Escúchalas una junto a otra.',
     '같은 멜로디라도 편곡과 목소리가 바뀌면 노래의 풍경이 바뀐다. 17살 아키나의 노래와, 비브라토를 거의 쓰지 않는 작자의 노래. 나란히 들어 보길 바란다.')
setk('k105', '同じメロディでも、声と編曲で景色が変わる。', 'Same melody — a different voice, a different arrangement, a different landscape.', '同样的旋律，声音与编曲一变，风景就变了。', 'La misma melodía; otra voz, otro arreglo, otro paisaje.', '같은 멜로디라도, 목소리와 편곡으로 풍경이 바뀐다.')

# ---------- 冒頭の名前の並び：星勝のクレジットが確かな人だけに ----------
setk('k16', 'モップス。井上陽水。小椋佳。RCサクセション。来生たかお。薬師丸ひろ子。安全地帯。尾崎豊。浜田省吾。名前だけ並べれば、昭和から平成のヒット曲の山になる。',
     'The Mops. Yosui Inoue. Kei Ogura. RC Succession. Takao Kisugi. Hiroko Yakushimaru. Anzen Chitai. Yutaka Ozaki. Shogo Hamada. Just line up the names, and you have a mountain of hits from the Showa era into the Heisei years.',
     'The Mops。井上阳水。小椋佳。RC Succession。来生隆夫。药师丸博子。安全地带。尾崎丰。滨田省吾。光是把名字排出来，就是一座从昭和到平成的金曲之山。',
     'The Mops. Yosui Inoue. Kei Ogura. RC Succession. Takao Kisugi. Hiroko Yakushimaru. Anzen Chitai. Yutaka Ozaki. Shogo Hamada. Basta alinear los nombres para levantar una montaña de éxitos desde la era Showa hasta Heisei.',
     '더 모프스. 이노우에 요스이. 오구라 케이. RC 석세션. 키스기 다카오. 야쿠시마루 히로코. 안전지대. 오자키 유타카. 하마다 쇼고. 이름만 늘어놓아도 쇼와부터 헤이세이까지의 히트곡이 산처럼 쌓인다.')

# ---------- 04章：「TV初出演」は投稿者のタイトル。断定しない ----------
setk('k46', 'いま鳴っているこの映像は、投稿者が「TV初出演」と題して残しているものだ。九州ニューミュージックフェスティバルの模様で、若い陽水が「窓の外ではリンゴ売り」と歌っている。',
     'The footage playing now was posted under the title "first TV appearance." Filmed at the Kyushu New Music Festival, it shows a young Yosui singing "outside the window, an apple seller."',
     '现在播放的这段影像，投稿者以“首次上电视”为题保存了下来。那是九州新音乐节的现场，年轻的阳水正唱着“窗外有卖苹果的人”。',
     'Estas imágenes las subió alguien con el título «primera vez en TV». En el Kyushu New Music Festival, un Yosui joven canta «al otro lado de la ventana, un vendedor de manzanas».',
     '지금 흐르는 이 영상은 올린 사람이 「첫 TV 출연」이라는 제목으로 남겨 둔 것이다. 규슈 뉴뮤직 페스티벌의 모습으로, 젊은 요스이가 \'창밖에는 사과 장수\'를 노래하고 있다.')
setk('k103', '若い陽水が、「窓の外ではリンゴ売り」と歌っている。', 'A young Yosui, singing "outside the window, an apple seller."', '年轻的阳水，唱着“窗外有卖苹果的人”。', 'Un Yosui joven canta «al otro lado de la ventana, un vendedor de manzanas».', '젊은 요스이가 \'창밖에는 사과 장수\'를 노래하고 있다.')
for k in ('k131', 'k204'):
    e = main.find(attrs={'data-i18n': k})
    if e is not None:
        setk(k, 'TV', 'TV', 'TV', 'TV', 'TV', e=e)
setk('k900', '最後にもう一度、04章の、若い陽水が歌う「氷の世界」を聴いてみてほしい。',
     'One last thing: go back to Chapter 04 and listen again to the young Yosui singing "Koori no Sekai."', '最后，请再回到第04章，听一遍年轻的阳水演唱的《冰的世界》。',
     'Por último: vuelve al capítulo 04 y escucha otra vez al joven Yosui cantando «Koori no Sekai».', '마지막으로 한 번 더, 04장에서 젊은 요스이가 부르는 「얼음의 세계」를 들어 봐 주었으면 한다.')

# ---------- 写真の添え文：裏の取れない言い方を外す ----------
setk('k35', '1970年3月15日から183日間、大阪・千里丘陵で日本万国博覧会が開かれた。アジアで初めての万博で、総入場者数は6421万人を超えた[[1]]。モップスが活動していた頃、日本はこんな未来の形を見上げていた。'.replace('[[1]]', src('Wikipedia — 日本万国博覧会', 'https://ja.wikipedia.org/wiki/%E6%97%A5%E6%9C%AC%E4%B8%87%E5%9B%BD%E5%8D%9A%E8%A6%A7%E4%BC%9A')),
     'For 183 days from March 15, 1970, the Japan World Exposition was held in the Senri Hills of Osaka. It was the first world\'s fair in Asia, and more than 64.2 million people came[[1]]. In the years The Mops were playing, Japan was gazing up at shapes like these — a picture of the future.',
     '1970年3月15日起的183天里，日本万国博览会在大阪千里丘陵举行。这是亚洲首届世博会，总入场人数超过6421万[[1]]。The Mops活跃的那些年，日本正仰望着这样的未来形状。',
     'Durante 183 días a partir del 15 de marzo de 1970, la Exposición Universal se celebró en las colinas de Senri, Osaka. Fue la primera de Asia y la visitaron más de 64,2 millones de personas[[1]]. En los años en que tocaba The Mops, Japón miraba hacia arriba, hacia formas como estas: una imagen del futuro.',
     '1970년 3월 15일부터 183일 동안, 오사카 센리 구릉에서 일본만국박람회가 열렸다. 아시아 최초의 엑스포로, 총 입장객은 6421만 명을 넘었다[[1]]. 더 모프스가 활동하던 무렵, 일본은 이런 미래의 모양을 올려다보고 있었다.')

# ---------- 吹き出し：多言語の対象に入れ、裏の取れない一言を外す ----------
SAY = {
 'この「月光仮面」': ('In "Gekko Kamen," that\'s Hoshi himself singing. Plenty of people still think it\'s Hiromitsu — but it\'s a different voice.', '这首《月光假面》，唱歌的是星胜本人。至今仍有不少人以为是弘光（其实是另一个声音）。', 'En «Gekko Kamen» canta el propio Hoshi. Todavía hay quien cree que es Hiromitsu, pero es otra voz.', '이 「월광가면」, 노래하는 사람은 호시 카츠 본인입니다. 히로미츠라고 생각하는 사람이 지금도 꽤 있어요(분명히 다른 목소리입니다).'),
 '「たどり着いたら': ('"Tadoritsuitara Itsumo Amefuri" is a Takuro Yoshida song, and this video has 1.49 million views. The Mops get called Group Sounds survivors, but really, after GS had faded away, they were the band making the heaviest sound.', '《每当抵达总是下雨》是吉田拓郎的歌，播放了149万次。The Mops常被说成是GS的幸存者，但其实，在GS全部消失之后，发出最强声音的正是这支乐队。', '«Tadoritsuitara Itsumo Amefuri» es de Takuro Yoshida y este video tiene 1,49 millones de vistas. A The Mops se les llama supervivientes del Group Sounds, pero en realidad, cuando el GS ya había desaparecido, eran la banda que sonaba más fuerte.', '「도착하면 언제나 비」는 요시다 타쿠로의 곡으로, 149만 회 재생되었습니다. 더 모프스는 GS의 생존자라고 불린 밴드지만, 실제로는 GS가 다 사라진 뒤에 가장 강한 소리를 내던 밴드였습니다.'),
 'このアルバムが売れていた年': ('The year this album was selling, Japan saw its first negative growth since the war. Prices rose 23 percent — the year that gave us the phrase "crazy prices." It wasn\'t a year when happy songs sold. And still: a million copies.', '这张专辑热卖的那年，日本经历了战后首次负增长。物价上涨23个百分点，连“狂乱物价”这个词都诞生了。那不是明快的歌能卖的年份。即便如此，一百万张。', 'El año en que se vendía este disco, Japón tuvo su primer crecimiento negativo de la posguerra. Los precios subieron un 23 por ciento: el año en que nació la expresión «precios enloquecidos». No era un año para canciones alegres. Y aun así: un millón.', '이 곡이 팔리던 해, 일본은 전후 처음으로 마이너스 성장을 겪었습니다. 물가는 23퍼센트 올라 \'광란물가\'라는 말까지 생긴 해예요. 밝은 노래가 팔리던 해가 아니었죠. 그래도 100만 장.'),
 'ロサンゼルスに行って': ('He went to Los Angeles, stood in front of top-tier players, and they rated him. I think that\'s what carried Hoshi\'s name beyond Japan.', '去到洛杉矶，站在当地一流乐手面前，并得到了认可。我想，正是这件事让星胜的名字走出了日本。', 'Fue a Los Ángeles, se plantó ante músicos de primera y lo valoraron. Creo que eso fue lo que llevó el nombre de Hoshi más allá de Japón.', '로스앤젤레스에 가서 그곳의 일류 연주자들 앞에서 인정받았다. 이것이 호시 카츠의 이름을 일본 밖까지 알린 사건이었다고 생각합니다.'),
 '小椋佳さんは譜面が': ('Kei Ogura couldn\'t read music and didn\'t play guitar. So when a lyric was hard to set, Hoshi wrote the melody. On "Stand Still," Hoshi sings too.', '小椋佳看不懂乐谱，也不会弹吉他。所以当歌词难以谱曲时，就由星胜来写曲。在这首《Stand Still》里，星胜自己也唱了。', 'Kei Ogura no sabía leer música ni tocaba la guitarra. Así que cuando una letra costaba ponerle música, la melodía la escribía Hoshi. En «Stand Still», Hoshi también canta.', '오구라 케이는 악보를 읽지 못하고 기타도 치지 못했습니다. 그래서 가사에 곡을 붙이기 어려울 때는 호시 카츠가 곡을 썼어요. 이 「스탠드 스틸」에서는 호시 카츠가 직접 노래도 합니다.'),
 '「セーラー服と機関銃」も': ('"Sailor Fuku to Kikanju" also has lyrics by Etsuko Kisugi, music by Takao Kisugi — and arrangement by Hoshi. It was the theme of a Kadokawa film and a huge hit in 1981.', '《水手服与机关枪》也是来生悦子作词、来生隆夫作曲，再由星胜编曲。它是角川电影的主题曲，在1981年大卖。', '«Sailor Fuku to Kikanju» también tiene letra de Etsuko Kisugi, música de Takao Kisugi y arreglo de Hoshi. Fue el tema de una película de Kadokawa y un gran éxito en 1981.', '「세일러복과 기관총」도 키스기 에츠코 작사, 키스기 다카오 작곡, 그리고 호시 카츠 편곡입니다. 가도카와 영화의 주제가로, 1981년의 대히트가 되었어요.'),
 '「悲しい色やね」も': ('"Kanashii Iro ya ne" is a Hoshi arrangement too. Masaki Ueda\'s Kansai blues, brought straight to Tokyo. Folk, rock or idol pop — Hoshi arranged it all with the same hands.', '《悲伤的颜色呢》也是星胜编曲。把上田正树的关西蓝调原原本本带到东京的声音。民谣也好，摇滚也好，偶像也好，星胜都用同一双手去编。', '«Kanashii Iro ya ne» también lleva arreglo de Hoshi. El blues de Kansai de Masaki Ueda, llevado tal cual a Tokio. Folk, rock o pop de ídolos: Hoshi lo arreglaba todo con las mismas manos.', '「슬픈 색이네」도 호시 카츠의 편곡입니다. 우에다 마사키의 간사이 블루스를 그대로 도쿄로 가져온 소리. 포크든 록이든 아이돌이든, 호시 카츠는 같은 손길로 엮는 사람이었습니다.'),
}
for b in main.select('.say__bub'):
    t = b.get_text()
    if t.startswith('小椋佳さんは譜面が'):
        b.string = '小椋佳さんは譜面が読めず、ギターも弾けない。だから詞に曲が付きにくいとき、星勝さんが曲を書いていました。この「スタンド・スティル」で、星勝さんは自分でも歌っています。'
    if t.startswith('「悲しい色やね」も'):
        b.string = '「悲しい色やね」も星勝さんの編曲です。上田正樹さんの関西ブルースを、そのまま東京に持ってきた音。星勝さんは、フォークでもロックでもアイドルでも、同じ手つきで編む人でした。'
    if t.startswith('この曲が売れていた年'):
        b.string = 'このアルバムが売れていた年、日本は戦後初めてのマイナス成長を経験しています。物価は23パーセント上がって、「狂乱物価」という言葉まで生まれた年です。明るい曲が売れた年じゃないんですよね。それでも、100万枚。'
    for head, v4 in SAY.items():
        if b.get_text().startswith(head):
            k = newk(); b['data-i18n'] = k; put(k, v4)

# ---------- 11章：森恵の動画は2019年のYouTubeカバー（アルバムは2020年） ----------
r = main.find('section', id='ch11').find('div', class_='cw-main').find('span', class_='cw-video__role')
if r is not None and r.string and '2020' in r.string:
    r.string = 'Cover'

# ---------- 制作側の注記は読者に出さない ----------
for n in main.select('p.cw-note'):
    n.decompose()

# ---------- 参考動画：怒れる人々と同じ大きさ・同じ位置（特集一覧の直前、cw-note の小さい1枚） ----------
ref = main.find('section', class_='cw-ref')
k1, k2, k3, k4 = newk(), newk(), newk(), newk()
note = frag(f'<div class="cw-note"><p data-i18n="{k1}">▼この記事を書くきっかけになった動画</p>'
            f'<figure class="cw-video cw-video--small"><div class="cw-video__frame"><button aria-label="再生" class="cw-video__cover" data-yt-cover="hmGwwZ5hjbI" type="button"><img alt="" decoding="async" loading="lazy" src="https://i.ytimg.com/vi/hmGwwZ5hjbI/mqdefault.jpg"/>'
            f'<span class="cw-video__role" data-i18n="{k2}">きっかけの動画</span><span aria-hidden="true" class="cw-video__play">{PLAY}</span></button></div>'
            f'<figcaption><span class="cw-video__name"><i data-i18n="{k3}">「なぜ、大人になると新しい曲を聴かなくなるのか【鳥類学×音楽心理学】」（汝、ヒトを知れ）</i></span></figcaption></figure>'
            f'<p data-i18n="{k4}">「歌を覚える季節は終わらない」——名前を知らなかった人の音も、今日から覚えられる。</p></div>')
ref.replace_with(note)
put(k1, ('▼ The video that started this article', '▼ 促成这篇文章的视频', '▼ El video que dio origen a este artículo', '▼ 이 글을 쓰게 된 계기의 영상'))
put(k2, ('Where it started', '起因的视频', 'El video que lo empezó', '계기가 된 영상'))
put(k3, ('"Why do we stop listening to new music as adults? [Ornithology × Music Psychology]" (Nanji, Hito wo Shire)', '《为什么长大后就不再听新歌【鸟类学×音乐心理学】》（汝，知人）', '«¿Por qué de adultos dejamos de escuchar música nueva? [Ornitología × Psicología musical]» (Nanji, Hito wo Shire)', '「왜 어른이 되면 새 노래를 듣지 않게 될까 【조류학×음악심리학】」(너 자신, 인간을 알라)'))
put(k4, ('"The season for learning songs never ends" — and the sound of someone whose name you didn\'t know, you can start learning today.', '“学歌的季节永不结束”——那个你不知道名字的人的声音，从今天起也能记住。', '«La estación de aprender canciones nunca termina»: también el sonido de alguien cuyo nombre no conocías se puede aprender desde hoy.', '\'노래를 익히는 계절은 끝나지 않는다\' — 이름을 몰랐던 사람의 소리도, 오늘부터 익힐 수 있다.'))

# ---------- 目次と曲の一覧を、章の中身から作り直す ----------
LAB = {}  # ja -> 4 langs, from existing translations
for e in main.select('[data-i18n]'):
    k = e['data-i18n']
    if all(k in TR.get(l, {}) for l in LG):
        LAB[e.decode_contents().strip()] = tuple(TR[l][k] for l in LG)
for c in main.select('section.cw-chapter'):
    no = c['id'][2:]
    span = main.select_one(f'.cw-toc__grid a[href="#ch{no}"] span')
    mfig = c.find('div', class_='cw-main').find('figure')
    vid = mfig.find('button')['data-yt-cover']
    main.select_one(f'.cw-toc__grid a[href="#ch{no}"] img')['src'] = f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg'
    song = mfig.select_one('.cw-video__name i').get_text().strip('「」')
    k = newk(); span.string = song; span['data-i18n'] = k
    four = LAB.get('「' + song + '」')
    if four:
        put(k, tuple(x.strip('"«»《》「」') for x in four))
ol = main.find('ol', class_='cw-map')
ol.clear(); n = 0
for c in main.select('section.cw-chapter'):
    for f in c.select('figure.cw-video'):
        b = f.find('button'); vid = b['data-yt-cover']; n += 1
        role = f.select_one('.cw-video__role').get_text()
        art = f.select_one('.cw-video__name b'); sng = f.select_one('.cw-video__name i'); cap = f.select_one('.cw-video__cap')
        pg = f.select_one('a.cw-video__page')
        href = pg['href'] if pg else '#' + c['id']
        kh, kc = newk(), newk()
        li = frag(f'<li><a href="{href}"><span class="cw-map__img"><img alt="" decoding="async" src="https://i.ytimg.com/vi/{vid}/mqdefault.jpg"/><em>{n:02d}</em></span>'
                  f'<span class="cw-map__txt" data-card-face="" data-card-music="1"><small data-card-genre="">{role}</small><b data-card-heading="" data-i18n="{kh}">{art.get_text()}{sng.get_text()}</b><i data-card-desc="" data-i18n="{kc}">{cap.decode_contents()}</i></span></a></li>')
        ol.append(li)
        a4 = LAB.get(art.decode_contents().strip()) or (None if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', art.get_text()) else (art.get_text(),) * 4)
        s4 = LAB.get(sng.decode_contents().strip()); c4 = LAB.get(cap.decode_contents().strip())
        sm = ol.find_all('li')[-1].find('small')
        if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', role):
            r4 = LAB.get(role)
            if r4:
                kr = newk(); sm['data-i18n'] = kr; put(kr, r4)
        if a4 and s4:
            put(kh, tuple((a + ('' if l == 'zh-Hans' else ' ') + s) for a, s, l in zip(a4, s4, LG)))
        if c4:
            put(kc, c4)
lbl = main.find('p', string=re.compile(r'THE MAP — \d+ SONGS'))
if lbl is not None:
    lbl.string = f'THE MAP — {n} SONGS'

# ---------- 出典：使わなくなったものを外し、確かめたものを足す ----------
ul = main.select_one('.cw-sources ul')
for a in ul.select('li a'):
    if 'WikiHouse' in a.get_text():
        a.find_parent('li').decompose()
for lab, u, four in [('Wikipedia — セーラー服と機関銃（曲）', W_SAILOR, ('Wikipedia (ja) — Sailor Fuku to Kikanju (song)', 'Wikipedia（日文）— 水手服与机关枪（歌曲）', 'Wikipedia (ja) — Sailor Fuku to Kikanju (canción)', 'Wikipedia(일본어) — 세일러복과 기관총(곡)')),
                     ('YouTube — 来生たかお「セカンド・ラブ」公式配信のクレジット', YT_SECOND, ('YouTube — credits for Takao Kisugi\'s "Second Love" (official)', 'YouTube — 来生隆夫《Second Love》官方音源署名', 'YouTube — créditos de «Second Love» de Takao Kisugi (oficial)', 'YouTube — 키스기 다카오 「세컨드 러브」 공식 크레디트')),
                     ('YouTube — 来生たかお「夢の途中」公式配信のクレジット', YT_YUME, ('YouTube — credits for Takao Kisugi\'s "Yume no Tochu" (official)', 'YouTube — 来生隆夫《梦的途中》官方音源署名', 'YouTube — créditos de «Yume no Tochu» de Takao Kisugi (oficial)', 'YouTube — 키스기 다카오 「꿈의 도중」 공식 크레디트'))]:
    k = newk(); ul.append(frag(f'<li><a data-i18n="{k}" href="{u}" rel="noopener noreferrer" target="_blank">{lab}</a></li>')); put(k, four)

h2 = str(soup)
h2 = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', h2)
h2 = h2.replace('<div aria-hidden="true" class="cw-hero__bg">', '<div class="cw-hero__bg" aria-hidden="true">')
h2 = re.sub(r'(<div class="cw-hero__bg" aria-hidden="true">)<img alt="" decoding="async" src="([^"]+)"/>', r'\1<img src="\2" alt="" decoding="async"/>', h2)
# 音を消さずに再生（mute を付けない）＋関連動画を出さない（怒れる人々と同じ）
h2 = h2.replace("?autoplay=1&playsinline=1\"", "?autoplay=1&playsinline=1&rel=0\"").replace("?autoplay=1&amp;playsinline=1\"", "?autoplay=1&amp;playsinline=1&amp;rel=0\"")
h2 = h2.replace('</style>', '.cw .cw-note .cw-video--small{max-width:360px;margin:14px 0 6px}.cw .cw-note .cw-video--small figcaption{font-size:12.5px}</style>', 1)
TR['_title'] = TR.get('_title', {})
json.dump(TR, open(os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
JN = 'kimi-wa-hoshi-katsu.i18n.json'
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, JN), 'w', encoding='utf-8').write(json.dumps(TR, ensure_ascii=False, separators=(',', ':')))
h2 = h2.replace('</body>', MB.i18n_script(TR, JN) + '</body>', 1)
out = sys.argv[2] if len(sys.argv) > 2 else SRC
open(out, 'w', encoding='utf-8').write(h2)
print('ok', n, 'songs', len(h2))
