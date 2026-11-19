# -*- coding: utf-8 -*-
"""出典は本文に出さず、記事の最後に章ごとにまとめる（全マガジン共通・2026-10-19 たまごさん）。

たまごさん：「本文の中の出典リンク（文の途中の『Wikipedia』『musicman』など）が細かすぎて読みにくい」
決め：
  ・本文の中の出典リンク（<a class="cw-src">）は全部外す。小さな番号も付けない。
  ・出典は記事の最後の「出典」欄（cw-sources）に、章ごとにまとめる（章名 → 出典名とリンク）。同じ出典は1つにまとめる
    （最初に出てきた章に置く）。本文で使っていない出典は最後に「そのほか」。
  ・どの事実がどの出典に基づくかの対応は、データとして残す（照合と関所のため・表には出さない）：
    tools/magazine/shutten/<ページ名>.json  = [{"ch": "ch03", "chName": "...", "url": "...", "label": "...", "fact": "本文の該当の文"}]
    ※本文から外した後にもう一度通しても、前に残した対応は消さない（外す前の対応だけが正）。
  ・訳（<ページ>.i18n.json）の [[1]] などの出典の差し込み印も外す。
何度通しても同じ結果。mag_build.unify_look（＝組み直し・直接組んだページ）と sokkou.py（Gensparkの叩きの即公開）から通る。

  python3 tools/magazine/shutten.py <ページ.html> [...]   … その場で変換（訳の .i18n.json が隣にあれば一緒に）
  python3 tools/magazine/shutten.py --check <ページ.html>  … 本文に出典リンクが残っていれば exit 2
  python3 tools/magazine/shutten.py --self-test
"""
import html as H
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'shutten')
SRC_A = re.compile(r'\s*<a\b[^>]*class="cw-src"[^>]*>(.*?)</a>', re.S)
CSS = ('.cw .cw-sources h4{margin:22px 0 8px;font:600 12.5px/1.6 "Hiragino Sans","Yu Gothic",sans-serif;letter-spacing:.04em;color:var(--ink)}'
       '.cw .cw-sources h4:first-of-type{margin-top:4px}')
LABEL = {'intro': ('c_sh_intro', 'はじめに'), 'close': ('c_sh_close', 'おわりに'), 'other': ('c_sh_other', 'そのほか')}
I18N = {'c_sh_intro': ('Introduction', '引言', 'Introducción', '들어가며'),
        'c_sh_close': ('Closing', '结语', 'Cierre', '맺으며'),
        'c_sh_other': ('Other sources', '其他出处', 'Otras fuentes', '그 밖의 출처')}


def _norm(u):
    return H.unescape(u).split('#')[0].rstrip('/').replace('http://', 'https://')


def _text(s):
    return re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', '', s))).strip()


def chapters(h):
    """[(位置, id, 章名, data-i18n)]。章名は章頭の h2（cw-chead__title）。"""
    out = []
    for m in re.finditer(r'<section\b[^>]*\bid="(ch\d+)"[^>]*>', h):
        seg = h[m.end():m.end() + 6000]
        t = re.search(r'<h2\b([^>]*)class="cw-chead__title"([^>]*)>(.*?)</h2>', seg, re.S)
        name, key = m.group(1), None
        if t:
            name = _text(t.group(3))
            k = re.search(r'data-i18n="([^"]+)"', t.group(1) + t.group(2))
            key = k.group(1) if k else None
        out.append((m.start(), m.group(1), name, key))
    return out


def where(pos, chs, close_pos):
    if close_pos is not None and pos > close_pos:
        return ('close', None, None)
    cur = ('intro', None, None)
    for p, cid, name, key in chs:
        if p <= pos:
            cur = (cid, name, key)
    return cur


def convert(h, name=None):
    """→ (新しいHTML, 対応のリスト)。出典リンクが本文に無ければ何もしない。"""
    m_src = re.search(r'<section\b[^>]*class="cw-sources"[^>]*>.*?</section>', h, re.S)
    body_end = m_src.start() if m_src else len(h)
    found = [m for m in SRC_A.finditer(h[:body_end])]
    if not found:
        return h, []
    chs = chapters(h)
    cm = re.search(r'<section\b[^>]*class="cw-close"', h)
    close_pos = cm.start() if cm else None
    # 元の出典欄の項目（訳のキー付きの <a> をそのまま使う）
    old = []
    if m_src:
        for li in re.findall(r'<li>(.*?)</li>', m_src.group(0), re.S):
            a = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>.*?</a>', li, re.S)
            if a:
                old.append((_norm(a.group(1)), a.group(0)))
    old_by = {}
    for u, a in old:
        old_by.setdefault(u, a)
    pairs = []
    for m in found:
        a = m.group(0)
        u = re.search(r'href="([^"]+)"', a)
        if not u:
            continue
        cid, cname, ckey = where(m.start(), chs, close_pos)
        # 事実＝同じ段落の、この出典の直前までの文（前の出典・文の切れ目から）
        ps = h.rfind('<p', 0, m.start())
        before = _text(SRC_A.sub('｜', h[h.find('>', ps) + 1:m.start()])) if ps >= 0 else ''
        fact = re.split(r'[｜。]', before)[-1].strip() or before[-120:]
        pairs.append({'ch': cid, 'chName': cname or LABEL.get(cid, (None, cid))[1], 'url': H.unescape(u.group(1)),
                      'label': _text(m.group(1)), 'fact': fact[:300], '_a': a.strip(), '_key': ckey})
    # 本文から外す
    new_body = SRC_A.sub('', h[:body_end])
    h = new_body + h[body_end:]
    # 出典欄を章ごとに組み直す
    groups, seen = [], set()
    def grp(cid, cname, ckey):
        for g in groups:
            if g['ch'] == cid:
                return g
        g = {'ch': cid, 'name': cname, 'key': ckey, 'items': []}
        groups.append(g)
        return g
    for p in pairs:
        u = _norm(p['url'])
        if u in seen:
            continue
        seen.add(u)
        a = old_by.get(u)
        if not a:
            a = re.sub(r'\sclass="cw-src"', '', p['_a'])
        grp(p['ch'], p['chName'], p['_key'])['items'].append(a)
    for u, a in old:
        if u not in seen:
            seen.add(u)
            grp('other', None, None)['items'].append(a)
    # はじめに → 章の順 → おわりに → そのほか
    order = {'intro': -1, 'close': 10 ** 6, 'other': 10 ** 6 + 1}
    groups.sort(key=lambda g: order.get(g['ch'], int(g['ch'][2:]) if g['ch'][2:].isdigit() else 0))
    parts = []
    for g in groups:
        if g['ch'] in LABEL:
            k, t = LABEL[g['ch']]
            head = f'<h4 data-i18n="{k}">{t}</h4>'
        else:
            k = f' data-i18n="{g["key"]}"' if g['key'] else ''
            head = f'<h4{k}>{H.escape(g["name"] or g["ch"])}</h4>'
        parts.append(head + '<ul>' + ''.join(f'<li>{a}</li>' for a in g['items']) + '</ul>')
    note = ''
    if m_src:
        nm = re.search(r'<p class="cw-note">.*?</p>', m_src.group(0), re.S)
        note = nm.group(0) if nm else ''
    sec = f'<section aria-label="出典" class="cw-sources" data-shutten="ch"><h3>SOURCES</h3>{"".join(parts)}{note}</section>'
    if m_src:
        s0 = h.find(m_src.group(0))
        h = h[:s0] + sec + h[s0 + len(m_src.group(0)):]
    else:
        h = h.replace('</main>', sec + '</main>', 1)
    h = re.sub(r'<style id="cw-shutten">.*?</style>', '', h, flags=re.S)
    h = h.replace('</head>', f'<style id="cw-shutten">{CSS}</style></head>', 1)
    for p in pairs:
        p.pop('_a', None); p.pop('_key', None)
    return h, pairs


def save_pairs(name, pairs):
    if not name or not pairs:
        return
    os.makedirs(DATA, exist_ok=True)
    json.dump(pairs, open(os.path.join(DATA, name.replace('.html', '') + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def fix_i18n(d):
    """訳の [[n]]（本文の出典の差し込み印）を外し、章ごとの見出しの訳を足す。"""
    for lg, tab in d.items():
        if not isinstance(tab, dict) or lg.startswith('_'):
            continue
        for k, v in list(tab.items()):
            if isinstance(v, str) and '[[' in v:
                tab[k] = re.sub(r'\s*\[\[\d+\]\]', '', v)
        i = ['en', 'zh-Hans', 'es', 'ko'].index(lg) if lg in ('en', 'zh-Hans', 'es', 'ko') else None
        if i is not None:
            for k, v in I18N.items():
                tab.setdefault(k, v[i])
    return d


def run_file(path):
    h = open(path, encoding='utf-8').read()
    name = os.path.basename(path)
    h2, pairs = convert(h, name)
    if h2 != h:
        open(path, 'w', encoding='utf-8').write(h2)
        save_pairs(name, pairs)
    ip = path.replace('.html', '.i18n.json')
    if os.path.exists(ip):
        d = json.load(open(ip, encoding='utf-8'))
        s0 = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
        s1 = json.dumps(fix_i18n(d), ensure_ascii=False, separators=(',', ':'))
        if s1 != s0:
            open(ip, 'w', encoding='utf-8').write(s1)
    return len(pairs)


def left_in_body(h):
    m = re.search(r'<section\b[^>]*class="cw-sources"', h)
    return len(SRC_A.findall(h[:m.start()] if m else h))


def self_test():
    h = ('<html><head><style></style></head><body><main class="cw"><section class="cw-open"><p>はじめの話<a class="cw-src" href="https://a.example/1">A</a>。</p></section>'
         '<section class="cw-chapter" id="ch01"><header class="cw-chead"><h2 class="cw-chead__title" data-i18n="k9">歌手 - 曲</h2></header>'
         '<p data-i18n="k1">1979年のデビュー曲<a class="cw-src" href="https://w.example/x">Wikipedia</a>。1位になった<a class="cw-src" href="https://a.example/1">A</a>。</p></section>'
         '<section class="cw-close"><p>おしまい</p></section>'
         '<section aria-label="出典" class="cw-sources"><h3>SOURCES</h3><ul><li><a href="https://w.example/x" data-i18n="k50">Wikipedia — X</a></li><li><a href="https://z.example/">Z</a></li></ul></section></main></body></html>')
    h2, pairs = convert(h, 't.html')
    assert left_in_body(h2) == 0, '本文に出典リンクが残った'
    sec = re.search(r'<section aria-label="出典".*?</section>', h2, re.S).group(0)
    assert sec.index('はじめに') < sec.index('歌手 - 曲') < sec.index('そのほか'), sec
    assert sec.count('https://a.example/1') == 1, '重複がまとまっていない'
    assert 'data-i18n="k50"' in sec and '<h4 data-i18n="k9">' in sec
    assert [p['fact'] for p in pairs] == ['はじめの話', '1979年のデビュー曲', '1位になった'], pairs
    assert convert(h2, 't.html')[0] == h2, '2回目で変わった'
    d = fix_i18n({'en': {'k1': 'Debut in 1979[[1]]. Hit No. 1[[2]].'}})
    assert d['en']['k1'] == 'Debut in 1979. Hit No. 1.' and d['en']['c_sh_other'] == 'Other sources'
    print('SELF-TEST OK')
    return 0


def main(argv):
    if '--self-test' in argv:
        return self_test()
    if '--check' in argv:
        bad = [(p, left_in_body(open(p, encoding='utf-8').read())) for p in argv[2:]]
        bad = [b for b in bad if b[1]]
        for p, n in bad:
            print('SHUTTEN_NG', p, n)
        return 2 if bad else 0
    for p in argv[1:]:
        print(p, run_file(p))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
