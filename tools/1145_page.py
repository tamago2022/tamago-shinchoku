#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1145番【ページを実物で見る】曲ページのHTMLを実際に取って、4つを確かめる。

★工場（Mac）側で走る。
★1件ごとに status/1145/page.jsonl へ追記。落ちても続きから。

見るもの:
  ①200が返るか                     code
  ②動画の埋め込みが実際に入っているか  ogImageVideoId（/api/public/share-image/<動画ID>）
                                    ＋ 実測（oembed.jsonl）でそれが生きているか
  ③OG画像が共通画像でないか          ogImage を実際に取って md5。共通画像は後で束ねて判る
  ④コピーが入っているか              og:description が曲の紹介として中身を持つか

使い方:
  python3 tools/1145_page.py --list status/1145/page_todo.txt
  python3 tools/1145_page.py --list ... --limit 300
"""
from __future__ import annotations
import hashlib, io, json, os, random, re, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "status", "1145")
JSONL = os.path.join(OUT, "page.jsonl")
PROG = os.path.join(OUT, "page_progress.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")
WORKERS = 5

_lock = threading.Lock()
_n = {"done": 0, "ng": 0}
_started = time.time()
NOIMG = "--noimg" in sys.argv

RE_OG = re.compile(r'<meta\s+property="og:(image|description|title)"\s+content="(.*?)"', re.S)
RE_SHARE = re.compile(r'/api/public/share-image/([A-Za-z0-9_-]{6,})')


def enc(url):
    """日本語を含むURLをそのままurllibに渡すと落ちる。先に%エンコードする。"""
    try:
        url.encode("ascii")
        return url
    except UnicodeEncodeError:
        pr = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit((
            pr.scheme, pr.netloc,
            urllib.parse.quote(pr.path, safe="/%"),
            urllib.parse.quote(pr.query, safe="=&%"),
            pr.fragment))


def _get(url, timeout=30, head_only=False):
    url = enc(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept-Language": "ja"})
    if head_only:
        req.get_method = lambda: "HEAD"
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read() if not head_only else b"", dict(r.headers)


def _emit(rec):
    line = json.dumps(rec, ensure_ascii=False)
    with _lock:
        with io.open(JSONL, "a", encoding="utf-8") as f:
            f.write(line + "\n"); f.flush(); os.fsync(f.fileno())
        _n["done"] += 1
        if rec.get("赤"):
            _n["ng"] += 1
        if _n["done"] % 25 == 0:
            el = time.time() - _started
            json.dump({"時刻": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "この回で見た": _n["done"], "赤": _n["ng"],
                       "秒": round(el, 1),
                       "件/分": round(_n["done"] / el * 60, 1) if el > 0 else 0},
                      io.open(PROG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def unesc(s):
    return (s.replace("&amp;", "&").replace("&quot;", '"')
             .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))


def one(url):
    rec = {"url": url, "t": int(time.time()), "赤": []}
    html = b""
    for attempt in range(4):
        try:
            code, html, _ = _get(url)
            rec["code"] = code
            break
        except urllib.error.HTTPError as e:
            rec["code"] = e.code
            break
        except Exception as e:
            rec["err"] = type(e).__name__
            time.sleep(3 * (attempt + 1) + random.random())
    if rec.get("code") != 200:
        rec["赤"].append("200が返らない")
        _emit(rec); return
    t = html.decode("utf-8", "ignore")
    og = {}
    for k, v in RE_OG.findall(t):
        og.setdefault(k, unesc(v))
    rec["ogTitle"] = og.get("title", "")
    rec["ogDesc"] = og.get("description", "")
    rec["ogImage"] = og.get("image", "")
    m = RE_SHARE.search(rec["ogImage"])
    rec["videoId"] = m.group(1) if m else ""
    rec["bodyLen"] = len(t)

    d = rec["ogDesc"]
    rec["copyCore"] = d.split("\u2014", 1)[1].strip() if "\u2014" in d else ""

    # OG画像を実際に取って md5（共通画像かどうかは後で束ねて判る）
    if rec["ogImage"] and not NOIMG:
        try:
            c, b, h = _get(rec["ogImage"], timeout=40)
            rec["ogImageCode"] = c
            rec["ogImageBytes"] = len(b)
            rec["ogImageMd5"] = hashlib.md5(b).hexdigest()
            if c != 200 or len(b) < 1000:
                rec["赤"].append("OG画像が出ない")
        except urllib.error.HTTPError as e:
            rec["ogImageCode"] = e.code
            rec["赤"].append("OG画像が出ない(%d)" % e.code)
        except Exception as e:
            rec["ogImageErr"] = type(e).__name__
    _emit(rec)


def already():
    s = set()
    if os.path.exists(JSONL):
        for line in io.open(JSONL, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    s.add(json.loads(line)["url"])
                except Exception:
                    pass
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    lst = sys.argv[sys.argv.index("--list") + 1]
    urls = [x.strip() for x in io.open(lst, encoding="utf-8") if x.strip()]
    seen = already()
    todo = [u for u in urls if u not in seen]
    if "--limit" in sys.argv:
        todo = todo[:int(sys.argv[sys.argv.index("--limit") + 1])]
    print("全%d件／見た%d件／これから%d件" % (len(urls), len(seen), len(todo)), flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(one, todo))
    print("おわり done=%d 赤=%d" % (_n["done"], _n["ng"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
