#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""リンクを読む道具（link_yomu）— 2026-10-25 たまごさん指示

目的：X・YouTube のリンクが来るたびに「スクショください」となる水汲みをゼロにする。
無料・ログイン不要・ブラウザなし・許可ポップアップなし・有料APIなし。

  X       ：①公式 oEmbed（publish.twitter.com）②FxTwitter JSON（api.fxtwitter.com）③vxtwitter（api.vxtwitter.com）
            の順で試し、取れたものを重ねる。投稿者・日時・本文（原文）・画像/動画の枚数・引用元の本文・本文中のリンク。
  YouTube ：oEmbed（題名・チャンネル）＋ yt-dlp -J（説明欄・字幕の場所）→ 字幕（手動→自動、日本語→英語）を本文にする。
            yt-dlp は ~/.tamago/bin/yt-dlp（GitHub公式の単体版。無ければ自動で取る。sudo不要）。
  その他  ：ページの <title> と og:description だけ。

使い方：
  python3 tools/link_yomu.py <URL>            # 本文テキスト → 標準出力（最後に JSON 1行）
  python3 tools/link_yomu.py <URL> --json     # JSON だけ
  python3 tools/link_yomu.py --self-test
サンドボックス（外へ出られない所）から呼ぶと、自動で status/mac_jobs/pending/ に札を置き、Mac で走らせた結果を読む。

保存：status/link_yomu/<日付>/<id>.md（30日より古い日付フォルダは自分で消す）。一時ファイルは作らない（字幕もメモリで読む）。
読めなければ：Grokボットに共有メモ経由で頼む（python3 tools/zen_ai_kyouyu.py kaku --title "このリンクを読んで" --body "<URL>"）。
"""
from __future__ import print_function

import datetime
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE = os.path.join(REPO, "status", "link_yomu")
JOBS = os.path.join(REPO, "status", "mac_jobs")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) tamago-link-yomu/1"
YTDLP = os.path.expanduser("~/.tamago/bin/yt-dlp")
KEEP_DAYS = 30


def get(url, timeout=25, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
    return b if raw else b.decode("utf-8", "replace")


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def find_links(text):
    return sorted(set(re.findall(r"https?://[^\s\"'<>）」]+", text or "")))


# ---------------- X ----------------
def x_ids(url):
    m = re.search(r"(?:x|twitter|fxtwitter|vxtwitter|fixupx)\.com/([^/?#]+)/status(?:es)?/(\d+)", url)
    return (m.group(1), m.group(2)) if m else (None, None)


def parse_oembed_html(h):
    m = re.search(r"<p[^>]*>(.*?)</p>", h, re.S)
    text = strip_tags(m.group(1)) if m else ""
    links = re.findall(r'href="([^"]+)"', m.group(1)) if m else []
    d = re.findall(r"<a [^>]*>([^<]+)</a>\s*</blockquote>", h)
    return text, (d[-1].strip() if d else ""), links


def x_from_fx(j):
    t = j.get("tweet") or {}
    media = t.get("media") or {}
    q = t.get("quote") or {}
    return {
        "author": "%s (@%s)" % ((t.get("author") or {}).get("name", ""), (t.get("author") or {}).get("screen_name", "")),
        "date": t.get("created_at", ""),
        "text": t.get("text", ""),
        "photos": len(media.get("photos") or []),
        "videos": len(media.get("videos") or []),
        "quote": ("@%s：%s" % ((q.get("author") or {}).get("screen_name", ""), q.get("text", ""))) if q else "",
        "quote_id": str(q.get("id") or ""),
        "quote_user": (q.get("author") or {}).get("screen_name", ""),
        "links": [u for u in fx_urls(t) if u],
    }


def fx_urls(st):
    return [f.get("replacement") or f.get("expanded_url") or f.get("original")
            for f in ((st.get("raw_text") or {}).get("facets") or []) if f.get("type") == "url"]


def self_thread(user, sid):
    """本人の続き（自分リプ）を [{id,date,text,links}] で返す。取れなければ (…, 理由)"""
    errs = []
    for ep, keys in (("thread", ("thread",)), ("conversation", ("thread", "replies"))):
        try:
            d = json.loads(get("https://api.fxtwitter.com/2/%s/%s" % (ep, sid)))
            me = ((d.get("status") or {}).get("author") or {}).get("screen_name") or user
            out, seen = [], set()
            for k in keys:
                for st in d.get(k) or []:
                    if not isinstance(st, dict) or str(st.get("id")) in (sid, *seen):
                        continue
                    if ((st.get("author") or {}).get("screen_name") or "").lower() != me.lower():
                        continue
                    seen.add(str(st.get("id")))
                    txt = st.get("text", "")
                    out.append({"id": str(st.get("id")), "date": st.get("created_at", ""), "text": txt,
                                "links": sorted(set([u for u in fx_urls(st) if u] + find_links(txt)))})
            return out, ""
        except Exception as e:
            errs.append("%s: %s" % (ep, str(e)[:80]))
    return [], "自分リプ取れず（%s）→ Grokボットへ回す" % " ／ ".join(errs)


def x_from_vx(j):
    mt = j.get("media_extended") or []
    qrt = j.get("qrt") or {}
    return {
        "author": "%s (@%s)" % (j.get("user_name", ""), j.get("user_screen_name", "")),
        "date": j.get("date", ""),
        "text": j.get("text", ""),
        "photos": sum(1 for m in mt if m.get("type") == "image"),
        "videos": sum(1 for m in mt if m.get("type") in ("video", "gif")),
        "quote": ("@%s：%s" % (qrt.get("user_screen_name", ""), qrt.get("text", ""))) if qrt else "",
        "links": [],
    }


def read_x(url):
    user, sid = x_ids(url)
    if not sid:
        raise ValueError("X の投稿URLではない")
    canon = "https://x.com/%s/status/%s" % (user, sid)
    r = {"kind": "x", "url": canon, "id": sid, "methods": [], "errors": []}
    try:
        j = json.loads(get("https://publish.twitter.com/oembed?omit_script=1&dnt=true&url=" + urllib.parse.quote(canon, safe="")))
        text, date, links = parse_oembed_html(j.get("html", ""))
        r.update(author=j.get("author_name", ""), date=date, text=text, links=links)
        r["methods"].append("oembed")
    except Exception as e:
        r["errors"].append("oembed: %s" % str(e)[:120])
    for name, api, conv in (("fxtwitter", "https://api.fxtwitter.com/%s/status/%s", x_from_fx),
                            ("vxtwitter", "https://api.vxtwitter.com/%s/status/%s", x_from_vx)):
        try:
            d = conv(json.loads(get(api % (user, sid))))
            if not d.get("text") and not r.get("text"):
                raise ValueError("本文が空")
            for k, v in d.items():
                if k == "text" and r.get("text"):
                    continue  # 本文は oEmbed（公式）を優先
                if v or k not in r:
                    r[k] = v
            r["methods"].append(name)
            break  # 枚数・引用まで取れたら終わり
        except Exception as e:
            r["errors"].append("%s: %s" % (name, str(e)[:120]))
    if not r["methods"]:
        r["ok"] = False
        return r
    # 自分リプ（投稿者が自分の投稿に続けて書いた返信）＝FxTwitter /2/thread → 無ければ /2/conversation の本人分
    r["self_replies"], note = self_thread(user, sid)
    if note:
        r["errors"].append(note)
    elif r["self_replies"]:
        r["methods"].append("fx-thread")
    if r.get("quote_id"):  # 引用元の本人スレッドのリンクも拾う（例：引用元の「リポジトリはコメントに」）
        qr, qnote = self_thread(r.get("quote_user") or "i", r["quote_id"])
        r["quote_self_replies"] = qr
        if qnote:
            r["errors"].append("引用元の" + qnote)
    thread_links = [u for t in (r["self_replies"] + r.get("quote_self_replies", [])) for u in t["links"]]
    r["thread_links"] = sorted(set(thread_links))
    r["links"] = sorted(set((r.get("links") or []) + find_links(r.get("text")) + thread_links))
    r["ok"] = True
    return r


# ---------------- YouTube ----------------
def yt_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/|embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def ensure_ytdlp():
    if os.path.isfile(YTDLP) and os.access(YTDLP, os.X_OK):
        if time.time() - os.path.getmtime(YTDLP) > 7 * 86400:
            subprocess.call([YTDLP, "-U"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            os.utime(YTDLP, None)
        return YTDLP
    w = shutil.which("yt-dlp")
    if w:
        return w
    if sys.platform != "darwin":
        return None
    os.makedirs(os.path.dirname(YTDLP), exist_ok=True)
    b = get("https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos", timeout=180, raw=True)
    io.open(YTDLP + ".tmp", "wb").write(b)
    os.chmod(YTDLP + ".tmp", 0o755)
    os.replace(YTDLP + ".tmp", YTDLP)
    return YTDLP


def pick_sub(info):
    """手動字幕→自動字幕、日本語→英語。(種類, 言語, json3のURL)"""
    for kind, key in (("手動字幕", "subtitles"), ("自動字幕", "automatic_captions")):
        subs = info.get(key) or {}
        for want in ("ja", "en"):
            langs = [l for l in subs if l == want or l.startswith(want + "-")]
            if kind == "自動字幕":  # 自動字幕は翻訳版が大量にあるので、原語(-orig)か素の言語を優先
                langs.sort(key=lambda l: (not l.endswith("-orig"), l != want))
            for l in langs:
                for f in subs[l]:
                    if f.get("ext") == "json3" and f.get("url"):
                        return kind, l, f["url"]
    return None, None, None


def json3_text(s):
    out = []
    for ev in json.loads(s).get("events") or []:
        t = "".join(seg.get("utf8", "") for seg in ev.get("segs") or []).strip()
        if t and (not out or out[-1] != t):
            out.append(t)
    return "\n".join(out)


def read_yt(url):
    vid = yt_id(url)
    if not vid:
        raise ValueError("YouTube の動画URLではない")
    canon = "https://www.youtube.com/watch?v=" + vid
    r = {"kind": "youtube", "url": canon, "id": vid, "methods": [], "errors": []}
    try:
        j = json.loads(get("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(canon, safe="")))
        r.update(title=j.get("title", ""), author=j.get("author_name", ""))
        r["methods"].append("oembed")
    except Exception as e:
        r["errors"].append("oembed: %s" % str(e)[:120])
    try:
        y = ensure_ytdlp()
        if not y:
            raise RuntimeError("yt-dlp が無い（Mac で走らせれば自動で入る）")
        p = subprocess.run([y, "-J", "--no-playlist", "--no-warnings", "--skip-download", canon],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=150)
        if p.returncode != 0:
            raise RuntimeError(p.stderr.decode("utf-8", "replace").strip().splitlines()[-1][:160])
        info = json.loads(p.stdout.decode("utf-8", "replace"))
        r.update(title=r.get("title") or info.get("title", ""), author=r.get("author") or info.get("channel", ""),
                 date=info.get("upload_date", ""), description=info.get("description", ""),
                 duration=info.get("duration"), views=info.get("view_count"))
        r["methods"].append("yt-dlp")
        kind, lang, su = pick_sub(info)
        if su:
            r["text"] = json3_text(get(su, timeout=60))
            r["sub"] = "%s(%s)" % (kind, lang)
        else:
            r["sub"] = "字幕なし"
    except Exception as e:
        r["errors"].append("yt-dlp: %s" % str(e)[:160])
    r["links"] = find_links(r.get("description"))
    r["ok"] = bool(r["methods"])
    return r


def read_other(url):
    r = {"kind": "web", "url": url, "id": re.sub(r"\W+", "_", url)[-60:], "methods": [], "errors": []}
    try:
        h = get(url)
        t = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
        d = re.search(r'<meta[^>]+(?:property|name)="(?:og:)?description"[^>]+content="([^"]*)"', h, re.I)
        r.update(title=strip_tags(t.group(1)) if t else "", text=html.unescape(d.group(1)) if d else "")
        r["methods"].append("html")
    except Exception as e:
        r["errors"].append("html: %s" % str(e)[:120])
    r["ok"] = bool(r["methods"])
    return r


def yomu(url):
    if x_ids(url)[1]:
        return read_x(url)
    if re.search(r"(youtube\.com|youtu\.be)/", url):
        return read_yt(url)
    return read_other(url)


# ---------------- 出力・保存 ----------------
def to_md(r):
    L = ["# %s" % (r.get("title") or r.get("author") or r["url"]), "", "- URL: %s" % r["url"],
         "- 読めた方法: %s" % (" + ".join(r["methods"]) or "なし")]
    for k, lab in (("author", "投稿者"), ("date", "日時"), ("sub", "字幕"), ("duration", "長さ(秒)"), ("views", "再生数")):
        if r.get(k) not in (None, ""):
            L.append("- %s: %s" % (lab, r[k]))
    if r["kind"] == "x":
        L.append("- 画像 %s枚・動画 %s本" % (r.get("photos", "?"), r.get("videos", "?")))
    if r.get("errors"):
        L.append("- 失敗: %s" % " ／ ".join(r["errors"]))
    L += ["", "## 本文", "", r.get("text") or "（取れず）"]
    if r.get("quote"):
        L += ["", "## 引用元", "", r["quote"]]
    for key, lab in (("self_replies", "自分リプ（投稿者本人の続き）"), ("quote_self_replies", "引用元の自分リプ")):
        if r.get(key):
            L += ["", "## " + lab, ""] + ["- %s %s　%s" % (t["date"], t["text"].replace("\n", " ")[:300], " ".join(t["links"])) for t in r[key]]
    if r.get("thread_links"):
        L += ["", "## スレッドのリンク（GitHub等）", ""] + ["- " + u for u in r["thread_links"]]
    if r.get("description"):
        L += ["", "## 説明欄", "", r["description"]]
    if r.get("links"):
        L += ["", "## リンク", ""] + ["- " + u for u in r["links"]]
    if not r.get("ok"):
        L += ["", "→ 読めなかった。Grokボットに共有メモで頼む：python3 tools/zen_ai_kyouyu.py kaku --title \"このリンクを読んで\" --body \"%s\"" % r["url"]]
    return "\n".join(L) + "\n"


def save(r, md):
    day = datetime.date.today().isoformat()
    d = os.path.join(SAVE, day)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s.md" % r["id"])
    io.open(p, "w", encoding="utf-8").write(md)
    cut = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    for n in os.listdir(SAVE):
        if re.match(r"^\d{4}-\d{2}-\d{2}$", n) and n < cut:
            shutil.rmtree(os.path.join(SAVE, n), ignore_errors=True)
    return os.path.relpath(p, REPO)


def online():
    try:
        get("https://publish.twitter.com/oembed?url=https://x.com/x/status/20", timeout=8)
        return True
    except urllib.error.HTTPError:
        return True  # 返事が来た＝外へ出られる
    except Exception:
        return False


def via_mac(url, wait=240):
    """サンドボックスから：Mac に走らせてもらう（mac_fetch と同じ札の道）"""
    name = "ly_%s_%d" % (time.strftime("%H%M%S"), os.getpid())
    os.makedirs(os.path.join(JOBS, "pending"), exist_ok=True)
    import shlex
    sh = "#!/bin/bash\n# link_yomu.py が置いた1回きりの読み取り\ncd \"$HOME/tamago/tamago-shinchoku\"\n/usr/bin/python3 tools/link_yomu.py --json %s\n" % shlex.quote(url)
    tmp = os.path.join(JOBS, "pending", name + ".sh.tmp")
    io.open(tmp, "w", encoding="utf-8").write(sh)
    os.replace(tmp, tmp[:-4])
    done = os.path.join(JOBS, "done", name + ".out")
    end = time.time() + wait
    while time.time() < end:
        if os.path.exists(done):
            time.sleep(2)
            s = io.open(done, encoding="utf-8", errors="ignore").read()
            for line in reversed(s.strip().splitlines()):
                if line.startswith("{"):
                    return json.loads(line)
            return {"kind": "?", "url": url, "id": name, "ok": False, "methods": [], "errors": ["Mac側の出力にJSONなし：" + s[-200:]]}
        time.sleep(3)
    return {"kind": "?", "url": url, "id": name, "ok": False, "methods": [], "errors": ["Macが%d秒で拾わなかった（後で %s）" % (wait, os.path.relpath(done, REPO))]}


def self_test():
    ok = True
    ok &= x_ids("https://x.com/kemu_aii/status/2113799520371023890?s=20") == ("kemu_aii", "2113799520371023890")
    ok &= x_ids("https://twitter.com/a/statuses/1") == ("a", "1")
    ok &= yt_id("https://youtu.be/28x7Wirobjw?t=3") == "28x7Wirobjw"
    ok &= yt_id("https://www.youtube.com/shorts/28x7Wirobjw") == "28x7Wirobjw"
    t, d, l = parse_oembed_html('<blockquote class="twitter-tweet"><p lang="ja">こんにちは<br>世界 <a href="https://t.co/x">t.co/x</a></p>&mdash; A (@a) <a href="https://x.com/a/status/1">October 1, 2026</a></blockquote>')
    ok &= t.startswith("こんにちは\n世界") and d == "October 1, 2026" and l == ["https://t.co/x"]
    info = {"automatic_captions": {"fr": [{"ext": "json3", "url": "F"}], "ja": [{"ext": "json3", "url": "J"}], "en-orig": [{"ext": "json3", "url": "E"}]}}
    ok &= pick_sub(info)[2] == "J"
    ok &= pick_sub({"subtitles": {"en": [{"ext": "json3", "url": "M"}]}, "automatic_captions": info["automatic_captions"]})[2] == "M"
    ok &= json3_text('{"events":[{"segs":[{"utf8":"あ"},{"utf8":"い"}]},{"segs":[{"utf8":"\\n"}]},{"segs":[{"utf8":"あい"}]}]}') == "あい"
    ok &= "Grok" in to_md({"kind": "x", "url": "u", "id": "1", "methods": [], "errors": ["e"], "ok": False})
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    as_json = "--json" in a
    urls = [x for x in a if not x.startswith("--")]
    if not urls:
        print(__doc__)
        return 1
    rc = 0
    for url in urls:
        if sys.platform != "darwin" and not online():
            r = via_mac(url)  # Mac 側で保存まで済んでいる
            md = to_md(r)
        else:
            try:
                r = yomu(url)
            except Exception as e:
                r = {"kind": "?", "url": url, "id": re.sub(r"\W+", "_", url)[-40:], "ok": False, "methods": [], "errors": [str(e)[:160]]}
            md = to_md(r)
            r["saved"] = save(r, md)
        if not as_json:
            sys.stdout.write(md)
        print(json.dumps(r, ensure_ascii=False))
        rc = rc or (0 if r.get("ok") else 2)
    return rc


if __name__ == "__main__":
    sys.exit(main())
