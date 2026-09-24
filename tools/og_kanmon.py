#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1092番【投稿の前に必ず通る門（サムネイルとURLの門）】

たまごさん（2026-09-24・実測）:
  「サムネイルが出た投稿＝111インプレッション／出なかった投稿＝17。数字が数倍変わっている。」
  「OG画像が出ないURLは投稿もリンク共有もさせない。もう二度と起きない形にする。」

■ この門が止めるもの（1つでも当たったら ✕。投稿しない）
  ① 曲のURLなのに、曲ページにならない（canonical から `&song=` が消える＝アーティストページに落ちる）
  ② og:image が無い
  ③ og:image の住所を叩いて 200 が返らない
  ④ ページが返るまで 3.0秒 を超える（Xの取りに来る待ち時間は数秒。超えると何も出さずに諦める）
  ⑤ og:image がよその倉庫（pbs.twimg.com＝消える／img.youtube.com＝480x360で小さい）

■ 使い方
    python3 tools/og_kanmon.py <URL> [<URL>...]
    python3 tools/og_kanmon.py --file urls.txt
  ★rc=0 … 全部通った（投稿してよい）
  ★rc=1 … 1本でも止まった（投稿しない）

■ 決め
  ・外のAIを呼ばない。0円。ブラウザを使わない（素のHTTPだけ）。
  ・直し方は言うが、勝手に消さない・勝手に投稿しない。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (compatible; tamago-og-kanmon)"
OSOI = 3.0
YOSO = {"pbs.twimg.com": "Xの倉庫。時間が経つと消える", "img.youtube.com": "480x360しかない。Xで小さい四角になる"}
CANON = re.compile(r'rel="canonical"[^>]*href="([^"]+)"')
OGIMG = re.compile(r'property="og:image"[^>]*content="([^"]+)"')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(REPO, "status", "og_kanmon.jsonl")


def _get(url, timeout=20):
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(400000).decode("utf-8", "ignore")
        return r.getcode(), body, time.time() - t0


def _code(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode()
    except Exception as e:
        return getattr(e, "code", 0) or 0


def shiraberu(url):
    riyuu = []
    try:
        code, html, byou = _get(url)
    except Exception as e:
        return {"url": url, "tsuuka": False, "riyuu": ["ページが返ってこない: %s" % repr(e)[:80]]}
    if code != 200:
        riyuu.append("ページが %d を返す" % code)
    if byou > OSOI:
        riyuu.append("返るまで %.1f秒（%.1f秒を超えるとXは諦める）" % (byou, OSOI))
    canon = (CANON.search(html) or [None, ""])[1].replace("&amp;", "&")
    if "song=" in url and "song=" not in canon:
        riyuu.append("曲ページにならない（アーティストページに落ちる）")
    img = (OGIMG.search(html) or [None, ""])[1].replace("&amp;", "&")
    if not img:
        riyuu.append("og:image が無い")
    else:
        for host, naze in YOSO.items():
            if host in img:
                riyuu.append("サムネがよその倉庫（%s）… %s" % (host, naze))
        c = _code(img)
        if c != 200:
            riyuu.append("og:image の住所が %d" % c)
    return {"url": url, "tsuuka": not riyuu, "byou": round(byou, 2),
            "canonical": canon, "og_image": img, "riyuu": riyuu}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    urls = list(a.urls)
    if a.file:
        urls += [l.strip() for l in open(a.file, encoding="utf-8") if l.strip()]
    if not urls:
        print("URLを1本ください"); return 2
    out = [shiraberu(u) for u in urls]
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps({"at": time.strftime("%F %T"), **r}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for r in out:
            print(("◯ " if r["tsuuka"] else "✕ ") + r["url"])
            for x in r["riyuu"]:
                print("    - " + x)
    ng = [r for r in out if not r["tsuuka"]]
    if ng:
        print("\n★%d本 止めました。このURLは投稿もリンク共有もしないでください。" % len(ng))
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
