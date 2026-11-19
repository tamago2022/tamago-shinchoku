# -*- coding: utf-8 -*-
"""特集（React の /feature/*）の出典を、章ごとにまとめる表を作る（2026-10-19 たまごさん・shutten.py の React 版）。

本文の <Src …> は画面には何も出さない（部品が null を返す）。ソースには残す＝どの事実がどの出典かの対応はコードとデータに残る。
このスクリプトは各特集のソースを読み、章（id="chNN"）ごとに出てくる出典の URL を並べて
  src/lib/shuttenGroups.generated.ts（SHUTTEN_GROUPS）            … 画面の出典欄（章名 → 出典）
  tamago-shinchoku tools/magazine/shutten/feature-<名前>.json       … 事実と出典の対応（照合と関所のため・表には出さない）
を作る。特集の文を直したら、もう一度走らせる（magazine_gate.py が --check で、表とソースのずれを不合格にする）。

  python3 tools/magazine/shutten_tsx.py <joy-relief-station>
  python3 tools/magazine/shutten_tsx.py <joy-relief-station> --check   … 表が古ければ exit 2
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'shutten')
ROUTES = {'/feature/citypop-sekai': 'src/routes/feature.citypop-sekai.tsx',
          '/feature/hikigatari': 'src/routes/feature.hikigatari.tsx',
          '/feature/ekkyo': 'src/routes/feature.ekkyo.tsx'}
OUT = 'src/lib/shuttenGroups.generated.ts'


def src_map(s):
    """SRC のキー → URL"""
    m = {}
    srcs = []
    sb = re.search(r'const SOURCES[^=]*=\s*\[(.*?)\n\];', s, re.S)
    if sb:
        srcs = re.findall(r'url:\s*"([^"]+)"', sb.group(1))
    b = re.search(r'const SRC\s*=\s*\{(.*?)\n\}', s, re.S)
    if b:
        for k, i in re.findall(r'(\w+):\s*SOURCES\[(\d+)\]\.url', b.group(1)):
            if int(i) < len(srcs):
                m[k] = srcs[int(i)]
        for k, u in re.findall(r'(\w+):\s*\{\s*label:\s*"[^"]*",\s*url:\s*"([^"]+)"', b.group(1)):
            m[k] = u
        for k, u in re.findall(r'(\w+):\s*"(https?://[^"]+)"', b.group(1)):
            m[k] = u
    return m, srcs


def _clean(t):
    t = re.sub(r'<[^>]+>|\{[^}]*\}', '', t)
    t = re.sub(r'\s*\n\s*', '', t).replace('&#39;', "'")
    return re.sub(r'\s+', ' ', t).strip()


def groups_for(s):
    m, srcs = src_map(s)
    chs = [(x.start(), x.group(1)) for x in re.finditer(r'id="(ch\d+)"', s)]
    titles = {}
    for p, cid in chs:
        t = re.search(r'<CwChapterHead\b[^>]*?\stitle="([^"]+)"', s[p:p + 1500], re.S)
        titles[cid] = t.group(1) if t else cid
    close = s.find('className="cw-close"')
    srcsec = s.find('className="cw-sources"')
    pairs = []
    pat = re.compile(r'<Src\s+k="(\w+)"\s*/>|<Src\s+href=\{SRC\.(\w+)\}>[^<]*</Src>|<Src\s+href=\{SOURCES\[(\d+)\]\.url\}>[^<]*</Src>|<Src\s+href="([^"]+)">[^<]*</Src>')
    for x in pat.finditer(s):
        if 0 <= srcsec < x.start():
            break
        k1, k2, idx, raw = x.groups()
        url = m.get(k1 or k2) if (k1 or k2) else (srcs[int(idx)] if idx and int(idx) < len(srcs) else raw)
        if not url:
            continue
        if 0 <= close < x.start():
            cid = 'close'
        else:
            cid = 'intro'
            for p, c in chs:
                if p <= x.start():
                    cid = c
        before = s[max(0, x.start() - 600):x.start()]
        before = re.split(r'<Src\b|</p>|<p>', before)[-1]
        fact = re.split(r'。', _clean(before).rstrip('。'))[-1][:300]
        pairs.append({'ch': cid, 'chName': titles.get(cid, cid), 'url': url, 'fact': fact})
    groups, seen = [], set()
    for p in pairs:
        if p['url'] in seen:
            continue
        seen.add(p['url'])
        g = next((g for g in groups if g['ch'] == p['ch']), None)
        if not g:
            g = {'ch': p['ch'], 'title': p['chName'] if p['ch'] not in ('intro', 'close') else '', 'urls': []}
            groups.append(g)
        g['urls'].append(p['url'])
    order = lambda g: -1 if g['ch'] == 'intro' else (10 ** 6 if g['ch'] == 'close' else int(g['ch'][2:]))
    groups.sort(key=order)
    return groups, pairs


def build(jrs):
    allg = {}
    for route, rel in ROUTES.items():
        p = os.path.join(jrs, rel)
        if not os.path.exists(p):
            continue
        g, pairs = groups_for(open(p, encoding='utf-8').read())
        allg[route] = g
        if pairs:
            os.makedirs(DATA, exist_ok=True)
            json.dump(pairs, open(os.path.join(DATA, 'feature-' + route.split('/')[-1] + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return ('// 特集の出典を章ごとにまとめた表（2026-10-19）。tamago-shinchoku tools/magazine/shutten_tsx.py が各特集のソースの <Src> から作る。手で書き換えない。\n'
            'export type ShuttenGroup = { ch: string; title: string; urls: string[] };\n'
            'export const SHUTTEN_GROUPS: Record<string, ShuttenGroup[]> = ' + json.dumps(allg, ensure_ascii=False, indent=2) + ';\n')


def main(argv):
    jrs = argv[1]
    t = build(jrs)
    p = os.path.join(jrs, OUT)
    if '--check' in argv:
        cur = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
        if cur != t:
            print('SHUTTEN_TSX_NG：出典の表が特集のソースと合っていない（python3 tools/magazine/shutten_tsx.py <jrs> で作り直す）')
            return 2
        print('SHUTTEN_TSX_OK')
        return 0
    open(p, 'w', encoding='utf-8').write(t)
    print('ok', {k: sum(len(g['urls']) for g in v) for k, v in json.loads(t[t.index('[]> = ') + 5:t.rindex(';')]).items()})
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
