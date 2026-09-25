#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【本番の実測】隠したはずの曲が、本番の出口から本当に消えたか、本番のURLを叩いて数える。

たまごさん（2026-09-25）:
  「『積みました』は不合格。本番のURLを叩いて消えていることを確認するまで。」

■ 物差しを間違えた記録（2026-09-25・そのまま残す）

  ①「&」で数えた → サイトマップのXMLでは & が &amp; になっている。
    直さないと1件も一致せず「全部消えている」という**嘘の合格**が出た。
  ②「artist=X&song=Y が本文に含まれるか」で数えた → 前方一致で余計に当たる。
    song=try-again が song=try-again-remix にも当たり、消えているのに「まだ出ている」と出た。
  → だから今は **<loc>を1本ずつ解いて、artistとsongを丸ごと突き合わせる**。
  ③ 対照を必ず測る。隠さないはずの曲が居ることを確かめてから、隠すはずの曲を数える。
    対照が0件なら物差しが壊れている＝結果は読まない。

出す場所: status/1144/honban.json
"""
from __future__ import annotations
import io, json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://joy-relief-station.lovable.app"
KAKUSU = os.path.join(ROOT, "status", "1140", "kakusu.txt")
KENSA = os.path.join(ROOT, "status", "1140", "kensa.json")
OUT = os.path.join(ROOT, "status", "1144", "honban.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36"


def get(url, timeout=240):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.headers.get("x-deployment-id", ""), resp.read().decode("utf-8", "replace")


def sitemap_keys(xml):
    """サイトマップに載っている曲の鍵（"artistId/songId"）を丸ごと拾う。"""
    out = set()
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        loc = loc.replace("&amp;", "&")
        q = urllib.parse.urlparse(loc).query
        if not q:
            continue
        d = urllib.parse.parse_qs(q)
        a = (d.get("artist") or [""])[0]
        s = (d.get("song") or [""])[0]
        if a and s:
            out.add("%s/%s" % (a, s))
    return out


def main():
    kakusu = {x.split()[0] for x in io.open(KAKUSU, encoding="utf-8") if x.strip()}
    dep, xml = get(SITE + "/sitemap.xml?t=%d" % time.time())
    dep = dep.split(".")[1] if "." in dep else dep
    inmap = sitemap_keys(xml)
    print("本番 = %s / sitemap %d byte / 曲のURL %d本" % (dep, len(xml), len(inmap)))

    # 対照：隠さないはずの曲が地図に居ることを先に確かめる（居なければ物差しが壊れている）
    taisho, taisho_ok = [], 0
    try:
        rows = json.load(io.open(KENSA, encoding="utf-8"))
        rows = rows["rows"] if isinstance(rows, dict) else rows
        taisho = [r["key"] for r in rows
                  if not ({"noVideo", "deadVideo"} & set(r.get("faults", [])))][:50]
        taisho_ok = sum(1 for k in taisho if k in inmap)
    except Exception as e:
        print("対照が測れません: %r" % (e,))
    print("対照: 隠さないはずの曲 %d件のうち %d件が地図に居る" % (len(taisho), taisho_ok))

    nokori = sorted(kakusu & inmap)
    res = {
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "honbanDeployment": dep,
        "kakusuKensuu": len(kakusu),
        "chizuNoKyokuURL": len(inmap),
        "taishoNokosuGaIru": "%d/%d" % (taisho_ok, len(taisho)),
        "kietaKensuu": len(kakusu) - len(nokori),
        "madaDeteruKensuu": len(nokori),
        "rei": nokori[:20],
        "kekka": ("★物差しが壊れている（対照が0件）" if taisho and taisho_ok == 0 else
                  "★全部消えている" if not nokori else
                  "★まだ出ている（%d件）" % len(nokori)),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not nokori else 1


if __name__ == "__main__":
    sys.exit(main())
