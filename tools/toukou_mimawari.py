#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【投稿済み曲の見回り】SNSに出した曲の台帳を毎日作り、曲ページの5点を点検し、落ちた曲は直す仕事を積む。

たまごさん（2026-10-17・優先順位1位「SNSで発信したもの周りのページ品質」）：
  「もう投稿したもの（X・TikTok・YouTubeショート）をちゃんと把握して。世の中に出した曲からページを濃くしていく。
    検索で出ない、関連が2曲しかない、はおかしい。80点以上は基本中の基本」
  実例：X投稿 2108437452188762302 の布袋寅泰「Dancing with the Moonlight」。サイトで「ダンス」「ダンシング」で
        検索しても出ない。曲ページの関連は布袋の曲2曲だけ。

━━ 1日1回（心臓 top_status.py の相乗り・中で20時間に1回に間引く）━━
  ① 台帳を作る（集める）  → status/public/toukou_daicho.json
       X（予約）   : status/buffer_queue/dashita.jsonl（Bufferに入れた控え＝正本）。予定時刻を過ぎたもの
       X（手で出した）: tools/x_toukou.py の取り出し（0円・鍵なし・GETだけ）。本文の自サイトURLから曲を引く
       サイトの投稿ログ: joy-relief-station docs/operations/sns-post-log.json の status=posted
       TikTok      : 公開プロフィール @joyreliefstation を Mac の curl で1回（0円）。取れなければ「取れない」と書く
       YouTubeショート: status/toukou_daicho_config.json の youtube_channel_id があれば公開RSS（0円）。無ければ「未登録」
       ★有料APIは使わない。ブラウザを開かない。投稿・いいね・削除は一切しない。
  ② 点検する              → status/public/toukou_tenken.json
       joy-relief-station の最新 main を一時の作業場に出し、scripts/patrol/check-posted-songs.mts を走らせる
       （①検索 ②関連4本以上 ③メモと出典 ④マガジンへの入口 ⑤動画の生死＝oEmbed）。作業場は終わったら自分で消す。
  ③ 直す仕事を積む         → status/queue.json（command_ingest.queue_add・origin=factory・sonnet）
       落ちた曲があれば、その日1件だけ「直して本番まで」の仕事を積む。台帳が変わった日も、台帳の写しを
       サイトへ入れる仕事として同じ1件に含める（検索で「SNSで紹介した曲」を少し先に出すのに使う）。

使い方:
  python3 tools/toukou_mimawari.py --daily        # 心臓から（20時間に1回）
  python3 tools/toukou_mimawari.py --collect      # 台帳だけ作る（サンドボックスからでも動く・TikTok等は飛ばす）
  python3 tools/toukou_mimawari.py --check        # 点検だけ（Macで）
  python3 tools/toukou_mimawari.py --self-test
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

JST = _dt.timezone(_dt.timedelta(hours=9))
DASHITA = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
X_LIVE = os.path.join(REPO, "status", "1075_x", "toukou_oasisjoyrelief.json")
CONFIG = os.path.join(REPO, "status", "toukou_daicho_config.json")
DAICHO = os.path.join(REPO, "status", "public", "toukou_daicho.json")
TENKEN = os.path.join(REPO, "status", "public", "toukou_tenken.json")
STAMP = os.path.join(REPO, "status", ".toukou_mimawari_at")
LOG = os.path.join(REPO, "status", "toukou_mimawari.log")
JRS = os.path.expanduser(os.environ.get("TOUKOU_JRS", "~/tamago/jrs_fix"))
GH_TOKEN_FILE = os.path.expanduser("~/tamago/gh_token")
SITE = "https://joy-relief-station.lovable.app"
TIKTOK = "joyreliefstation"
GATE_HOURS = 20


def _now():
    return _dt.datetime.now(JST)


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (_now().strftime("%F %T"), msg))
    except Exception:
        pass


def _read_json(p, default):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ────────────────────────── ① 集める ──────────────────────────
SONG_URL = re.compile(r"/cover-guide\?([^\s\"'<>)]+)")


def song_key_from_text(text):
    """本文の自サイトURL（/cover-guide?artist=..&song=..）から曲キーを取る。"""
    for m in SONG_URL.finditer(text or ""):
        q = urllib.parse.parse_qs(m.group(1).replace("&amp;", "&"))
        a = (q.get("artist") or [""])[0]
        s = (q.get("song") or [""])[0]
        if a and s:
            return "%s/%s" % (a, s)
    return None


def from_buffer(now_utc):
    """Buffer に入れた控え（正本）。予定時刻を過ぎたもの＝もう出たもの。"""
    out = []
    try:
        lines = io.open(DASHITA, encoding="utf-8").read().splitlines()
    except Exception:
        return out, "dashita.jsonl が読めない"
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        where = r.get("where") or ""
        due = r.get("due_utc") or ""
        m = re.search(r"\((\d{4}-\d\d-\d\dT[\d:.]+Z)\)", where)
        if not due and m:
            due = m.group(1)
        manual = "手でXに投稿" in where
        if due and due > now_utc and not manual:
            continue  # まだ予定（出ていない）
        key = r.get("song_key")
        out.append({
            "platform": "x",
            "via": "buffer" if not manual else "manual",
            "at": due or r.get("at") or "",
            "url": ("https://x.com/oasisjoyrelief (Buffer %s)" % r.get("post_id")) if r.get("post_id") else "",
            "songKey": urllib.parse.unquote(key) if key else None,
            "text": (r.get("head") or "")[:200],
            "id": "buffer:%s" % (r.get("post_id") or r.get("text_key") or due),
        })
    return out, ""


def from_x_live():
    d = _read_json(X_LIVE, {})
    out = []
    for t in d.get("toukou") or []:
        body = t.get("honbun") or ""
        out.append({
            "platform": "x",
            "via": "x",
            "at": t.get("itsu") or "",
            "url": t.get("url") or "",
            "songKey": song_key_from_text(body),
            "text": body[:200],
            "id": "x:%s" % t.get("id"),
        })
    return out, ("" if out else "x_toukou の取り出しが空（%s）" % (d.get("at") or "未実行"))


def from_sns_log(jrs_dir):
    p = os.path.join(jrs_dir, "docs", "operations", "sns-post-log.json")
    d = _read_json(p, {})
    out = []
    for e in d.get("posts") or []:
        if e.get("status") != "posted":
            continue
        out.append({
            "platform": "x",
            "via": "sns-post-log",
            "at": e.get("date") or "",
            "url": e.get("postedUrl") or "",
            "songKey": song_key_from_text(e.get("pageUrl") or ""),
            "text": "%s %s" % (e.get("artist") or "", e.get("songTitle") or ""),
            "id": "x:%s" % ((e.get("postedUrl") or "").rsplit("/", 1)[-1] or e.get("id")),
        })
    return out, ""


def _curl(url, timeout=30):
    """Mac の curl（0円・鍵なし）。サンドボックスでは届かないことがある。"""
    try:
        r = subprocess.run(["curl", "-sL", "-m", str(timeout), "-A",
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
                            url], capture_output=True, timeout=timeout + 5)
        return r.stdout.decode("utf-8", "ignore")
    except Exception:
        return ""


YT_HANDLE = "joy-relief-station"
MAX_DETAIL_FETCH = 25  # 1日に詳しく見に行く本数（新しい投稿だけ・叩きすぎない）


def _old_posts():
    return {p["id"]: p for p in (_read_json(DAICHO, {}).get("posts") or []) if p.get("id")}


def _json_str(raw):
    try:
        return json.loads('"' + raw + '"')
    except Exception:
        return raw


def tiktok_detail(vid):
    """TikTok の1本：公開の動画ページから「使った音（曲名・アーティスト）」と本文。取れなければ oEmbed の題。0円・ログイン無し。"""
    url = "https://www.tiktok.com/@%s/video/%s" % (TIKTOK, vid)
    html = _curl(url)
    music, desc, ts = None, "", None
    i = html.find('"music":{"id"')
    if i >= 0:
        seg = html[i:i + 4000]
        t = re.search(r'"title":"((?:[^"\\]|\\.)*)"', seg)
        a = re.search(r'"authorName":"((?:[^"\\]|\\.)*)"', seg)
        orig = re.search(r'"original":(true|false)', seg)
        if t and not (orig and orig.group(1) == "true"):
            music = {"title": _json_str(t.group(1)), "artist": _json_str(a.group(1)) if a else ""}
    m = re.search(r'"desc":"((?:[^"\\]|\\.)*)"', html)
    if m:
        desc = _json_str(m.group(1))
    m = re.search(r'"createTime":"?(\d{9,11})', html)
    if m:
        ts = int(m.group(1))
    if not desc:
        try:
            o = json.loads(_curl("https://www.tiktok.com/oembed?url=%s" % urllib.parse.quote(url, safe=":/")) or "{}")
            desc = o.get("title") or ""
        except Exception:
            pass
    return {"music": music, "desc": desc, "ts": ts}


def from_tiktok():
    """一覧は公開の「クリエイター埋め込み」ページ（tiktok.com/embed/@名前）から。本人ページはログイン無しだと一覧を返さない。
    status/toukou_daicho_config.json の tiktok_urls に書いたURLも足す（たまごさんが個別に渡したもの）。"""
    cfg = _read_json(CONFIG, {})
    html = _curl("https://www.tiktok.com/embed/@%s" % TIKTOK)
    ids = {}
    for mm in re.finditer(r'"id":"(\d{18,20})".{0,400}?"desc":"((?:[^"\\]|\\.)*)"', html, re.S):
        ids.setdefault(mm.group(1), _json_str(mm.group(2)))
    for vid in re.findall(r"/video/(\d{18,20})", html):
        ids.setdefault(vid, "")
    for u in cfg.get("tiktok_urls") or []:
        if "vt.tiktok.com" in u or "vm.tiktok.com" in u:
            u = _final_url(u) or u  # 短いリンクは飛び先（/video/数字）を見る
        m = re.search(r"/video/(\d{18,20})", u)
        if m:
            ids.setdefault(m.group(1), "")
    old = _old_posts()
    out, fetched = [], 0
    for vid, desc in ids.items():
        pid = "tiktok:%s" % vid
        prev = old.get(pid) or {}
        music, ts = prev.get("music"), None
        if (not prev or not prev.get("music")) and fetched < MAX_DETAIL_FETCH:
            d = tiktok_detail(vid)
            fetched += 1
            music, desc, ts = d["music"] or music, d["desc"] or desc, d["ts"]
        at = prev.get("at") or (_dt.datetime.fromtimestamp(ts, JST).isoformat() if ts else
                                _dt.datetime.fromtimestamp(int(vid) >> 32, JST).isoformat())
        text = desc or prev.get("text") or ""
        out.append({"platform": "tiktok", "via": "tiktok-embed", "at": at,
                    "url": "https://www.tiktok.com/@%s/video/%s" % (TIKTOK, vid),
                    "songKey": song_key_from_text(text) or prev.get("songKey"),
                    "music": music, "text": text[:300], "id": pid})
    return out, ("" if out else "TikTok の公開埋め込みページから一覧が取れない")


def youtube_detail(vid):
    """YouTube の1本：公開の再生ページから説明文と「使っている曲」（ショートの音楽の表示）。0円・鍵なし。"""
    html = _curl("https://www.youtube.com/watch?v=%s" % vid)
    d = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', html)
    t = re.search(r"<title>([^<]*)</title>", html)
    music = None
    m = re.search(r'"videoAttributeViewModel":\{(.{0,1500})', html)
    if m:
        seg = m.group(1)
        tt = re.search(r'"title":"((?:[^"\\]|\\.)*)"', seg)
        st = re.search(r'"subtitle":"((?:[^"\\]|\\.)*)"', seg)
        if tt:
            music = {"title": _json_str(tt.group(1)), "artist": _json_str(st.group(1)) if st else ""}
    return {"desc": _json_str(d.group(1)) if d else "",
            "title": (t.group(1).replace(" - YouTube", "") if t else ""), "music": music}


def _yt_channel_id(cfg):
    ch = cfg.get("youtube_channel_id")
    if ch:
        return ch
    html = _curl("https://www.youtube.com/@%s" % (cfg.get("youtube_handle") or YT_HANDLE))
    m = re.search(r'"externalId":"(UC[\w-]{20,})"', html) or re.search(r'"channelId":"(UC[\w-]{20,})"', html)
    if m:
        cfg["youtube_channel_id"] = m.group(1)
        _write_json(CONFIG, cfg)
        return m.group(1)
    return None


def from_youtube():
    """@joy-relief-station（ショート含む）。新しい15本は公開RSS、それより前はチャンネルのショート一覧ページから。"""
    cfg = _read_json(CONFIG, {})
    ch = _yt_channel_id(cfg)
    if not ch:
        return [], "YouTube のチャンネルIDが取れない（@%s）" % (cfg.get("youtube_handle") or YT_HANDLE)
    vids = {}
    xml = _curl("https://www.youtube.com/feeds/videos.xml?channel_id=%s" % ch)
    for e in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        vid = (re.search(r"<yt:videoId>([^<]+)", e) or [None, ""])[1]
        vids[vid] = {"title": (re.search(r"<title>([^<]*)", e) or [None, ""])[1],
                     "desc": (re.search(r"<media:description>([^<]*)", e, re.S) or [None, ""])[1],
                     "at": (re.search(r"<published>([^<]+)", e) or [None, ""])[1]}
    for path in ("shorts", "videos"):
        page = _curl("https://www.youtube.com/channel/%s/%s" % (ch, path))
        for vid in re.findall(r'/shorts/([\w-]{11})|"videoId":"([\w-]{11})"', page):
            v = vid[0] or vid[1]
            vids.setdefault(v, {"title": "", "desc": "", "at": ""})
    old = _old_posts()
    out, fetched = [], 0
    for vid, info in vids.items():
        pid = "yt:%s" % vid
        prev = old.get(pid) or {}
        music = prev.get("music")
        title, desc = info["title"] or prev.get("title", ""), info["desc"]
        if (not prev or not prev.get("music")) and fetched < MAX_DETAIL_FETCH:
            d = youtube_detail(vid)
            fetched += 1
            music, desc, title = d["music"] or music, d["desc"] or desc, title or d["title"]
        text = ("%s %s" % (title, desc)).strip() or prev.get("text") or ""
        out.append({"platform": "youtube", "via": "youtube", "at": info["at"] or prev.get("at") or "",
                    "url": "https://www.youtube.com/shorts/%s" % vid,
                    "songKey": song_key_from_text(text) or prev.get("songKey"),
                    "music": music, "title": title, "text": text[:300], "id": pid})
    return out, ("" if out else "YouTube の公開RSS・一覧が空")


def _final_url(u):
    try:
        r = subprocess.run(["curl", "-sIL", "-m", "20", "-o", "/dev/null", "-w", "%{url_effective}", u],
                           capture_output=True, timeout=25)
        return r.stdout.decode("utf-8", "ignore").strip()
    except Exception:
        return ""


def tweet_result(tid):
    """X の1本：公式の埋め込み用の口（cdn.syndication tweet-result）。0円・鍵なし・GETだけ。"""
    try:
        d = json.loads(_curl("https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ja&token=a" % tid) or "{}")
    except Exception:
        return {}
    txt = d.get("text") or ""
    for u in (d.get("entities") or {}).get("urls") or []:
        if u.get("url") and u.get("expanded_url"):
            txt = txt.replace(u["url"], u["expanded_url"])
    d["_text"] = txt
    return d


def from_x_urls():
    """たまごさんが渡したXの投稿URL（status/toukou_daicho_config.json の x_urls）。Buffer を通らずに出したものを拾う。"""
    cfg = _read_json(CONFIG, {})
    old = _old_posts()
    out = []
    for u in cfg.get("x_urls") or []:
        m = re.search(r"/status/(\d+)", u)
        if not m:
            continue
        tid = m.group(1)
        pid = "x:%s" % tid
        prev = old.get(pid) or {}
        text, at = prev.get("text") or "", prev.get("at") or ""
        if not text:
            d = tweet_result(tid)
            text, at = d.get("_text") or "", d.get("created_at") or ""
        out.append({"platform": "x", "via": "x-url", "at": at, "url": "https://x.com/oasisjoyrelief/status/%s" % tid,
                    "songKey": song_key_from_text(text) or prev.get("songKey"), "text": text[:300], "id": pid})
    return out, ""


# ────────────────────────── 反応（再生数・いいね）を日々記録 ──────────────────────────
HANNOU = os.path.join(REPO, "status", "sns_hannou.json")
HANNOU_DAYS = 30  # 出してから30日までの投稿を毎日見る（叩きすぎない）


def _num(x):
    try:
        return int(str(x).replace(",", ""))
    except Exception:
        return None


def stats_of(post):
    """1投稿の反応。取れた数字だけ入れる（取れないものは書かない＝0で埋めない）。すべて0円・鍵なし。"""
    url = post.get("url") or ""
    if post.get("platform") == "tiktok":
        vid = url.rsplit("/", 1)[-1]
        html = _curl("https://www.tiktok.com/@%s/video/%s" % (TIKTOK, vid))
        i = html.find('"stats":{')
        seg = html[i:i + 600] if i >= 0 else ""
        g = lambda k: _num((re.search(r'"%s":"?(\d+)' % k, seg) or [None, None])[1])
        return {"views": g("playCount"), "likes": g("diggCount"), "comments": g("commentCount"),
                "shares": g("shareCount"), "saves": g("collectCount")}
    if post.get("platform") == "youtube":
        vid = url.rsplit("/", 1)[-1]
        html = _curl("https://www.youtube.com/watch?v=%s" % vid)
        v = re.search(r'"viewCount":"(\d+)"', html)
        lk = re.search(r'"likeCount":"?(\d+)', html) or re.search(r'"likeCountIfIndifferentNumber":"(\d+)"', html)
        return {"views": _num(v.group(1)) if v else None, "likes": _num(lk.group(1)) if lk else None}
    if post.get("platform") == "x":
        m = re.search(r"/status/(\d+)", url)
        if not m:
            return {}
        d = tweet_result(m.group(1))
        return {"likes": _num(d.get("favorite_count")), "replies": _num(d.get("conversation_count"))}
    return {}


def record_hannou(daicho):
    """status/sns_hannou.json に1日1行ずつ足す（Dispatch が読む）。同じ日に2回走ったら上書き。"""
    h = _read_json(HANNOU, {"what": "SNS投稿の反応（再生数・いいね等）。tools/toukou_mimawari.py が毎日記録。取れない数字は書かない。", "posts": {}})
    today = _now().strftime("%Y-%m-%d")
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=HANNOU_DAYS)).isoformat()
    n = 0
    for p in daicho.get("posts") or []:
        at = p.get("at") or ""
        if p.get("platform") not in ("tiktok", "youtube", "x") or (at and at[:19] < cutoff[:19]):
            continue
        if p.get("platform") == "x" and "/status/" not in (p.get("url") or ""):
            continue  # Buffer 経由で投稿IDがまだ分からないもの
        st = {k: v for k, v in (stats_of(p) or {}).items() if v is not None}
        if not st:
            continue
        rec = h["posts"].setdefault(p["id"], {"platform": p["platform"], "url": p.get("url"), "songKey": p.get("songKey"),
                                              "postedAt": at, "history": []})
        rec["songKey"] = rec.get("songKey") or p.get("songKey")
        rec["history"] = [x for x in rec["history"] if x.get("date") != today] + [dict(date=today, **st)]
        rec["latest"] = dict(date=today, **st)
        n += 1
    h["updatedAt"] = _now().isoformat()
    _write_json(HANNOU, h)
    try:  # 進捗表・Dispatch が外から読めるように公開側にも写す（数字だけ・個人情報なし）
        _write_json(os.path.join(REPO, "status", "public", "sns_hannou.json"), h)
    except Exception:
        pass
    log("反応 %d本を記録" % n)
    return n


def collect(jrs_dir=None, net=True):
    now_utc = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    old = _read_json(DAICHO, {})
    posts = {p["id"]: p for p in old.get("posts") or [] if p.get("id")}
    sources = {}
    getters = [("x_buffer", lambda: from_buffer(now_utc)), ("x_live", from_x_live), ("x_urls", from_x_urls)]
    if jrs_dir:
        getters.append(("sns_post_log", lambda: from_sns_log(jrs_dir)))
    if net:
        getters += [("tiktok", from_tiktok), ("youtube_shorts", from_youtube)]
    else:
        sources["tiktok"] = {"n": 0, "why": "このときは見ていない（--collect をネット無しで実行）"}
        sources["youtube_shorts"] = {"n": 0, "why": "このときは見ていない"}
    for name, fn in getters:
        try:
            got, why = fn()
        except Exception as e:  # 1つ落ちても他は続ける
            got, why = [], "失敗：%s" % e
        for p in got:
            prev = posts.get(p["id"])
            if prev and prev.get("songKey") and not p.get("songKey"):
                p["songKey"] = prev["songKey"]
            if prev and prev.get("songKeys") and not p.get("songKeys"):
                p["songKeys"] = prev["songKeys"]
            posts[p["id"]] = p
        sources[name] = {"n": len(got), "why": why}
    # 同じ投稿が「Buffer の控え」と「X から取り出した本文」の2つで入る。本文の頭が同じなら、控えの曲キーを写す
    #（写さないと、本文に出てくる別の人の名前＝原曲の人などで、違う曲に結んでしまう）
    heads = {}
    for p in posts.values():
        if p.get("platform") == "x" and p.get("songKey") and p.get("text"):
            heads[re.sub(r"\s+", "", p["text"])[:30]] = p["songKey"]
    for p in posts.values():
        if p.get("platform") == "x" and not p.get("songKey") and p.get("text"):
            k = heads.get(re.sub(r"\s+", "", p["text"])[:30])
            if k:
                p["songKey"] = k
    # 手で結んだ曲（status/toukou_daicho_config.json の post_song_keys：{投稿ID: [曲キー…]}）。マガジン紹介の投稿など、1本で何曲も扱う時
    for pid, keys in (_read_json(CONFIG, {}).get("post_song_keys") or {}).items():
        if pid in posts:
            posts[pid]["songKeys"] = sorted(set((posts[pid].get("songKeys") or []) + list(keys)))
    rows = sorted(posts.values(), key=lambda p: p.get("at") or "")
    daicho = {
        "updatedAt": _now().isoformat(),
        "what": "ごきげん補給所のアカウント（X @oasisjoyrelief・TikTok @joyreliefstation・YouTubeショート）に出た投稿の台帳。tools/toukou_mimawari.py が毎日作る。",
        "sources": sources,
        "songs": len({p["songKey"] for p in rows if p.get("songKey")}),
        "posts": rows,
    }
    _write_json(DAICHO, daicho)
    log("台帳 %d件（曲 %d）%s" % (len(rows), daicho["songs"],
                                 " ".join("%s=%s" % (k, v["n"]) for k, v in sources.items())))
    return daicho


# ────────────────────────── ② 点検 ──────────────────────────
def _git(args, cwd, timeout=300):
    env = dict(os.environ)
    cmd = ["git"]
    try:
        tok = io.open(GH_TOKEN_FILE).read().strip()
        if tok:
            import base64
            b = base64.b64encode(("x-access-token:%s" % tok).encode()).decode()
            cmd += ["-c", "http.extraheader=Authorization: Basic %s" % b]
    except Exception:
        pass
    return subprocess.run(cmd + args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def check():
    """joy-relief-station の最新 main を一時の作業場に出して点検する。作業場は終わったら必ず消す。"""
    if not os.path.isdir(os.path.join(JRS, ".git")):
        return {"ok": False, "why": "joy-relief-station の手元の複製が無い（%s）" % JRS}
    log("点検 開始（%s）" % JRS)
    r = _git(["fetch", "-q", "origin", "main"], JRS)
    if r.returncode != 0:
        log("fetch 失敗：%s" % (r.stderr or "")[:200])
    wt = tempfile.mkdtemp(prefix="toukou_wt_", dir="/private/tmp" if os.path.isdir("/private/tmp") else None)
    try:
        r = _git(["worktree", "add", "--detach", "-f", wt, "origin/main"], JRS)
        if r.returncode != 0:
            return {"ok": False, "why": "作業場を作れない：%s" % (r.stderr or "")[:200]}
        nm = os.path.join(JRS, "node_modules")
        if os.path.isdir(nm):
            os.symlink(nm, os.path.join(wt, "node_modules"))
        ledger_in = os.path.join(wt, "docs", "operations", "posted-songs.json")
        shutil.copyfile(DAICHO, ledger_in)
        log("作業場 %s で点検を走らせる" % wt)
        out = os.path.join(REPO, "status", "public", "toukou_tenken.json.tmp")
        r = subprocess.run(["npx", "tsx", "--import", "./scripts/_asset-stub.mjs",
                            "scripts/patrol/check-posted-songs.mts", "--ledger", ledger_in,
                            "--json", out, "--oembed"], cwd=wt, capture_output=True, text=True, timeout=1500)
        if not os.path.exists(out):
            return {"ok": False, "why": "点検が結果を出さなかった：%s" % ((r.stderr or r.stdout or "")[-300:])}
        os.replace(out, TENKEN)
        res = _read_json(TENKEN, {})
        log("点検 曲%s 合格%s 不合格%s" % (res.get("songs"), res.get("pass"), res.get("fail")))
        # 台帳がサイトの写しと違うか（違えば、直す仕事に「写しを入れる」も含める）
        site_copy = _git(["show", "origin/main:docs/operations/posted-songs.json"], JRS).stdout
        res["_ledger_changed"] = _ledger_keys(site_copy) != _ledger_keys(io.open(DAICHO, encoding="utf-8").read())
        return {"ok": True, "result": res}
    finally:
        # 使ったらしまう：作業場は自分で消す（worktree_taihi も拾う）
        try:
            _git(["worktree", "remove", "--force", wt], JRS, timeout=120)
        except Exception:
            pass
        shutil.rmtree(wt, ignore_errors=True)
        try:
            _git(["worktree", "prune"], JRS, timeout=60)
        except Exception:
            pass


def _ledger_keys(text):
    try:
        d = json.loads(text or "{}")
    except Exception:
        return set()
    return {p.get("songKey") for p in d.get("posts") or [] if p.get("songKey")}


# ────────────────────────── ③ 直す仕事を積む ──────────────────────────
def build_job(res, today):
    ng = [it for it in res.get("items") or [] if not it.get("ok")]
    lines = []
    for it in ng[:40]:
        lines.append("- %s「%s」 %s ：%s" % (it.get("artist"), it.get("title"), it.get("url"), " ／ ".join(it.get("fails") or [])))
    more = "" if len(ng) <= 40 else "\n（ほか%d曲。全部は status/public/toukou_tenken.json）" % (len(ng) - 40)
    unm = res.get("unmatchedPosts") or []
    text = (
        "【タスク】SNSに出した曲の曲ページを、5点（検索・関連4本以上・メモと出典・マガジンへの入口・動画）を満たすまで直して本番に出す（%s の見回り）\n"
        "【落ちた曲】%d曲\n%s%s\n"
        "【台帳】tamago-shinchoku/status/public/toukou_daicho.json を joy-relief-station の docs/operations/posted-songs.json に写す（%s）\n"
        "【直し方】関連は理由の言えるものだけ（src/lib/relatedReason.ts・shelfPicks.ts の手書き・moodThreads.ts の気分の糸・coverGuide.ts の relatedProjects）。"
        "メモは sekisho-jijitsu-shutten の関所を通し、出典を src に入れる。検索で出ないものは src/lib/searchCards.ts／searchVariants.ts を直す（曲だけの手当てで済ませない）。"
        "新しい日本語は src/i18n/overlay の4言語に訳を足す。見た目は変えない。\n"
        "【点検】npx tsx --import ./scripts/_asset-stub.mjs scripts/patrol/check-posted-songs.mts --oembed で全曲合格\n"
        "【公開】prebuild の関所を全部通して push → Lovable の deploy_project → tools/koukai_kakunin.py で本番が変わったことまで\n"
        "【曲に結べなかった投稿】%d件（本文に曲名とアーティスト名が無い）。分かるものは台帳の songKey を埋める。\n"
        "【報告】完了/問題/判断待ち、3行以内。たまごさんに質問しない。"
    ) % (today, len(ng), "\n".join(lines), more,
         "変わっている" if res.get("_ledger_changed") else "変わっていなければ不要", len(unm))
    return text, len(ng)


def enqueue(res):
    today = _now().strftime("%Y-%m-%d")
    ng_n = sum(1 for it in res.get("items") or [] if not it.get("ok"))
    if ng_n == 0 and not res.get("_ledger_changed"):
        log("落ちた曲0・台帳変化なし → 積まない")
        return None
    text, n = build_job(res, today)
    try:
        import command_ingest
        r = command_ingest.queue_add(text, priority=2,
                                     label="投稿済み曲のページを直す %s（%d曲）" % (today, n),
                                     origin="factory", model="claude-sonnet-5")
        log("仕事を積んだ：%s" % (r,))
        return r
    except Exception as e:
        log("仕事を積めなかった：%s" % e)
        return None


# ────────────────────────── 入口 ──────────────────────────
def daily(force=False):
    if not force:
        try:
            if time.time() - os.path.getmtime(STAMP) < GATE_HOURS * 3600:
                return "skip"
        except OSError:
            pass
        if _now().hour < 6:
            return "skip"
    io.open(STAMP, "w").write(_now().isoformat())
    # X の手で出した分も拾えるよう、取り出し係を先に1回（0円・GETだけ）
    try:
        subprocess.run(["python3", os.path.join(HERE, "x_toukou.py")], capture_output=True, timeout=180)
    except Exception:
        pass
    d = collect(jrs_dir=JRS, net=True)
    try:
        record_hannou(d)
    except Exception as e:
        log("反応の記録で落ちた：%r" % (e,))
    try:
        c = check()
    except Exception as e:  # 落ちた理由を必ず残す（黙って死なない）
        c = {"ok": False, "why": "点検の途中で落ちた：%r" % (e,)}
    if not c.get("ok"):
        log("点検できず：%s" % c.get("why"))
        _write_json(TENKEN, {"at": _now().isoformat(), "error": c.get("why")})
        return "check-failed"
    enqueue(c["result"])
    return "done"


def self_test():
    assert song_key_from_text("見て https://joy-relief-station.lovable.app/cover-guide?artist=hotei-tomoyasu&song=dancing-with-the-moonlight #布袋") == "hotei-tomoyasu/dancing-with-the-moonlight"
    assert song_key_from_text("リンク無し") is None
    assert _ledger_keys('{"posts":[{"songKey":"a/b"},{"songKey":null}]}') == {"a/b"}
    text, n = build_job({"items": [{"ok": False, "artist": "A", "title": "T", "url": "u", "fails": ["関連が2本"]},
                                   {"ok": True}], "_ledger_changed": True}, "2026-10-17")
    assert n == 1 and "関連が2本" in text and "変わっている" in text
    print("SELF-TEST OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        self_test()
    elif "--hannou" in a:
        print("反応", record_hannou(_read_json(DAICHO, {})))
    elif "--collect" in a:
        d = collect(jrs_dir=JRS if os.path.isdir(JRS) else None, net="--no-net" not in a)
        print("台帳 %d件 曲%d" % (len(d["posts"]), d["songs"]))
    elif "--check" in a:
        c = check()
        print(json.dumps({k: v for k, v in c.items() if k != "result"}, ensure_ascii=False),
              (c.get("result") or {}).get("pass"), (c.get("result") or {}).get("fail"))
    else:
        print(daily(force="--force" in a))
