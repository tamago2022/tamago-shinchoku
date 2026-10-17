# -*- coding: utf-8 -*-
"""Genspark の納品HTML（本文・章立て・曲と画像の選定・出典）を、工場側の受け持ちで「確定した型」に仕上げる（2026-10-18）。

分担（#1015/#1018 で Genspark と確定）：Genspark＝本文HTML。工場＝<head>のメタ（og:url等）・曲ページへのリンク・i18nのキー・画像の移し替え。
型の正本＝怒れる人々 vol.1（CLAUDE.md「【10-18確定】マガジンの正式な型」）。

使い方：
  python3 tools/magazine/nouhin_shiage.py SPEC.json            → status/magazine_prod/<name>（＋画像・訳キー一覧）
  python3 tools/magazine/nouhin_shiage.py SPEC.json --i18n TR.json → 訳を足して <name>.i18n.json も出す
  python3 tools/magazine/nouhin_shiage.py --self-test

SPEC（JSON）：
  in        Genspark の HTML（または今の本番の写し）
  name      本番のファイル名（public/magazine/<name>）
  key       mag_build.OTHERS のキー（ほかの特集の並びで自分を外すため）
  title/desc/og_image_yt  シェア表示（og:title・og:description・og:image）
  hero_yt   ヘッダーの絵（取り上げた曲のサムネイル。sspark 等の仮置きは使わない）
  imgs      {sspark のID: "drop" | {"file": 手元の画像, "page","credit","lic"（差し替えのとき）, "cap"（キャプションを替えるとき）}}
            ★自由ライセンス（CC0/PD/CC BY/BY-SA）だけ残す。観光サイト・雑誌・料理ブログ・AI画像サイトの写真は drop か差し替え。
  songs     {動画ID: 曲ページURL}（coverGuideLite で アーティスト＋曲名 が一致したものだけ。推測で作らない）
画像は幅960のwebp（軽く・遅延読み込み・幅と高さつき）にして status/magazine_prod/assets/<key>/ に置く（本番では /magazine/assets/<key>/）。
"""
import io, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mag_build as MB  # noqa: E402

REPO = MB.REPO
PROD = os.path.join(REPO, 'status/magazine_prod')
FREE_HINT = re.compile(r'パブリックドメイン|Public Domain|CC0|CC BY|Wikimedia|PICRYL|GetArchive|Pixnio|NegativeSpace|NASA', re.I)


def webp(src, dst, maxw=960):
    from PIL import Image
    im = Image.open(src)
    im = im.convert('RGB')
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst, 'WEBP', quality=76, method=6)
    return im.width, im.height


def fix_images(h, spec):
    key = spec['key']
    n = [0]
    report = []

    def one(m):
        blk = m.group(0)
        sid = re.search(r'sspark\.genspark\.ai/i/([A-Za-z0-9]+)', blk)
        if not sid:
            return blk
        sid = sid.group(1)
        rule = spec.get('imgs', {}).get(sid)
        if rule is None:
            cr = re.search(r'class="cw-credit">(.*?)</span>', blk, re.S)
            if cr and FREE_HINT.search(cr.group(1)):
                report.append('★指定なし（自由ライセンス表記あり・画像が無いので外す）: ' + sid)
            else:
                report.append('外した（ライセンス不明）: ' + sid)
            return ''
        if rule == 'drop':
            report.append('外した: ' + sid)
            return ''
        n[0] += 1
        rel = 'assets/%s/%02d.webp' % (key, n[0])
        w, hh = webp(rule['file'], os.path.join(PROD, rel))
        alt = re.search(r'alt="([^"]*)"', blk)
        alt = alt.group(1) if alt else ''
        blk = re.sub(r'<img[^>]*>', '<img src="%s" width="%d" height="%d" alt="%s" loading="lazy" decoding="async"/>' % (rel, w, hh, alt), blk, count=1)
        if rule.get('page'):
            cr = '<span class="cw-credit">写真:<a href="%s" rel="noopener" target="_blank">%s</a> / %s / Wikimedia Commons</span>' % (
                MB.e(rule['page']), MB.e(rule.get('credit') or 'Wikimedia Commons'), MB.e(rule.get('lic') or ''))
            blk = re.sub(r'<span class="cw-credit">.*?</span>', cr, blk, count=1, flags=re.S)
        if rule.get('cap'):
            blk = re.sub(r'(<figcaption>).*?(<span class="cw-credit">)', lambda q: q.group(1) + MB.e(rule['cap']) + q.group(2), blk, count=1, flags=re.S)
        report.append('移した: %s → %s (%dx%d)' % (sid, rel, w, hh))
        return blk

    h = re.sub(r'<div class="cw-interlude"><figure>.*?</figure></div>', one, h, flags=re.S)
    return h, report


def fix_head(h, spec):
    url = MB.BASE + spec['name']
    img = 'https://i.ytimg.com/vi/%s/maxresdefault.jpg' % (spec.get('og_image_yt') or spec['hero_yt'])
    h = re.sub(r'<link[^>]*rel="canonical"[^>]*>|<meta[^>]*(?:property="og:|name="twitter:|name="description")[^>]*>\s*', '', h)
    h = re.sub(r'<link as="image" href="https://sspark[^"]*"[^>]*>', '', h)
    t, d = MB.e(spec['title']), MB.e(spec['desc'])
    meta = ('<meta name="description" content="%s"/><link rel="canonical" href="%s"/>'
            '<meta property="og:type" content="article"/><meta property="og:site_name" content="ごきげん補給所"/>'
            '<meta property="og:title" content="%s"/><meta property="og:description" content="%s"/>'
            '<meta property="og:url" content="%s"/><meta property="og:image" content="%s"/>'
            '<meta property="og:image:width" content="1280"/><meta property="og:image:height" content="720"/>'
            '<meta name="twitter:card" content="summary_large_image"/><meta name="twitter:title" content="%s"/>'
            '<meta name="twitter:description" content="%s"/><meta name="twitter:image" content="%s"/>') % (d, url, t, d, url, img, t, d, img)
    h = h.replace('</title>', '</title>' + meta, 1)
    # ヘッダーの絵＝曲のサムネイル
    h = re.sub(r'(<div class="cw-hero__bg"[^>]*>\s*<img )([^>]*?)src="[^"]*"', lambda m: m.group(1) + m.group(2) + 'src="https://i.ytimg.com/vi/%s/maxresdefault.jpg"' % spec['hero_yt'], h, count=1)
    h = re.sub(r'(<div aria-hidden="true" class="cw-hero__bg">\s*<img )([^>]*?)src="[^"]*"', lambda m: m.group(1) + m.group(2) + 'src="https://i.ytimg.com/vi/%s/maxresdefault.jpg"' % spec['hero_yt'], h, count=1)
    return h


def fix_songs(h, spec):
    songs = spec.get('songs') or {}

    def one(m):
        fig = m.group(0)
        if 'cw-video__page' in fig:
            return fig
        yt = re.search(r'data-yt-cover="([^"]+)"', fig)
        u = songs.get(yt.group(1)) if yt else None
        if not u:
            return fig
        return fig.replace('</figcaption>', '<a class="cw-video__page" data-i18n="c_songpage" href="%s">この曲のページへ →</a></figcaption>' % MB.e(u), 1)
    return re.sub(r'<figure class="cw-video[^"]*">.*?</figure>', one, h, flags=re.S)


def stamp_keep(h):
    """本文の訳キー（k1..）を要素に書き込む。すでに data-i18n を持つ要素（共通部品の c_…）はそのまま。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(h, 'html.parser')
    main = soup.find('main')
    used = {el['data-i18n'] for el in main.select('[data-i18n]')}
    n = max([int(k[1:]) for k in used if re.fullmatch(r'k\d+', k)] or [0])
    seen = set()
    for q in MB.I18N_SEL:
        for el in main.select(q):
            if id(el) in seen or el.has_attr('data-i18n') or any(id(a) in seen or a.has_attr('data-i18n') for a in el.parents):
                continue
            if not re.search(r'[぀-ヿ一-鿿]', el.get_text()):
                continue
            n += 1; seen.add(id(el)); el['data-i18n'] = 'k%d' % n
    out = str(soup)
    out = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', out)
    return out


def keys(h):
    """訳す人向け：k キー → 日本語（出典リンクは [[1]] [[2]]…）。"""
    from bs4 import BeautifulSoup
    main = BeautifulSoup(h, 'html.parser').find('main')
    out = {}
    for el in main.select('[data-i18n]'):
        k = el['data-i18n']
        if not re.fullmatch(r'k\d+', k):
            continue
        s = el.decode_contents().strip()
        i = [0]

        def ph(m):
            i[0] += 1
            return '[[%d]]' % i[0]
        out[k] = re.sub(r'<a [^>]*class="cw-src"[^>]*>.*?</a>', ph, s, flags=re.S)
    return out


def add_switch(h, name):
    if 'class="cw-lang"' in h:
        h = re.sub(r'<label class="cw-lang".*?</label>', '', h, flags=re.S)
        h = re.sub(r'<script>\(function\(\)\{var L=.*?</script>', '', h, flags=re.S)
        h = h.replace(MB.I18N_CSS, '')
    h = re.sub(r'(<nav[^>]*class="cw-nav"[^>]*>.*?)</nav>', lambda m: m.group(1) + MB.i18n_switch() + '</nav>', h, count=1, flags=re.S)
    h = h.replace('</style>', MB.I18N_CSS + '</style>', 1)
    return h.replace('</body>', MB.i18n_script(None, name.replace('.html', '.i18n.json')) + '</body>', 1)


def build(spec):
    h = open(spec['in'], encoding='utf-8').read()
    h = re.sub(r'<div class="cw-allback"><a href="https://joy-relief-station\.lovable\.app/"[^>]*>ごきげん補給所へ戻る →</a></div>', '', h)
    h, rep = fix_images(h, spec)
    h = fix_head(h, spec)
    h = fix_songs(h, spec)
    h = add_switch(h, spec['name'])
    h = MB.unify_tail(h, spec['key'])
    h = MB.unify_look(h)
    h = stamp_keep(h)
    h = MB.unify_look(h)   # bs4 で崩れた並びを戻す（何度通しても同じ）
    return h, rep


def main(argv):
    spec = json.load(open(argv[1], encoding='utf-8'))
    h, rep = build(spec)
    bad = MB.look_check(h)
    out = os.path.join(PROD, spec['name'])
    open(out, 'w', encoding='utf-8').write(h)
    k = keys(h)
    kp = os.path.join(PROD, spec['name'].replace('.html', '.keys.json'))
    json.dump(k, open(kp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if '--i18n' in argv:
        tr = json.load(open(argv[argv.index('--i18n') + 1], encoding='utf-8'))
        for l, d in MB.common_i18n().items():
            tr.setdefault(l, {}).update(d)
        miss = {l: [x for x in k if x not in tr.get(l, {})] for l in MB._LG4}
        json.dump(tr, open(out.replace('.html', '.i18n.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        print('訳の抜け:', {l: len(v) for l, v in miss.items()})
    print('\n'.join(rep))
    print('OK' if not bad else 'NG ' + '／'.join(bad), out, len(h.encode()), 'keys=%d' % len(k))
    return 0 if not bad else 2


def self_test():
    h = ('<html><head><title>t</title></head><body><main class="cw"><div class="cw-interlude"><figure><img src="https://sspark.genspark.ai/i/AAA?width=2560"/>'
         '<figcaption>x<span class="cw-credit">写真:<a href="https://www.cntraveler.com/">CN</a></span></figcaption></figure></div>'
         '<figure class="cw-video cw-video--main"><button data-yt-cover="ID1"></button><figcaption><span class="cw-video__name"><b>A</b></span></figcaption></figure></main></body></html>')
    out, rep = fix_images(h, {'key': 't', 'imgs': {}})
    assert 'sspark' not in out and 'ライセンス不明' in rep[0], rep
    out = fix_songs(h, {'songs': {'ID1': 'https://x/cover-guide?artist=a&song=b'}})
    assert 'cw-video__page' in out and 'artist=a&amp;song=b' in out
    out = fix_head(h, {'name': 'n.html', 'title': 'T', 'desc': 'D', 'hero_yt': 'ID1'})
    assert 'og:url" content="https://joy-relief-station.lovable.app/magazine/n.html"' in out and 'twitter:card' in out
    print('SELF-TEST OK')
    return 0


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    sys.exit(main(sys.argv))
