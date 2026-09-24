#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1110番【鍵なしでSpotifyの公開プレイリストを読む係】

なぜこれか（実測・2026-09-24）:
  ・Macにも~/.tamagoにもキーチェーンにも env にも Spotify の鍵は **1件も無い**（1110番の実測）
  ・匿名トークン(open.spotify.com/get_access_token) は **403 URL Blocked**（1111番）
  ・しかし **embedページ**（open.spotify.com/embed/playlist/<id>）は **200** で
    __NEXT_DATA__ に全曲（曲名・アーティスト・長さ・track id）が入っている。＝鍵0で読める。
  ・曲のembed（embed/track/<id>）に **releaseDate**（リリース年）が入っている。

取れないもの（鍵が無いと原理的に無理・空欄にする）:
  ・アルバム名／プレイリストへの追加日（Web APIのみ）

口:
  python3 tools/spotify_kokai_yomu.py --ids <id> <id> ...   # 一覧を仕入れる
  python3 tools/spotify_kokai_yomu.py --enrich --byou 150   # 年を埋める（途中で切れても再開できる）
  python3 tools/spotify_kokai_yomu.py --dasu                # CSV/JSON を書き出す
"""
from __future__ import annotations
import argparse, csv, io, json, os, re, sys, time, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "status", "1075_spotify")
STORE = os.path.join(OUT, "kokai_data.json")
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("__NEXT_DATA__ が無い")
    return json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]


def _load():
    try:
        return json.load(io.open(STORE, encoding="utf-8"))
    except Exception:
        return {"playlists": {}, "tracks": {}}


def _save(d):
    os.makedirs(OUT, exist_ok=True)
    tmp = STORE + ".tmp"
    json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, STORE)


def ids(pids):
    d = _load()
    for pid in pids:
        try:
            ent = _next_data(_get("https://open.spotify.com/embed/playlist/%s" % pid))
        except Exception as e:
            print("%s NG %s" % (pid, repr(e)[:120]))
            continue
        rows = []
        for t in (ent.get("trackList") or []):
            tid = (t.get("uri") or "").split(":")[-1]
            rows.append({"id": tid, "title": t.get("title"), "artist": t.get("subtitle"),
                         "ms": t.get("duration")})
            d["tracks"].setdefault(tid, {})
        d["playlists"][pid] = {"name": ent.get("name"), "tracks": rows,
                               "at": time.strftime("%F %T")}
        print("%s OK %r %d曲" % (pid, ent.get("name"), len(rows)))
    _save(d)
    return 0


def enrich(byou=150):
    d = _load()
    need = [t for t, v in d["tracks"].items() if not v.get("done")]
    t0 = time.time()
    n = 0
    for tid in need:
        if time.time() - t0 > byou:
            break
        try:
            ent = _next_data(_get("https://open.spotify.com/embed/track/%s" % tid, timeout=12))
            rd = ((ent.get("releaseDate") or {}).get("isoString") or "")[:4]
            d["tracks"][tid] = {"done": True, "year": rd,
                                "artists": ", ".join(a.get("name", "") for a in (ent.get("artists") or [])),
                                "name": ent.get("name")}
        except Exception as e:
            d["tracks"][tid] = {"done": True, "year": "", "why": repr(e)[:60]}
        n += 1
        if n % 20 == 0:
            _save(d)
    _save(d)
    left = len([1 for v in d["tracks"].values() if not v.get("done")])
    print("埋めた=%d 残り=%d" % (n, left))
    return 0


def dasu():
    d = _load()
    rows = []
    for pid, p in sorted(d["playlists"].items(), key=lambda kv: kv[1].get("name") or ""):
        for i, t in enumerate(p["tracks"], 1):
            tk = d["tracks"].get(t["id"]) or {}
            rows.append({
                "プレイリスト名": p.get("name") or "",
                "順": i,
                "曲名": t.get("title") or tk.get("name") or "",
                "アーティスト": tk.get("artists") or t.get("artist") or "",
                "アルバム": "",
                "リリース年": tk.get("year") or "",
                "追加日": "",
                "長さ": "%d:%02d" % ((t.get("ms") or 0) // 60000, ((t.get("ms") or 0) // 1000) % 60),
                "playlist_id": pid,
                "track_id": t["id"],
                "spotify": "https://open.spotify.com/track/%s" % t["id"],
            })
    os.makedirs(OUT, exist_ok=True)
    cols = list(rows[0].keys()) if rows else []
    with io.open(os.path.join(OUT, "playlists.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    json.dump({"updatedAt": time.strftime("%F %T"),
               "playlists": [{"id": k, "name": v.get("name"), "count": len(v["tracks"])}
                             for k, v in d["playlists"].items()],
               "rows": rows},
              io.open(os.path.join(OUT, "playlists.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("書きました: %d本 / %d曲" % (len(d["playlists"]), len(rows)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--enrich", action="store_true")
    ap.add_argument("--byou", type=int, default=150)
    ap.add_argument("--dasu", action="store_true")
    a = ap.parse_args()
    if a.ids:
        return ids(a.ids)
    if a.enrich:
        return enrich(a.byou)
    if a.dasu:
        return dasu()
    ap.error("--ids / --enrich / --dasu のどれか")


if __name__ == "__main__":
    sys.exit(main())
