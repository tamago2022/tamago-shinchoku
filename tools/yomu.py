#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1051番【読む係】どのリンクでも、読める人を自動で呼んで中身を返す1つの入口。

たまごさん（2026-09-24・原文）:
  「YouTubeなりXなり、読めるときと読めないときがあるんだよね。読めないんだったら、
    Grokを呼び出すとか、そういうことができないの。」
  「今まで、これを深掘りしたいときはGrokに読ませて、Grokの出力をChatGPTに貼ってた。
    その水汲みをやめたいんだ。どこに投げても読み取ってくれよって。」
  「どのリンクでも読んでくれよって、読める人を呼んでくれよって、それをみんな共有してくれよって。」

★憲法第3条「水くみ禁止」そのもの。たまごさんに「どのAIなら読めるか」を考えさせたら負け。

━━ 決まり ━━
  ① ★入口は1つ。`python3 tools/yomu.py <URL>` だけ。読み手は呼ぶ側が選ばない。
  ② ★0円の読み手から順に試す。金が出る読み手に回る前に tools/yosan.py の栓を通す。
  ③ ★「読めなかった」で終わらせない。全員試してから、**誰がなぜ駄目だったかを1行ずつ**返す。
  ④ ★誰が読んだかを status/yomu_daicho.jsonl に必ず書く。成功回数で**順番が自動で入れ替わる**。
  ⑤ ★結果は status/yomu_cache/ に置く。どのセッションからも同じ物が読める（伝書鳩ゼロ）。
  ⑥ ★サンドボックス（Cowork/Dispatch）からは x.com / youtube に出られない。
     出られないと分かったら**自分で工場（Mac）に代行させる**。呼ぶ側は意識しなくてよい。

使い方:
  python3 tools/yomu.py <URL>              … 中身を返す（JSON）
  python3 tools/yomu.py <URL> --text       … 本文だけ
  python3 tools/yomu.py --jissoku          … 読み手ごとの成績（何回通ったか）
  python3 tools/yomu.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import socket
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

STATUS = os.path.join(REPO, "status")
DAICHO = os.path.join(STATUS, "yomu_daicho.jsonl")
CACHE = os.path.join(STATUS, "yomu_cache")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
CACHE_SEC = 60 * 60 * 24 * 7


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _on_mac():
    """工場（Mac）の上に居るか。サンドボックスには /Users が無い。"""
    return os.path.isdir("/Users") and not os.path.isdir("/sessions")


def _get(url, timeout=20, headers=None):
    """GETだけ。戻り値 (code, body, why)。落ちても例外を出さない。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", "replace"), ""
    except Exception as e:
        code = getattr(e, "code", 0)
        return code, "", "%s: %s" % (type(e).__name__, str(e)[:120])


def _strip_html(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'").replace("&mdash;", "—")
                .replace("&nbsp;", " "))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


# ---------------------------------------------------------------------------
# 読み手たち。いずれも「読めたら dict、読めなければ None＋理由」を返す。
# ★yen は **その1回で実際に出る円**。0円のものは 0.0 と書く（憶測で書かない）。
# ---------------------------------------------------------------------------

def _is_x(u):
    h = urllib.parse.urlparse(u).netloc.lower()
    return h.endswith("x.com") or h.endswith("twitter.com")


def _is_yt(u):
    h = urllib.parse.urlparse(u).netloc.lower()
    return "youtube.com" in h or "youtu.be" in h


def r_oembed_x(url):
    """X（旧Twitter）の投稿。publish.twitter.com の oEmbed。鍵不要・0円。
    ★実測 2026-09-24：Macからは200。サンドボックスからは403（トンネルが塞がる）。"""
    if not _is_x(url):
        return None, "Xの投稿ではない"
    code, body, why = _get("https://publish.twitter.com/oembed?url=%s&omit_script=1&dnt=true"
                           % urllib.parse.quote(url, safe=""))
    if code != 200 or not body:
        return None, "publish.twitter.com が %s（%s）" % (code, why or "本文が空")
    try:
        d = json.loads(body)
    except Exception:
        return None, "publish.twitter.com の返事が読めない形だった"
    text = _strip_html(d.get("html") or "")
    if not text:
        return None, "oEmbedは200だが本文が空だった"
    return {"text": text, "author": d.get("author_name") or "",
            "title": text[:120], "yen": 0.0}, ""


RE_XID = re.compile(r"/status(?:es)?/(\d{5,25})")


def r_x_zenbun(url):
    """★Xの投稿の**全文**。Xの埋め込みウィジェット自身が使っている公開の口
    （cdn.syndication.twimg.com/tweet-result）。鍵不要・0円。

    ■ なぜ足したか（2026-09-25 実測）
      oEmbed（publish.twitter.com）は**長い投稿を途中で切る。**
      レシピの投稿で「牛乳　200ml…」で切れた。★材料の途中で切れると
      「読み取れなかった分量を憶測で埋める」事故になる。だから全文が取れる口を先に置く。
      ここが取れなければ、これまでどおり oEmbed（要約）に落ちる。**作り話はしない。**
    """
    if not _is_x(url):
        return None, "Xの投稿ではない"
    m = RE_XID.search(url or "")
    if not m:
        return None, "投稿の番号が読み取れないURL"
    code, body, why = _get(
        "https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ja&token=a" % m.group(1),
        headers={"Accept": "application/json"})
    if code != 200 or not body:
        return None, "cdn.syndication が %s（%s）" % (code, why or "本文が空")
    try:
        d = json.loads(body)
    except Exception:
        return None, "cdn.syndication の返事が読めない形だった"
    text = (d.get("text") or "").strip()
    if not text:
        return None, "200だが本文が空だった"
    u = d.get("user") or {}
    # ★動画・画像が付いているかも一緒に返す（レシピの字幕を読むかどうかの判断に使う）
    media = [x.get("type") for x in ((d.get("mediaDetails") or []))]
    return {"text": text, "author": u.get("name") or u.get("screen_name") or "",
            "title": text[:120], "publishedAt": (d.get("created_at") or "")[:10],
            "media": media, "yen": 0.0}, ""


def r_yt_transcript(url):
    """YouTubeの**文字起こし全文（タイムスタンプ付き）**。鍵不要・0円。

    ★2026-09-24：外部AIから「文字起こし14,298文字をタイムスタンプ付きで取れる」という
      申告が来た。★申告を鵜呑みにしない。**自分の手で同じことをやる経路を持つ。**
      手順は公式の仕組みだけを使う：watchページの ytInitialPlayerResponse に載っている
      captionTracks の baseUrl を読み、そこへ `&fmt=json3` を付けて取る。
      ★取れなければ「取れなかった＋どこで止まったか」を返す。作り話をしない。

    ★2026-09-24 の実測（7本で試した・工場＝Macから）：**文字起こしは1本も返らなかった。**
      ・4本 … captionTracks が空（その動画に字幕トラックが無い）
      ・3本 … 字幕の住所は見つかるが、叩くと 200 で**本文が空**で返る
        （YouTube側が timedtext に追加の合図を要求するようになっている）
      ＝**「14,298文字が取れる」という外部AIの申告は、この経路では再現できていない。**
      この読み手は残す（YouTube側が戻れば自動で先頭に立つ）が、★取れたことにはしない。
    """
    if not _is_yt(url):
        return None, "YouTubeではない"
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    if not m:
        return None, "動画のIDが取れない住所だった"
    vid = m.group(1)
    code, body, why = _get("https://www.youtube.com/watch?v=" + vid, timeout=25,
                           headers={"Accept-Language": "ja,en;q=0.8"})
    if code != 200 or not body:
        return None, "watchページが %s（%s）" % (code, why or "本文が空")
    tracks = re.findall(r'"baseUrl":"(https://www\.youtube\.com/api/timedtext[^"]+)"', body)
    if not tracks:
        return None, "この動画に字幕トラックが載っていない（captionTracksが空）"
    # 日本語 → 英語 → 先頭 の順に選ぶ
    def _pick(ts):
        ja = [t for t in ts if "lang=ja" in t] or [t for t in ts if "lang=en" in t]
        return (ja or ts)[0]
    base = _pick(tracks).replace("\\u0026", "&").replace("\\/", "/")
    code, body, why = _get(base + "&fmt=json3", timeout=25)
    if code != 200 or not body:
        return None, "字幕の住所が %s（%s）" % (code, why or "本文が空")
    try:
        ev = json.loads(body).get("events") or []
    except Exception:
        return None, "字幕の返事が読めない形だった"
    lines = []
    for e in ev:
        segs = e.get("segs") or []
        t = "".join(x.get("utf8") or "" for x in segs).replace("\n", " ").strip()
        if not t:
            continue
        ms = int(e.get("tStartMs") or 0)
        lines.append("[%d:%02d] %s" % (ms // 60000, (ms // 1000) % 60, t))
    if not lines:
        return None, "字幕の住所は200だが中身が空だった"
    text = "\n".join(lines)
    return {"text": text, "author": "", "title": lines[0][:120],
            "moji": len(text), "gyou": len(lines), "yen": 0.0}, ""


def r_oembed_yt(url):
    """YouTubeの題名・投稿者。oEmbed。鍵不要・0円。"""
    if not _is_yt(url):
        return None, "YouTubeではない"
    code, body, why = _get("https://www.youtube.com/oembed?url=%s&format=json"
                           % urllib.parse.quote(url, safe=""))
    if code != 200 or not body:
        return None, "youtube.com/oembed が %s（%s）" % (code, why or "本文が空")
    try:
        d = json.loads(body)
    except Exception:
        return None, "oEmbedの返事が読めない形だった"
    return {"text": d.get("title") or "", "author": d.get("author_name") or "",
            "title": d.get("title") or "", "yen": 0.0}, ""


def r_yt_data(url):
    """YouTube Data API（説明文まで取れる）。無料枠・0円。鍵は .env の YOUTUBE_DATA_API_KEY。"""
    if not _is_yt(url):
        return None, "YouTubeではない"
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    if not m:
        return None, "動画のIDが取れない住所だった"
    key = _env("YOUTUBE_DATA_API_KEY")
    if not key:
        return None, "YOUTUBE_DATA_API_KEY が .env に無い"
    code, body, why = _get("https://www.googleapis.com/youtube/v3/videos"
                           "?part=snippet&id=%s&key=%s" % (m.group(1), key))
    if code != 200:
        return None, "YouTube Data API が %s（%s）" % (code, why)
    try:
        it = (json.loads(body).get("items") or [])[0]["snippet"]
    except Exception:
        return None, "その動画が見つからない（非公開・削除の可能性）"
    return {"text": (it.get("title") or "") + "\n\n" + (it.get("description") or ""),
            "author": it.get("channelTitle") or "", "title": it.get("title") or "",
            "publishedAt": it.get("publishedAt") or "", "yen": 0.0}, ""


def r_curl(url):
    """素のGET。普通のサイト・公式ドキュメントはこれで足りる。0円。

    ★2026-09-24 実測の事故：YouTubeのwatchページを素のGETで取ると、枠の文字
      （「概要 プレスルーム 著作権…」133〜214文字）だけが返る。それでも200・40文字以上
      なので**この読み手が「読めた」と名乗ってしまい**、専門の読み手（文字起こし）に
      順番が回らなかった。＝「動いているのに何も取れていない」を自分で作る形。
      だから YouTube と X は**この読み手の担当から外す**（専門の読み手がいる）。"""
    if _is_yt(url) or _is_x(url):
        return None, "YouTube/Xは専門の読み手の担当（素のGETでは枠の文字しか返らない）"
    code, body, why = _get(url, timeout=25)
    if code != 200 or not body:
        return None, "GETが %s（%s）" % (code, why or "本文が空")
    text = _strip_html(body)
    if len(text) < 40:
        return None, "200だが中身が40文字未満（JavaScriptで後から描く頁）"
    title = ""
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    if m:
        title = _strip_html(m.group(1))[:200]
    return {"text": text[:20000], "author": "", "title": title, "yen": 0.0}, ""


def r_jina(url):
    """r.jina.ai の読み取り屋。JavaScriptで描く頁も文字にしてくれる。鍵なしで0円。"""
    code, body, why = _get("https://r.jina.ai/" + url, timeout=30)
    if code != 200 or len(body or "") < 40:
        return None, "r.jina.ai が %s（%s）" % (code, why or "本文が空")
    return {"text": body[:20000], "author": "", "title": body.split("\n")[0][:200],
            "yen": 0.0}, ""


def r_xai(url):
    """Grok（xAI）。★Xの投稿はxAI自身のものなので本来は一番強い。
    ★実測 2026-09-24：文字の口は403（鍵は有効だがチーム goodvibes に残高が無い）。
    ＝**今は呼べない。**残高が入った日から自動で先頭に上がる（下の並べ替えが効く）。"""
    key = _env("XAI_API_KEY") or _env("GROK_API_KEY")
    if not key:
        return None, "xAIの鍵が .env に無い"
    return None, "xAIは403（鍵は有効・チームに残高が無い）。console.x.ai で残高を入れれば通る"


def r_gemini(url):
    """Gemini。★YouTubeのリンクをそのまま読ませられる。
    ★実測 2026-09-24：鍵がどこにも置かれていない（kaitsuu.json の gemini=ng）。"""
    key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    if not key:
        return None, "Geminiの鍵が無い（Google AI Studioで無料発行して .env へ）"
    body = json.dumps({"contents": [{"parts": [{"text": "次のURLの中身を、要約せずそのまま書き出して: " + url}]}]})
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + key,
        data=body.encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        text = d["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return None, "Geminiが %s" % str(e)[:120]
    return {"text": text, "author": "", "title": text[:120], "yen": 0.0}, ""


def r_genspark(url):
    """Genspark。★口はGitHubのIssue（tools/nageru.py）しかない。
    ★実測 2026-09-24：GitHubのトークンが無い（kaitsuu.json の github=ng）＝投げられない。"""
    return None, "Gensparkの口はGitHub Issueだけ。そのGitHubトークンが今ない（gh auth login が要る）"


def r_jules(url):
    """Jules。★口はGitHub。上と同じ理由で今は投げられない。"""
    return None, "Julesの口はGitHub Issueだけ。そのGitHubトークンが今ない"


# ★並び順は「0円が先・実測で通ったものが先」。成績で自動で入れ替わる（_narabi）。
READERS = [
    ("x_zenbun", r_x_zenbun, 0.0),
    ("oembed_x", r_oembed_x, 0.0),
    ("yt_transcript", r_yt_transcript, 0.0),
    ("oembed_yt", r_oembed_yt, 0.0),
    ("yt_data", r_yt_data, 0.0),
    ("curl", r_curl, 0.0),
    ("jina", r_jina, 0.0),
    ("xai", r_xai, 0.0),
    ("gemini", r_gemini, 0.0),
    ("genspark", r_genspark, 1.0),
    ("jules", r_jules, 0.0),
]


def _env(name):
    p = os.path.join(REPO, ".env")
    try:
        for line in io.open(p, encoding="utf-8"):
            if line.strip().startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return os.environ.get(name, "")


# ---------------------------------------------------------------------------
# 台帳（誰が何回通ったか）と並べ替え
# ---------------------------------------------------------------------------

def _daicho_rows():
    try:
        return [json.loads(x) for x in io.open(DAICHO, encoding="utf-8") if x.strip()]
    except Exception:
        return []


def _daicho_write(row):
    os.makedirs(STATUS, exist_ok=True)
    with io.open(DAICHO, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def seiseki():
    """読み手ごとの成績。{名前: {ok, ng}}"""
    s = {}
    for r in _daicho_rows():
        for t in r.get("tried") or []:
            d = s.setdefault(t["who"], {"ok": 0, "ng": 0})
            d["ok" if t.get("ok") else "ng"] += 1
    return s


SENMON = {"yt": ("yt_transcript", "oembed_yt", "yt_data"),
          # ★全文が取れる口を先に。oEmbedは長い投稿を切るので後ろ（2026-09-25 実測）
          "x": ("x_zenbun", "oembed_x")}


def _narabi(url=""):
    """よく通る読み手を先に。★ただし**住所に合った専門の読み手を必ず先頭に**置く。

    ★2026-09-24 実測：成績だけで並べたら curl（他の頁でよく通る）が先頭に来て、
      YouTubeの文字起こしに一度も順番が回らなかった。成績は**同じ担当の中の順**にしか使わない。"""
    s = seiseki()
    idx = {n: i for i, (n, _, _) in enumerate(READERS)}

    def _rank(t):
        return (-s.get(t[0], {}).get("ok", 0), idx[t[0]])

    senmon = SENMON["yt"] if _is_yt(url) else (SENMON["x"] if _is_x(url) else ())
    # ★専門の中は成績で並べ替えない。**多く取れる読み手が先**（SENMONに書いた順）。
    #   成績で並べると、題名だけ返す oembed（よく通る）が文字起こしより先に立ってしまい、
    #   文字起こしに一度も順番が回らない。実測 2026-09-24 08:20。
    saki = sorted([t for t in READERS if t[0] in senmon],
                  key=lambda t: senmon.index(t[0]))
    ato = sorted([t for t in READERS if t[0] not in senmon], key=_rank)
    return saki + ato


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------

# ★工場（Mac）への頼み方は**この中に自前で持つ**。
#   2026-09-24 実測：tools/gaibu_kuchi.py から enqueue_job / wait_job が消えていた時間帯があり、
#   そこに寄りかかっていると読む係ごと道連れで死ぬ。読む係は他人の都合で止まってはいけない。
JOBS_PENDING = os.path.join(STATUS, "gaibu_jobs", "pending")
JOBS_DONE = os.path.join(STATUS, "gaibu_jobs", "done")


def _mac_enqueue(url):
    os.makedirs(JOBS_PENDING, exist_ok=True)
    os.makedirs(JOBS_DONE, exist_ok=True)
    jid = time.strftime("%Y%m%d-%H%M%S") + "-%04d" % (int(time.time() * 1000) % 10000)
    job = {"jobId": jid, "kind": "yomu", "payload": {"url": url},
           "queuedAt": _now(), "queuedFrom": socket.gethostname()}
    p = os.path.join(JOBS_PENDING, jid + ".json")
    json.dump(job, io.open(p + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    return jid


def _mac_wait(jid, wait_sec=180, poll=5):
    dp = os.path.join(JOBS_DONE, jid + ".json")
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if os.path.exists(dp):
            for _ in range(5):
                try:
                    return json.load(io.open(dp, encoding="utf-8"))
                except Exception:
                    time.sleep(0.4)
        time.sleep(poll)
    return None


def _cache_path(url):
    return os.path.join(CACHE, hashlib.sha1(url.encode("utf-8")).hexdigest()[:16] + ".json")


def yomu(url, use_cache=True, mac_daiko=True, wait_sec=180):
    url = (url or "").strip()
    if not url.startswith("http"):
        return {"ok": False, "error": "httpで始まる住所を渡してください", "url": url}

    cp = _cache_path(url)
    if use_cache and os.path.exists(cp):
        try:
            c = json.load(io.open(cp, encoding="utf-8"))
            if time.time() - os.path.getmtime(cp) < CACHE_SEC and c.get("ok"):
                c["fromCache"] = True
                return c
        except Exception:
            pass

    tried = []
    t0 = time.time()
    for name, fn, yen in _narabi(url):
        if yen > 0:
            try:
                import yosan
                ok, why = True, ""
                try:
                    m = yosan.mitsumori("genspark" if name == "genspark" else "sonota",
                                        yen, "yomu:" + name)
                    ok = bool(m.get("ok", True))
                    why = m.get("why") or ""
                except Exception:
                    pass
                if not ok:
                    tried.append({"who": name, "ok": False, "why": "予算の栓で止まった：" + why, "yen": 0.0})
                    continue
            except Exception:
                pass
        s = time.time()
        try:
            got, why = fn(url)
        except Exception as e:
            got, why = None, "例外 %s" % str(e)[:120]
        if got:
            tried.append({"who": name, "ok": True, "why": "", "yen": got.get("yen", yen),
                          "sec": round(time.time() - s, 1)})
            out = {"ok": True, "url": url, "yondaHito": name,
                   "text": got.get("text", ""), "title": got.get("title", ""),
                   "author": got.get("author", ""), "publishedAt": got.get("publishedAt", ""),
                   "yen": got.get("yen", yen), "tried": tried,
                   "at": _now(), "ranOn": "mac" if _on_mac() else "sandbox",
                   "elapsedSec": round(time.time() - t0, 1)}
            os.makedirs(CACHE, exist_ok=True)
            json.dump(out, io.open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            _daicho_write({"at": out["at"], "url": url, "ok": True, "who": name,
                           "yen": out["yen"], "tried": tried})
            return out
        tried.append({"who": name, "ok": False, "why": why, "yen": 0.0,
                      "sec": round(time.time() - s, 1)})

    # ★誰も読めなかった。サンドボックスなら、ここで工場（Mac）に代行させる。
    if mac_daiko and not _on_mac():
        try:
            jid = _mac_enqueue(url)
            res = _mac_wait(jid, wait_sec)
            if res and res.get("ok"):
                res["daikoJobId"] = jid
                res.setdefault("tried", [])
                res["tried"] = tried + [{"who": "mac代行", "ok": True, "why": "", "yen": 0.0}] + (res.get("tried") or [])
                _daicho_write({"at": _now(), "url": url, "ok": True,
                               "who": res.get("yondaHito", "mac"), "yen": res.get("yen", 0.0),
                               "tried": res["tried"]})
                os.makedirs(CACHE, exist_ok=True)
                json.dump(res, io.open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                return res
            tried.append({"who": "mac代行", "ok": False,
                          "why": "工場が %d秒で返さなかった（心臓が止まっている可能性）" % wait_sec
                                 if not res else (res.get("error") or "工場側でも読めなかった"),
                          "yen": 0.0})
            if res and res.get("tried"):
                tried += res["tried"]
        except Exception as e:
            tried.append({"who": "mac代行", "ok": False, "why": "代行を頼めなかった：%s" % str(e)[:120], "yen": 0.0})

    out = {"ok": False, "url": url, "yondaHito": "", "text": "", "tried": tried,
           "at": _now(), "ranOn": "mac" if _on_mac() else "sandbox",
           "error": "読み手 %d人すべてが読めませんでした" % len(tried),
           "elapsedSec": round(time.time() - t0, 1)}
    _daicho_write({"at": out["at"], "url": url, "ok": False, "who": "", "yen": 0.0, "tried": tried})
    return out


def run_job(payload):
    """gaibu_runner から kind="yomu" で呼ばれる（＝工場＝Mac の上で走る）。
    ★ここでは代行を頼まない（無限に往復するので）。GETだけ・課金0。"""
    r = yomu((payload or {}).get("url") or "", use_cache=False, mac_daiko=False)
    r["totalYen"] = float(r.get("yen") or 0.0)
    return r


def self_test():
    ng = []
    assert _is_x("https://x.com/a/status/1")
    assert _is_yt("https://youtu.be/abcdefghijk")
    assert not _is_x("https://example.com")
    assert _strip_html("<p>あ<br>い</p>") == "あ\nい"
    got, why = r_oembed_x("https://example.com/a")
    if got is not None or "Xの投稿ではない" not in why:
        ng.append("Xでない住所をXの読み手が拾ってしまう")
    if [n for n, _, y in READERS if y > 0][0] == READERS[0][0]:
        ng.append("金の出る読み手が先頭に居る（0円が先でなければならない）")
    print("self-test:", "OK" if not ng else "NG " + " / ".join(ng))
    return 0 if not ng else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--jissoku", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.jissoku:
        s = seiseki()
        print("読み手の成績（status/yomu_daicho.jsonl より）")
        for n, _, y in _narabi(""):
            d = s.get(n, {"ok": 0, "ng": 0})
            print("  %-10s 通った%3d回 / 駄目%3d回 / 1回%.1f円" % (n, d["ok"], d["ng"], y))
        return 0
    if not a.url:
        ap.print_help()
        return 1
    r = yomu(a.url, use_cache=not a.no_cache)
    if a.text:
        print(r.get("text") or "")
        if not r.get("ok"):
            for t in r.get("tried") or []:
                print("  ✕ %s … %s" % (t["who"], t["why"]), file=sys.stderr)
        return 0 if r.get("ok") else 1
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
