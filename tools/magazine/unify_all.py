# -*- coding: utf-8 -*-
"""全マガジンの「ページの終わり」を共通部品（mag_build.unify_tail）で組み直す（2026-10-16）。
本番の写し（status/magazine_prod/*.html）をそのまま読み、終わりだけ差し替える＝本文は触らない。
多言語つきの号は、先に今の訳のキーを要素に書き込んでから組み直し、共通部品の訳を訳ファイルへ足す。
使い方: python3 tools/magazine/unify_all.py   → status/magazine_prod/ と share/check/ の両方を上書き
"""
import os, re, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mag_build as MB

REPO = MB.REPO
PAGES = [  # key, 本番名, 確認ページ名
    ('harakami', 'rei-harakami.html', 'tokushu-rei-harakami.html'),
    ('ikareru', 'ikareru-01.html', 'tokushu-ikareru-01.html'),
    ('takoukan', 'naze-ongaku-01-takoukan.html', 'naze-ongaku-01-takoukan.html'),
    ('josh', 'hikigatari-josh-turner.html', 'hikigatari-josh-turner-b.html'),
    ('hoshikatsu', 'kimi-wa-hoshi-katsu.html', 'tokushu-hoshi-katsu.html'),
]


def stamp(h):
    """実行時にJSが振るキー（k1..）を、同じ順番で要素へ書き込む（あとで要素を足し引きしても訳がずれない）。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(h, 'html.parser')
    main = soup.find('main')
    seen, n = set(), 0
    for q in MB.I18N_SEL:
        for el in main.select(q):
            if id(el) in seen or any(id(a) in seen for a in el.parents):
                continue
            if not re.search(r'[぀-ヿ一-鿿]', el.get_text()):
                continue
            n += 1; seen.add(id(el)); el['data-i18n'] = f'k{n}'
    out = str(soup)
    out = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', out)
    out = out.replace('<div aria-hidden="true" class="cw-hero__bg">', '<div class="cw-hero__bg" aria-hidden="true">')
    out = re.sub(r'(<div class="cw-hero__bg" aria-hidden="true">)<img ([^>]*?)src="([^"]+)"([^>]*)/>', r'\1<img src="\3" \2\4/>', out)
    return out, n


def main():
    for key, prod, chk in PAGES:
        p = os.path.join(REPO, 'status/magazine_prod', prod)
        if not os.path.exists(p):
            print('なし', prod); continue
        h = open(p, encoding='utf-8').read()
        jn = prod.replace('.html', '.i18n.json')
        has_i18n = 'gokigen-lang' in h
        if has_i18n and 'data-i18n="' not in h.split('<script', 1)[0]:
            h, n = stamp(h)
            print('キーを書き込み', prod, n)
        h = MB.unify_tail(h, key)
        if has_i18n:
            jp = os.path.join(REPO, 'status/magazine_prod', jn)
            tr = json.load(open(jp, encoding='utf-8'))
            for l, d in MB.common_i18n().items():
                tr.setdefault(l, {}).update(d)
            t = json.dumps(tr, ensure_ascii=False, separators=(',', ':'))
            for d in ('status/magazine_prod', 'share/check'):
                open(os.path.join(REPO, d, jn), 'w', encoding='utf-8').write(t)
        for d, name in (('status/magazine_prod', prod), ('share/check', chk)):
            open(os.path.join(REPO, d, name), 'w', encoding='utf-8').write(h)
        print('OK', prod, len(h.encode()))


if __name__ == '__main__':
    main()
