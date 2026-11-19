#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引っ込み係（hikkomi）— 2026-10-25 たまごさん指示。

たまごさん（原文）：
  「『見つかりません』のままにしておくのは嫌。自動で引っ込んでほしい。今月引っ込んだものの『引っ込んだリスト』が欲しい。
    もしあるなら差し替えて。Grok botにも共有して。あなたも探すし、Grok botも探す。
    他の人がアップロードしている場合もあるし、Twitterにあるかもしれない。歯抜けの状態が嫌」
  きっかけ：「生放送中になかやまきんに君と対面した一橋アナウンサーの反応」（X @rurutannnnnn107・あるある 人間だもの）が「見つかりません」。

■ 何をするか（毎日1回）
  ① 棚のカードの元（DB の admin_stock の X・YouTube 全部＋joy-relief-station のコードの棚に書かれた X 投稿
       ＋マガジン・特集の動画 status/hikkomi/magazine_videos.json＝magazine_gate.py が毎日書く・2026-10-29）を1本ずつ確かめる。
       X       … publish.twitter.com の oEmbed と api.fxtwitter.com の2か所が両方「無い／非公開」と言ったら「消えた」。
       YouTube … youtube.com の oEmbed が 404/400（削除）・401/403（非公開・埋め込み不可）を2回続けて返したら「消えた」。
       どちらも、通信の失敗や片方だけの「無い」は「分からない」＝前の判定のまま（勝手に引っ込めない）。
  ② 消えたものを joy-relief-station の src/lib/hikkomi.generated.ts に書いて main へ push（中身が変わった時だけ）。
       サイト側（src/lib/hikkomi.ts）がそれを見て、棚・関連・検索からカードごと隠す。**データは消さない。**
       生き返ったら次の回で外れて、自動で棚に戻る。公開ボタンは公開押し係（kohyou_osu.py）が押す。
  ③ 台帳 status/hikkomi/daicho.json と、引っ込んだリスト share/check/hikkomi.html（月ごと・題名・元のURL・棚・引っ込んだ日・差し替え候補）を作り直す。
  ④ 毎週1回、差し替え候補がまだ無いものを振り分け所（tools/furiwake.py・ラベル「できる人いますか」）経由で Grok ボットに探してもらう。
       返事に「キー URL」の行があれば、そのURLが生きているか確かめて候補に載せる。

■ 使い方
  python3 tools/hikkomi.py --tick                 # 心臓から（中で間引く：見回り20時間・Grok 6.5日）
  python3 tools/hikkomi.py --mimawari [--no-push] # 今すぐ見回り
  python3 tools/hikkomi.py --page                 # 一覧だけ作り直す
  python3 tools/hikkomi.py --grok                 # 今すぐ Grok に頼む
  python3 tools/hikkomi.py --kouho <キー> <URL> [--memo 一言]   # 差し替え候補を足す（キー＝x:投稿ID／yt:動画ID）
  python3 tools/hikkomi.py --sashikae <キー> <URL> --title 題名  # 同じ枠の中身を入れ替える（admin_stock の ref・title を PATCH。棚は増やさない）
  python3 tools/hikkomi.py --self-test

■ 決まり
  ・棚に新しく足さない。差し替えは同じ行（同じ枠）の中身の入れ替えだけ。
  ・有料API・ブラウザ・許可ポップアップの出る道具は使わない。鍵の値は外へ出さない。
  ・一時ファイルは作らない（git は一時の index を1個だけ使い、終わったら消す）。

作るもの：status/hikkomi/{daicho.json,state.json,hikkomi.log}／status/public/hikkomi.json／share/check/hikkomi.html
台帳：tools/jidou_daicho.json の "hikkomi.py"
"""
import datetime
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
D = os.path.join(REPO, "status", "hikkomi")
DAICHO = os.path.join(D, "daicho.json")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "hikkomi.log")
PUB = os.path.join(REPO, "status", "public", "hikkomi.json")
PAGE = os.path.join(REPO, "share", "check", "hikkomi.html")
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/share/check/hikkomi.html"
JRS = os.path.expanduser("~/Desktop/joy-relief-station")
GEN_PATH = "src/lib/hikkomi.generated.ts"
SITE = "https://joy-relief-station.lovable.app"
JST = datetime.timezone(datetime.timedelta(hours=9))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
STATIC_FILES = ["src/lib/worlds.ts", "src/lib/extraCards.ts", "src/lib/foodCards.ts", "src/lib/danceCards.ts",
                "src/lib/summerCards.ts", "src/lib/uraTagAruaru.ts"]
MIMAWARI_GAP = 20 * 3600
GROK_GAP = int(6.5 * 86400)


def now():
    return datetime.datetime.now(JST)


def today():
    return now().strftime("%Y-%m-%d")


def log(msg):
    os.makedirs(D, exist_ok=True)
    line = "%s %s\n" % (now().strftime("%F %T"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
        # 300行を超えたら古い方を刈る
        lines = io.open(LOG, encoding="utf-8").read().splitlines(True)
        if len(lines) > 300:
            io.open(LOG, "w", encoding="utf-8").write("".join(lines[-300:]))
    except Exception:
        pass
    print(line, end="")


def jload(p, default):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return default


def jsave(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


# ------------------------------------------------------------------ 形
def tweet_id(s):
    if not s:
        return None
    s = urllib.parse.unquote(str(s))
    m = re.search(r"(?:twitter\.com|x\.com)/(?:[^/?#\s]+|i(?:/web)?)/status(?:es)?/(\d{5,25})", s)
    return m.group(1) if m else None


def yt_id(s):
    if not s:
        return None
    s = str(s)
    m = re.search(r"(?:youtu\.be/|[?&]v=|/embed/|/shorts/|/vi/)([A-Za-z0-9_-]{11})", s)
    if m:
        return m.group(1)
    m = re.match(r"^([A-Za-z0-9_-]{11})$", s.strip())
    return m.group(1) if m else None


def key_of(kind, ref):
    if kind == "x":
        t = tweet_id(ref)
        return ("x:" + t) if t else None
    if kind == "youtube":
        y = yt_id(ref)
        return ("yt:" + y) if y else None
    t = tweet_id(ref)
    if t:
        return "x:" + t
    return None


def url_of(key):
    k, v = key.split(":", 1)
    return ("https://x.com/i/status/" + v) if k == "x" else ("https://www.youtube.com/watch?v=" + v)


# ------------------------------------------------------------------ 確かめる
def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read(4000).decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception:
        return None, ""


def check_x(tid):
    """→ ("alive"|"dead"|"unknown", 理由)"""
    st, _ = _get("https://publish.twitter.com/oembed?omit_script=1&url=" + urllib.parse.quote("https://twitter.com/i/status/" + tid))
    if st == 200:
        return "alive", "oEmbed 200"
    o_dead = st in (404, 403, 410)
    st2, body = _get("https://api.fxtwitter.com/i/status/" + tid)
    code = None
    try:
        code = json.loads(body).get("code")
    except Exception:
        pass
    code = code or st2
    if code == 200:
        return "alive", "fxtwitter 200"
    f_dead = code in (404, 401, 403, 410)
    if o_dead and f_dead:
        why = "非公開（鍵）" if (st == 403 or code in (401, 403)) else "削除"
        return "dead", "%s（oEmbed %s・fxtwitter %s）" % (why, st, code)
    return "unknown", "oEmbed %s・fxtwitter %s" % (st, code)


def check_yt(vid):
    def once():
        st, _ = _get("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote("https://www.youtube.com/watch?v=" + vid))
        return st
    st = once()
    if st == 200:
        return "alive", "oEmbed 200"
    if st in (400, 401, 403, 404):
        time.sleep(1.5)
        st2 = once()
        if st2 == 200:
            return "alive", "oEmbed 200（2回目）"
        if st2 in (400, 401, 403, 404):
            why = "削除" if st2 in (400, 404) else "非公開か埋め込み不可"
            return "dead", "%s（oEmbed %s→%s）" % (why, st, st2)
    return "unknown", "oEmbed %s" % st


def check(key):
    k, v = key.split(":", 1)
    try:
        return check_x(v) if k == "x" else check_yt(v)
    except Exception as e:
        return "unknown", "例外 %s" % type(e).__name__


# ------------------------------------------------------------------ 集める
def _db():
    import tana
    diag = []
    url, key, _kn, where = tana.keys(diag)
    if not url:
        raise RuntimeError("Supabaseの鍵が見つからない：%s" % where)
    return url, key


def _get_all(url, key, path, page=1000):
    out = []
    off = 0
    while True:
        req = urllib.request.Request(url + path, headers={"apikey": key, "Authorization": "Bearer " + key,
                                                          "Accept": "application/json", "Range": "%d-%d" % (off, off + page - 1)})
        with urllib.request.urlopen(req, timeout=60) as r:
            rows = json.loads(r.read().decode("utf-8", "replace") or "[]")
        out.extend(rows)
        if len(rows) < page:
            break
        off += page
    return out


def collect():
    """→ {key: {kind, ref, title, stock_ids, shelves[], from}}"""
    items = {}
    url, key = _db()
    stock = _get_all(url, key, "/rest/v1/admin_stock?select=id,kind,ref,title,deleted_at&kind=in.(x,youtube)&order=created_at.asc")
    shelves = {s["id"]: s for s in _get_all(url, key, "/rest/v1/admin_shelves?select=id,title,world,extends_shelf_id")}
    picks = _get_all(url, key, "/rest/v1/admin_shelf_picks?select=stock_id,shelf_id,status&order=shelf_id.asc")
    on = {}
    for p in picks:
        if p.get("status") in ("excluded", "unmarked"):
            continue
        sh = shelves.get(p.get("shelf_id"))
        if sh:
            on.setdefault(p["stock_id"], []).append("%s（%s）" % (sh.get("title") or "", sh.get("world") or ""))
    for s in stock:
        if s.get("deleted_at"):
            continue
        k = key_of(s.get("kind"), s.get("ref"))
        if not k:
            continue
        it = items.setdefault(k, {"kind": s["kind"], "ref": s.get("ref"), "title": s.get("title") or "",
                                  "stock_ids": [], "shelves": [], "from": "db"})
        it["stock_ids"].append(s["id"])
        for t in on.get(s["id"], []):
            if t not in it["shelves"]:
                it["shelves"].append(t)
    # コードの棚（joy-relief-station の origin/main）に書かれた X 投稿
    n_static = 0
    for f in STATIC_FILES:
        try:
            src = subprocess.run(["git", "-C", JRS, "show", "origin/main:" + f], capture_output=True, text=True, timeout=60).stdout
        except Exception:
            src = ""
        for m in re.finditer(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9_]+/status/(\d{5,25})", src):
            k = "x:" + m.group(1)
            if k in items:
                continue
            # 近くの title を拾う（無ければ空）
            around = src[max(0, m.start() - 600):m.start()]
            tm = re.findall(r'title:\s*"((?:[^"\\]|\\.){2,120})"', around)
            items[k] = {"kind": "x", "ref": m.group(0), "title": (tm[-1] if tm else ""), "stock_ids": [],
                        "shelves": ["コードの棚（%s）" % os.path.basename(f)], "from": "code"}
            n_static += 1
    # マガジン・特集の動画（2026-10-29 マガジン曲点検：tools/magazine/magazine_gate.py が毎日この表を書く）
    n_mag = 0
    try:
        feed = json.load(io.open(os.path.join(REPO, "status", "hikkomi", "magazine_videos.json"), encoding="utf-8"))
        for vid, v in (feed.get("videos") or {}).items():
            k = "yt:" + vid
            if k in items:
                continue
            items[k] = {"kind": "youtube", "ref": "https://www.youtube.com/watch?v=" + vid, "title": v.get("title") or "",
                        "stock_ids": [], "shelves": ["マガジン（%s）" % "・".join(sorted(set(v.get("pages") or []))[:3])], "from": "magazine"}
            n_mag += 1
    except Exception:
        pass
    log("集めた：DB %d件（X・YouTube）＋コードの棚のX %d件＋マガジン・特集の動画 %d件 → 確かめる %d件" % (len(stock), n_static, n_mag, len(items)))
    return items


# ------------------------------------------------------------------ 見回り
def mimawari(push=True):
    daicho = jload(DAICHO, {})
    items = collect()
    keys = sorted(set(items) | {k for k, v in daicho.items() if v.get("jotai") == "hikkomi"})
    res = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for k, r in zip(keys, ex.map(check, keys)):
            res[k] = r
    t = today()
    n = {"alive": 0, "dead": 0, "unknown": 0}
    new_dead, back = [], []
    for k in keys:
        st, why = res[k]
        n[st] += 1
        it = items.get(k) or {}
        e = daicho.get(k)
        if e is not None and e.get("jotai") == "sashikae":
            # 差し替え済みの枠：元は消えたまま。差し替え先が消えたら、また引っ込める（候補探しに戻す）
            sk = e.get("sashikae") or {}
            if sk.get("key") and check(sk["key"])[0] == "dead":
                e.update({"jotai": "hikkomi", "hikkonda": t, "riyuu": "差し替え先 %s も消えた" % sk.get("url")})
                new_dead.append(k)
        elif st == "dead":
            if not e or e.get("jotai") != "hikkomi":
                e = e or {"kouho": []}
                e.update({"jotai": "hikkomi", "hikkonda": t, "riyuu": why})
                new_dead.append(k)
            daicho[k] = e
        elif st == "alive" and e and e.get("jotai") == "hikkomi":
            e.update({"jotai": "fukkatsu", "fukkatsu": t, "riyuu": e.get("riyuu", "") + "／%s 生き返った" % t})
            back.append(k)
        if e is not None:
            if it:
                e.update({"kind": it["kind"], "ref": it["ref"], "title": it["title"] or e.get("title", ""),
                          "stock_ids": it["stock_ids"], "shelves": it["shelves"], "from": it["from"]})
            e.setdefault("url", url_of(k))
            e["saigo"] = t
            e["saigo_kekka"] = "%s：%s" % (st, why)
    # 候補の生死も軽く確かめる（死んだ候補は印を付ける）
    for k, e in daicho.items():
        for c in e.get("kouho", []):
            ck = key_of("x" if tweet_id(c.get("url")) else "youtube", c.get("url"))
            if ck and not c.get("ikiteru_at") == t:
                st, _ = check(ck)
                c["ikiteru"] = (st != "dead")
                c["ikiteru_at"] = t
    jsave(DAICHO, daicho)
    st = jload(STATE, {})
    st.update({"mimawari_at": time.time(), "mimawari_jst": now().strftime("%F %T"), "kensu": n, "kakunin": len(keys)})
    jsave(STATE, st)
    log("見回り：確かめた %d件（生きている %d・消えた %d・分からない %d）／新しく引っ込めた %d・戻した %d" % (
        len(keys), n["alive"], n["dead"], n["unknown"], len(new_dead), len(back)))
    for k in new_dead:
        log("  引っ込めた %s %s %s" % (k, daicho[k].get("title", "")[:40], daicho[k].get("riyuu", "")))
    page()
    if push:
        push_generated(daicho)
    return {"kakunin": len(keys), "kensu": n, "new": new_dead, "back": back}


def hidden_sets(daicho):
    xs = sorted(k[2:] for k, v in daicho.items() if v.get("jotai") == "hikkomi" and k.startswith("x:"))
    ys = sorted(k[3:] for k, v in daicho.items() if v.get("jotai") == "hikkomi" and k.startswith("yt:"))
    return xs, ys


def gen_ts(xs, ys, sk=None):
    return ("// AUTO-GENERATED by tamago-shinchoku/tools/hikkomi.py — do not edit by hand.\n"
            "// 見回り（毎日）で「消えた・非公開になった」と判定されたX投稿・YouTube動画。\n"
            "// ここに載ったカードは棚・関連・検索から自動で引っ込む（データは消さない。生き返れば次の見回りで外れる）。\n"
            "// 一覧：%s\n"
            "export const HIKKOMI_X_IDS: ReadonlySet<string> = new Set(%s);\n"
            "export const HIKKOMI_YT_IDS: ReadonlySet<string> = new Set(%s);\n"
            "// 差し替え（同じ枠の中身の入れ替え）：admin_stock の行ID → 新しい中身\n"
            "export const HIKKOMI_SASHIKAE: Record<string, { kind: string; ref: string; title: string; thumbnail_url: string | null }> = %s;\n") % (
        PAGE_URL, json.dumps(xs), json.dumps(ys), json.dumps(sk or {}, ensure_ascii=False, indent=1))


def _git(*a, env=None, inp=None):
    p = subprocess.run(["git", "-C", JRS] + list(a), capture_output=True, text=True, timeout=120, env=env, input=inp)
    if p.returncode != 0:
        raise RuntimeError("git %s: %s" % (a[0], (p.stderr or p.stdout)[-300:]))
    return p.stdout.strip()


def push_generated(daicho):
    """作業場（worktree）を作らずに、origin/main の上へ1ファイルだけのコミットを積んで push する。"""
    xs, ys = hidden_sets(daicho)
    body = gen_ts(xs, ys, sashikae_map(daicho))
    try:
        _git("fetch", "-q", "origin", "main")
        base = _git("rev-parse", "origin/main")
        try:
            cur = subprocess.run(["git", "-C", JRS, "show", "%s:%s" % (base, GEN_PATH)], capture_output=True, text=True, timeout=60).stdout
        except Exception:
            cur = ""
        if cur == body:
            log("hikkomi.generated.ts は変わらない（push しない）")
            return False
        fd, idx = tempfile.mkstemp(prefix="hikkomi_idx_")
        os.close(fd)
        try:
            env = dict(os.environ, GIT_INDEX_FILE=idx)
            _git("read-tree", base, env=env)
            blob = _git("hash-object", "-w", "--stdin", inp=body)
            _git("update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, GEN_PATH), env=env)
            tree = _git("write-tree", env=env)
        finally:
            try:
                os.remove(idx)
            except Exception:
                pass
        msg = "hikkomi: 消えた・非公開のX投稿%d件・動画%d件を棚から自動で引っ込める（tools/hikkomi.py の毎日の見回り）\n\n一覧 %s" % (len(xs), len(ys), PAGE_URL)
        c = _git("commit-tree", tree, "-p", base, "-m", msg)
        _git("push", "-q", "origin", "%s:refs/heads/main" % c)
        log("push した：%s（X %d・動画 %d）" % (c[:10], len(xs), len(ys)))
        return True
    except Exception as e:
        log("push できず：%s" % e)
        return False


# ------------------------------------------------------------------ 一覧ページ
def _link_label(u):
    """リンクの文字に動画ID・投稿IDをもう一度書かない（鬼監督§0：同じ動画が同じページに2回出る扱いになる）"""
    u = str(u or "")
    m = re.search(r"(?:twitter\.com|x\.com)/([^/?#]+)/status", u)
    if m and m.group(1) not in ("i",):
        return "X @%s の投稿" % m.group(1)
    if tweet_id(u):
        return "Xの投稿"
    if yt_id(u):
        return "YouTubeの動画"
    return "リンク"


def page():
    daicho = jload(DAICHO, {})
    st = jload(STATE, {})
    rows = sorted(daicho.items(), key=lambda kv: (kv[1].get("hikkonda", ""), kv[0]), reverse=True)
    months = {}
    for k, e in rows:
        months.setdefault((e.get("hikkonda") or "")[:7], []).append((k, e))
    pub = {"at": now().strftime("%F %T"), "page": PAGE_URL, "mimawari": st.get("mimawari_jst"), "kensu": st.get("kensu"),
           "hikkomi_chuu": sum(1 for _k, e in rows if e.get("jotai") == "hikkomi"),
           "items": [dict(key=k, **{x: e.get(x) for x in ("jotai", "title", "url", "ref", "shelves", "hikkonda", "riyuu", "kouho", "fukkatsu", "sashikae")}) for k, e in rows]}
    jsave(PUB, pub)

    def esc(s):
        return html.escape(str(s or ""))
    jotai_label = {"hikkomi": "引っ込み中", "fukkatsu": "生き返った（棚に戻った）", "sashikae": "差し替え済み"}
    parts = []
    for m in sorted(months, reverse=True):
        lst = months[m]
        parts.append('<h2>%s　<small>%d件</small></h2>' % (esc(m.replace("-", "年", 1) + "月" if m else "日付なし"), len(lst)))
        parts.append('<table><tr><th>引っ込んだ日</th><th>題名</th><th>元のURL</th><th>棚</th><th>差し替え候補</th><th>状態</th></tr>')
        for k, e in lst:
            kouho = e.get("kouho") or []
            if kouho:
                kh = "<br>".join('<a href="%s">%s</a>%s%s' % (esc(c.get("url")), esc(_link_label(c.get("url"))), "（%s）" % esc(c.get("by")) if c.get("by") else "",
                                                             "" if c.get("ikiteru", True) else "※消えている") for c in kouho)
                kh = "あり<br>" + kh
            else:
                kh = "なし（探し中：工場＋Grok）"
            parts.append("<tr><td>%s</td><td>%s</td><td><a href=\"%s\">%s</a><br><small>%s</small></td><td>%s</td><td>%s</td><td>%s%s</td></tr>" % (
                esc(e.get("hikkonda")), esc(e.get("title") or "（題名なし）"), esc(e.get("ref") or e.get("url")), esc(_link_label(e.get("ref") or e.get("url"))),
                esc(e.get("riyuu")), esc("・".join(e.get("shelves") or []) or "棚の外（関連・検索のみ）"), kh,
                esc(jotai_label.get(e.get("jotai"), e.get("jotai"))),
                ("<br><small>→ %s</small>" % esc(e.get("sashikae", {}).get("title") or "差し替え先")) if e.get("sashikae") else ""))
        parts.append("</table>")
    kensu = st.get("kensu") or {}
    doc = """<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>引っ込んだリスト（消えたX投稿・動画）</title>
<style>body{font-family:-apple-system,"Hiragino Sans",sans-serif;margin:16px;line-height:1.6;color:#222}
table{border-collapse:collapse;width:100%%;font-size:14px;margin-bottom:24px}th,td{border:1px solid #ddd;padding:6px;vertical-align:top;text-align:left}
th{background:#f5f2ea}td a{word-break:break-all}h2 small{color:#888;font-weight:normal}.lead{color:#555}</style></head><body>
<h1>引っ込んだリスト</h1>
<p class="lead">X投稿・YouTube動画が消えた／非公開になったカードは、「見つかりません」を出さずに棚・関連・検索から自動で引っ込めています（データは消していません。生き返れば自動で戻ります）。<br>
見回り：毎日1回（最後 %s・確かめた %s件：生きている %s・消えた %s・分からない %s）。差し替え候補は工場と Grok ボット（毎週・振り分け所「できる人いますか」）で探しています。<br>
<a href="../../index.html">← 進捗表へ</a></p>
%s
<p class="lead">作り：tamago-shinchoku/tools/hikkomi.py ／ 台帳 status/hikkomi/daicho.json ／ サイト側 joy-relief-station src/lib/hikkomi.ts</p>
</body></html>
""" % (esc(st.get("mimawari_jst") or "まだ"), esc(st.get("kakunin", "—")), esc(kensu.get("alive", "—")), esc(kensu.get("dead", "—")),
       esc(kensu.get("unknown", "—")), "\n".join(parts) or "<p>今のところ引っ込んだカードはありません。</p>")
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    io.open(PAGE, "w", encoding="utf-8").write(doc)
    return PAGE


# ------------------------------------------------------------------ 候補・差し替え
def add_kouho(key, url, by="工場", memo=""):
    daicho = jload(DAICHO, {})
    e = daicho.get(key)
    if not e:
        raise SystemExit("台帳に無いキー：%s" % key)
    ck = key_of("x" if tweet_id(url) else "youtube", url)
    alive = None
    if ck:
        alive = check(ck)[0] != "dead"
    lst = e.setdefault("kouho", [])
    if not any(c.get("url") == url for c in lst):
        lst.append({"url": url, "by": by, "at": today(), "memo": memo, "ikiteru": alive, "ikiteru_at": today()})
    jsave(DAICHO, daicho)
    page()
    log("候補を足した %s ← %s（%s）" % (key, url, by))


def sashikae(key, url, title):
    """同じ枠（admin_stock の同じ行）の中身を入れ替える。棚は増やさない。
    DB は直接書けない（2026-10-25 実測：PATCH が0行）ので、joy-relief-station の hikkomi.generated.ts の
    HIKKOMI_SASHIKAE に「行ID → 新しい ref・kind・title・サムネ」を書き、読み出し側で上書きする（applySashikae）。"""
    daicho = jload(DAICHO, {})
    e = daicho.get(key)
    if not e or not e.get("stock_ids"):
        raise SystemExit("差し替えられる行が無い（DBのカードだけ差し替えられる）：%s" % key)
    newk = key_of("x" if tweet_id(url) else "youtube", url)
    if not newk or check(newk)[0] != "alive":
        raise SystemExit("差し替え先が生きていると確かめられない：%s" % url)
    kind = "x" if newk.startswith("x:") else "youtube"
    thumb = ("https://i.ytimg.com/vi/%s/hqdefault.jpg" % newk[3:]) if kind == "youtube" else None
    e["jotai"] = "sashikae"
    e["sashikae"] = {"url": url, "key": newk, "kind": kind, "title": title, "thumbnail_url": thumb, "at": today(),
                     "moto_title": e.get("title"), "moto_ref": e.get("ref")}
    jsave(DAICHO, daicho)
    page()
    pushed = push_generated(daicho)
    log("差し替えた %s → %s「%s」（行 %s・push %s）" % (key, url, title, ",".join(e["stock_ids"]), pushed))


def sashikae_map(daicho):
    m = {}
    for k, e in daicho.items():
        sk = e.get("sashikae") or {}
        if e.get("jotai") != "sashikae" or not sk.get("url"):
            continue
        for sid in e.get("stock_ids") or []:
            m[sid] = {"kind": sk["kind"], "ref": sk["url"], "title": sk["title"], "thumbnail_url": sk.get("thumbnail_url")}
    return dict(sorted(m.items()))


# ------------------------------------------------------------------ Grok（毎週）
def grok(force=False):
    st = jload(STATE, {})
    if not force and time.time() - st.get("grok_at", 0) < GROK_GAP:
        return None
    daicho = jload(DAICHO, {})
    nai = [(k, e) for k, e in daicho.items() if e.get("jotai") == "hikkomi" and not any(c.get("ikiteru", True) for c in e.get("kouho", []))]
    if not nai:
        st["grok_at"] = time.time()
        jsave(STATE, st)
        log("Grok：候補の無い引っ込みは0件（頼まない）")
        return None
    lines = "\n".join("- キー %s ／ 題名「%s」／ 元 %s ／ 棚 %s" % (k, e.get("title", ""), e.get("ref") or e.get("url"), "・".join(e.get("shelves") or []))
                      for k, e in nai[:25])
    import furiwake
    rec = furiwake.dasu(
        yaritai="消えたX投稿・動画の『同じ場面』の別の投稿を探す（%d件）" % len(nai[:25]),
        naze="工場はXの検索ができない（ログイン不要・無料の道具しか使えない）。Grokボットは X を検索できる。\n"
             "たまごさん（2026-10-25）「歯抜けの状態が嫌。他の人がアップロードしている場合もあるし、Twitterにあるかもしれない」\n\n" + lines,
        kanryo="Issue に1行1件で『キー URL 一言』を返す（例：x:2093171499125616764 https://x.com/xxx/status/123 同じ生放送の場面）。"
               "同じ場面（同じ人・同じ番組・同じ瞬間）だけ。見つからないキーは『キー なし』。取り違え禁止。",
        shimekiri=(now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d"), ate="grok", tags=["x_read", "web_research"],
        who="引っ込み係（tools/hikkomi.py・毎週）")
    st["grok_at"] = time.time()
    st.setdefault("grok_irai", []).append(rec["id"])
    st["grok_irai"] = st["grok_irai"][-20:]
    jsave(STATE, st)
    log("Grok に頼んだ：%s（%d件）" % (rec["id"], len(nai[:25])))
    return rec["id"]


def grok_kaeri():
    """振り分け所に返ってきた返事から『キー URL』を拾って候補にする。"""
    st = jload(STATE, {})
    ids = set(st.get("grok_irai", []))
    if not ids:
        return 0
    irai = jload(os.path.join(REPO, "status", "furiwake", "irai.json"), [])
    seen = set(st.get("grok_yonda", []))
    n = 0
    daicho = jload(DAICHO, {})
    for ir in irai if isinstance(irai, list) else []:
        if ir.get("id") not in ids or ir.get("id") in seen:
            continue
        body = (ir.get("kaeri") or {}).get("body") or ""
        if not body:
            continue
        for m in re.finditer(r"((?:x|yt):[A-Za-z0-9_-]+)\s+(https?://\S+)(?:[ \t]+([^\n]*))?", body):
            k, u, memo = m.group(1), m.group(2).rstrip("）)。、,"), (m.group(3) or "").strip()
            if k in daicho:
                try:
                    add_kouho(k, u, by="Grok", memo=memo[:80])
                    n += 1
                except SystemExit:
                    pass
        seen.add(ir["id"])
    st = jload(STATE, {})
    st["grok_yonda"] = sorted(seen)[-50:]
    jsave(STATE, st)
    if n:
        log("Grok の返事から候補 %d件" % n)
    return n


# ------------------------------------------------------------------ 心臓
def tick():
    st = jload(STATE, {})
    if time.time() - st.get("tick_at", 0) < 600:
        return
    st["tick_at"] = time.time()
    jsave(STATE, st)
    grok_kaeri()
    if time.time() - st.get("mimawari_at", 0) >= MIMAWARI_GAP:
        mimawari(push=True)
    grok()


# ------------------------------------------------------------------ 逆テスト
def self_test():
    ok = True

    def eq(a, b, what):
        nonlocal ok
        if a != b:
            ok = False
            print("NG", what, a, b)
    eq(tweet_id("https://x.com/rurutannnnnn107/status/2093171499125616764"), "2093171499125616764", "tweet")
    eq(tweet_id("/watch?tweet=https%3A%2F%2Fx.com%2Fa%2Fstatus%2F12345678"), "12345678", "tweet encoded")
    eq(tweet_id("https://example.com/"), None, "not tweet")
    eq(yt_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3"), "dQw4w9WgXcQ", "yt")
    eq(yt_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ", "yt short")
    eq(yt_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ", "yt bare")
    eq(key_of("x", "https://twitter.com/a/status/99999"), "x:99999", "key x")
    eq(key_of("youtube", "https://www.youtube.com/shorts/abcdefghijk"), "yt:abcdefghijk", "key yt")
    xs, ys = hidden_sets({"x:1": {"jotai": "hikkomi"}, "x:2": {"jotai": "fukkatsu"}, "yt:abcdefghijk": {"jotai": "hikkomi"}})
    eq((xs, ys), (["1"], ["abcdefghijk"]), "sets")
    ts = gen_ts(["1"], [])
    eq("HIKKOMI_X_IDS" in ts and '["1"]' in ts, True, "gen")
    body = "x:2093171499125616764 https://x.com/foo/status/123 同じ場面\nyt:abcdefghijk なし"
    got = [(m.group(1), m.group(2)) for m in re.finditer(r"((?:x|yt):[A-Za-z0-9_-]+)\s+(https?://\S+)", body)]
    eq(got, [("x:2093171499125616764", "https://x.com/foo/status/123")], "grok parse")
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(a):
    if "--self-test" in a:
        sys.exit(self_test())
    if "--tick" in a:
        return tick()
    if "--mimawari" in a:
        print(json.dumps(mimawari(push="--no-push" not in a), ensure_ascii=False))
        return
    if "--page" in a:
        print(page())
        return
    if "--grok" in a:
        print(grok(force=True))
        return
    if "--kouho" in a:
        i = a.index("--kouho")
        memo = a[a.index("--memo") + 1] if "--memo" in a else ""
        by = a[a.index("--by") + 1] if "--by" in a else "工場"
        return add_kouho(a[i + 1], a[i + 2], by=by, memo=memo)
    if "--sashikae" in a:
        i = a.index("--sashikae")
        title = a[a.index("--title") + 1] if "--title" in a else ""
        if not title:
            raise SystemExit("--title が要る（中身と一致する題名）")
        return sashikae(a[i + 1], a[i + 2], title)
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
