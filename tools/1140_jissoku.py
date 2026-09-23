#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1140番【実測】棚に載っている全YouTube動画IDを、1件ずつ叩いて本当に再生できるか確かめる。

たまごさん（2026-09-25）:
  「動画IDはあるがYouTube側で再生できない（削除・非公開・埋め込み禁止・地域制限）
    ← oEmbed等で1件ずつ叩いて実測。『データにある』は証拠にならない」

★ここは工場（Mac）で走る。サンドボックス（Cowork）からは youtube.com に回線が出ない
  （2026-09-25 実測：https://www.youtube.com → 000／i.ytimg.com → 000）。
  だから検査はサンドボックス、実測はここ、という分担。

判定:
  oEmbed が 200        → 生きている（title/author も控える）
  oEmbed が 401/403/404 → 死んでいる（削除・非公開・埋め込み禁止）
  それ以外・通信失敗    → 不明（deadには入れない。生きている扱いのまま、次回もう一度見る）

  ★「不明」を死亡に混ぜない。回線のご機嫌で生きている動画を隠すのが一番の恥。

出す場所:
  status/1140/jissoku.json   {"checked":[...], "dead":[...], "alive":{id:{title,author}}, "unknown":[...]}
  status/1140/jissoku_cache.json  1件ずつの結果（途中で落ちても次が拾える）

使い方:
  python3 tools/1140_jissoku.py            # 全部（キャッシュがあるぶんは飛ばす）
  python3 tools/1140_jissoku.py --limit 500
  python3 tools/1140_jissoku.py --recheck  # キャッシュを無視してやり直す
"""
from __future__ import annotations
import io, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "status", "1140")
IDS = os.path.join(OUT, "all_video_ids.txt")
CACHE = os.path.join(OUT, "jissoku_cache.json")
RESULT = os.path.join(OUT, "jissoku.json")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
WORKERS = 12          # 優しく。YouTubeに嫌われない速さ。
PAUSE = 0.05


def check(vid: str):
    url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({
        "url": "https://www.youtube.com/watch?v=" + vid, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
            return {"v": "alive", "title": d.get("title", ""), "author": d.get("author_name", "")}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return {"v": "dead", "code": e.code}
        return {"v": "unknown", "code": e.code}
    except Exception as e:
        return {"v": "unknown", "err": type(e).__name__}
    finally:
        time.sleep(PAUSE)


def run_job(payload=None):
    payload = payload or {}
    return {"ok": main(limit=payload.get("limit"), recheck=bool(payload.get("recheck"))) == 0,
            "totalYen": 0.0}


def main(limit=None, recheck=False):
    if not os.path.exists(IDS):
        print("先に tools/1140_kensa.py を走らせて all_video_ids.txt を作る", file=sys.stderr)
        return 1
    ids = [x.strip() for x in io.open(IDS, encoding="utf-8") if x.strip()]
    cache = {}
    if os.path.exists(CACHE) and not recheck:
        try:
            cache = json.load(io.open(CACHE, encoding="utf-8"))
        except Exception:
            cache = {}
    todo = [v for v in ids if v not in cache]
    if limit:
        todo = todo[:int(limit)]
    print("全%d件／未実測%d件を叩く" % (len(ids), len(todo)))

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for vid, res in zip(todo, ex.map(check, todo)):
            cache[vid] = res
            done += 1
            if done % 200 == 0:
                json.dump(cache, io.open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
                print("  %d / %d" % (done, len(todo)), flush=True)
    json.dump(cache, io.open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    dead = sorted([v for v, r in cache.items() if r.get("v") == "dead"])
    unknown = sorted([v for v, r in cache.items() if r.get("v") == "unknown"])
    alive = {v: {"title": r.get("title", ""), "author": r.get("author", "")}
             for v, r in cache.items() if r.get("v") == "alive"}
    out = {"生成": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "checked": sorted(cache.keys()), "dead": dead, "unknown": unknown,
           "alive_n": len(alive), "alive": alive}
    json.dump(out, io.open(RESULT, "w", encoding="utf-8"), ensure_ascii=False)
    print("実測おわり: 生きている%d / 死んでいる%d / 不明%d" % (len(alive), len(dead), len(unknown)))
    return 0


if __name__ == "__main__":
    lim = None
    if "--limit" in sys.argv:
        lim = sys.argv[sys.argv.index("--limit") + 1]
    sys.exit(main(limit=lim, recheck="--recheck" in sys.argv))
