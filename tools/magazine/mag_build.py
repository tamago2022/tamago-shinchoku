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
    'ikareru': (BASE + 'ikareru-01.html', 'シリーズ 怒れる人々 vol.1', '〜ロックは死んだのか〜'),
    'harakami': (BASE + 'rei-harakami.html', 'rei harakami／yanokami', '君はレイ・ハラカミを知っているか'),
    'hikigatari': ('https://joy-relief-station.lovable.app/feature/hikigatari', 'ピアノ、ギター、声ひとつ', '心を震わせる弾き語り'),
    'hoshikatsu': (BASE + 'kimi-wa-hoshi-katsu.html', '編曲家・作曲家', '君は星勝を知っているか'),
    'citypop': ('https://joy-relief-station.lovable.app/feature/citypop-sekai', 'City Pop × World', '世界が先に見つけた、日本の夜。'),
}
PROD = {'josh': 'hikigatari-josh-turner.html', 'takoukan': 'naze-ongaku-01-takoukan.html', 'ikareru': 'ikareru-01.html', 'harakami': 'rei-harakami.html', 'hoshikatsu': 'kimi-wa-hoshi-katsu.html'}
PLAY = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5.5v13l11-6.5z"></path></svg>'
# 吹き出しと「つなぎ」だけは、このシリーズの決まり（CLAUDE.md）で要る部品。元の型の色・字に合わせる
EXTRA_CSS = '''
.cw .say{display:flex;gap:14px;align-items:flex-start;margin:36px 0 0;max-width:640px}
.cw .say__ic{flex:0 0 48px;width:48px;height:48px;border-radius:50%;overflow:hidden;background:#f3e6d6;box-shadow:0 0 0 2px var(--red)}
.cw .say__ic img{width:100%;height:100%;object-fit:cover}
.cw .say__bub{background:rgba(237,230,214,.08);border-radius:4px 16px 16px 16px;padding:12px 16px;font:500 15px/1.8 "Hiragino Sans","Yu Gothic",sans-serif}
.cw .cw-chapter--paper .say__bub{background:rgba(29,37,54,.07)}
.cw .cw-chead__catch{font:700 clamp(24px,6.6vw,40px)/1.4 "Hiragino Mincho ProN","Yu Mincho",serif;letter-spacing:.04em;margin:18px 0 0}
.cw a.cw-inl{color:inherit;text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:1px}
.cw .cw-interlude{padding:48px 0}.cw .cw-interlude figure{margin:0 auto 28px;max-width:760px}.cw .cw-interlude img{display:block;width:100%;height:auto;border-radius:4px;filter:sepia(.12)}.cw .cw-interlude figcaption{margin-top:10px;font-size:13px;line-height:1.7;color:var(--mute)}.cw .cw-interlude .cw-credit{font-size:11.5px;opacity:.8}.cw .cw-interlude figcaption a{color:inherit;text-decoration:underline}
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
            f'<figcaption><span class="cw-video__name"><b>{e(v["artist"])}</b><i>「{e(v["song"])}」</i></span>' + (f'<span class="cw-video__cap">{v["cap"]}</span>' if v.get("cap") else '')
            + (f'<a href="{e(v["page"])}" class="cw-video__page">この曲のページへ →</a>' if v.get("page") else '') + '</figcaption></figure>')


def say(t):
    return f'<div class="say"><div class="say__ic"><img src="{AVATAR}" alt="" loading="lazy"/></div><div class="say__bub">{t}</div></div>'


def chead(c):
    """各章の頭（全マガジン共通の型・2026-10-16 たまごさん指示）：
    1行目 アーティスト名／曲タイトル（今の見出しの文字サイズ）→ 2行目 アルバム／年（小さく）→ 見出し＝その曲を一発で表すキャッチーな一言。
    spec では artist / song / album / year / catch を書く。古い spec（en / title / year）も同じ並びに読み替える。"""
    if c.get('artist'):
        meta1 = f'{c["artist"]} ／ {c["song"]}'
        meta2 = ' ／ '.join(x for x in [c.get('album', ''), c.get('year', '')] if x)
    else:
        meta1, meta2 = c['title'].replace(' - ', ' ／ ', 1), c.get('year', '')
    catch = c.get('catch') or c.get('en', '')
    return (f'<header class="cw-chead"><span class="cw-chead__no" aria-hidden="true">{c["no"]}</span><div>'
            f'<p class="cw-chead__title">{e(meta1)}</p>' + (f'<p class="cw-chead__year">{e(meta2)}</p>' if meta2 else '')
            + (f'<h2 class="cw-chead__catch">{e(catch)}</h2>' if catch else '') + '</div></header>')


def interlude(ph):
    """章の合間の写真（全マガジン共通・2026-10-16）。時代の空気を伝える自由ライセンス写真だけ（Wikimedia Commons 等、CC BY / BY-SA / CC0 / PD）。
    主役は曲と記事。写真はわさび・大葉。クレジット（撮影者・ライセンス・元ページ）を必ず付ける。
    ph = dict(src, w, h, alt, cap, credit, page, lic)"""
    return ('<section class="cw-interlude" aria-label="写真"><div class="cw-wrap">' + ''.join(
        f'<figure><img src="{e(x["src"])}" width="{x["w"]}" height="{x["h"]}" alt="{e(x["alt"])}" loading="lazy" decoding="async"/>'
        f'<figcaption>{x["cap"]}<br/><span class="cw-credit">写真：<a href="{e(x["page"])}" target="_blank" rel="noopener">{e(x["credit"])}</a>（{e(x["lic"])}）</span></figcaption></figure>'
        for x in ph) + '</div></section>')


def chapter(c, paper=False):
    parts = [chead(c),
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
    return f'<section class="{cls}" id="ch{c["no"]}"><div class="cw-wrap">' + ''.join(parts) + '</div></section>' + (interlude(c['after']) if c.get('after') else '')


# 参考動画コーナー（全マガジン共通の末尾・Genspark手紙 issue#7 の決まり6・2026-10-15）
REF = [dict(id='hmGwwZ5hjbI', role='最後にもう1本', artist='汝、ヒトを知れ', song='なぜ、大人になると新しい曲を聴かなくなるのか【鳥類学×音楽心理学】', cap='')]


def ref_section(m):
    r = m.get('ref', REF)
    if not r:
        return ''
    return ('<section class="cw-ref" aria-label="参考動画" style="margin-top:56px"><p class="cw-more__label">最後にもう1本 — なぜ、大人になると新しい曲を聴かなくなるのか</p>'
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
    others = ''.join(f'<li><a href="{e(OTHERS[k][0])}"><small>{e(OTHERS[k][1])}</small><b>{e(OTHERS[k][2])}</b><span aria-hidden="true">→</span></a></li>' for k in OTHERS if k != m['key'] and k not in m.get('others_skip', []))
    srcs = ''.join(f'<li><a href="{e(u)}" target="_blank" rel="noopener noreferrer">{e(l)}</a></li>' for l, u in m['sources'])
    hero = m['hero']
    return f'''<!DOCTYPE html><!-- tamago-dark 2 （GitHub Pages の暗くする機械に触らせない：シティポップ特集の型そのままの配色） --><html lang="ja"><head><meta charSet="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><meta name="robots" content="noindex"/><meta name="tamago-magazine" content="story"/>
<link rel="preload" as="image" href="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg"/><link rel="stylesheet" href="assets/cw/styles.css"/><title>{e(m["title"])}｜ごきげん補給所</title><meta name="theme-color" content="#faf5ec"/><meta name="description" content="{e(m["desc"])}"/><meta property="og:type" content="article"/><meta property="og:site_name" content="ごきげん補給所"/><meta property="og:title" content="{e(m["title"])}"/><meta property="og:description" content="{e(m["desc"])}"/><meta property="og:url" content="{BASE}{PROD[m["key"]]}"/><link rel="canonical" href="{BASE}{PROD[m["key"]]}"/><meta property="og:image" content="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg"/><meta property="og:image:width" content="1280"/><meta property="og:image:height" content="720"/><meta name="twitter:card" content="summary_large_image"/><meta name="twitter:title" content="{e(m["title"])}"/><meta name="twitter:description" content="{e(m["desc"])}"/><meta name="twitter:image" content="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg"/></head><body><div class="min-h-[100svh] w-full"><main class="cw" lang="ja"><style>{CW_CSS}{EXTRA_CSS}</style>
<header class="cw-hero"><div class="cw-hero__bg" aria-hidden="true"><img src="https://i.ytimg.com/vi/{hero}/maxresdefault.jpg" alt="" decoding="async"/></div><nav class="cw-nav" aria-label="ページ上部"><a href="https://joy-relief-station.lovable.app/">ごきげん補給所</a><span>Magazine Story</span></nav><div class="cw-hero__body"><p class="cw-eyebrow">{e(m["eyebrow"])}</p><h1 class="cw-hero__title">{m["h1"]}</h1><p class="cw-hero__lead">{m["lead"]}</p><div class="cw-hero__rule"></div></div></header>
<div class="cw-wrap"><section class="cw-toc" aria-label="この特集の章"><p class="cw-toc__label">IN THIS ISSUE</p><ul class="cw-toc__grid">{toc}</ul></section><section class="cw-open"><p class="cw-big">{m["big"]}</p>{"".join(f"<p>{p}</p>" for p in m["open"])}{('<p class="cw-door">' + m["door"] + '</p>') if m.get("door") else ""}</section></div>
{chs}
<div class="cw-wrap"><section class="cw-close">{"".join(f"<p>{p}</p>" for p in m["close"])}</section>{ref_section(m)}<section class="cw-other" aria-label="ほかの特集"><p class="cw-toc__label">つながっている特集</p><ul class="cw-other__grid">{others}</ul></section>{('<section class="cw-mapwrap" aria-label="曲の一覧"><p class="cw-toc__label">THE MAP — ' + str(m.get("songs_n", len(allv))) + ' SONGS</p><ol class="cw-map">' + mp + '</ol></section>') if m.get("map", True) else ""}<section class="cw-sources" aria-label="出典"><h3>SOURCES</h3><ul>{srcs}</ul>{('<p class="cw-note">' + m["note"] + '</p>') if m.get("note") else ""}</section></div></main></div>
{SCRIPT}
</body></html>'''


# 読者に出さない「制作側の都合・注記」（2026-10-16 たまごさん指示・全マガジン共通）。見つけたら書き出さずに止まる。
SEISAKU_NG = ['oEmbed', '配信元を確か', '引用していません', '引用してません', '転載', '万再生', '回以上再生', '再生されている', '使っています', '置いています',
              '小さく添え', 'ここに残す', 'メインに置く', 'メインの映像', '旬の姿で見たい', '証言は貴重', '一般の方の投稿', '字幕つき', '字幕付き', '字幕が付い', '字幕がつい']


def kanmon(m, h):
    """出す前の関所（write の中で必ず走る）。①制作側の注記が本文・キャプション・吹き出しに無い ②埋め込みが mute でない。"""
    import re as R
    txt = R.sub(r'<script.*?</script>|<style.*?</style>', '', h, flags=R.S)
    bad = [w for w in SEISAKU_NG if w in txt]
    if bad:
        raise SystemExit('★関所で停止（制作側の注記が読者に見える）：' + '、'.join(bad))
    if R.search(r'[?&]mute=1', h):
        raise SystemExit('★関所で停止：YouTube が mute=1 になっている（音はふつうに出す）')


def write(m):
    """確認ページ（share/check）と、本番に置く写し（status/magazine_prod/<PRODの名前>）の両方を書く。
    本番の写しは joy-relief-station の public/magazine/ にそのまま置く（assets も同じ相対の場所）。"""
    h = build(m)
    kanmon(m, h)
    p = os.path.join(REPO, 'share/check', m['file'])
    open(p, 'w', encoding='utf-8').write(h)
    d = os.path.join(REPO, 'status/magazine_prod')
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, PROD[m['key']]), 'w', encoding='utf-8').write(h)
    return p


# ===== 多言語（全マガジン共通の決まり・2026-10-16 たまごさん指示）=====
# サイト（joy-relief-station src/i18n/config.ts の SUPPORTED_LANGUAGES）と同じ5言語で読めるようにする。
# 仕組みもサイトと同じ：地球マーク＋今の言語（JP/EN…）を押すと端末標準のリストが開く。選択は localStorage "gokigen-lang"（サイトと共有）。
# 訳は spec 側で m['i18n'] = {'en': {'k1': '...'}, 'zh-Hans': {...}, 'es': {...}, 'ko': {...}, '_title': {...}} を渡す。
# キー k1..kN は I18N_SEL の順に「日本語を含む要素」へ振る（python3 tools/magazine/mag_build.py --i18n-keys <html> で一覧が出る）。
# 本文中の出典リンク（a.cw-src）は訳文の [[1]] [[2]] … に元のリンクがそのまま入る。
I18N_LANGS = [('ja', '日本語', 'JP'), ('en', 'English', 'EN'), ('zh-Hans', '中文', 'ZH'), ('es', 'Español', 'ES'), ('ko', '한국어', 'KO')]
I18N_SEL = ['h1', 'h2', 'h3', 'p', 'blockquote', 'figcaption .cw-video__cap', '.cw-video__role', '.cw-video__name b', '.cw-video__name i', 'a.cw-video__page',
            '.cw-toc__grid span', '.cw-map__txt small', '.cw-map__txt b', '.cw-map__txt i', '.cw-other__grid small', '.cw-other__grid b', '.cw-nav span',
            '.cw-interlude figcaption', '.cw-sources li a', '.say__bub']
I18N_CSS = ('.cw .cw-lang{position:relative;display:inline-flex;align-items:center;gap:4px;height:30px;padding:0 8px;border-radius:999px;color:inherit;opacity:.8}'
            '.cw .cw-lang:hover{background:rgba(255,255,255,.1)}.cw .cw-lang b{font:600 11px/1 system-ui,sans-serif;letter-spacing:.06em}'
            '.cw .cw-lang select{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}')
I18N_GLOBE = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'


def i18n_switch():
    opts = ''.join(f'<option value="{c}">{n}</option>' for c, n, _ in I18N_LANGS)
    return f'<label class="cw-lang" title="言語 / Language">{I18N_GLOBE}<b data-lang-code>JP</b><select aria-label="言語 / Language">{opts}</select></label>'


def i18n_script(tr, url=None):
    """tr を埋め込む（url=None）か、日本語以外を選んだときだけ url の JSON を読みに行く（ページを重くしない）。"""
    import json as J
    codes = {c: s for c, _, s in I18N_LANGS}
    data = 'null' if url else J.dumps(tr, ensure_ascii=False).replace('</', '<\\/')
    return ('<script>(function(){var L=' + data + ',U=' + J.dumps(url) + ',C=' + J.dumps(codes) + ',SEL=' + J.dumps(I18N_SEL) + ';'
            'var M=document.querySelector("main.cw");if(!M)return;var els=[],n=0;'
            'if(M.querySelector("[data-i18n]")){els=[].slice.call(M.querySelectorAll("[data-i18n]"));}else{SEL.forEach(function(q){M.querySelectorAll(q).forEach(function(el){'
            'if(el.closest("[data-i18n]"))return;if(!/[\\u3040-\\u30ff\\u4e00-\\u9fff]/.test(el.textContent))return;n++;el.setAttribute("data-i18n","k"+n);els.push(el);});});}'
            'els.forEach(function(el){el._ja=el.innerHTML;});var T0=document.title;'
            'function ap(lg){if(!C[lg])lg="ja";if(lg!=="ja"&&!L&&U){fetch(U).then(function(r){return r.json()}).then(function(d){L=d;ap(lg)}).catch(function(){});return;}'
            'var d=(L&&L[lg])||{};els.forEach(function(el){var v=d[el.getAttribute("data-i18n")];if(lg==="ja"||!v){el.innerHTML=el._ja;return;}'
            'var t=document.createElement("div");t.innerHTML=el._ja;var a=[].map.call(t.querySelectorAll("a.cw-src"),function(x){return x.outerHTML});'
            'el.innerHTML=v.replace(/\\[\\[(\\d+)\\]\\]/g,function(_,i){return a[i-1]||""});});'
            'document.title=(L&&L._title&&L._title[lg])||T0;document.documentElement.lang=lg;M.setAttribute("lang",lg);'
            'document.querySelectorAll("[data-lang-code]").forEach(function(b){b.textContent=C[lg]});document.querySelectorAll(".cw-lang select").forEach(function(s){s.value=lg});}'
            'var q=(location.search.match(/[?&]lang=([\\w-]+)/)||[])[1],s=null;try{s=localStorage.getItem("gokigen-lang")}catch(e){}'
            'ap(q||s||"ja");document.querySelectorAll(".cw-lang select").forEach(function(sel){sel.addEventListener("change",function(){try{localStorage.setItem("gokigen-lang",sel.value)}catch(e){}ap(sel.value);});});'
            '})();</script>')


def add_i18n(h, tr, url=None):
    """組み上がったHTMLに言語切替を入れる（build() が m['i18n'] を見て呼ぶ。直接組んだページにも使える）。
    url を渡すと訳は別ファイル（<本番名>.i18n.json）から、日本語以外を選んだときだけ読む。"""
    h = h.replace('<span>Magazine Story</span></nav>', '<span>Magazine Story</span>' + i18n_switch() + '</nav>', 1)
    h = h.replace('</style>', I18N_CSS + '</style>', 1)
    return h.replace('</body>', i18n_script(tr, url) + '</body>', 1)


def i18n_keys(h):
    """翻訳者向け：キーと日本語の一覧（JSの振り方と同じ順）。bs4 が要る。"""
    import re as R
    from bs4 import BeautifulSoup
    main = BeautifulSoup(h, 'html.parser').find('main')
    out, seen, n = {}, set(), 0
    for q in I18N_SEL:
        for el in main.select(q):
            if id(el) in seen or any(id(a) in seen for a in el.parents):
                continue
            if not R.search(r'[぀-ヿ一-鿿]', el.get_text()):
                continue
            n += 1; seen.add(id(el)); out[f'k{n}'] = el.decode_contents().strip()
    return out


_build_plain = build


def i18n_name(m):
    return PROD[m['key']].replace('.html', '.i18n.json')


def build(m):  # noqa: F811  多言語つき（訳は別ファイル。日本語の読者には1バイトも増やさない）
    h = _build_plain(m)
    if m.get('i18n'):
        h = add_i18n(h, m['i18n'], i18n_name(m))
    return h


_write_plain = write


def write(m):  # noqa: F811  訳のJSONも、確認ページと本番の写しの両方に置く
    p = _write_plain(m)
    if m.get('i18n'):
        import json as J
        t = J.dumps(m['i18n'], ensure_ascii=False, separators=(',', ':'))
        for d in (os.path.join(REPO, 'share/check'), os.path.join(REPO, 'status/magazine_prod')):
            open(os.path.join(d, i18n_name(m)), 'w', encoding='utf-8').write(t)
    return p


if __name__ == '__main__':
    import sys as _s, json as _j
    if len(_s.argv) == 3 and _s.argv[1] == '--i18n-keys':
        print(_j.dumps(i18n_keys(open(_s.argv[2], encoding='utf-8').read()), ensure_ascii=False, indent=1))


# ===== 共通部品：ページの終わり（全マガジン共通の型・2026-10-16 たまごさん確定）=====
# 並び：本文（締め・余韻）→ THE MAP（ある号だけ）→ きっかけの動画（怒れる人々と同じ大きさ＝cw-note の小さい1枚）→ 出典 → ほかの特集（ページの一番下）。
# 「つながっている特集」の欄は置かない。見出しの言い方は「OTHER MAGAZINES — ほかの特集」（シティポップ特集と同じ）に統一。
# 部品はここ1か所。各号は unify_tail() を通すだけ（mag_build で組む号は build() が自動で通す。直接組んだ号もこれで組み直す）。
TAIL_CSS = '.cw .cw-video__play:empty::before{content:"";display:block;margin-left:4px;border-style:solid;border-width:8px 0 8px 13px;border-color:transparent transparent transparent currentColor}.cw .cw-note .cw-video--small{max-width:360px;margin:14px 0 6px}.cw .cw-note .cw-video--small figcaption{font-size:12.5px}.cw .cw-allback{margin:28px 0 0;text-align:right}.cw .cw-allback a{color:inherit;font:500 13px/1.6 "Helvetica Neue",Arial,sans-serif;letter-spacing:.12em;text-decoration:underline;text-underline-offset:4px}'
OTHERS_LABEL = 'OTHER MAGAZINES — ほかの特集'
TAIL_CSS_OLD = ['.cw .cw-note .cw-video--small{max-width:360px;margin:14px 0 6px}.cw .cw-note .cw-video--small figcaption{font-size:12.5px}.cw .cw-allback{margin:28px 0 0;text-align:right}.cw .cw-allback a{color:inherit;font:500 13px/1.6 "Helvetica Neue",Arial,sans-serif;letter-spacing:.12em;text-decoration:underline;text-underline-offset:4px}',
                '.cw .cw-note .cw-video--small{max-width:360px;margin:14px 0 6px}.cw .cw-note .cw-video--small figcaption{font-size:12.5px}']
BACKNUMBER_URL = BASE + 'backnumber.html'  # バックナンバー一覧（全マガジン共通の行き先）
OTHERS['hoshikatsu'] = (BASE + 'kimi-wa-hoshi-katsu.html', '編曲家・作曲家', '君は星勝を知っているか')
OTHERS_ORDER = ['hoshikatsu', 'harakami', 'ikareru', 'takoukan', 'josh', 'hikigatari', 'citypop']
COMMON_I18N = {  # 共通部品の訳（en, zh-Hans, es, ko）
    'c_kk_label': ('▼ The video that started this article', '▼ 促成这篇文章的视频', '▼ El video que dio origen a este artículo', '▼ 이 글을 쓰게 된 계기의 영상'),
    'c_kk_role': ('Where it started', '起因的视频', 'El video que lo empezó', '계기가 된 영상'),
    'c_kk_title': ('"Why do we stop listening to new music as adults? [Ornithology × Music Psychology]" (Nanji, Hito wo Shire)', '《为什么长大后就不再听新歌【鸟类学×音乐心理学】》（汝，知人）', '«¿Por qué de adultos dejamos de escuchar música nueva? [Ornitología × Psicología musical]» (Nanji, Hito wo Shire)', '「왜 어른이 되면 새 노래를 듣지 않게 될까 【조류학×음악심리학】」(너 자신, 인간을 알라)'),
    'c_kk_note': ('"The season for learning songs never ends."', '“学歌的季节永不结束。”', '«La estación de aprender canciones nunca termina».', '\'노래를 익히는 계절은 끝나지 않는다.\''),
    'c_allback': ('All back issues →', '全部往期 →', 'Todos los números →', '모든 백넘버 →'),
    'c_ot_label': ('OTHER MAGAZINES — more features', 'OTHER MAGAZINES — 其他专题', 'OTHER MAGAZINES — más especiales', 'OTHER MAGAZINES — 다른 특집'),
    'c_ot_hoshikatsu_s': ('Arranger / composer', '编曲家・作曲家', 'Arreglista y compositor', '편곡가・작곡가'),
    'c_ot_hoshikatsu_b': ('Do You Know Katz Hoshi?', '你知道星胜吗', '¿Conoces a Katz Hoshi?', '호시 카츠를 아십니까'),
    'c_ot_harakami_b': ('Do You Know Rei Harakami?', '你知道Rei Harakami吗', '¿Conoces a Rei Harakami?', '레이 하라카미를 아십니까'),
    'c_ot_ikareru_s': ('Series: The Angry Ones vol.1', '系列 愤怒的人们 vol.1', 'Serie: La gente enfadada vol.1', '시리즈 분노한 사람들 vol.1'),
    'c_ot_ikareru_b': ('— Is Rock Dead? —', '〜摇滚死了吗〜', '— ¿Ha muerto el rock? —', '〜록은 죽었는가〜'),
    'c_ot_takoukan_s': ('Why do we listen to music? Part 1', '人为什么听音乐 第1回', '¿Por qué escuchamos música? Parte 1', '사람은 왜 음악을 듣는가 제1회'),
    'c_ot_takoukan_b': ('Because we want to feel good — euphoric pop', '因为想变快乐 ― 幸福感流行乐', 'Porque queremos sentirnos bien — pop eufórico', '즐거워지고 싶어서 ― 다행감 팝스'),
    'c_ot_josh_s': ('From Happy End\'s "Kaze wo Atsumete"', '从Happy End《风之聚集》开始', 'Desde «Kaze wo Atsumete» de Happy End', '핫피 엔드 「바람을 모아서」에서'),
    'c_ot_josh_b': ('Singing with an instrument: Josh Turner', '自弹自唱・Josh Turner篇', 'Cantar y tocar: Josh Turner', '弾き語り・조시 터너 편'),
    'c_ot_hikigatari_s': ('A piano, a guitar, a single voice', '一架钢琴、一把吉他、一个声音', 'Un piano, una guitarra, una sola voz', '피아노, 기타, 목소리 하나'),
    'c_ot_hikigatari_b': ('Songs that shake the heart, voice and instrument', '震撼心灵的自弹自唱', 'Canciones que estremecen, voz e instrumento', '마음을 울리는 弾き語り'),
    'c_ot_citypop_b': ('The world found Japan\'s night first.', '世界先发现的，日本之夜。', 'El mundo descubrió primero la noche de Japón.', '세계가 먼저 발견한, 일본의 밤.'),
}
_LG4 = ['en', 'zh-Hans', 'es', 'ko']


def common_i18n():
    out = {l: {} for l in _LG4}
    for k, v in COMMON_I18N.items():
        for l, t in zip(_LG4, v):
            out[l][k] = t
    return out


def kikkake_html():
    return ('<div class="cw-note cw-kikkake"><p data-i18n="c_kk_label">▼この記事を書くきっかけになった動画</p>'
            '<figure class="cw-video cw-video--small"><div class="cw-video__frame"><button type="button" class="cw-video__cover" data-yt-cover="hmGwwZ5hjbI" aria-label="ここで再生：汝、ヒトを知れ「なぜ、大人になると新しい曲を聴かなくなるのか」">'
            '<img src="https://i.ytimg.com/vi/hmGwwZ5hjbI/mqdefault.jpg" alt="" loading="lazy" decoding="async"/><span class="cw-video__role" data-i18n="c_kk_role">きっかけの動画</span>'
            f'<span class="cw-video__play" aria-hidden="true">{PLAY}</span></button></div><figcaption><span class="cw-video__name"><i data-i18n="c_kk_title">「なぜ、大人になると新しい曲を聴かなくなるのか【鳥類学×音楽心理学】」（汝、ヒトを知れ）</i></span></figcaption></figure>'
            '<p data-i18n="c_kk_note">「歌を覚える季節は終わらない」</p></div>')


def others_html(key):
    li = []
    for k in OTHERS_ORDER:
        if k == key or k not in OTHERS:
            continue
        u, sm, b = OTHERS[k]
        ks = f' data-i18n="c_ot_{k}_s"' if f'c_ot_{k}_s' in COMMON_I18N else ''
        kb = f' data-i18n="c_ot_{k}_b"' if f'c_ot_{k}_b' in COMMON_I18N else ''
        li.append(f'<li><a href="{e(u)}"><small{ks}>{e(sm)}</small><b{kb}>{e(b)}</b><span aria-hidden="true">→</span></a></li>')
    return (f'<section class="cw-other" aria-label="ほかの特集"><p class="cw-toc__label" data-i18n="c_ot_label">{OTHERS_LABEL}</p>'
            f'<ul class="cw-other__grid">{"".join(li)}</ul>'
            f'<p class="cw-allback"><a href="{BACKNUMBER_URL}" data-i18n="c_allback">すべてのバックナンバー →</a></p></section>')


def unify_tail(h, key):
    """ページの終わりを共通部品で組み直す（何度通しても同じ結果になる）。"""
    import re as R
    # 1) 古い部品を外す：ほかの特集／つながっている特集、参考動画（グリッド版・cw-note版）、前回の共通部品
    h = R.sub(r'<section[^>]*class="cw-other"[^>]*>.*?</section>', '', h, flags=R.S)
    h = R.sub(r'<section[^>]*class="cw-ref"[^>]*>.*?</section>', '', h, flags=R.S)
    h = R.sub(r'<div class="cw-note[^"]*">(?:(?!</div></div>|<div class="cw-note).)*?hmGwwZ5hjbI.*?</figure>.*?</div>', '', h, flags=R.S)
    # 2) きっかけの動画を出典のすぐ上、ほかの特集を出典のすぐ下（ページの一番下）へ
    m = R.search(r'<section[^>]*class="cw-sources"[^>]*>.*?</section>', h, flags=R.S)
    if not m:
        raise SystemExit('出典(cw-sources)が無いページ: ' + key)
    h = h[:m.start()] + kikkake_html() + m.group(0) + others_html(key) + h[m.end():]
    h = R.sub(r'/\*tail\*/.*?/\*/tail\*/', '', h, flags=R.S)  # 前回の共通部品のCSS
    # 軽くする（全マガジン共通）：noreferrer は noopener で足りる／form の無いページの type="button"／遅延読み込みの画像の decoding 指定
    h = h.replace('rel="noopener noreferrer"', 'rel="noopener"').replace(' type="button"', '')
    h = R.sub(r'<img([^>]*?) decoding="async"([^>]*?loading="lazy")', r'<img\1\2', h)
    h = R.sub(r'<img([^>]*?loading="lazy"[^>]*?) decoding="async"', r'<img\1', h)
    for old_css in TAIL_CSS_OLD:
        h = h.replace(old_css, '')
    # 再生ボタンの三角は CSS 1か所で描く（各動画に同じ SVG を持たせない＝軽く、全マガジンで同じ見た目）
    h = R.sub(r'(<span[^>]*class="cw-video__play"[^>]*>)(?:<svg.*?</svg>|▶)?(</span>)', r'\1\2', h, flags=R.S)
    h = h.replace('</style>', '/*tail*/' + TAIL_CSS + '/*/tail*/</style>', 1)
    return h


_build_i18n = build


def build(m):  # noqa: F811  終わりの並びを共通部品で
    return unify_tail(_build_i18n(m), m['key'])


# ===== 訳のキーを書き込んでから終わりを組む（2026-10-16 怒れる人々）=====
# unify_tail の共通部品は data-i18n="c_…" を最初から持つ。ページに data-i18n が1つでもあると JS は自動でキーを振らない
# （＝本文の訳が全部効かなくなる）。だから build の中で、共通部品を足す前に本文の k1.. を要素へ書き込む。
def stamp_keys(h):
    import importlib
    ua = importlib.import_module('unify_all')
    return ua.stamp(h)[0]


def build(m):  # noqa: F811
    h = _build_i18n(m)
    if m.get('i18n'):
        h = stamp_keys(h)
    return unify_tail(h, m['key'])


_write_tail = write


def write(m):  # noqa: F811  共通部品の訳も訳ファイルへ足す
    p = _write_tail(m)
    if m.get('i18n'):
        import json as J
        tr = J.loads(J.dumps(m['i18n']))
        for l, d in common_i18n().items():
            tr.setdefault(l, {}).update(d)
        t = J.dumps(tr, ensure_ascii=False, separators=(',', ':'))
        for d in (os.path.join(REPO, 'share/check'), os.path.join(REPO, 'status/magazine_prod')):
            open(os.path.join(d, i18n_name(m)), 'w', encoding='utf-8').write(t)
    return p
