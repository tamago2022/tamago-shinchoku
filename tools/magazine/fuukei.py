# -*- coding: utf-8 -*-
"""雰囲気の静止画（全マガジン共通の部品・2026-10-18 たまごさん「賑やかしに5〜6枚。人に見せても恥ずかしくない85〜90点に」）
- 写真は自由ライセンスだけ（Wikimedia Commons の CC0／PD／CC BY／CC BY-SA）。クレジットは小さく（撮影者・ライセンス・元ページ）。
- たまごさんのAI絵：Google Drive「マイドライブ/AI制作物/Claude/マガジン/<マガジン名>/」に `ch03.jpg`（＝3章の後ろに置く）の名前で入れる
  → `python3 tools/magazine/ai_e_torikomi.py` が軽いwebpにして fuukei.json に足す（クレジットなし・キャプションなし）。
- 置き場所は「隣の文章を強める位置」＝その章（id="chNN"）のすぐ後ろ。キャプションは付けない（訳のキーがずれない／文章の邪魔をしない）。
- 軽く：幅960pxのwebp（だいたい40〜120KB）・loading=lazy・decoding=async・幅と高さを書いて画面がガタつかない。
- データは tools/magazine/fuukei.json（{ページ名: [{after, src, w, h, alt, credit, page, lic}]}）。静的マガジンは mag_build.unify_look の最後で入る＝何度組み直しても消えない。
  React の特集（/feature/citypop-sekai・/feature/hikigatari）は同じ json から src/lib/fuukeiPhotos.ts を作って <CwFuukei after="ch03" /> で入れる。
"""
import json, os, re
from html import escape as e

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'fuukei.json')
CSS = ('.cw .cw-fk{padding:40px 0}.cw .cw-fk figure{margin:0 auto;max-width:760px}'
       '.cw .cw-fk img{display:block;width:100%;height:auto;border-radius:4px;filter:sepia(.1)}'
       '.cw .cw-fk__cr{display:block;margin-top:6px;font-size:10.5px;line-height:1.5;opacity:.55;text-align:right}'
       '.cw .cw-fk__cr a{color:inherit}')


def load():
    return json.load(open(DATA, encoding='utf-8')) if os.path.exists(DATA) else {}


def figure(x):
    cr = ''
    if x.get('credit'):
        cr = (f'<small class="cw-fk__cr">Photo: <a href="{e(x["page"])}" target="_blank" rel="noopener">{e(x["credit"])}</a>'
              f' / {e(x["lic"])} / Wikimedia Commons</small>')
    return (f'<section class="cw-fk" data-fk="1" aria-label="写真"><div class="cw-wrap"><figure>'
            f'<img src="{e(x["src"])}" width="{x["w"]}" height="{x["h"]}" alt="{e(x["alt"])}" loading="lazy" decoding="async"/>{cr}</figure></div></section>')


def _section_end(h, start):
    """start（<section の位置）から、対になる </section> の終わりの位置を返す（入れ子を数える）。"""
    depth, i = 0, start
    for m in re.finditer(r'<section\b|</section>', h[start:]):
        depth += 1 if m.group(0) == '<section' else -1
        if depth == 0:
            return start + m.end()
    return -1


def page_name(h):
    m = re.search(r'<link rel="canonical" href="[^"]*/magazine/([^"/]+\.html)"', h)
    return m.group(1) if m else None


def add(h, name=None):
    """組み上がったマガジンに雰囲気の静止画を入れる（何度通しても同じ）。"""
    h = re.sub(r'<section class="cw-fk" data-fk="1".*?</section>', '', h, flags=re.S)
    h = re.sub(r'<style id="cw-fk">.*?</style>', '', h, flags=re.S)
    items = load().get(name or page_name(h) or '', [])
    if not items:
        return h
    by = {}
    for x in items:
        by.setdefault(x['after'], []).append(x)
    for ch, xs in by.items():
        m = re.search(r'<section[^>]*\bid="' + re.escape(ch) + r'"', h)
        if not m:
            continue
        end = _section_end(h, m.start())
        if end < 0:
            continue
        # 章のすぐ後ろに既存の写真（cw-interlude）があれば、その後ろ
        m2 = re.match(r'\s*<section class="cw-interlude"', h[end:])
        if m2:
            e2 = _section_end(h, end + m2.end() - len('<section class="cw-interlude"'))
            end = e2 if e2 > 0 else end
        h = h[:end] + ''.join(figure(x) for x in xs) + h[end:]
    return h.replace('</head>', f'<style id="cw-fk">{CSS}</style></head>', 1)


def check(h, name=None):
    items = load().get(name or page_name(h) or '', [])
    n = h.count('data-fk="1"')
    return [] if n == len(items) else [f'静止画 {n}/{len(items)}']
