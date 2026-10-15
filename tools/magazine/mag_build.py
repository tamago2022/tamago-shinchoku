# シティポップ特集（/feature/citypop-sekai）の実ページのHTML・CSSを複製して、中身だけ差し替える（2026-10-14）
# 使い方: python3 tools/magazine/spec_ikareru.py（各マガジンの中身＝spec_*.py、型＝mag_build.py。型はシティポップ特集の実ページ tools/magazine/cw_inline.css（シティポップ特集の実ページから抜いた style の複製））
import html as H
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CW_CSS = open(os.path.join(REPO, 'tools/magazine/cw_inline.css'), encoding='utf-8').read()
AVATAR = 'assets/owner/x-avatar.jpg'
import json as _json
try:
    SONG_PAGES = _json.load(open(os.path.join(REPO, 'tools/magazine/song_pages.json'), encoding='utf-8'))['pages']
except Exception:
    SONG_PAGES = {}
BASE = 'https://joy-relief-station.lovable.app/magazine/'  # 本番（ごきげん補給所 public/magazine/）
PAGES_BASE = 'https://tamago2022.github.io/tamago-shinchoku/share/check/'
OTHERS = {
    'josh': (BASE + 'hikigatari-josh-turner.html', 'はっぴいえんど「風をあつめて」から', '弾き語り・ジョシュ・ターナー編'),
    'takoukan': (BASE + 'naze-ongaku-01-takoukan.html', '人はなぜ音楽を聴くのか 第1回', '楽しくなりたいから ― 多幸感ポップス'),
    'ikareru': (BASE + 'ikareru-01.html', 'ロック企画 vol.1', '怒れる人々'),
    'harakami': (BASE + 'rei-harakami.html', 'rei harakami／yanokami', '君はレイ・ハラカミを知っているか'),
    'hikigatari': ('https://joy-relief-station.lovable.app/feature/hikigatari', 'ピアノ、ギター、声ひとつ', '心を震わせる弾き語り'),
    'citypop': ('https://joy-relief-station.lovable.app/feature/citypop-sekai', 'City Pop × World', '世界が先に見つけた、日本の夜。'),
}
PROD = {'josh': 'hikigatari-josh-turner.html', 'takoukan': 'naze-ongaku-01-takoukan.html', 'ikareru': 'ikareru-01.html', 'harakami': 'rei-harakami.html'}
PLAY = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5.5v13l11-6.5z"></path></svg>'
# 吹き出しと「つなぎ」だけは、このシリーズの決まり（CLAUDE.md）で要る部品。元の型の色・字に合わせる
EXTRA_CSS = '''
.cw .say{display:flex;gap:14px;align-items:flex-start;margin:36px 0 0;max-width:640px}
.cw .say__ic{flex:0 0 48px;width:48px;height:48px;border-radius:50%;overflow:hidden;background:#f3e6d6;box-shadow:0 0 0 2px var(--red)}
.cw .say__ic img{width:100%;height:100%;object-fit:cover}
.cw .say__bub{background:rgba(237,230,214,.08);border-radius:4px 16px 16px 16px;padding:12px 16px;font:500 15px/1.8 "Hiragino Sans","Yu Gothic",sans-serif}
.cw .cw-chapter--paper .say__bub{background:rgba(29,37,54,.07)}
.cw .bridge{margin:2.2em 0 0;padding-top:1.4em;border-top:1px solid var(--line);font-size:14.5px;color:var(--mute)}
.cw .cw-chapter--paper .bridge{color:var(--paper-mute);border-color:rgba(29,37,54,.16)}
'''
SCRIPT = '''<script>
document.querySelectorAll('.cw-video__cover[data-yt-cover]').forEach(function(b){
  var img=b.querySelector('img');
  if(img){img.addEventListener('load',function(){if(img.naturalWidth>0&&img.naturalWidth<=200&&!img.dataset.fb){img.dataset.fb=1;img.src='https://i.ytimg.com/vi/'+b.dataset.ytCover+'/hqdefault.jpg';}});
          img.addEventListener('error',function(){if(!img.dataset.fb){img.dataset.fb=1;img.src='https://i.ytimg.com/vi/'+b.dataset.ytCover+'/hqdefault.jpg';}});}
  b.addEventListener('click',function(){var f=b.parentNode;f.innerHTML='<iframe src="https://www.youtube-nocookie.com/embed/'+b.dataset.ytCover+'?autoplay=1&playsinline=1" title="'+(b.getAttribute('aria-label')||'')+'" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>';});
});
</script>'''


def e(t):
    return H.escape(t, quote=True)


def src(label, url):
    return f'<a class="cw-src" href="{e(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'


def video(v, size='main'):
    v = dict(v); v.setdefault('page', SONG_PAGES.get(v['id']))
    q = 'maxresdefault' if size == 'main' else 'hqdefault'
    return (f'<figure class="cw-video cw-video--{size}"><div class="cw-video__frame"><button type="button" class="cw-video__cover" '
            f'data-yt-cover="{v["id"]}" aria-label="ここで再生：{e(v["artist"])}「{e(v["song"])}」"><img src="https://i.ytimg.com/vi/{v["id"]}/{q}.jpg" alt="" loading="lazy" decoding="async"/>'
            f'<span class="cw-video__role">{e(v["role"])}</span><span class="cw-video__play" aria-hidden="true">{PLAY}</span></button></div>'
            f'<figcaption><span class="cw-video__name"><b>{e(v["artist"])}</b><i>「{e(v["song"])}」</i></span><span class="cw-video__cap">{v["cap"]}</span>'
            + (f'<a href="{e(v["page"])}" class="cw-video__page">この曲のページへ →</a>' if v.get("page") else '') + '</figcaption></figure>')


def say(t):
    return f'<div class="say"><div class="say__ic"><img src="{AVATAR}" alt="" loading="lazy"/></div><div class="say__bub">{t}</div></div>'


def chapter(c, paper=False):
    parts = [f'<header class="cw-chead"><span class="cw-chead__no" aria-hidden="true">{c["no"]}</span><div><p class="cw-chead__en">{e(c["en"])}</p>'
             f'<h2 class="cw-chead__title">{e(c["title"])}</h2><p class="cw-chead__year">{e(c["year"])}</p></div></header>',
             f'<div class="cw-main">{video(c["main"])}</div>',
             '<div class="cw-body" style="margin-top:40px">' + ''.join(f'<p>{p}</p>' for p in c['body']) + '</div>']
    if c.get('pull'):
        parts.append(f'<blockquote class="cw-pull">{c["pull"]}</blockquote>')
    if c.get('more'):
        parts.append(f'<p class="cw-more__label">{e(c["more_label"])}</p><div class="cw-more__grid">' + ''.join(video(v, 'small') for v in c['more']) + '</div>')
    if c.get('say'):
        parts.append(say(c['say']))
    if c.get('bridge'):
        parts.append(f'<p class="bridge">{c["bridge"]}</p>')
    cls = 'cw-chapter cw-chapter--paper' if paper else 'cw-chapter'
    return f'<section class="{cls}" id="ch{c["no"]}"><div class="cw-wrap">' + ''.join(parts) + '</div></section>'


# 参考動画コーナー（全マガジン共通の末尾・Genspark手紙 issue#7 の決まり6・2026-10-15）
REF = [dict(id='hmGwwZ5hjbI', role='きっかけの動画', artist='汝、ヒトを知れ', song='なぜ、大人になると新しい曲を聴かなくなるのか【鳥類学×音楽心理学】', cap='歌を覚える季節は終わらない')]


def ref_section(m):
    r = m.get('ref', REF)
    if not r:
        return ''
    return ('<section class="cw-ref" aria-label="参考動画" style="margin-top:56px"><p class="cw-more__label">参考動画 — この記事を書くきっかけになった動画</p>'
            '<div class="cw-more__grid">' + ''.join(video(v, 'small') for v in r) + '</div></section>')


def build(m):
    toc = ''.join(f'<li><a href="#ch{c["no"]}"><img src="https://i.ytimg.com/vi/{c["main"]["id"]}/mqdefault.jpg" alt="" loading="lazy" decoding="async"/><b>CHAPTER {c["no"]}</b><span>{e(c["main"]["song"])}</span></a></li>' for c in m['chapters'])
    chs = ''.join(chapter(c, paper=(i in m.get('paper', []))) for i, c in enumerate(m['chapters']))
    allv = []
    for c in m['chapters']:
        allv.append(c['main'])
        allv += c.get('more', [])
    mp = ''.join(f'<li><a href="{e(v.get("page") or SONG_PAGES.get(v["id"]) or ("#ch" + c["no"]))}"><span class="cw-map__img"><img src="https://i.ytimg.com/vi/{v["id"]}/mqdefault.jpg" alt="" loading="lazy" decoding="async"/><em>{i:02d}</em></span>'
                 f'<span class="cw-map__txt" data-card-face="" data-card-music="1"><small data-card-genre="">{e(v["role"])}</small><b data-card-heading="">{e(v["artist"])}「{e(v["song"])}」</b><i data-card-desc="">{v["cap"]}</i></span></a></li>'
                 for i, (c, v) in enumerate(((c, v) for c in m['chapters'] for v in [c['main']] + c.get('more', [])), 1))
    others = ''.join(f'<li><a href="{e(OTHERS[k][0])}"><small>{e(OTHERS[k][1])}</small><b>{e(OTHERS[k][2])}</b><span aria-hidden="true">→</span></a></li>' for k in OTHERS if k != m['key'])
    srcs = ''.join(f'<li><a href="{e(u)}" target="_blank" rel="noopener noreferrer">{e(l)}</a></li>' for l, u in m['sources'])
    hero = m['hero']
    return f'''<!DOCTYPE html><!-- tamago-dark 2 （GitHub Pages の暗くする機械に触らせない：シティポップ特集の型そのままの配色） --><html lang="ja"><head><meta charSet="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><meta name="robots" content="noindex"/><meta name="tamago-magazine" content="story"/>
<link rel="preload" as="image" href="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg"/><link rel="stylesheet" href="assets/cw/styles.css"/><title>{e(m["title"])}｜ごきげん補給所</title><meta name="theme-color" content="#faf5ec"/><meta name="description" content="{e(m["desc"])}"/><meta property="og:type" content="article"/><meta property="og:site_name" content="ごきげん補給所"/><meta property="og:title" content="{e(m["title"])}"/><meta property="og:description" content="{e(m["desc"])}"/><meta property="og:url" content="{BASE}{PROD[m["key"]]}"/><link rel="canonical" href="{BASE}{PROD[m["key"]]}"/><meta property="og:image" content="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg"/><meta property="og:image:width" content="1280"/><meta property="og:image:height" content="720"/><meta name="twitter:card" content="summary_large_image"/><meta name="twitter:title" content="{e(m["title"])}"/><meta name="twitter:description" content="{e(m["desc"])}"/><meta name="twitter:image" content="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg"/></head><body><div class="min-h-[100svh] w-full"><main class="cw" lang="ja"><style>{CW_CSS}{EXTRA_CSS}</style>
<header class="cw-hero"><div class="cw-hero__bg" aria-hidden="true"><img src="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg" alt="" decoding="async"/></div><nav class="cw-nav" aria-label="ページ上部"><a href="https://joy-relief-station.lovable.app/">ごきげん補給所</a><span>Magazine Story</span></nav><div class="cw-hero__body"><p class="cw-eyebrow">{e(m["eyebrow"])}</p><h1 class="cw-hero__title">{m["h1"]}</h1><p class="cw-hero__lead">{m["lead"]}</p><div class="cw-hero__rule"></div></div></header>
<div class="cw-wrap"><section class="cw-toc" aria-label="この特集の章"><p class="cw-toc__label">IN THIS ISSUE</p><ul class="cw-toc__grid">{toc}</ul></section><section class="cw-open"><p class="cw-big">{m["big"]}</p>{"".join(f"<p>{p}</p>" for p in m["open"])}{('<p class="cw-door">' + m["door"] + '</p>') if m.get("door") else ""}</section></div>
{chs}
<div class="cw-wrap"><section class="cw-close">{"".join(f"<p>{p}</p>" for p in m["close"])}</section>{ref_section(m)}<section class="cw-other" aria-label="ほかの特集"><p class="cw-toc__label">OTHER MAGAZINES — ほかの特集</p><ul class="cw-other__grid">{others}</ul></section><section class="cw-mapwrap" aria-label="曲の一覧"><p class="cw-toc__label">THE MAP — {m.get("songs_n", len(allv))} SONGS</p><ol class="cw-map">{mp}</ol></section><section class="cw-sources" aria-label="出典"><h3>SOURCES</h3><ul>{srcs}</ul><p class="cw-note">{m["note"]}</p></section></div></main></div>
{SCRIPT}
</body></html>'''


def write(m):
    """確認ページ（share/check）と、本番に置く写し（status/magazine_prod/<PRODの名前>）の両方を書く。
    本番の写しは joy-relief-station の public/magazine/ にそのまま置く（assets も同じ相対の場所）。"""
    h = build(m)
    p = os.path.join(REPO, 'share/check', m['file'])
    open(p, 'w', encoding='utf-8').write(h)
    d = os.path.join(REPO, 'status/magazine_prod')
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, PROD[m['key']]), 'w', encoding='utf-8').write(h)
    return p
