# -*- coding: utf-8 -*-
"""目次（IN THIS ISSUE）から章へ、滑らかに飛ぶ（全マガジン・全特集の共通の型・2026-10-19 たまごさん確定）。

たまごさん：「カットで飛ぶんじゃなくてビュイーンと飛ぶのが気持ちいい。採用」「（目次のサムネが）押せると最近まで気づかなかった」
  ① ページ全体を scroll-behavior:smooth（動きを減らす設定の人には、いつもどおり一瞬で）
  ② 「IN THIS ISSUE」のすぐ下に、小さく1行「押すとそこに飛びます」（5言語・英語は Tap to jump）。目立たせすぎない
静的マガジンは mag_build.unify_look が必ず通す（何度通しても同じ）。特集（React）は featureCityPopSekai.tsx の cwStyles と各特集の目次に同じもの。
magazine_gate.py が、外れている号・特集を不合格にする（check）。

  python3 tools/magazine/toc_smooth.py <ページ.html> [...]    … その場で入れる（隣の .i18n.json にも訳を足す）
  python3 tools/magazine/toc_smooth.py --self-test
"""
import json, os, re, sys

HINT_JA = '押すとそこに飛びます'
HINT_KEY = 'c_toc_hint'
I18N = {'en': 'Tap to jump', 'zh-Hans': '点一下就能跳过去', 'es': 'Toca para ir', 'ko': '누르면 바로 이동해요'}
CSS = ('html{scroll-behavior:smooth}@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}'
       '.cw .cw-toc__hint{margin:-10px 0 16px;font:400 11px/1.6 "Hiragino Sans","Yu Gothic",sans-serif;letter-spacing:.04em;color:var(--mute);opacity:.85}')
HINT = f'<p class="cw-toc__hint" data-i18n="{HINT_KEY}">{HINT_JA}</p>'


def add(h):
    h = re.sub(r'<style id="cw-toc-smooth">.*?</style>', '', h, flags=re.S)
    h = h.replace('</head>', f'<style id="cw-toc-smooth">{CSS}</style></head>', 1)
    h = re.sub(r'<p class="cw-toc__hint"[^>]*>.*?</p>', '', h, flags=re.S)
    h = re.sub(r'(<p class="cw-toc__label"[^>]*>\s*IN THIS ISSUE\s*</p>)', r'\1' + HINT, h, count=1, flags=re.I)
    return h


def check(h):
    """外れていれば理由のリスト（目次の無いページは問わない）"""
    ng = []
    if not re.search(r'IN THIS ISSUE', h, re.I):
        return ng
    if 'scroll-behavior:smooth' not in h.replace(' ', ''):
        ng.append('滑らかに飛ばない（scroll-behavior:smooth が無い）')
    if 'cw-toc__hint' not in h:
        ng.append('「押すとそこに飛びます」が無い')
    return ng


def check_tsx(jrs):
    """特集（React）：cwStyles に smooth、目次のある特集に「押すとそこに飛びます」"""
    ng = []
    css = open(os.path.join(jrs, 'src/components/featureCityPopSekai.tsx'), encoding='utf-8').read()
    if 'html{scroll-behavior:smooth}' not in css:
        ng.append('cwStyles に scroll-behavior:smooth が無い')
    rd = os.path.join(jrs, 'src/routes')
    for f in sorted(os.listdir(rd)):
        if f.startswith('feature.') and f.endswith('.tsx'):
            s = open(os.path.join(rd, f), encoding='utf-8').read()
            if 'IN THIS ISSUE' in s and HINT_JA not in s:
                ng.append(f + '：「押すとそこに飛びます」が無い')
    return ng


def fix_i18n(d):
    for lg, t in I18N.items():
        if isinstance(d.get(lg), dict):
            d[lg].setdefault(HINT_KEY, t)
    return d


def run_file(p):
    h = open(p, encoding='utf-8').read()
    h2 = add(h)
    if h2 != h:
        open(p, 'w', encoding='utf-8').write(h2)
    ip = p.replace('.html', '.i18n.json')
    if os.path.exists(ip):
        d = json.load(open(ip, encoding='utf-8'))
        s0 = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
        s1 = json.dumps(fix_i18n(d), ensure_ascii=False, separators=(',', ':'))
        if s1 != s0:
            open(ip, 'w', encoding='utf-8').write(s1)
    return check(h2)


def self_test():
    h = '<html><head></head><body><section class="cw-toc"><p class="cw-toc__label">IN THIS ISSUE</p><ul></ul></section></body></html>'
    assert check(h)
    h2 = add(h)
    assert not check(h2) and add(h2) == h2 and h2.count(HINT_JA) == 1
    assert h2.index('IN THIS ISSUE') < h2.index(HINT_JA) < h2.index('<ul>')
    assert check('<html><body>目次なし</body></html>') == []
    d = fix_i18n({'en': {}, 'ko': {}})
    assert d['en'][HINT_KEY] == 'Tap to jump'
    print('SELF-TEST OK')
    return 0


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    for p in sys.argv[1:]:
        print(p, run_file(p) or 'OK')
