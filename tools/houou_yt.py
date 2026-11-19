#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YouTube の検索（公開の検索ページ）と oEmbed 確認を Mac 側でまとめて行う（0円・鍵なし・ブラウザなし）。
使い方: python3 tools/houou_yt.py <in.json> <out.json>
  in.json = {"search": ["AY YOLA Homay", ...], "oembed": ["videoId", ...], "top": 8}
  out.json = {"search": {q: [{id,title,channel,views,len}...]}, "oembed": {id: {ok, title, author_name, author_url} }}
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.8"}


def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25).read().decode("utf-8", "ignore")


def _txt(o):
    if not o:
        return ""
    if "simpleText" in o:
        return o["simpleText"]
    return "".join(r.get("text", "") for r in o.get("runs", []))


def walk(o, out):
    if isinstance(o, dict):
        if "videoRenderer" in o:
            v = o["videoRenderer"]
            out.append({"id": v.get("videoId"), "title": _txt(v.get("title")),
                        "channel": _txt(v.get("ownerText")),
                        "channelUrl": (((v.get("ownerText") or {}).get("runs") or [{}])[0].get("navigationEndpoint") or {}).get("browseEndpoint", {}).get("canonicalBaseUrl", ""),
                        "views": _txt(v.get("viewCountText")), "len": _txt(v.get("lengthText")),
                        "published": _txt(v.get("publishedTimeText"))})
        for x in o.values():
            walk(x, out)
    elif isinstance(o, list):
        for x in o:
            walk(x, out)


def search(q, top):
    h = get("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q, "hl": "en"}))
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", h, re.S)
    if not m:
        return {"error": "ytInitialData なし"}
    out = []
    walk(json.loads(m.group(1)), out)
    return out[:top]


def oembed(vid):
    try:
        d = json.loads(get("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote("https://www.youtube.com/watch?v=" + vid)))
        return {"ok": True, "title": d.get("title"), "author_name": d.get("author_name"), "author_url": d.get("author_url")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def main():
    a = json.load(open(sys.argv[1], encoding="utf-8"))
    top = int(a.get("top") or 8)
    res = {"search": {}, "oembed": {}}
    for q in a.get("search") or []:
        try:
            res["search"][q] = search(q, top)
        except Exception as e:  # noqa: BLE001
            res["search"][q] = {"error": str(e)[:200]}
        time.sleep(0.4)
    for v in a.get("oembed") or []:
        res["oembed"][v] = oembed(v)
    json.dump(res, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done")


if __name__ == "__main__":
    main()
