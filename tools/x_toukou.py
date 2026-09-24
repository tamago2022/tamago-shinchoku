#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1075番【Xの投稿を取る係】@oasisjoyrelief の投稿の**本文**を、道を全部試して取る。

たまごさん（2026-09-24・原文）:
  「俺のTwitterが読めない。プロフィールは読めるけど、ツイートが読めない。」
  「Xもプロフィールまでは読めるんだけど、投稿が読めないんだって残念ながら。」

★「読めません」で終わらせない。**誰がなぜ駄目だったかを1行ずつ**返す。

━━ 試す順（0円のものから）━━
  ① syndication.twimg.com の timeline-profile
       …公式の埋め込み用の口。鍵不要・0円。本文がそのまま入っている。
  ② cdn.syndication.twimg.com/tweet-result（①で id だけ取れて本文が無いとき）
  ③ publish.twitter.com の oEmbed（1本ずつ・鍵不要・0円／yomu.py と同じ道）
  ④ ダメなら「本人のアーカイブ」の入り口URLを1本だけ返す
       …本人なら API の制限に関係なく**全投稿**を取れる。押すのは1回きり。

━━ なぜ工場（Mac）側で走るか ━━
  サンドボックスからは x.com / publish.twitter.com / syndication.twimg.com とも
  curl が 000（実測 2026-09-24 09:06）。＝向こうは票を置くだけ。読むのはここ。

━━ 決まり ━━
  ★GETだけ。1件も投稿しない・消さない・いいねしない。★鍵を使わない。★課金0。
  ★ブラウザを開かない。たまごさんのBraveに触らない。
  ★書き先は status/1075_x/ だけ。

口:
  run_job({"op":"toru","user":"oasisjoyrelief"})
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT_DIR = os.path.join(REPO, "status", "1075_x")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# ★白名簿：ここ以外へは1本も出ない
ALLOW = ("https://syndication.twimg.com/", "https://cdn.syndication.twimg.com/",
         "https://publish.twitter.com/", "https://x.com/", "https://twitter.com/")

# 本人アーカイブの入り口（押すのは本人・1回きり）
ARCHIVE_URL = "https://x.com/settings/download_your_data"


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _get(url, timeout=25, headers=None):
    if not url.startswith(ALLOW):
        return 0, "", "白名簿の外"
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "ja,en;q=0.8",
                                               **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", "replace"), ""
    except Exception as e:
        return getattr(e, "code", 0), "", "%s: %s" % (type(e).__name__, str(e)[:110])


def _strip(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>", "\n", html)
    t = re.sub(r"<[^>]+>", " ", html)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&#39;", "'"), ("&nbsp;", " "), ("&mdash;", "—")):
        t = t.replace(a, b)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def _id_to_time(i):
    try:
        return time.strftime("%Y-%m-%d %H:%M",
                             time.localtime(((int(i) >> 22) + 1288834974657) / 1000))
    except Exception:
        return ""


# ───────────────────── ① syndication の timeline-profile ─────────────────────

def _michi1(user):
    url = ("https://syndication.twimg.com/srv/timeline-profile/screen-name/%s"
           % urllib.parse.quote(user))
    code, body, why = _get(url)
    if code != 200 or not body:
        return [], "timeline-profile が %s（%s）" % (code, why or "本文が空")

    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
    if not m:
        return [], "timeline-profile は200だが __NEXT_DATA__ が無かった"
    try:
        d = json.loads(m.group(1))
    except Exception as e:
        return [], "__NEXT_DATA__ が読めない形だった: %s" % str(e)[:80]

    found = {}

    def walk(o):
        if isinstance(o, dict):
            tid = o.get("id_str") or o.get("rest_id")
            txt = o.get("full_text") or o.get("text")
            if tid and txt and re.fullmatch(r"\d{15,25}", str(tid)):
                found.setdefault(str(tid), o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    out = []
    for tid, o in found.items():
        txt = o.get("full_text") or o.get("text") or ""
        ents = (o.get("entities") or {}).get("urls") or []
        for u in ents:
            if u.get("url") and u.get("expanded_url"):
                txt = txt.replace(u["url"], u["expanded_url"])
        u = o.get("user") or {}
        out.append({"id": tid, "honbun": txt.strip(),
                    "dare": (u.get("screen_name") or ""),
                    "itsu": o.get("created_at") or _id_to_time(tid),
                    "url": "https://x.com/%s/status/%s" % (user, tid),
                    "fav": o.get("favorite_count") or 0,
                    "rt": o.get("retweet_count") or 0,
                    "dokokara": "syndication"})
    return out, "" if out else "timeline-profile に投稿が1件も入っていなかった"


# ───────────────────── ② cdn.syndication の tweet-result ─────────────────────

def _michi2(tid):
    url = ("https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ja&token=a" % tid)
    code, body, why = _get(url)
    if code != 200 or not body:
        return None, "tweet-result が %s（%s）" % (code, why or "空")
    try:
        d = json.loads(body)
    except Exception:
        return None, "tweet-result の返事が読めない形だった"
    txt = d.get("text") or ""
    if not txt:
        return None, "tweet-result は200だが本文が空"
    return {"id": str(tid), "honbun": txt.strip(),
            "dare": ((d.get("user") or {}).get("screen_name") or ""),
            "itsu": d.get("created_at") or _id_to_time(tid),
            "url": "https://x.com/i/status/%s" % tid,
            "fav": d.get("favorite_count") or 0, "rt": 0,
            "dokokara": "tweet-result"}, ""


# ───────────────────── ③ publish.twitter.com の oEmbed ─────────────────────

def _michi3(url_of_tweet):
    code, body, why = _get("https://publish.twitter.com/oembed?url=%s&omit_script=1&dnt=true"
                           % urllib.parse.quote(url_of_tweet, safe=""))
    if code != 200 or not body:
        return None, "oEmbed が %s（%s）" % (code, why or "空")
    try:
        d = json.loads(body)
    except Exception:
        return None, "oEmbed の返事が読めない形だった"
    txt = _strip(d.get("html") or "")
    if not txt:
        return None, "oEmbed は200だが本文が空"
    return {"honbun": txt, "dare": d.get("author_name") or "",
            "url": url_of_tweet, "dokokara": "oembed"}, ""


# ───────────────────────────────── 口 ─────────────────────────────────

def _id_sagashi(user):
    """★投稿のidを探す。①〜③はidかURLが要る口なので、ここが本当の関門。
    x.com は中身をJSで描くので、そのままでは本文が入っていないことが多い。
    ★UAを変えると**そのまま組み上げたHTML**を返す口があるか、1つずつ実測する。"""
    uas = [
        ("ふつうのChrome", UA),
        ("Googlebot", "Mozilla/5.0 (compatible; Googlebot/2.1; "
                      "+http://www.google.com/bot.html)"),
        ("Twitterbot", "Twitterbot/1.0"),
        ("Bingbot", "Mozilla/5.0 (compatible; bingbot/2.0; "
                    "+http://www.bing.com/bingbot.htm)"),
        ("facebookexternalhit", "facebookexternalhit/1.1"),
    ]
    saki = ["https://x.com/%s" % user,
            "https://twitter.com/%s" % user,
            "https://x.com/%s/with_replies" % user]
    tried, ids = [], set()
    for na, ua in uas:
        for u in saki:
            code, body, why = _get(u, timeout=30, headers={"User-Agent": ua})
            found = set(re.findall(r"/status(?:es)?/(\d{15,25})", body))
            found |= set(re.findall(r'"(?:id_str|rest_id)"\s*:\s*"(\d{15,25})"', body))
            tried.append({"ua": na, "url": u, "code": code, "nagasa": len(body),
                          "mitsuketaId": len(found), "why": why})
            ids |= found
            if found:
                break
        if ids:
            break
    return sorted(ids, reverse=True), tried


def _shindan(user):
    """★工場（Mac）からどの口まで出られるかを1本ずつ実測する。推測を書かないため。"""
    saki = [
        ("x.com のプロフィール", "https://x.com/%s" % user),
        ("syndication timeline-profile",
         "https://syndication.twimg.com/srv/timeline-profile/screen-name/%s" % user),
        ("cdn.syndication tweet-result",
         "https://cdn.syndication.twimg.com/tweet-result?id=20&lang=ja&token=a"),
        ("publish.twitter.com oEmbed",
         "https://publish.twitter.com/oembed?url=https%3A%2F%2Fx.com%2Fjack%2Fstatus%2F20"),
    ]
    out = []
    for na, u in saki:
        t0 = time.time()
        code, body, why = _get(u, timeout=45)
        out.append({"saki": na, "code": code, "byou": round(time.time() - t0, 1),
                    "nagasa": len(body), "why": why})
    return out


def run_job(payload):
    payload = payload or {}
    op = (payload.get("op") or "toru")
    if op == "shindan":
        u = (payload.get("user") or "oasisjoyrelief").lstrip("@")
        return {"ok": True, "op": "shindan", "user": u,
                "kekka": _shindan(u), "totalYen": 0.0}
    if op == "idsagashi":
        u = (payload.get("user") or "oasisjoyrelief").lstrip("@")
        ids, tried = _id_sagashi(u)
        return {"ok": bool(ids), "op": op, "user": u, "idSu": len(ids),
                "ids": ids[:60], "tried": tried, "totalYen": 0.0}
    if op != "toru":
        return {"ok": False, "error": "知らない op です", "totalYen": 0.0}
    user = (payload.get("user") or "oasisjoyrelief").lstrip("@")
    os.makedirs(OUT_DIR, exist_ok=True)

    tried = []
    toukou = []

    got, why = _michi1(user)
    tried.append({"michi": "① syndication timeline-profile", "ok": bool(got),
                  "kensu": len(got), "why": why})
    if got:
        toukou = got

    # ①で本文が欠けた分を②で埋める
    if toukou:
        naoshita = 0
        for t in toukou:
            if not t.get("honbun"):
                g, w = _michi2(t["id"])
                if g:
                    t.update(g)
                    naoshita += 1
        if naoshita:
            tried.append({"michi": "② cdn.syndication tweet-result", "ok": True,
                          "kensu": naoshita, "why": ""})

    # ①が空なら、x.com の組み上げたHTMLから id を探して、②③に回す。
    if not toukou:
        ids, sagashi = _id_sagashi(user)
        tried.append({"michi": "①' x.com のHTMLから投稿idを探す（UAを5通り）",
                      "ok": bool(ids), "kensu": len(ids),
                      "why": "" if ids else "どのUAでも投稿idが1つも入っていなかった",
                      "meisai": sagashi})
        n2 = n3 = 0
        why2 = why3 = ""
        for tid in ids[:60]:
            g, w = _michi2(tid)
            if g:
                g["url"] = "https://x.com/%s/status/%s" % (user, tid)
                toukou.append(g)
                n2 += 1
                continue
            why2 = why2 or w
            g, w = _michi3("https://x.com/%s/status/%s" % (user, tid))
            if g:
                g["id"] = str(tid)
                g["itsu"] = _id_to_time(tid)
                toukou.append(g)
                n3 += 1
            else:
                why3 = why3 or w
        tried.append({"michi": "② cdn.syndication tweet-result", "ok": bool(n2),
                      "kensu": n2,
                      "why": why2 if not n2 else ""} if ids else
                     {"michi": "② cdn.syndication tweet-result", "ok": False, "kensu": 0,
                      "why": "投稿のidが1つも取れていないので回せなかった（idが要る口）"})
        tried.append({"michi": "③ publish.twitter.com oEmbed", "ok": bool(n3),
                      "kensu": n3,
                      "why": why3 if not n3 else ""} if ids else
                     {"michi": "③ publish.twitter.com oEmbed", "ok": False, "kensu": 0,
                      "why": "投稿のURLが1本も取れていないので回せなかった（URLが要る口）"})
    else:
        # ③は答え合わせに1本だけ使う（0円・叩きすぎない）
        g, w = _michi3(toukou[0]["url"])
        tried.append({"michi": "③ publish.twitter.com oEmbed（1本で答え合わせ）",
                      "ok": bool(g), "kensu": 1 if g else 0, "why": w})

    toukou.sort(key=lambda t: int(t["id"]), reverse=True)
    for t in toukou:
        t["itsuJst"] = _id_to_time(t["id"])

    pj = os.path.join(OUT_DIR, "toukou_%s.json" % user)
    json.dump({"at": _now(), "user": user, "kensu": len(toukou),
               "tried": tried, "toukou": toukou},
              io.open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    pm = os.path.join(OUT_DIR, "toukou_%s.md" % user)
    with io.open(pm, "w", encoding="utf-8") as f:
        f.write("# @%s の投稿（%s）\n\n全%d件\n\n" % (user, _now(), len(toukou)))
        if not toukou:
            f.write("**取れなかった。**試した道と理由：\n\n")
            for t in tried:
                f.write("- %s … %s\n" % (t["michi"], t["why"] or "OK"))
            f.write("\n残りの道：本人のアーカイブ（本人なら全投稿が取れる）\n%s\n"
                    % ARCHIVE_URL)
        for t in toukou:
            f.write("---\n\n**%s**　%s\n\n%s\n\n" %
                    (t.get("itsuJst") or "", t["url"], t.get("honbun") or "（本文が取れず）"))

    ok = bool(toukou)
    return {"ok": ok, "user": user, "kensu": len(toukou), "tried": tried,
            "files": [os.path.relpath(pj, REPO), os.path.relpath(pm, REPO)],
            "tsugiNoMichi": None if ok else ARCHIVE_URL,
            "honbunNashi": [t["id"] for t in toukou if not t.get("honbun")],
            "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"op": "toru",
                              "user": sys.argv[1] if len(sys.argv) > 1 else "oasisjoyrelief"}),
                     ensure_ascii=False, indent=1))
