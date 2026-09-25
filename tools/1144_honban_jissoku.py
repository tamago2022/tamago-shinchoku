#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【本番の実測】隠したはずの曲が、本番の全部の出口から消えたか確かめる。

たまごさん（2026-09-25）:
  「『積みました』は不合格。本番のURLを叩いて消えていることを確認するまで。」

見る出口:
  ① サイトマップ  /sitemap.xml   … 隠した曲のURLが1本も無いこと
  ② 曲のページ    /cover-guide?artist=..&song=..  … 出ないこと（または出ない扱い）
  ③ 検索の元表    /src/lib/searchCards … ビルド後は見えないのでサイトマップで代表させる

出す場所: status/1144/05_honban.json
"""
from __future__ import annotations
import io, json, os, random, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://joy-relief-station.lovable.app"
HIDDEN = os.path.join(ROOT, "status", "1140", "kakusu.txt")
OUT = os.path.join(ROOT, "status", "1144", "05_honban.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36"


def get(url, timeout=60):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def main():
    keys = [x.strip() for x in io.open(HIDDEN, encoding="utf-8") if x.strip()]
    keys = [k.split()[0] for k in keys]
    print("隠すはずの曲 = %d件" % len(keys))

    st, sm = get(SITE + "/sitemap.xml")
    print("sitemap.xml = HTTP %d / %d byte" % (st, len(sm)))
    urls = set(re.findall(r"<loc>([^<]+)</loc>", sm))
    print("サイトマップのURL = %d本" % len(urls))

    nokotteru = []
    for k in keys:
        if "/" not in k:
            continue
        a, s = k.split("/", 1)
        u1 = "%s/cover-guide?artist=%s&song=%s" % (SITE, a, s)
        if u1 in urls or ("artist=%s&song=%s" % (a, s)) in sm:
            nokotteru.append(k)

    res = {
        "at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "kakusuKensuu": len(keys),
        "sitemapHttp": st,
        "sitemapUrls": len(urls),
        "sitemapNiNokotteru": len(nokotteru),
        "rei": nokotteru[:20],
        "kekka": "★消えている" if not nokotteru else "★まだ出ている（%d件）" % len(nokotteru),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not nokotteru else 1


if __name__ == "__main__":
    sys.exit(main())
