#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1092番【URLのズレとサムネイルを全件で当たる】

たまごさん（2026-09-24・原文）:
  「枯葉／Nat King Cole は棚の登録が nat-king-cole/autumn-leaves だが、
    そのURLはアーティストページに飛んでしまい、曲ページにならない。」
  「同じズレが他の曲でも起きている可能性が高い。全曲（26,890件）を機械で当たる。」

■ 判定のしかた（実測で確かめた・2026-09-24 09:27）
    曲ページ  … canonical に `&song=` が入って返る（og:type = music.song）
    ズレ      … canonical が `?artist=` だけになって返る（og:type = profile）＝アーティストページに落ちた
  ★つまり 200 が返るかどうかでは分からない。**canonical を見る。**

■ 使い方（Macの上で走らせる。サンドボックスは外に出られない）
    python3 tools/kareha_sweep.py --build   # 棚（coverGuide.ts）から全曲のURLを作る
    python3 tools/kareha_sweep.py --links   # 棚以外に貼ってあるURL（worlds.ts 等）を集める
    python3 tools/kareha_sweep.py --check <対象jsonl> [--workers 6] [--limit N]
    python3 tools/kareha_sweep.py --matome  # 結果を数える

■ 決め
  ・外のAIを1回も呼ばない。0円。
  ・**1行も消さない・動かさない。**出すのは一覧だけ。直すのは別の道（alias追加）。
  ・途中で止まっても続きから走る（済んだURLは飛ばす）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUTDIR = os.path.join(REPO, "status", "1092_url_zure")
SRC_CANDIDATES = [
    "/tmp/jrs-pub/src/lib",
    "/Users/mac/Desktop/joy-relief-station/src/lib",
    os.path.join(REPO, "status", "_1039", "lib"),
]
BASE = "https://joy-relief-station.lovable.app"
UA = "Mozilla/5.0 (compatible; tamago-1092-sweep)"

sys.path.insert(0, HERE)


def srcdir() -> str:
    for d in SRC_CANDIDATES:
        if os.path.isfile(os.path.join(d, "coverGuide.ts")):
            return d
    raise SystemExit("coverGuide.ts が見つかりません")


def parse_shelf():
    import tsunagatte_nai as T
    d = srcdir()
    text = open(os.path.join(d, "coverGuide.ts"), encoding="utf-8").read()
    arts = T.parse_artists(text)
    return d, arts


def cmd_build():
    d, arts = parse_shelf()
    os.makedirs(OUTDIR, exist_ok=True)
    p = os.path.join(OUTDIR, "all_songs.jsonl")
    n = 0
    with open(p, "w", encoding="utf-8") as f:
        for a in arts:
            for s in a["songs"]:
                f.write(json.dumps({
                    "kind": "shelf", "artist": a["id"], "song": s["id"],
                    "url": f"{BASE}/cover-guide?artist={urllib.parse.quote(a['id'])}&song={urllib.parse.quote(s['id'])}",
                }, ensure_ascii=False) + "\n")
                n += 1
    ids = {}
    for a in arts:
        ids[a["id"]] = [s["id"] for s in a["songs"]]
    json.dump(ids, open(os.path.join(OUTDIR, "shelf_ids.json"), "w"), ensure_ascii=False)
    # 同じアーティストの中で id が重なっている＝片方のURLに永久に行けない
    dup = {}
    for a, v in ids.items():
        seen, d2 = set(), []
        for x in v:
            if x in seen:
                d2.append(x)
            seen.add(x)
        if d2:
            dup[a] = d2
    json.dump(dup, open(os.path.join(OUTDIR, "kasanari.json"), "w"), ensure_ascii=False, indent=1)
    print(f"棚: アーティスト{len(arts)}・曲{n} → {p}")
    print(f"id重なり: {len(dup)}人 {sum(len(v) for v in dup.values())}曲 → kasanari.json")


URLPAT = re.compile(
    r'/cover-guide\?artist=([A-Za-z0-9\-_%\.]+)(?:&amp;|&|\\u0026)song=([A-Za-z0-9\-_%\.]+)')


def cmd_links():
    d, arts = parse_shelf()
    shelf = {a["id"]: set(s["id"] for s in a["songs"]) for a in arts}
    os.makedirs(OUTDIR, exist_ok=True)
    root = os.path.dirname(d)  # src/
    found = {}
    for dirpath, _dn, fns in os.walk(root):
        for fn in fns:
            if not fn.endswith((".ts", ".tsx", ".json", ".md", ".html")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for a, s in URLPAT.findall(t):
                found.setdefault((a, s), set()).add(os.path.relpath(p, root))
    rows = []
    for (a, s), files in sorted(found.items()):
        if a in shelf and s in shelf[a]:
            judge = "ok"
        elif a not in shelf:
            judge = "artist_nashi"
        else:
            judge = "song_zure"
        rows.append({"kind": "link", "artist": a, "song": s, "judge": judge,
                     "files": sorted(files)[:6],
                     "url": f"{BASE}/cover-guide?artist={a}&song={s}"})
    p = os.path.join(OUTDIR, "links.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    c = Counter(r["judge"] for r in rows)
    print(f"貼ってあるURL {len(rows)}件 → {p}")
    print("  " + " / ".join(f"{k}={v}" for k, v in c.most_common()))


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read(400000).decode("utf-8", "ignore")


def head_ok(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode()
    except Exception as e:
        return getattr(e, "code", 0) or 0


CANON = re.compile(r'rel="canonical"[^>]*href="([^"]+)"')
OGIMG = re.compile(r'property="og:image"[^>]*content="([^"]+)"')
OGTYPE = re.compile(r'property="og:type"[^>]*content="([^"]+)"')


def check_one(row, og_image_hit=True):
    url = row["url"]
    out = dict(row)
    try:
        code, html = fetch(url)
    except Exception as e:
        out.update(status=0, err=repr(e)[:120], hantei="torenai")
        return out
    canon = (CANON.search(html) or [None, ""])[1].replace("&amp;", "&")
    ogimg = (OGIMG.search(html) or [None, ""])[1].replace("&amp;", "&")
    ogtype = (OGTYPE.search(html) or [None, ""])[1]
    out.update(status=code, canonical=canon, og_type=ogtype, og_image=ogimg)
    if code != 200:
        out["hantei"] = "code" + str(code)
    elif "song=" not in canon:
        out["hantei"] = "zure"          # アーティストページに落ちた
    else:
        out["hantei"] = "ok"
    if ogimg:
        out["og_image_status"] = head_ok(ogimg) if og_image_hit else None
        if out.get("og_image_status") not in (200, None):
            out["hantei_og"] = "og_ng"
        else:
            out["hantei_og"] = "og_ok"
    else:
        out["hantei_og"] = "og_nashi"
    return out


def cmd_check(target, workers, limit, og_hit):
    os.makedirs(OUTDIR, exist_ok=True)
    name = os.path.basename(target).replace(".jsonl", "")
    outp = os.path.join(OUTDIR, name + "_kekka.jsonl")
    done = set()
    if os.path.exists(outp):
        for line in open(outp, encoding="utf-8"):
            try:
                done.add(json.loads(line)["url"])
            except Exception:
                pass
    rows = []
    for line in open(target, encoding="utf-8"):
        r = json.loads(line)
        if r["url"] in done:
            continue
        rows.append(r)
    if limit:
        rows = rows[:limit]
    print(f"対象 {len(rows)}件（済 {len(done)}件）→ {outp}", flush=True)
    f = open(outp, "a", encoding="utf-8")
    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(lambda r: check_one(r, og_hit), rows):
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            n += 1
            if n % 200 == 0:
                f.flush()
                print(f"  {n}/{len(rows)}", flush=True)
    f.close()
    print("おわり", n, flush=True)


def cmd_matome():
    from collections import Counter
    for fn in sorted(os.listdir(OUTDIR)):
        if not fn.endswith("_kekka.jsonl"):
            continue
        c, co = Counter(), Counter()
        zure, ogng = [], []
        for line in open(os.path.join(OUTDIR, fn), encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            c[r.get("hantei")] += 1
            co[r.get("hantei_og")] += 1
            if r.get("hantei") == "zure":
                zure.append(r)
            if r.get("hantei_og") in ("og_ng", "og_nashi"):
                ogng.append(r)
        print(f"== {fn}: {sum(c.values())}件")
        print("   URL: " + " / ".join(f"{k}={v}" for k, v in c.most_common()))
        print("   サムネ: " + " / ".join(f"{k}={v}" for k, v in co.most_common()))
        json.dump(zure, open(os.path.join(OUTDIR, fn.replace("_kekka.jsonl", "_zure.json")), "w"),
                  ensure_ascii=False, indent=1)
        json.dump(ogng, open(os.path.join(OUTDIR, fn.replace("_kekka.jsonl", "_ogng.json")), "w"),
                  ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--links", action="store_true")
    ap.add_argument("--check")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-og-hit", action="store_true")
    ap.add_argument("--matome", action="store_true")
    a = ap.parse_args()
    if a.build:
        cmd_build()
    if a.links:
        cmd_links()
    if a.check:
        cmd_check(a.check, a.workers, a.limit, not a.no_og_hit)
    if a.matome:
        cmd_matome()


if __name__ == "__main__":
    main()
