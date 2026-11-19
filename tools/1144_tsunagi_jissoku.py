#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【繋ぎの実測】「同じ時代の曲」が本番の曲ページから消えたか、実物を叩いて数える。

見出しは `${artistName} と同じ時代の曲`（src/routes/cover-guide.tsx の EraHitsSection）。
ページはサーバ側で描かれて返ってくる（実測: 曲名・アーティスト名がHTMLに入っている）ので、
HTMLに「と同じ時代の曲」が在るかで数えられる。

★人が書いた繋ぎ（curated eraHits）は残す方針なので、0件にはならない。
  「年号入りの曲で、人が書いた繋ぎが無いページ」から消えていればよい。

使い方: python3 tools/1144_tsunagi_jissoku.py [見る件数]
出す場所: status/1144/tsunagi_honban.json
"""
from __future__ import annotations
import io, json, os, random, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://joy-relief-station.lovable.app"
OUT = os.path.join(ROOT, "status", "1144", "tsunagi_honban.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36"
MIDASHI = "と同じ時代の曲"


def get(url, timeout=90):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.headers.get("x-deployment-id", ""), resp.read().decode("utf-8", "replace")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    # 年号が入っている曲＝検査で eraOnlyTsunagi が付いた曲。そこに機械の繋ぎが生えていた。
    keys = [x.strip() for x in io.open(os.path.join(ROOT, "status", "1140",
                                                    "kata_eraOnlyTsunagi.txt"),
                                       encoding="utf-8") if x.strip()]
    random.seed(1144)                     # 毎回同じ標本＝前後で比べられる
    mihon = random.sample(keys, min(n, len(keys)))
    dep, aru, nai, err = "", [], [], []
    for k in mihon:
        a, s = k.split("/", 1)
        u = "%s/cover-guide?artist=%s&song=%s" % (SITE, urllib.parse.quote(a),
                                                  urllib.parse.quote(s))
        try:
            d, html = get(u)
            dep = dep or (d.split(".")[1] if "." in d else d)
            (aru if MIDASHI in html else nai).append(k)
        except Exception as e:
            err.append("%s: %s" % (k, type(e).__name__))
        time.sleep(0.3)
    res = {
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "honbanDeployment": dep,
        "mitaKensuu": len(mihon),
        "eraSectionGaAru": len(aru),
        "eraSectionGaNai": len(nai),
        "yomenakatta": err,
        "aruRei": aru[:10],
        "kekka": ("★年が近いだけの繋ぎは出ていない" if not aru else
                  "★まだ出ている（%d/%d ページ）" % (len(aru), len(mihon))),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
