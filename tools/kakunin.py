#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""961番【検品】出したページが本当に生きているかを、工場側から叩いて確かめる。

■ なぜ要るか（2026-09-20 実測）
  たまご憲法：「渡せるのは自分で叩いて200を確認したURLだけ」。
  ところが Cowork/Dispatch のサンドボックスからは tamago2022.github.io に**出られない**
  （プロキシが 403 Forbidden でトンネルを塞ぐ。curl も urllib も同じ）。
  ブラウザで見に行く道は request_access が要るので、指示で禁じられていることがある。
  → 工場（Mac）からなら出られる。だから「200かどうか見てくるだけ」の係をここに置く。

■ できること・できないこと
  ・GETだけ。POSTもPUTもしない。金もかからない。
  ・**行き先は tamago2022.github.io の中だけ**（下の ALLOW_PREFIX）。
    ここを狭くしてあるのは、この窓口が「なんでも取りに行ける穴」にならないようにするため。
  ・返すのは status / 長さ / 題 / 表の行数 / リンク数 / 探した言葉が有るか、だけ。
    本文そのものは返さない（長すぎて報告が読めなくなる）。

■ 使い方
  gaibu_kuchi.enqueue_job("kakunin", {"urls": ["https://tamago2022.github.io/..."],
                                      "must": ["言い分", "AITuberKit"]})
"""
import json
import re
import ssl
import time
import urllib.error
import urllib.request

# 2026-09-23（1027番・区間8）：出したものを叩いて確かめる先は、うちが出している2か所。
#   ・tamago2022.github.io      … 進捗表・確認ページ（GitHub Pages）
#   ・joy-relief-station.lovable.app … ごきげん補給所の本番（Lovableが main から配信）
#   ★joy-relief-station は GitHub Pages **ではない**。mainに入れただけでは本番に出ない。
#     だから「mainに入った＝出た」と数えていると、区間7（公開）の詰まりが見えない。
#   GETだけ・鍵を使わない・課金0 は変えていない。
ALLOW_PREFIX = ("https://tamago2022.github.io/",
                "https://joy-relief-station.lovable.app/")
UA = "tamago-kakunin/1.0 (+961)"


def _one(url, must):
    r = {"url": url, "ok": False, "status": 0, "bytes": 0}
    if not url.startswith(ALLOW_PREFIX):
        r["error"] = "行き先が許してある場所の外です（tamago2022.github.io の中だけ）"
        return r
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Cache-Control": "no-cache", "Pragma": "no-cache"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as res:
            body = res.read().decode("utf-8", "ignore")
            r["status"] = res.status
    except urllib.error.HTTPError as e:
        r["status"] = e.code
        r["error"] = "HTTP %d" % e.code
        r["seconds"] = round(time.time() - t0, 1)
        return r
    except Exception as e:
        r["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        r["seconds"] = round(time.time() - t0, 1)
        return r

    r["seconds"] = round(time.time() - t0, 1)
    r["bytes"] = len(body)
    m = re.search(r"<title>([^<]*)", body)
    r["title"] = m.group(1) if m else ""
    r["rows"] = body.count("<tr>")
    r["links"] = len(re.findall(r'href="https', body))
    # 「文字化けしていないか」の当たり。日本語が1文字も無ければ何かおかしい。
    r["hasJa"] = bool(re.search(r"[ぁ-んァ-ン一-龥]", body))
    if must:
        r["must"] = {w: (w in body) for w in must}
    r["ok"] = (r["status"] == 200 and r["bytes"] > 0
               and all((r.get("must") or {}).values()))
    return r


def run_job(payload=None):
    payload = payload or {}
    urls = payload.get("urls") or ([payload["url"]] if payload.get("url") else [])
    must = payload.get("must") or []
    results = [_one(u, must) for u in urls]
    return {"ok": all(x.get("ok") for x in results) if results else False,
            "results": results, "totalYen": 0.0}


if __name__ == "__main__":
    import sys
    print(json.dumps(run_job({"urls": sys.argv[1:]}), ensure_ascii=False, indent=1))
