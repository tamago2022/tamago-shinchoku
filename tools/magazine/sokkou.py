# -*- coding: utf-8 -*-
"""Genspark の叩きを「60点でも即本番」に出す（2026-10-18 たまごさん方針確定）。

流れ：拾う（claude_uketsuke）→ ここ（型の最低限）→ main へ置く → 公開（Lovable）→ バックナンバーに載せる → 本番URLを Dispatch へ。
審査・配分ゲートで止めない。85点への磨き込みは、あとから積む改善便（1〜2週間）でやる。

型の最低限（ここで必ずやること）：
  ・読者に見える制作メモを消す（未確認・要確認・「公開前に確認」・埋め込みやクレジットの説明）。「（未確認）」付きの文はその文ごと外す
  ・ライセンスの無い写真は外す（自由ライセンスの置き場の写真だけ webp にして自前ホストへ移す）。公開は止めない
  ・<head>：og/canonical/twitter、ヘッダーの絵＝最初の曲のサムネイル
  ・曲ページ導線：動画IDが coverGuideLite の曲と完全一致したものだけ（名前の一致では紐付けない＝sekisho-artist-song）
  ・この特集をシェア／ごきげん補給所をフォロー／きっかけの動画／OTHER MAGAZINES／すべてのバックナンバー（mag_build の共通部品）
  ・バックナンバー（tools/magazine/backnumber_auto.json → backnumber.py が「新着」に載せる）
多言語の切替は訳ができてから（改善便）。訳の無い切替は出さない。

使い方（Mac）：python3 tools/magazine/sokkou.py <叩きのHTML> <本番名.html> [--num Issue番号] [--put]
  --put を付けると joy-relief-station main へ gh api で置き、公開を試し、だめなら Dispatch へ「公開待ち」。
逆テスト：python3 tools/magazine/sokkou.py --self-test
"""
import base64, json, os, re, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import mag_build as MB  # noqa: E402
import nouhin_shiage as NS  # noqa: E402

REPO = MB.REPO
PROD = os.path.join(REPO, 'status/magazine_prod')
SRC = os.path.join(REPO, 'status/magazine_src')
JRS = 'tamago2022/joy-relief-station'
AUTO_BN = os.path.join(HERE, 'backnumber_auto.json')
# 自由ライセンスの置き場（ここ以外の写真は外す）
FREE_HOSTS = ('commons.wikimedia.org', 'upload.wikimedia.org', 'picryl.com', 'getarchive.net', 'publicdomainpictures.net',
              'pixnio.com', 'negativespace.co', 'nasa.gov', 'loc.gov', 'archives.gov', 'flickr.com/commons')
NOTE_WORDS = r'未確認|要確認|確認できていない|確認できず|公開前に|ライセンス確認済み|埋め込んでいます|埋め込みで参照|サイトDBで'
PATHS = [os.path.expanduser(p) for p in ('~/.npm-global/bin', '~/.local/bin')] + ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin']
ENV = dict(os.environ, PATH=':'.join(PATHS + [os.environ.get('PATH', '')]))


def strip_notes(h):
    """読者に見える制作メモを消す。消したものの一覧も返す。"""
    gone = []

    def rm(m):
        gone.append(re.sub(r'<[^>]+>', '', m.group(0))[:80])
        return ''
    h = re.sub(r'<span class="cw-video__cap">[^<]*(?:%s)[^<]*</span>' % NOTE_WORDS, rm, h)
    h = re.sub(r'<li[^>]*>(?:(?!</li>).)*?(?:%s)(?:(?!</li>).)*</li>\s*' % NOTE_WORDS, rm, h, flags=re.S)
    h = re.sub(r'<p class="cw-note">(?:(?!</p>).)*?(?:%s)(?:(?!</p>).)*</p>' % NOTE_WORDS, rm, h, flags=re.S)
    h = re.sub(r'<strong>[^<]*(?:%s)[^<]*</strong>' % NOTE_WORDS, rm, h)
    # 本文の「（未確認）」付きの文は、その文ごと外す（裏が取れないことは書かない）
    h = re.sub(r'(?<=[。>])[^。<>]*?[（(](?:未確認|要確認)[)）][^。<>]*。', rm, h)
    h = re.sub(r'[（(](?:未確認|要確認)[)）]', rm, h)
    return h, gone


def image_rules(h, key, workdir):
    """sspark の写真：クレジットが自由ライセンスの置き場なら取って webp、そうでなければ外す。"""
    rules, rep = {}, []
    for blk in re.findall(r'<div class="cw-interlude"><figure>.*?</figure></div>', h, flags=re.S):
        sid = re.search(r'sspark\.genspark\.ai/i/([A-Za-z0-9]+)', blk)
        if not sid:
            continue
        sid = sid.group(1)
        cr = re.search(r'class="cw-credit">.*?href="([^"]+)"', blk, re.S)
        host = cr.group(1) if cr else ''
        if not any(f in host for f in FREE_HOSTS):
            rules[sid] = 'drop'; rep.append('外した（ライセンスの無い置き場）: ' + host[:70])
            continue
        dst = os.path.join(workdir, sid)
        try:
            if not os.path.exists(dst):
                d = urllib.request.urlopen(urllib.request.Request('https://sspark.genspark.ai/i/' + sid, headers={'User-Agent': 'Mozilla/5.0'}), timeout=40).read()
                open(dst, 'wb').write(d)
            rules[sid] = {'file': dst}
        except Exception as e:
            rules[sid] = 'drop'; rep.append('外した（取れない）: %s %r' % (sid, e))
    return rules, rep


def auto_songs(h):
    """動画ID が coverGuideLite の曲と完全一致したものだけ（名前の一致では紐付けない）。"""
    import magazine_gate as MG
    idx = MG.load_lite()
    out = {}
    for yt in re.findall(r'data-yt-cover="([^"]+)"', h):
        hit = idx['byyt'].get(yt)
        if hit and len(hit) == 1:
            a, s = hit[0][0], hit[0][2]
            out[yt] = 'https://joy-relief-station.lovable.app/cover-guide?artist=%s&song=%s' % (a, s)
    return out


def spec_for(src, name, workdir):
    h = open(src, encoding='utf-8').read()
    key = re.sub(r'[^a-z0-9]', '', name.replace('.html', '').lower())[:16]
    title = (re.search(r'<title>([^<｜|]*)', h) or [None, name])[1].strip()
    lead = re.search(r'<p class="cw-hero__lead">(.*?)</p>', h, re.S)
    desc = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', lead.group(1))).strip()[:160] if lead else title
    yts = re.findall(r'data-yt-cover="([^"]+)"', h)
    rules, rep = image_rules(h, key, workdir)
    return {'in': src, 'name': name, 'key': key, 'title': title, 'desc': desc, 'hero_yt': yts[0] if yts else '',
            'imgs': rules, 'songs': auto_songs(h)}, rep


def build(src, name):
    os.makedirs(os.path.join(SRC, name.replace('.html', '')), exist_ok=True)
    work = os.path.join(SRC, name.replace('.html', ''))
    raw = open(src, encoding='utf-8').read()
    clean, gone = strip_notes(raw)
    cp = os.path.join(work, 'genspark_clean.html')
    open(cp, 'w', encoding='utf-8').write(clean)
    spec, rep = spec_for(cp, name, work)
    json.dump(spec, open(os.path.join(work, 'spec.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    h, rep2 = NS.build(spec)
    h = re.sub(r'<label class="cw-lang".*?</label>', '', h, flags=re.S)           # 訳ができるまで切替は出さない
    h = re.sub(r'<script>\(function\(\)\{var L=.*?</script>', '', h, flags=re.S)
    h, gone2 = strip_notes(h)
    open(os.path.join(PROD, name), 'w', encoding='utf-8').write(h)
    bad = MB.look_check(h)
    return h, {'gone': gone + gone2, 'img': rep + rep2, 'songs': len(spec['songs']), 'bad': bad, 'key': spec['key'], 'title': spec['title']}


def add_backnumber(name, title, kicker):
    d = json.load(open(AUTO_BN, encoding='utf-8')) if os.path.exists(AUTO_BN) else []
    url = MB.BASE + name
    if not any(x['url'] == url for x in d):
        d.insert(0, {'title': title, 'kicker': kicker, 'url': url, 'at': time.strftime('%F')})
        json.dump(d, open(AUTO_BN, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(HERE, 'backnumber.py')], check=True, cwd=REPO)


def gh_put(local, dst, msg):
    sha = subprocess.run(['gh', 'api', 'repos/%s/contents/%s?ref=main' % (JRS, dst), '--jq', '.sha'], capture_output=True, text=True, env=ENV).stdout.strip()
    body = {'message': msg, 'branch': 'main', 'content': base64.b64encode(open(local, 'rb').read()).decode()}
    if sha and not sha.startswith('{'):
        body['sha'] = sha
    p = subprocess.run(['gh', 'api', '-X', 'PUT', 'repos/%s/contents/%s' % (JRS, dst), '--input', '-', '--jq', '.commit.sha'],
                       input=json.dumps(body), capture_output=True, text=True, env=ENV)
    return p.returncode == 0


def put_all(name, key):
    ok = True
    files = [(os.path.join(PROD, name), 'public/magazine/' + name), (os.path.join(PROD, 'backnumber.html'), 'public/magazine/backnumber.html'),
             (os.path.join(PROD, 'backnumber.i18n.json'), 'public/magazine/backnumber.i18n.json')]
    ad = os.path.join(PROD, 'assets', key)
    if os.path.isdir(ad):
        files += [(os.path.join(ad, f), 'public/magazine/assets/%s/%s' % (key, f)) for f in sorted(os.listdir(ad))]
    for loc, dst in files:
        ok &= gh_put(loc, dst, '即公開（叩き・60点で出して直す）：%s' % dst)
    return ok


def deploy():
    """Lovable の公開。鍵が切れていれば False（Dispatch が押す）。"""
    p = subprocess.run([sys.executable, os.path.join(REPO, 'tools/98403_lovable_publish_mcp.py')], capture_output=True, text=True, timeout=170, env=ENV)
    out = (p.stdout or '') + (p.stderr or '')
    return ('need_consent' not in out and 'http=403' not in out and 'http=401' not in out and p.returncode == 0), out[-300:]


def main(argv):
    src, name = argv[1], argv[2]
    num = argv[argv.index('--num') + 1] if '--num' in argv else None
    h, r = build(src, name)
    print(json.dumps({k: (v if k != 'gone' else len(v)) for k, v in r.items()}, ensure_ascii=False))
    add_backnumber(name, r['title'], '新着')
    # 曲ページの関所：公開と同時に回し、足りない所を埋める便を積む
    try:
        import magazine_gate as MG
        MG.run([name], tsumu=True)
    except Exception as e:
        print('magazine_gate で例外', repr(e))
    if '--put' not in argv:
        return 0
    if not put_all(name, r['key']):
        print('main へ置けない'); return 2
    os.makedirs('/private/tmp/q98403', exist_ok=True)
    ok, out = deploy()
    sys.path.insert(0, os.path.dirname(HERE))
    import claude_uketsuke as cu
    url = MB.BASE + name
    cu.outbox('【即公開】%s' % r['title'] if ok else '【公開待ち】%s' % r['title'],
              ('本番：%s' % url) if ok else ('main に入りました。Lovable の公開（deploy_project）を押してください：%s' % url), [url])
    print('deploy', ok, out[-160:])
    return 0


def self_test():
    h, g = strip_notes('<p>あ。番組に出たと伝えられています（未確認）。い。</p><span class="cw-video__cap">放送日は確認できていない</span><li>写真はライセンス確認済み</li>')
    assert '未確認' not in h and '確認できていない' not in h and 'ライセンス' not in h and 'あ。' in h and 'い。' in h, h
    print('SELF-TEST OK'); return 0


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    sys.exit(main(sys.argv))
