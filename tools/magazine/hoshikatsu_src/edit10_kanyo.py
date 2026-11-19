# -*- coding: utf-8 -*-
"""君は星勝を知っているか：星勝が関わっていない曲を外し、各曲に「星勝が何をしたか」を同じ位置・同じ表記で入れる（2026-10-16 たまごさん）
出典（status/hsk_audit/ に取得物）：
  Wikipedia「星勝」（モップスのギター・ボーカル／主な編曲作品：心もよう・スタンド・スティル・ワインレッドの心・悲しい色やね・夢の途中・セカンド・ラブ ほか／主なプロデュース：二色の独楽）
  Wikipedia「飾りじゃないのよ涙は」（明菜版の編曲は萩田光雄、陽水のセルフカバー『9.5カラット』の編曲は久石譲＝星勝の関与なし→外す）
  Wikipedia「スローモーション (中森明菜の曲)」（編曲は船山基紀→外す）／「セカンド・ラブ（曲）」明菜版は萩田光雄→外す
  Wikipedia「悲しみは雪のように」（1992年版のアレンジャーは星勝）／「悲しい色やね」（編曲：星勝）／「たどりついたらいつも雨ふり」（メンバーの星勝）
外したもの：中森明菜「セカンド・ラブ」「スローモーション」、譚詠麟「酒紅色的心」、森恵「氷の世界」、King Gnu「飾りじゃないのよ涙は」
"""
import json, os, re, sys
from bs4 import BeautifulSoup
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB

SRC = os.path.join(R, 'share/check/tokushu-hoshi-katsu.html')
h = open(SRC, encoding='utf-8').read()
s = BeautifulSoup(h, 'html.parser')
TRP = os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json')
tr = json.load(open(TRP, encoding='utf-8'))
L4 = ['en', 'zh-Hans', 'es', 'ko']


def settr(key, d):
    for l in L4:
        tr[l][key] = d[l]


ARR = {'ja': '編曲：星勝', 'en': 'Arrangement: Katz Hoshi', 'zh-Hans': '编曲：星胜', 'es': 'Arreglos: Katz Hoshi', 'ko': '편곡: 호시 카츠'}
PERF = {'ja': '演奏：星勝（モップスのギター）', 'en': 'Guitar: Katz Hoshi (The Mops)', 'zh-Hans': '演奏：星胜（The Mops 吉他）', 'es': 'Guitarra: Katz Hoshi (The Mops)', 'ko': '연주: 호시 카츠 (더 몹스 기타)'}
CREDIT = {
    'DYe-_UV1ZE8': PERF, 'qx6gEp_P-4E': PERF, 'o8PEXUTnagw': PERF, '6YZabGNLn7c': PERF,
    'cnP5OAeSjPY': {'ja': '作曲・演奏：星勝', 'en': 'Composition & guitar: Katz Hoshi', 'zh-Hans': '作曲・演奏：星胜', 'es': 'Composición y guitarra: Katz Hoshi', 'ko': '작곡・연주: 호시 카츠'},
    'mqlqEb22EUA': ARR,
    'PGkM8FDFsJI': {'ja': '編曲：星勝、ニック・ハリソン', 'en': 'Arrangement: Katz Hoshi, Nick Harrison', 'zh-Hans': '编曲：星胜、Nick Harrison', 'es': 'Arreglos: Katz Hoshi, Nick Harrison', 'ko': '편곡: 호시 카츠, 닉 해리슨'},
    '4YM9lH_82vU': {'ja': 'プロデュース：星勝（アルバム『二色の独楽』）', 'en': 'Producer: Katz Hoshi (album Nishoku no Koma)', 'zh-Hans': '制作人：星胜（专辑《二色的陀螺》）', 'es': 'Producción: Katz Hoshi (álbum Nishoku no Koma)', 'ko': '프로듀스: 호시 카츠 (앨범 『二色の独楽』)'},
    '42vMJqDngVg': {'ja': '編曲：小野崎孝輔、星勝', 'en': 'Arrangement: Kosuke Onozaki, Katz Hoshi', 'zh-Hans': '编曲：小野崎孝辅、星胜', 'es': 'Arreglos: Kosuke Onozaki, Katz Hoshi', 'ko': '편곡: 오노자키 고스케, 호시 카츠'},
    'Pn75eje0b8k': ARR,
    'e6oHTWcA4YA': {'ja': '編曲：星勝、RCサクセション', 'en': 'Arrangement: Katz Hoshi, RC Succession', 'zh-Hans': '编曲：星胜、RC Succession', 'es': 'Arreglos: Katz Hoshi, RC Succession', 'ko': '편곡: 호시 카츠, RC 석세션'},
    'KgVkLLwUP18': ARR, 'ueF5Lc0oVKQ': ARR, 'w2UzVC9fYhQ': ARR, 'hEyxari6i-g': ARR,
    'N7w2qGktIFU': {'ja': 'プロデュース・編曲：星勝', 'en': 'Producer & arrangement: Katz Hoshi', 'zh-Hans': '制作・编曲：星胜', 'es': 'Producción y arreglos: Katz Hoshi', 'ko': '프로듀스・편곡: 호시 카츠'},
    'VKQQruBxWMM': ARR,
    'tGzS70EnrEE': {'ja': '編曲：星勝（1992年版）', 'en': 'Arrangement: Katz Hoshi (1992 version)', 'zh-Hans': '编曲：星胜（1992年版）', 'es': 'Arreglos: Katz Hoshi (versión de 1992)', 'ko': '편곡: 호시 카츠 (1992년판)'},
    'yK1HlQD34mU': {'ja': '星勝を紹介するテレビ番組', 'en': 'A TV segment introducing Katz Hoshi', 'zh-Hans': '介绍星胜的电视节目', 'es': 'Programa de TV que presenta a Katz Hoshi', 'ko': '호시 카츠를 소개하는 TV 프로그램'},
    'viIw3G2bw6I': ARR, 'BMatWYmur_M': ARR, 'mOQE4GN7Pl8': ARR, 'am9FcU6qhLk': ARR,
}
REMOVE = ['i5U93W19Ays', 'HAh_Z4Uq0UM', 'dgT4nU34uOE', 'qIKvTmMrtl8', 'cAVnxFszvKo']


def fig_of(yt):
    b = s.select_one(f'[data-yt-cover="{yt}"]')
    return b.find_parent('figure') if b else None


# ch11：浜田省吾（1992年版・編曲 星勝）を主役に。森恵とKing Gnuは外す
main11 = s.select_one('#ch11 .cw-main')
ham = fig_of('tGzS70EnrEE')
ham.extract()
ham['class'] = ['cw-video', 'cw-video--main']
img = ham.select_one('img'); img['src'] = img['src'].replace('hqdefault', 'maxresdefault')
main11.clear(); main11.append(ham)

for yt in REMOVE:
    f = fig_of(yt)
    if f: f.decompose()
# 中身が空になった「聴きくらべ」は見出しごと外す
for g in s.select('.cw-more__grid'):
    if not g.select('figure'):
        lab = g.find_previous_sibling(class_='cw-more__label')
        if lab: lab.decompose()
        g.decompose()

# 各曲の「星勝が何をしたか」（キャプションの位置・同じ表記）
for f in s.select('figure.cw-video'):
    b = f.select_one('[data-yt-cover]')
    if not b: continue
    c = CREDIT.get(b['data-yt-cover'])
    if not c: continue
    cap = f.select_one('.cw-video__cap')
    if cap is None:
        cap = s.new_tag('span', attrs={'class': 'cw-video__cap'}); f.select_one('figcaption').append(cap)
    cap.string = c['ja']
    k = cap.get('data-i18n')
    if k: settr(k, c)

# ch11 の文
def setp(key, ja, d):
    el = s.select_one(f'[data-i18n="{key}"]'); el.clear(); el.append(BeautifulSoup(ja, 'html.parser')); settr(key, d)

WY = 'https://ja.wikipedia.org/wiki/%E6%82%B2%E3%81%97%E3%81%BF%E3%81%AF%E9%9B%AA%E3%81%AE%E3%82%88%E3%81%86%E3%81%AB'
A = f'<a class="cw-src" href="{WY}" rel="noopener" target="_blank">Wikipedia — 悲しみは雪のように</a>'
setp('k91', '11年後に、もう一度降った雪', {'en': 'The snow that fell again, eleven years later', 'zh-Hans': '十一年后，又下了一场雪', 'es': 'La nieve que volvió a caer once años después', 'ko': '11년 뒤, 다시 내린 눈'})
setp('k12', '浜田省吾 - 悲しみは雪のように', {'en': 'Shogo Hamada - Kanashimi wa Yuki no You ni', 'zh-Hans': '滨田省吾 - 悲伤如雪', 'es': 'Shogo Hamada - Kanashimi wa Yuki no You ni', 'ko': '하마다 쇼고 - 슬픔은 눈처럼'})
yr = s.select_one('#ch11 .cw-chead__year'); yr.string = '1992'
setp('k92', f'もとは1981年の曲。1992年、フジテレビのドラマ『愛という名のもとに』の主題歌になったのをきっかけに、アレンジを大きく変えて録り直し、シングルで出し直した{A}。',
     {'en': 'It was originally a 1981 song. In 1992, when it became the theme of the Fuji TV drama <i>Ai to Iu Na no Moto ni</i>, it was re-recorded with a completely new arrangement and released again as a single[[1]].',
      'zh-Hans': '原本是1981年的歌。1992年成为富士电视台日剧《以爱为名》的主题曲，借此大幅改编重录，重新发行单曲[[1]]。',
      'es': 'Era una canción de 1981. En 1992, al convertirse en el tema del drama de Fuji TV <i>Ai to Iu Na no Moto ni</i>, se volvió a grabar con un arreglo totalmente nuevo y salió otra vez como sencillo[[1]].',
      'ko': '원래는 1981년 곡이다. 1992년 후지TV 드라마 『사랑이라는 이름 아래』의 주제가가 되면서 편곡을 크게 바꿔 다시 녹음하고, 싱글로 새로 냈다[[1]].'})
setp('k93', f'イントロはポリスの「見つめていたい」に似ていると言われる。でも浜田省吾の頭にあったのは、ジュード・コールというアーティストの曲だった。その曲を星勝に聴かせて「こういう感じにしたい」と頼んだ。結果は、浜田のシングルで過去最大のヒットになった{A}。',
     {'en': 'People say the intro sounds like the Police\'s "Every Breath You Take." But what Hamada actually had in mind was a song by an artist named Jude Cole. He played it for Katz Hoshi and said, "I want it to feel like this." It became the biggest hit single of Hamada\'s career[[1]].',
      'zh-Hans': '有人说前奏像The Police的《Every Breath You Take》。但滨田心里想的，其实是一位叫Jude Cole的歌手的歌。他把那首歌放给星胜听，说“想要这种感觉”。结果成了滨田历来最大的热门单曲[[1]]。',
      'es': 'Dicen que la intro se parece a «Every Breath You Take» de The Police. Pero lo que Hamada tenía en la cabeza era una canción de un artista llamado Jude Cole. Se la puso a Katz Hoshi y le dijo: «Quiero que suene así». Acabó siendo el sencillo más vendido de toda su carrera[[1]].',
      'ko': '인트로가 폴리스의 「Every Breath You Take」와 닮았다는 말이 있다. 하지만 하마다 쇼고가 떠올린 건 주드 콜이라는 아티스트의 곡이었다. 그 곡을 호시 카츠에게 들려주며 “이런 느낌으로 하고 싶다”고 부탁했다. 결과는 하마다의 싱글 사상 최대의 히트였다[[1]].'})
# ch10 の「聴きくらべ」見出しとつなぎ
setp('k89', 'もう1曲 — 星勝の編曲', {'en': 'One more — arranged by Katz Hoshi', 'zh-Hans': '再来一首 — 星胜编曲', 'es': 'Una más — con arreglos de Katz Hoshi', 'ko': '한 곡 더 — 호시 카츠 편곡'})
setp('k90', '最後は1992年。11年前の歌が、星勝の手でもう一度生まれ変わる。', {'en': 'Last stop: 1992. A song from eleven years earlier is reborn in Katz Hoshi\'s hands.', 'zh-Hans': '最后是1992年。一首十一年前的歌，在星胜手中重生。', 'es': 'Última parada: 1992. Una canción de once años antes renace en manos de Katz Hoshi.', 'ko': '마지막은 1992년. 11년 전의 노래가 호시 카츠의 손에서 다시 태어난다.'})
# 目次の11章
li = s.select_one('.cw-toc__grid a[href="#ch11"]')
li.select_one('img')['src'] = 'https://i.ytimg.com/vi/tGzS70EnrEE/mqdefault.jpg'
sp = li.select_one('span'); sp.string = '悲しみは雪のように'
if sp.get('data-i18n'): settr(sp['data-i18n'], {'en': 'Kanashimi wa Yuki no You ni', 'zh-Hans': '悲伤如雪', 'es': 'Kanashimi wa Yuki no You ni', 'ko': '슬픔은 눈처럼'})

out = str(s)
out = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', out)
out = MB.unify_look(out)
for p in (SRC, os.path.join(R, 'status/magazine_prod/kimi-wa-hoshi-katsu.html')):
    open(p, 'w', encoding='utf-8').write(out)
json.dump(tr, open(TRP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
t = json.dumps(dict(tr, **{l: dict(tr[l], **MB.common_i18n()[l]) for l in L4}), ensure_ascii=False, separators=(',', ':'))
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, 'kimi-wa-hoshi-katsu.i18n.json'), 'w', encoding='utf-8').write(t)
left = [yt for yt in REMOVE if yt in out]
print('removed-left', left, 'credits', sum(1 for f in s.select('figure.cw-video') if f.select_one('.cw-video__cap')), MB.look_check(out))
