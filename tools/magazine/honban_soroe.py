#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""マガジンの控え（status/magazine_prod/）が本番より古いまま一括公開して、本番を戻す事故を止める関所（2026-10-30）。

実例（2026-10-30）：
  怒れる人々（ikareru-01.html）は本番（joy-relief-station main の public/magazine/）で
  10-29 に「2本目のきっかけ動画」（5acf8d616）と「うちのYouTubeの一枚＝レニー・クラヴィッツのショート」（957c1a2c7）が入ったが、
  工場の控えは 10-22 のまま。put_prod.sh を走らせると、控えで本番を丸ごと上書きして2つとも消えるところだった。
  控え9本・訳9本が本番とずれていた。

決まり：
  本番（main）のファイルが「工場が最後に置いた／そろえた版」から変わっていたら、置かない（exit 2）。
  先に --soroe で本番を控えに取り込み（本番が正）、その上に自分の直しを重ねてから置く。

台帳：status/magazine_prod/.honban_sha.json  {本番のパス: {"sha": 置いた/そろえた時の git blob sha, "at": 日時}}

使い方（Mac の上。gh を使う。サンドボックスからは status/mac_jobs/pending に置く）
  python3 tools/magazine/honban_soroe.py --check 控え...     置く前の関所（put_prod.sh・sokkou.py が通す）。古い控えがあれば exit 2
  python3 tools/magazine/honban_soroe.py --kiroku 控え...    置けた控えの sha を台帳へ（put_prod.sh・sokkou.py が置くたびに）
  python3 tools/magazine/honban_soroe.py --soroe [控え...]   本番（main）を控えへ取り込む（前の控えは status/honban_soroe/mae/ へ）。省略時は控え全部
  python3 tools/magazine/honban_soroe.py --hikaku            控えと本番のずれの一覧だけ（書き換えない）
  python3 tools/magazine/honban_soroe.py --self-test
控えのパス（status/magazine_prod/x.html）→ 本番のパス（public/magazine/x.html）。assets も同じ並び。
"""
import base64, hashlib, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PROD = os.path.join(REPO, 'status', 'magazine_prod')
DAICHO = os.path.join(PROD, '.honban_sha.json')
MAE = os.path.join(REPO, 'status', 'honban_soroe', 'mae')
JRS = 'tamago2022/joy-relief-station'
ENV = dict(os.environ, PATH=os.path.expanduser('~/.local/bin') + ':/usr/local/bin:/opt/homebrew/bin:' + os.environ.get('PATH', ''))


def blob_sha(b):
    return hashlib.sha1(b'blob %d\0' % len(b) + b).hexdigest()


def dst_of(local):
    rel = os.path.relpath(os.path.abspath(local), PROD)
    if rel.startswith('..'):
        return None
    return 'public/magazine/' + rel.replace(os.sep, '/')


def load():
    try:
        return json.load(open(DAICHO, encoding='utf-8'))
    except Exception:
        return {}


def save(d):
    tmp = DAICHO + '.tmp'
    json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, DAICHO)


def gh_sha(dst):
    """本番（main）の blob sha。無ければ ''。取れなければ None。"""
    p = subprocess.run(['gh', 'api', 'repos/%s/contents/%s?ref=main' % (JRS, dst), '--jq', '.sha'],
                       capture_output=True, text=True, env=ENV)
    if p.returncode == 0:
        return p.stdout.strip()
    return '' if '404' in (p.stderr + p.stdout) else None


def gh_raw(dst):
    p = subprocess.run(['gh', 'api', 'repos/%s/contents/%s?ref=main' % (JRS, dst), '-H', 'Accept: application/vnd.github.raw'],
                       capture_output=True, env=ENV)
    return p.stdout if p.returncode == 0 else None


def gh_last(dst):
    p = subprocess.run(['gh', 'api', 'repos/%s/commits?path=%s&per_page=1' % (JRS, dst),
                        '--jq', '.[0] | .sha[0:9] + " " + .commit.author.date + " " + .commit.message[0:50]'],
                       capture_output=True, text=True, env=ENV)
    return p.stdout.strip().replace('\n', ' ')


def kensa(locals_, sha_of=gh_sha, last_of=gh_last, daicho=None):
    """古い控えの一覧 [(控え, 理由)]。空なら置いてよい。"""
    d = load() if daicho is None else daicho
    ng = []
    for loc in locals_:
        dst = dst_of(loc)
        if not dst or not os.path.isfile(loc):
            continue
        cur = sha_of(dst)
        if cur is None:
            ng.append((loc, '本番の sha が取れない（gh）。確かめられないので置かない'))
            continue
        if cur == '':
            continue  # 本番に無い＝新しいファイル
        mine = blob_sha(open(loc, 'rb').read())
        if mine == cur:
            continue  # 中身が同じ
        kiroku = (d.get(dst) or {}).get('sha')
        if kiroku == cur:
            continue  # 本番は工場が最後に置いた/そろえた版のまま＝控えの直しは本番より新しい
        why = '本番が工場の知らない変更で進んでいる' if kiroku else '台帳に記録なし（そろえたことがない）'
        ng.append((loc, '%s｜本番の最後の変更：%s' % (why, last_of(dst))))
    return ng


def kiroku(locals_, daicho=None):
    d = load() if daicho is None else daicho
    for loc in locals_:
        dst = dst_of(loc)
        if dst and os.path.isfile(loc):
            d[dst] = {'sha': blob_sha(open(loc, 'rb').read()), 'at': time.strftime('%F %T')}
    if daicho is None:
        save(d)
    return d


def hikae_all():
    out = []
    for n in sorted(os.listdir(PROD)):
        if n.endswith('.html') or n.endswith('.i18n.json'):
            out.append(os.path.join(PROD, n))
    return out


def soroe(locals_, raw_of=gh_raw, daicho=None):
    """本番（main）を控えへ。前の控えは mae/<日時>/ へ。本番に無い控えは触らない。"""
    d = load() if daicho is None else daicho
    stamp = time.strftime('%Y%m%d-%H%M%S')
    kaeta = []
    for loc in locals_:
        dst = dst_of(loc)
        if not dst:
            continue
        b = raw_of(dst)
        if not b:
            continue
        old = open(loc, 'rb').read() if os.path.isfile(loc) else None
        if old != b:
            if old is not None:
                os.makedirs(os.path.join(MAE, stamp), exist_ok=True)
                shutil.copyfile(loc, os.path.join(MAE, stamp, os.path.basename(loc)))
            open(loc, 'wb').write(b)
            kaeta.append(os.path.basename(loc))
        d[dst] = {'sha': blob_sha(b), 'at': time.strftime('%F %T'), 'soroe': True}
    if daicho is None:
        save(d)
    return kaeta


def self_test():
    import tempfile
    global PROD, MAE
    keep = (PROD, MAE)
    t = tempfile.mkdtemp(prefix='honban_soroe_test-')
    try:
        PROD, MAE = t, os.path.join(t, 'mae')
        a = os.path.join(t, 'a.html'); open(a, 'wb').write(b'local-new')
        honban = {'public/magazine/a.html': b'prod-v1'}
        sha_of = lambda dst: blob_sha(honban[dst]) if dst in honban else ''
        last = lambda dst: 'x'
        d = {}
        assert kensa([a], sha_of, last, d), '台帳なし・中身違い→止まるはず'
        soroe([a], lambda dst: honban.get(dst), d)
        assert open(a, 'rb').read() == b'prod-v1' and not kensa([a], sha_of, last, d), 'そろえた直後は通るはず'
        open(a, 'wb').write(b'prod-v1+mine')
        assert not kensa([a], sha_of, last, d), '本番そのまま＋自分の直し→通るはず'
        honban['public/magazine/a.html'] = b'prod-v2-kravitz'
        assert kensa([a], sha_of, last, d), '本番がよそで進んだ→止まるはず（今回の事故）'
        kiroku([a], d)
        honban['public/magazine/a.html'] = b'prod-v1+mine'
        assert not kensa([a], sha_of, last, d), '置いた版のまま→通るはず'
        b = os.path.join(t, 'b.html'); open(b, 'wb').write(b'new')
        assert not kensa([b], sha_of, last, d), '本番に無い新しいファイル→通るはず'
        assert kensa([a], lambda dst: None, last, d), 'sha が取れない→止まるはず'
        print('SELF-TEST OK')
        return 0
    finally:
        PROD, MAE = keep
        shutil.rmtree(t, ignore_errors=True)


def main(argv):
    if '--self-test' in argv:
        return self_test()
    files = [os.path.join(REPO, a) if not os.path.isabs(a) else a for a in argv[2:] if not a.startswith('--')]
    if argv[1:2] == ['--check']:
        ng = kensa(files)
        for loc, why in ng:
            print('HONBAN_SOROE: STOP ｜ %s ｜ %s' % (os.path.relpath(loc, REPO), why))
        if ng:
            print('→ 先に python3 tools/magazine/honban_soroe.py --soroe %s で本番を控えに取り込み、直しを重ね直してから置く' %
                  ' '.join(os.path.relpath(l, REPO) for l, _ in ng))
            return 2
        print('HONBAN_SOROE: PASS（%d本）' % len(files))
        return 0
    if argv[1:2] == ['--kiroku']:
        kiroku(files); return 0
    if argv[1:2] == ['--soroe']:
        k = soroe(files or hikae_all())
        print('そろえた：%s' % (', '.join(k) or 'なし（全部本番と同じ）'))
        return 0
    if argv[1:2] == ['--hikaku']:
        for loc in hikae_all():
            dst = dst_of(loc); cur = gh_sha(dst); mine = blob_sha(open(loc, 'rb').read())
            print('%s %s' % ('同じ' if cur == mine else ('本番に無い' if cur == '' else 'ずれ'), os.path.basename(loc)))
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
