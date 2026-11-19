#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""特集の最後に、うちのYouTube（@joy-relief-station）の一枚を置く部品（2026-10-30 たまごさん）。

台帳（正本）：tools/magazine/channel_cut.json の cuts[]（page／yt／short／label／ato）。
  page が「ikareru-01」のような名前 → 静的マガジン（public/magazine/<名前>.html）。add() が入れる（mag_build.unify_look から毎回通る）。
  page が「/feature/…」 → 特集（React）。--gen-ts で joy-relief-station の src/lib/channelCut.generated.ts へ写し、
  src/components/ChannelCut.tsx が出す。
置き方：文言なし・動画だけ。ショートは縦長（9:16）。最初はサムネだけ（遅延読み込み）、押したらその場で再生（ページの既存の
  data-yt-cover の仕組み＝autoplay=1・playsinline=1）。ato があればその文を含む段落の直後、無ければ締め（cw-close）の直後。
  figure の class は cw-video で始めない（曲として数えない＝曲数・曲ページの関所の対象外）。

使い方：
  python3 tools/magazine/channel_cut.py --apply <html>...     # その場で入れ直す（何度通しても同じ）
  python3 tools/magazine/channel_cut.py --gen-ts <jrs>         # React 側の表を書き出す
  python3 tools/magazine/channel_cut.py --self-test
"""
import html as H
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DAICHO = os.path.join(HERE, 'channel_cut.json')
MARK = 'data-chcut'
CSS_ID = 'cw-chcut'
CSS = ('.cw-chcut{margin:40px 0 8px;max-width:300px}'
       '.cw-chcut .cw-chcut__frame{position:relative;aspect-ratio:9/16;background:#000;overflow:hidden;border-radius:6px}'
       '.cw-chcut--wide .cw-chcut__frame{aspect-ratio:16/9;border-radius:2px}.cw-chcut--wide{max-width:640px}'
       '.cw-chcut .cw-chcut__frame iframe{position:absolute;inset:0;width:100%;height:100%;border:0}'
       '.cw-chcut .cw-video__cover img{object-fit:cover}')


def cuts():
    try:
        return json.load(open(DAICHO, encoding='utf-8')).get('cuts', [])
    except Exception:
        return []


def page_of(h):
    """ページ名（canonical か og:url。属性の順に依らない＝fuukei.page_name と同じ読み方）。"""
    for pat in (r'<link\b[^>]*rel="canonical"[^>]*>', r'<meta\b[^>]*property="og:url"[^>]*>'):
        for tag in re.findall(pat, h):
            m = re.search(r'(?:href|content)="[^"]*/magazine/([^"/]+?)\.html"', tag)
            if m:
                return m.group(1)
    return None


def figure(c):
    yt = c['yt']
    short = c.get('short', True)
    q = 'oardefault' if short else 'hqdefault'
    lab = H.escape('ここで再生：' + c.get('label', ''), quote=True)
    return (f'<figure class="cw-chcut{"" if short else " cw-chcut--wide"}" {MARK}="{yt}"><div class="cw-chcut__frame">'
            f'<button class="cw-video__cover" data-yt-cover="{yt}" aria-label="{lab}">'
            f'<img src="https://i.ytimg.com/vi/{yt}/{q}.jpg" alt="" loading="lazy"/>'
            f'<span class="cw-video__play" aria-hidden="true"></span></button></div></figure>')


def strip(h):
    h = re.sub(r'<figure class="cw-chcut[^"]*" ' + MARK + r'="[^"]*">.*?</figure>', '', h, flags=re.S)
    return re.sub(r'<style id="' + CSS_ID + r'">.*?</style>', '', h, flags=re.S)


def add(h, page=None):
    """台帳に載ったページだけに入れる。何度通しても同じ結果。"""
    page = page or page_of(h)
    c = next((x for x in cuts() if x.get('page') == page), None)
    h = strip(h)
    if not c:
        return h
    fig = figure(c)
    pos = -1
    if c.get('ato'):
        i = h.find(c['ato'])
        if i >= 0:
            j = h.find('</p>', i)
            pos = j + 4 if j >= 0 else -1
    if pos < 0:
        m = re.search(r'<section[^>]*class="cw-close"[^>]*>.*?</section>', h, flags=re.S)
        pos = m.end() if m else -1
    if pos < 0:
        raise SystemExit('channel_cut: 置き場所が見つからない：%s' % page)
    h = h[:pos] + fig + h[pos:]
    return h.replace('</head>', f'<style id="{CSS_ID}">{CSS}</style></head>', 1)


def gen_ts(jrs):
    rows = {c['page']: {'yt': c['yt'], 'short': bool(c.get('short', True)), 'label': c.get('label', '')}
            for c in cuts() if c.get('page', '').startswith('/feature/')}
    body = ('// 自動生成：tools/magazine/channel_cut.py --gen-ts（正本は tamago-shinchoku tools/magazine/channel_cut.json）。手で直さない。\n'
            'export interface ChannelCutItem { yt: string; short: boolean; label: string }\n'
            'export const CHANNEL_CUTS: Record<string, ChannelCutItem> = '
            + json.dumps(rows, ensure_ascii=False, indent=2) + ';\n')
    p = os.path.join(jrs, 'src/lib/channelCut.generated.ts')
    open(p, 'w', encoding='utf-8').write(body)
    return p


def self_test():
    global cuts
    orig = cuts
    cuts = lambda: [{'page': 'x', 'yt': 'AAAAAAAAAAA', 'label': 'a「b」', 'ato': '次回もね'},
                    {'page': 'y', 'yt': 'BBBBBBBBBBB', 'short': False}]
    try:
        base = ('<html><head><link href="https://e/magazine/x.html" rel="canonical"/></head><body>'
                '<section class="cw-close"><p>おわり。次回もね。</p><p>あと</p></section></body></html>')
        a = add(base)
        assert a.count(MARK) == 1 and a.count('id="%s"' % CSS_ID) == 1
        assert a.index(MARK) < a.index('<p>あと</p>'), '指定の文の直後に入る'
        assert add(a) == a, '何度通しても同じ'
        assert 'oardefault' in a and 'data-yt-cover="AAAAAAAAAAA"' in a
        assert not re.search(r'<figure class="cw-video', a), '曲として数えない'
        b = add(base.replace('x.html', 'y.html'))
        assert b.index(MARK) > b.index('</section>') and 'cw-chcut--wide' in b, '指定が無ければ締めの直後'
        z = add(base.replace('x.html', 'z.html'))
        assert MARK not in z, '台帳に無いページには出さない'
        assert add(a, page='z') == strip(a), '台帳から外せば消える'
    finally:
        cuts = orig
    print('channel_cut self-test OK')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['--self-test']:
        self_test()
    elif a[:1] == ['--gen-ts'] and len(a) == 2:
        print(gen_ts(a[1]))
    elif a[:1] == ['--apply']:
        for p in a[1:]:
            h = open(p, encoding='utf-8').read()
            n = add(h)
            open(p, 'w', encoding='utf-8').write(n)
            print(p, 'changed' if n != h else 'same', page_of(h))
    else:
        print(__doc__)
