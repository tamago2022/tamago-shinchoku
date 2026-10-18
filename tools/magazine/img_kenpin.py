# -*- coding: utf-8 -*-
"""壊れた画像の検品（img_kenpin）— 2026-10-19 たまごさん至急。

起きたこと：シティポップ特集から写真6枚を外したとき、画像ファイルだけ消えて、別の便が組み直した
src/lib/fuukeiPhotos.ts に写真の枠（img・figure・クレジット）が残った。本番で、紺の大きな空白に
壊れた画像のアイコンと代替テキスト「1985年、東京の商店街の看板」だけが出た。

ここで見るもの（どれか1つでも当たれば不合格）：
  ① 手元（main の写し）：マガジン（public/magazine/*.html）の <img src>／<source srcset>／og:image と、
     特集の写真の表（src/lib/fuukeiPhotos.ts）の src が、public/ に実在するか（無い＝本番で必ず404）
  ② 本番：全マガジン（/magazine/*.html）と特集（/feature/*）のページに出てくる画像を1枚ずつ叩き、404 等で読めないもの
     ・YouTube の maxresdefault は、無い動画では YouTube が小さな灰色画像を返すため、ページ側で hqdefault に落とす作りになっている
       （onerror／onLoad）。これは壊れた画像として数えない。

使い方：
  python3 tools/magazine/img_kenpin.py --local <joy-relief-station の作業場>
  python3 tools/magazine/img_kenpin.py --prod
  python3 tools/magazine/img_kenpin.py --self-test
magazine_gate.py の一巡から両方を呼ぶ（壊れた画像＝不合格・直す便を積む）。
"""
import html as H
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse, unquote

SITE = 'https://joy-relief-station.lovable.app'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh) tamago-img-kenpin/1.0'}
FEATURES = ['/feature/citypop-sekai', '/feature/hikigatari', '/feature/ekkyo']   # 特集（React）。足したらここにも
IMG_RE = re.compile(r'<img\b[^>]*?\ssrc="([^"]+)"', re.I)
SRCSET_RE = re.compile(r'\ssrcset="([^"]+)"', re.I)
OG_RE = re.compile(r'<meta\b[^>]*(?:property|name)="(?:og:image|twitter:image)"[^>]*content="([^"]+)"', re.I)
FALLBACK_OK = re.compile(r'i\.ytimg\.com/vi/[^/]+/maxresdefault\.jpg|img\.youtube\.com/vi/[^/]+/maxresdefault\.jpg')


def refs_in_html(h):
    out = [H.unescape(m) for m in IMG_RE.findall(h)]
    for ss in SRCSET_RE.findall(h):
        out += [p.strip().split(' ')[0] for p in H.unescape(ss).split(',') if p.strip()]
    out += [H.unescape(m) for m in OG_RE.findall(h)]
    return [u for u in out if u and not u.startswith('data:')]


def refs_in_fuukei_ts(s):
    return re.findall(r'"src":\s*"([^"]+)"', s)


def local_path(w, ref, base='/magazine/'):
    """サイト内の参照 → public/ のファイル。外部URLは None。"""
    if re.match(r'^(https?:)?//', ref):
        u = urlparse(ref if ref.startswith('http') else 'https:' + ref)
        if u.netloc and 'joy-relief-station' not in u.netloc:
            return None
        ref = u.path
    p = urljoin(base, ref.split('?')[0].split('#')[0])
    return os.path.join(w, 'public', unquote(p).lstrip('/'))


def check_local(w):
    """main の写しの中で、参照先のファイルが無いもの → [(ページ, 参照)]"""
    bad = []
    md = os.path.join(w, 'public', 'magazine')
    for n in sorted(os.listdir(md)) if os.path.isdir(md) else []:
        if not n.endswith('.html'):
            continue
        h = open(os.path.join(md, n), encoding='utf-8', errors='ignore').read()
        for r in sorted(set(refs_in_html(h))):
            p = local_path(w, r)
            if p and not os.path.exists(p):
                bad.append(('magazine/' + n, r))
    ts = os.path.join(w, 'src', 'lib', 'fuukeiPhotos.ts')
    if os.path.exists(ts):
        for r in sorted(set(refs_in_fuukei_ts(open(ts, encoding='utf-8').read()))):
            p = local_path(w, r, '/')
            if p and not os.path.exists(p):
                bad.append(('src/lib/fuukeiPhotos.ts', r))
    return bad


def _status(u):
    for meth in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(u, headers=UA, method=meth)
            with urllib.request.urlopen(req, timeout=25) as r:
                if meth == 'GET':
                    r.read(1024)
                return r.status
        except urllib.error.HTTPError as e:
            if meth == 'HEAD' and e.code in (403, 405):
                continue
            return e.code
        except Exception:
            if meth == 'HEAD':
                continue
            return 0
    return 0


def prod_pages():
    pages = list(FEATURES)
    try:
        with urllib.request.urlopen(urllib.request.Request(SITE + '/magazine/backnumber.html', headers=UA), timeout=30) as r:
            bn = r.read().decode('utf-8', 'ignore')
        pages += sorted(set('/magazine/' + m for m in re.findall(r'href="(?:https://joy-relief-station\.lovable\.app)?(?:/magazine/|\./)?([a-z0-9][a-z0-9\-]*\.html)"', bn)))
        pages.append('/magazine/backnumber.html')
    except Exception:
        pass
    return list(dict.fromkeys(pages))


def check_prod(pages=None):
    """本番の各ページに出てくる画像を叩く → [(ページ, URL, 状態)]"""
    pages = pages or prod_pages()
    refs = {}
    for pg in pages:
        try:
            with urllib.request.urlopen(urllib.request.Request(SITE + pg, headers=UA), timeout=30) as r:
                h = r.read().decode('utf-8', 'ignore')
        except Exception as e:
            refs.setdefault(SITE + pg, set()).add('(ページ)')
            continue
        for ref in refs_in_html(h):
            u = urljoin(SITE + pg, ref if not ref.startswith('//') else 'https:' + ref)
            if FALLBACK_OK.search(u):
                continue
            refs.setdefault(u, set()).add(pg)
    urls = [u for u in refs if not u.endswith('(ページ)')]
    with ThreadPoolExecutor(8) as ex:
        st = dict(zip(urls, ex.map(_status, urls)))
    bad = []
    for u, pgs in refs.items():
        if '(ページ)' in pgs:
            bad.append((u, '(ページが開かない)', 0))
            continue
        if st.get(u) != 200:
            for pg in sorted(pgs):
                bad.append((pg, u, st.get(u)))
    return bad, len(pages), len(urls)


def self_test():
    import tempfile, shutil
    w = tempfile.mkdtemp(prefix='imgk_')
    try:
        os.makedirs(os.path.join(w, 'public/magazine/assets/fuukei'))
        os.makedirs(os.path.join(w, 'src/lib'))
        open(os.path.join(w, 'public/magazine/assets/fuukei/a.webp'), 'w').write('x')
        open(os.path.join(w, 'public/magazine/x.html'), 'w').write(
            '<img src="assets/fuukei/a.webp"><img src="assets/fuukei/gone.webp"><img src="https://i.ytimg.com/vi/Q/hqdefault.jpg">'
            '<meta property="og:image" content="https://joy-relief-station.lovable.app/magazine/assets/fuukei/og.jpg">')
        open(os.path.join(w, 'src/lib/fuukeiPhotos.ts'), 'w').write('{"src": "/magazine/assets/fuukei/a.webp"}, {"src": "/magazine/assets/fuukei/citypop-sekai-6.webp"}')
        bad = check_local(w)
        got = sorted(r for _, r in bad)
        assert got == ['/magazine/assets/fuukei/citypop-sekai-6.webp', 'assets/fuukei/gone.webp',
                       'https://joy-relief-station.lovable.app/magazine/assets/fuukei/og.jpg'], got
        assert FALLBACK_OK.search('https://i.ytimg.com/vi/abc/maxresdefault.jpg')
        assert not FALLBACK_OK.search('https://i.ytimg.com/vi/abc/hqdefault.jpg')
        print('SELF-TEST OK')
        return 0
    finally:
        shutil.rmtree(w, ignore_errors=True)   # 使ったらしまう


def main(argv):
    if '--self-test' in argv:
        return self_test()
    rc = 0
    if '--local' in argv:
        bad = check_local(argv[argv.index('--local') + 1])
        for pg, r in bad:
            print('LOCAL_NG', pg, r)
        print('LOCAL 壊れた画像 %d件' % len(bad))
        rc = rc or (2 if bad else 0)
    if '--prod' in argv:
        bad, np, nu = check_prod()
        for b in bad:
            print('PROD_NG', *b)
        print('PROD ページ%d 画像%d 壊れた画像 %d件' % (np, nu, len(bad)))
        rc = rc or (2 if bad else 0)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv))
