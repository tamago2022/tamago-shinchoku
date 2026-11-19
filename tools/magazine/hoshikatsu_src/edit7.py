# -*- coding: utf-8 -*-
# 2026-10-16 未明：終わりの流れ（本文 → 坂崎さんの動画と余韻 → きっかけの動画 → 出典 → ほかの特集）
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
close = soup.find('section', class_='cw-close')
for k in ('k97', 'k98', 'k99'):
    e = close.find(attrs={'data-i18n': k})
    if e is not None:
        e.decompose()
PLAY = MB.PLAY
SZ = ('<p data-i18n="h_sz">星勝さんのことを、坂崎幸之助さんがテレビで紹介している映像が、一般の方の投稿で残っている。</p>'
      '<figure class="cw-video cw-video--small"><div class="cw-video__frame"><button type="button" class="cw-video__cover" data-yt-cover="yK1HlQD34mU" aria-label="ここで再生：坂崎幸之助（テレビ番組）">'
      '<img src="https://i.ytimg.com/vi/yK1HlQD34mU/hqdefault.jpg" alt="" loading="lazy" decoding="async"/><span class="cw-video__role" data-i18n="k136">星勝を知るための動画</span>'
      f'<span class="cw-video__play" aria-hidden="true">{PLAY}</span></button></div><figcaption><span class="cw-video__name"><b data-i18n="k159">坂崎幸之助（テレビ番組）</b>'
      '<i data-i18n="k183">「坂崎幸之助が星勝さんを紹介！井上陽水や小椋佳とも深いつながりが！」</i></span><span class="cw-video__cap" data-i18n="k130">一般投稿・10年前から残る</span></figcaption></figure>'
      '<p data-i18n="h_yoin1">名前を知らなくても、あなたはこの人の音を耳にしているかもしれない。</p>'
      '<p data-i18n="h_yoin2">知らなかったら、今日からでいい。日本の音楽の裏舞台を支えた編曲家を、今から辿ってみてはどうだろう。</p>')
close.append(BeautifulSoup(SZ, 'html.parser'))
NEWT = {
 'h_sz': ('There is footage — posted by a fan — of Konosuke Sakazaki introducing Katz Hoshi on television.', '有一段影像，是坂崎幸之助在电视上介绍星胜的，由网友上传保存了下来。', 'Hay unas imágenes, subidas por un fan, en las que Konosuke Sakazaki presenta a Katz Hoshi en televisión.', '사카자키 고노스케가 TV에서 호시 카츠를 소개하는 영상이, 일반인의 업로드로 남아 있다.'),
 'h_yoin1': ('You may not know his name — but you may well have heard his sound.', '就算不知道他的名字，你或许也听过他的声音。', 'Quizá no sepas su nombre, pero puede que hayas oído su sonido.', '이름은 몰라도, 당신은 이 사람의 소리를 들은 적이 있을지도 모른다.'),
 'h_yoin2': ('If you didn\'t know him, today is a fine place to start. Why not trace, from here, the arranger who held up the backstage of Japanese music?', '如果不知道，从今天开始也不晚。何不从现在起，去追寻那位支撑日本音乐幕后的编曲家？', 'Si no lo conocías, hoy es un buen día para empezar. ¿Por qué no seguir, desde aquí, el rastro del arreglista que sostuvo la trastienda de la música japonesa?', '몰랐다면 오늘부터면 된다. 일본 음악의 무대 뒤를 떠받친 편곡가를, 지금부터 따라가 보는 건 어떨까.'),
}
for k, v in NEWT.items():
    for l, t in zip(LG, v):
        TR.setdefault(l, {})[k] = t
# 共通部品の訳も入れる
for l, d in MB.common_i18n().items():
    TR.setdefault(l, {}).update(d)
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
