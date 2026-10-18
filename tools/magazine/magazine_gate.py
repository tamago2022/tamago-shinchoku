# -*- coding: utf-8 -*-
"""マガジンの関所（magazine_gate）— 2026-10-18 たまごさん「何回も言うけど、全部だよ。徹底して」。

マガジンに載っている曲は全部：
  ① 独立した曲ページがある
  ② マガジンのリンクで本当にその曲ページに飛べる（本番で200・ページの題がその曲。アーティストの棚に落ちていない）
  ③ 飛んだ先の関連（おすすめ）が4曲以上（1〜2曲は禁止）
  ④ コピーとメモがある（メモに年号・数字があれば出典 src も）
を機械で確かめる。

曲の決め方（アーティストの取り違え禁止＝sekisho-artist-song の基準）：
  ・マガジンの動画ID が coverGuideLite の曲の動画ID と完全一致（1曲だけ）→ その曲
  ・すでに貼ってあるリンクは、リンク先の曲のアーティスト名がマガジンの表記と一致する時だけ正しいとする
  ・名前（アーティスト名＋曲名）の一致だけでは結ばない（「候補」として直す便に渡すだけ）
その場で直すもの：①が動画IDで確定しているのにリンクが無い → リンクを貼る（tools/magazine/song_pages.json にも足す＝組み直しても消えない）
直す便に積むもの：曲ページが無い（作る）／関連が4未満（足す）／コピー・メモが無い（出典を取ってから書く）／リンクの取り違え

使い方（Mac）：
  python3 tools/magazine/magazine_gate.py            → 全マガジンを一巡（本番の main を一時の作業場に出して見る）。直す便を積み、Dispatch に1行
  python3 tools/magazine/magazine_gate.py --daily    → 1日1回だけ（心臓の相乗り。20時間の間引き）
  python3 tools/magazine/magazine_gate.py --only uke-01.html   → その号だけ（即公開 sokkou.py から）
  python3 tools/magazine/magazine_gate.py --self-test
作るもの：status/public/magazine_gate.json（結果）／status/magazine_gate.log／一時の作業場 $TMPDIR/mgate_*（終わったら必ず消す）
台帳：tools/jidou_daicho.json の "magazine/magazine_gate.py"
"""
import html as H
import json, os, re, shutil, subprocess, sys, tempfile, time, unicodedata, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
ST = os.path.join(REPO, 'status')
OUT = os.path.join(ST, 'public', 'magazine_gate.json')
LOG = os.path.join(ST, 'magazine_gate.log')
STAMP = os.path.join(ST, '.magazine_gate_daily')
STATE = os.path.join(ST, 'magazine_gate_state.json')
SONG_PAGES = os.path.join(HERE, 'song_pages.json')
JOGAI = os.path.join(HERE, 'magazine_gate_jogai.json')   # 曲ではない動画（ドキュメンタリー等）：{"動画ID": "理由"}
LITE_CACHE = os.path.join(ST, 'magazine_gate_lite.ts')
JRS_URL = 'https://github.com/tamago2022/joy-relief-station.git'
NM = os.path.expanduser('~/tamago/jrs_fix/node_modules')
SITE = 'https://joy-relief-station.lovable.app'
PROD_LOCAL = os.path.join(ST, 'magazine_prod')
SKIP = {'backnumber.html'}
PATHS = [os.path.expanduser(p) for p in ('~/.npm-global/bin', '~/.local/bin')] + ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin']
ENV = dict(os.environ, PATH=':'.join(PATHS + [os.environ.get('PATH', '')]))
MIN_RELATED = 4


def log(m):
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%F %T'), m))
        ls = open(LOG, encoding='utf-8').read().splitlines()
        if len(ls) > 600:
            open(LOG, 'w', encoding='utf-8').write('\n'.join(ls[-400:]) + '\n')
    except Exception:
        pass


def norm(s):
    s = unicodedata.normalize('NFKC', H.unescape(s or '')).lower()
    return re.sub(r'[\s・･.\-_\'’"“”「」『』()（）!！?？,，、。:：/&＆]', '', s)


# ────────── 曲の名簿（coverGuideLite）──────────
def parse_lite(text):
    arts = []
    for l in text.splitlines():
        l = l.strip().rstrip(',')
        if l.startswith('{"id"'):
            try:
                arts.append(json.loads(l))
            except Exception:
                pass
    byyt, byid = {}, {}
    for a in arts:
        byid[a['id']] = a
        for s in a['songs']:
            if s.get('youtubeId'):
                byyt.setdefault(s['youtubeId'], []).append((a['id'], a['name'], s['id'], s['title']))
    return {'byyt': byyt, 'byid': byid, 'n': len(arts)}


def load_lite(path=None):
    """作業場があればそこの名簿。無ければ6時間以内の控え、古ければ gh で取り直す。"""
    if path and os.path.exists(path):
        return parse_lite(open(path, encoding='utf-8').read())
    if not os.path.exists(LITE_CACHE) or time.time() - os.path.getmtime(LITE_CACHE) > 6 * 3600:
        p = subprocess.run(['gh', 'api', '-H', 'Accept: application/vnd.github.raw',
                            'repos/tamago2022/joy-relief-station/contents/src/lib/coverGuideLite.generated.ts?ref=main'],
                           capture_output=True, text=True, env=ENV, timeout=180)
        if p.returncode == 0 and len(p.stdout) > 100000:
            open(LITE_CACHE, 'w', encoding='utf-8').write(p.stdout)
    return parse_lite(open(LITE_CACHE, encoding='utf-8').read())


def artist_names(a):
    return {norm(x) for x in [a.get('name')] + list(a.get('aliases') or []) if x}


# ────────── マガジンから曲を抜き出す ──────────
FIG_RE = re.compile(r'<figure class="cw-video[^"]*">.*?</figure>', re.S)


def songs_in(h):
    out = []
    for fig in FIG_RE.findall(h):
        yt = re.search(r'data-yt-cover="([^"]+)"', fig)
        b = re.search(r'class="cw-video__name"[^>]*>\s*<b[^>]*>(.*?)</b>', fig, re.S)
        i = re.search(r'class="cw-video__name"[^>]*>.*?<i[^>]*>(.*?)</i>', fig, re.S)
        link = re.search(r'class="cw-video__page"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*class="cw-video__page"', fig)
        if not yt:
            continue
        artist = re.sub(r'<[^>]+>', '', b.group(1)).strip() if b else ''
        title = re.sub(r'<[^>]+>', '', i.group(1)).strip() if i else ''
        title = re.sub(r'^「(.*?)」.*$', r'\1', title) or title
        out.append({'yt': yt.group(1), 'artist': H.unescape(artist), 'title': H.unescape(title),
                    'link': H.unescape((link.group(1) or link.group(2))) if link else None})
    return out


def parse_link(u):
    m = re.search(r'/cover-guide\?(.*)$', u or '')
    if not m:
        return None
    from urllib.parse import parse_qs
    q = parse_qs(m.group(1))
    a, s = (q.get('artist') or [None])[0], (q.get('song') or [None])[0]
    return (a, s) if a and s else None


def resolve(song, lite):
    """(確定した曲キー, 状態, メモ)。名前の一致だけでは確定にしない。"""
    hits = lite['byyt'].get(song['yt']) or []
    linked = parse_link(song['link']) if song['link'] else None
    an = norm(song['artist'])
    if linked:
        a = lite['byid'].get(linked[0])
        s = next((x for x in (a or {}).get('songs', []) if x['id'] == linked[1]), None) if a else None
        if not s:
            return None, 'link_dead', 'リンク先の曲が名簿に無い：%s/%s' % linked
        if names_overlap(an, a):
            return '%s/%s' % linked, 'ok', ''
        return '%s/%s' % linked, 'link_wrong', 'リンク先のアーティスト「%s」とマガジンの表記「%s」が合わない（取り違えの疑い。同じ人の別表記なら名簿の aliases に足す）' % (a['name'], song['artist'])
    if len(hits) == 1 and names_overlap(an, lite['byid'][hits[0][0]]):
        return '%s/%s' % (hits[0][0], hits[0][2]), 'no_link', ''
    if len(hits) == 1:
        return None, 'suspect', '同じ動画が「%s」の棚に入っている（マガジンの表記「%s」と合わない＝取り違えの疑い）：%s/%s' % (hits[0][1], song['artist'], hits[0][0], hits[0][2])
    if len(hits) > 1:
        # 同じ動画が複数の棚にある：マガジンのアーティスト表記と合う1つだけなら確定
        ok = [h for h in hits if names_overlap(an, lite['byid'][h[0]])]
        if len(ok) == 1:
            return '%s/%s' % (ok[0][0], ok[0][2]), 'no_link', ''
        return None, 'ambiguous', '同じ動画が%d曲に入っている：%s' % (len(hits), '、'.join('%s/%s' % (h[0], h[2]) for h in hits[:4]))
    # 候補（名前の一致）だけ探す。確定はしない
    cand = []
    tn = norm(song['title'])
    for a in lite['byid'].values():
        if an and an in artist_names(a):
            for x in a['songs']:
                if tn and len(tn) >= 2 and norm(x['title']).startswith(tn):
                    cand.append('%s/%s' % (a['id'], x['id']))
    if cand:
        return None, 'cand', '名前が合う曲ページ（動画は別。同じ曲か確かめてからリンク）：' + '、'.join(cand[:3])
    return None, 'no_page', '曲ページが無い'


def names_overlap(an, a):
    """マガジンの表記と名簿のアーティスト（名前・別名）が合うか。「忌野清志郎 / RCサクセション」⇔「忌野清志郎 / RCサクセション / ザ・タイマーズ」のような包含も可。"""
    if not an:
        return False
    for n in artist_names(a):
        if n and (n == an or (len(min(n, an, key=len)) >= 3 and (n in an or an in n))):
            return True
    return False


# ────────── 作業場（本番 main の写し）──────────
def workspace():
    w = tempfile.mkdtemp(prefix='mgate_', dir=os.environ.get('TMPDIR') or None)
    p = subprocess.run(['git', 'clone', '-q', '--depth', '1', JRS_URL, w], capture_output=True, text=True, env=ENV, timeout=600)
    if p.returncode != 0:
        shutil.rmtree(w, ignore_errors=True)
        raise RuntimeError('作業場を作れない：' + (p.stderr or '')[:200])
    if os.path.isdir(NM):
        os.symlink(NM, os.path.join(w, 'node_modules'))
    return w


TSX = r'''
import { readFileSync, writeFileSync } from "node:fs";
import { getArtist, getRelatedProjects } from "../../src/lib/coverGuideAccess";
import { getShelfPicks } from "../../src/lib/shelfPicks";
import { getMoodSiblings } from "../../src/lib/moodThreads";
import { KANSEI_HIDDEN_SONG_KEYS } from "../../src/lib/kanseiHidden.generated";
const keys: string[] = JSON.parse(readFileSync(process.argv[2], "utf8"));
const NEEDS_SOURCE = /\d|「|『|受賞|売上|位|万枚|原曲|カバー|オリジナル/;
const out: Record<string, unknown> = {};
for (const key of keys) {
  const i = key.indexOf("/"); const a = getArtist(key.slice(0, i)); const s = a?.songs.find((x) => x.id === key.slice(i + 1));
  if (!a || !s) { out[key] = { exists: false }; continue; }
  const picks = getShelfPicks(a.id, s.id).slice(0, 6).map((p) => `${p.artistId}/${p.songId}`);
  const per = new Map<string, number>(); const mood: string[] = [];
  for (const { thread, member } of getMoodSiblings(a.id, s.id)) { const n = per.get(thread.id) ?? 0; if (n >= 2) continue; per.set(thread.id, n + 1); mood.push(`${member.artistId}/${member.songId}`); }
  const members = getRelatedProjects(a.id).map((r) => `artist:${r.id}`);
  const related = new Set([...picks, ...mood, ...members]); related.delete(key);
  const note = (s.note ?? "").trim(); const copy = ((s as { copy?: string }).copy ?? "").trim();
  const src = (s as { src?: string | string[] }).src; const srcN = Array.isArray(src) ? src.length : src ? 1 : 0;
  out[key] = { exists: true, artist: a.name, title: s.title, related: related.size, note: note.length, copy: copy.length,
    noteNeedsSrc: NEEDS_SOURCE.test(note) && srcN === 0, hidden: KANSEI_HIDDEN_SONG_KEYS.has(key), yt: s.youtubeId ?? null };
}
writeFileSync(process.argv[3], JSON.stringify(out));
'''


def song_facts(w, keys):
    kin = os.path.join(w, 'mgate_keys.json'); kout = os.path.join(w, 'mgate_out.json')
    json.dump(sorted(keys), open(kin, 'w'))
    sp = os.path.join(w, 'scripts', 'patrol', '_mgate.mts')
    open(sp, 'w', encoding='utf-8').write(TSX)
    p = subprocess.run(['npx', 'tsx', '--import', './scripts/_asset-stub.mjs', 'scripts/patrol/_mgate.mts', kin, kout],
                       cwd=w, capture_output=True, text=True, env=ENV, timeout=1500)
    if not os.path.exists(kout):
        raise RuntimeError('曲の中身を読めない：' + (p.stderr or p.stdout or '')[-300:])
    return json.load(open(kout))


def prod_ok(key, title):
    """本番でその曲ページが開くか（200・<title> が曲名で始まる＝アーティストの棚に落ちていない）。"""
    a, s = key.split('/', 1)
    from urllib.parse import quote
    u = '%s/cover-guide?artist=%s&song=%s' % (SITE, quote(a), quote(s))
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'tamago-factory/1.0'}), timeout=30) as r:
            body = r.read(60000).decode('utf-8', 'ignore')
            t = re.search(r'<title>([^<]*)', body)
            t = H.unescape(t.group(1)) if t else ''
            return r.status == 200 and '代表曲・関連アーティスト' not in t and '案内所｜' not in t, t
    except Exception as e:
        return False, repr(e)[:80]


def add_link(h, yt, key):
    a, s = key.split('/', 1)
    from urllib.parse import quote
    url = '%s/cover-guide?artist=%s&song=%s' % (SITE, quote(a, safe=''), quote(s, safe=''))
    link = '<a href="%s" class="cw-video__page" data-i18n="c_songpage">この曲のページへ →</a>' % H.escape(url, quote=True)

    def one(m):
        fig = m.group(0)
        if 'data-yt-cover="%s"' % yt not in fig or 'cw-video__page' in fig:
            return fig
        return fig.replace('</figcaption>', link + '</figcaption>', 1)
    return FIG_RE.sub(one, h), url


# ────────── 一巡 ──────────
def run(only=None, tsumu=True, put=True):
    import fcntl
    lf = open(os.path.join(ST, '.magazine_gate.lock'), 'a+')
    fcntl.flock(lf.fileno(), fcntl.LOCK_EX)   # 二重に回さない（毎日便と即公開がぶつかっても順番に）
    t0 = time.time()
    w = workspace()
    try:
        lite = load_lite(os.path.join(w, 'src/lib/coverGuideLite.generated.ts'))
        md = os.path.join(w, 'public', 'magazine')
        for n in only or []:   # 即公開の直後で、まだ main に無い号は手元の写しで見る
            loc = os.path.join(PROD_LOCAL, n)
            if os.path.exists(loc):
                shutil.copy(loc, os.path.join(md, n))
        names = sorted(f for f in os.listdir(md) if f.endswith('.html') and f not in SKIP and (not only or f in only))
        jogai = json.load(open(JOGAI, encoding='utf-8')) if os.path.exists(JOGAI) else {}
        mags, keys = {}, set()
        for n in names:
            rows = []
            for s in songs_in(open(os.path.join(md, n), encoding='utf-8').read()):
                if s['yt'] in jogai or s['yt'] == 'hmGwwZ5hjbI':   # きっかけの動画は全号共通の部品
                    continue
                key, stt, memo = resolve(s, lite)
                s.update(key=key, state=stt, memo=memo)
                rows.append(s)
                if key:
                    keys.add(key)
            mags[n] = rows
        facts = song_facts(w, keys) if keys else {}
        # その場で直す：動画IDで確定しているのにリンクが無い → リンクを貼る（song_pages にも足す）
        sp = json.load(open(SONG_PAGES, encoding='utf-8'))
        changed = []
        for n, rows in mags.items():
            path = os.path.join(md, n); h = open(path, encoding='utf-8').read(); h0 = h
            for s in rows:
                if s['state'] == 'no_link' and facts.get(s['key'], {}).get('exists'):
                    h, url = add_link(h, s['yt'], s['key'])
                    sp['pages'][s['yt']] = url
                    s['fixed'] = 'リンクを貼った'
            if h != h0:
                open(path, 'w', encoding='utf-8').write(h)
                loc = os.path.join(PROD_LOCAL, n)
                if os.path.exists(loc):   # 手元の写しにも同じ直し
                    lh = open(loc, encoding='utf-8').read()
                    for s in rows:
                        if s.get('fixed'):
                            lh, _ = add_link(lh, s['yt'], s['key'])
                    open(loc, 'w', encoding='utf-8').write(lh)
                changed.append(n)
        json.dump(sp, open(SONG_PAGES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        # 判定
        cnt = {'mags': len(mags), 'songs': 0, 'no_page': 0, 'cand': 0, 'link_ng': 0, 'prod_ng': 0, 'related_lt4': 0, 'copy_memo_ng': 0, 'fixed': 0}
        prod_cache = {}
        for n, rows in mags.items():
            for s in rows:
                cnt['songs'] += 1
                f = facts.get(s['key']) if s['key'] else None
                fails = []
                if s['state'] == 'cand':
                    fails.append(s['memo']); cnt['cand'] += 1
                elif s['state'] in ('no_page', 'ambiguous', 'suspect') or (s['key'] and not (f or {}).get('exists')):
                    fails.append('曲ページが無い' + ('（%s）' % s['memo'] if s['memo'] and s['memo'] != '曲ページが無い' else ''))
                    cnt['no_page'] += 1
                if s['state'] in ('link_wrong', 'link_dead'):
                    fails.append(s['memo']); cnt['link_ng'] += 1
                if f and f.get('exists'):
                    if s['key'] not in prod_cache:
                        prod_cache[s['key']] = prod_ok(s['key'], f.get('title'))
                    ok, t = prod_cache[s['key']]
                    if not ok:
                        fails.append('本番で曲ページが開かない（%s）' % t[:40]); cnt['prod_ng'] += 1
                    if f['related'] < MIN_RELATED:
                        fails.append('関連が%d曲（4曲以上必要）' % f['related']); cnt['related_lt4'] += 1
                    cm = []
                    if f['copy'] < 8: cm.append('コピーなし')
                    if f['note'] < 30: cm.append('メモなし' if f['note'] == 0 else 'メモが短い（%d字）' % f['note'])
                    elif f['noteNeedsSrc']: cm.append('メモに事実があるのに出典なし')
                    if cm:
                        fails.append('／'.join(cm)); cnt['copy_memo_ng'] += 1
                    if f.get('hidden'): fails.append('動画が再生できない（隠す表）')
                if s.get('fixed'):
                    cnt['fixed'] += 1
                s['related'] = (f or {}).get('related'); s['fails'] = fails; s['ok'] = not fails
        res = {'at': time.strftime('%F %T'), 'sec': int(time.time() - t0), 'count': cnt, 'changed': changed,
               'mags': {n: rows for n, rows in mags.items()}}
        if put and changed:
            res['pushed'] = push(w, changed)
        json.dump(res, open(OUT + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(OUT + '.tmp', OUT)
        jobs = enqueue(res) if tsumu else []
        res['jobs'] = jobs
        log('一巡 %s 号%d 曲%d ページ無し%d 取り違え%d 本番NG%d 関連4未満%d コピーメモ%d 直した%d 便%s' % (
            ','.join(only or ['全号']), cnt['mags'], cnt['songs'], cnt['no_page'], cnt['link_ng'], cnt['prod_ng'],
            cnt['related_lt4'], cnt['copy_memo_ng'], cnt['fixed'], jobs))
        return res
    finally:
        shutil.rmtree(w, ignore_errors=True)   # 使ったらしまう


def push(w, changed):
    """リンクを貼った号を main へ（作業場は最新 main の写し）。prebuild の生成物も一緒に。"""
    subprocess.run(['node', 'scripts/related/gen-magazine-html-songs.mjs'], cwd=w, capture_output=True, env=ENV, timeout=300)
    os.remove(os.path.join(w, 'scripts', 'patrol', '_mgate.mts')) if os.path.exists(os.path.join(w, 'scripts', 'patrol', '_mgate.mts')) else None
    for f in ('mgate_keys.json', 'mgate_out.json'):
        p = os.path.join(w, f)
        if os.path.exists(p):
            os.remove(p)
    g = lambda *a: subprocess.run(['git'] + list(a), cwd=w, capture_output=True, text=True, env=ENV, timeout=300)
    g('add', *['public/magazine/' + n for n in changed], 'src/lib/magazineHtmlSongs.generated.ts')
    who = g('log', '-1', '--format=%an|%ae').stdout.strip().split('|')
    r = g('-c', 'user.name=' + who[0], '-c', 'user.email=' + who[-1], 'commit', '-q', '-m',
          'マガジンの関所：曲ページへのリンクを貼った（動画IDで曲が確定しているのにリンクが無かった分）：' + '、'.join(changed))
    if r.returncode != 0:
        return 'commit なし'
    r = g('push', '-q', 'origin', 'HEAD:main')
    return 'push ok' if r.returncode == 0 else 'push 失敗：' + (r.stderr or '')[:120]


def _open_job(n):
    try:
        q = json.load(open(os.path.join(ST, 'queue.json'), encoding='utf-8'))
        for it in q.get('items', []):
            if str(it.get('n')) == str(n):
                return it.get('status') in ('waiting', 'running', 'hold', 'stuck')
    except Exception:
        pass
    return False


def enqueue(res):
    """号ごとに、落ちた曲を直す便を1本。前の便がまだ開いていれば積まない（同じ仕事を重ねない）。"""
    st = json.load(open(STATE, encoding='utf-8')) if os.path.exists(STATE) else {}
    sys.path.insert(0, TOOLS)
    import command_ingest as ci
    jobs = []
    for n, rows in res['mags'].items():
        ng = [s for s in rows if not s['ok']]
        if not ng:
            continue
        if st.get(n) and _open_job(st[n]):
            jobs.append('%s=既存%s' % (n, st[n]))
            continue
        lines = ['- %s「%s」（動画 %s）%s：%s' % (s['artist'], s['title'], s['yt'], (' → ' + s['key']) if s['key'] else '', ' ／ '.join(s['fails'])) for s in ng[:60]]
        text = '\n'.join([
            '【タスク】マガジン %s%s に載っている曲を、全部「独立した曲ページ・正しいリンク・関連4曲以上・コピーとメモ」にそろえる（マガジンの関所 %s）' % (SITE + '/magazine/', n, res['at']),
            '【たまごさん】「何回も言うけど、全部だよ。徹底して」。1〜2曲しか関連が無い状態は禁止。',
            '【落ちた曲】%d曲' % len(ng)] + lines + [
            '【直し方】曲ページが無い曲は sekisho-artist-song の関所を通して作る（アーティストの取り違え禁止：名前の一致だけで紐付けない。動画の公式チャンネル・本人で確かめる。名カバーの棚には足さない）。',
            '　関連は理由の言えるものだけ4曲以上（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。',
            '　メモとコピーは sekisho-jijitsu-shutten（出典を取ってから書く・src に入れる）とボンジョビおじさん構文。新しい日本語は src/i18n/overlay の4言語に訳を足す。',
            '　曲ページができたら、マガジンの動画に「この曲のページへ →」を貼る（tools/magazine/song_pages.json に 動画ID→URL を足すと組み直しても消えない）。',
            '【点検】python3 tools/magazine/magazine_gate.py --only %s で、この号の落ちた曲が0になること。' % n,
            '【公開】prebuild の関所を全部通して main → deploy_project（鍵が切れていれば Dispatch へ「公開待ち」1行）。',
            '【報告】Dispatch へ1行（本番URLだけ。GitHubのURLは書かない）。たまごさんに質問しない。'])
        try:
            _, msg = ci.queue_add(text, priority=1, label='マガジンの曲ページ %s（%d曲）' % (n.replace('.html', ''), len(ng)), origin='factory')
            m = re.search(r'(\d+)番', msg or '')
            if m:
                st[n] = m.group(1)
                import claude_uketsuke as cu
                cu.mark_mitai(msg)
            jobs.append('%s=%s' % (n, m.group(1) if m else msg))
        except Exception as e:
            log('積めない %s: %r' % (n, e))
    json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return jobs


def report(res):
    c = res['count']
    sys.path.insert(0, TOOLS)
    import claude_uketsuke as cu
    cu.outbox('【マガジンの関所】%d号・曲%d' % (c['mags'], c['songs']),
              '曲%d／ページが無かった%d（ほか名前の合う候補あり%d）／関連4未満%d／コピー・メモ不足%d／リンク取り違え%d／本番で開かない%d／その場で直した%d（直す便：%s）' % (
                  c['songs'], c['no_page'], c.get('cand', 0), c['related_lt4'], c['copy_memo_ng'], c['link_ng'], c['prod_ng'], c['fixed'], '、'.join(res.get('jobs') or []) or 'なし'),
              [SITE + '/magazine/backnumber.html'])


def self_test():
    lite = parse_lite('  {"id":"ado","name":"Ado","aliases":["アド"],"songs":[{"id":"usseewa","title":"うっせぇわ","youtubeId":"Q1"}]},\n'
                      '  {"id":"ado2","name":"AKIKO","songs":[{"id":"x","title":"うっせぇわ","youtubeId":"Q9"}]},')
    s = {'yt': 'Q1', 'artist': 'Ado', 'title': 'うっせぇわ', 'link': None}
    assert resolve(s, lite)[:2] == ('ado/usseewa', 'no_link')
    s = {'yt': 'ZZ', 'artist': 'Ado', 'title': 'うっせぇわ', 'link': None}
    k, stt, memo = resolve(s, lite)
    assert k is None and stt == 'cand' and 'ado/usseewa' in memo   # 名前の一致は候補止まり
    s = {'yt': 'ZZ', 'artist': 'Ado', 'title': 'x', 'link': SITE + '/cover-guide?artist=ado2&song=x'}
    assert resolve(s, lite)[1] == 'link_wrong'                        # 別人の棚へのリンクは取り違え
    h = '<figure class="cw-video cw-video--main"><button data-yt-cover="Q1"></button><figcaption><span class="cw-video__name"><b>Ado</b><i>「うっせぇわ」（MV）</i></span></figcaption></figure>'
    rows = songs_in(h)
    assert rows[0]['title'] == 'うっせぇわ' and rows[0]['artist'] == 'Ado'
    h2, url = add_link(h, 'Q1', 'ado/usseewa')
    assert 'cw-video__page' in h2 and songs_in(h2)[0]['link'] == url
    # 同じ動画でも、別人の棚なら確定しない（来生たかお「夢の途中」の動画が別の人の棚に入っていた件）
    lite2 = parse_lite('  {"id":"rg","name":"Rufus Gumede","songs":[{"id":"y","title":"夢の途中","youtubeId":"V1"}]},')
    assert resolve({'yt': 'V1', 'artist': '来生たかお', 'title': '夢の途中', 'link': None}, lite2)[1] == 'suspect'
    assert resolve({'yt': 'V1', 'artist': '来生たかお', 'title': '夢の途中', 'link': SITE + '/cover-guide?artist=rg&song=y'}, lite2)[1] == 'link_wrong'
    print('SELF-TEST OK')
    return 0


def main(argv):
    if '--self-test' in argv:
        return self_test()
    if '--daily' in argv:
        try:
            if time.time() - os.path.getmtime(STAMP) < 20 * 3600:
                return 0
        except OSError:
            pass
        open(STAMP, 'w').write(time.strftime('%F %T'))
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
    res = run(only=only, tsumu='--no-tsumu' not in argv, put='--no-put' not in argv)
    report(res)
    print(json.dumps(res['count'], ensure_ascii=False), res.get('jobs'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
