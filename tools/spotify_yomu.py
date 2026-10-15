#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1075番【Spotifyを読む係】たまごさんのプレイリストの全曲を、ブラウザを使わずに取る。

たまごさん（2026-09-24・原文）:
  「俺のSpotifyのファイルがGensparkで読めない。そのプレイリストのリストを上げたいんで。
    秋の曲、45曲は棚にあるけど、俺のSpotifyにはめちゃくちゃ入ってる。何百曲あるかもしれない。」
  「Spotifyのリストデータを読ませるんだよ。」

━━ なぜ工場（Mac）側で走るか ━━
  サンドボックス（Cowork）からは accounts.spotify.com / api.spotify.com に
  **1本も出られない**（curl が 000。実測 2026-09-24 09:06）。
  ＝向こうは「読んでくれ」と票を置くだけ。読むのはここ。

━━ 決まり ━━
  ① ★GETだけ。プレイリストに1曲も足さない・消さない・並べ替えない。
  ② ★鍵の値（refreshToken / accessToken / clientId）を**返り値にもログにも1文字も書かない**。
  ③ ★ブラウザを開かない。たまごさんのBraveに触らない。
  ④ ★課金0（Spotify Web API は無料）。
  ⑤ ★書き先は status/1075_spotify/ だけ。たまごさんのファイルを消さない・動かさない。

口:
  run_job({"op": "shirabe"})                 … 鍵が通るか・何枚あるかだけ見る（軽い）
  run_job({"op": "ichiran"})                 … プレイリストの一覧（名前・枚数・id）
  run_job({"op": "zenkyoku", "only": "秋"})  … 名前に「秋」を含む物の全曲
  run_job({"op": "zenkyoku"})                … 全部のプレイリストの全曲
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT_DIR = os.path.join(REPO, "status", "1075_spotify")
API = "https://api.spotify.com/v1"

# ★白名簿：ここ以外へは1本も出ない
ALLOW_PREFIX = ("https://api.spotify.com/v1/",)


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _token():
    """spotify_ninshou.py が保管した refresh_token から access_token を作る。
    ★値はこの関数の外に出さない。"""
    import spotify_ninshou
    return spotify_ninshou.access_token()


def _get(url, tok):
    if not url.startswith(ALLOW_PREFIX):
        raise RuntimeError("白名簿の外には出ません")
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 429:              # ★Spotifyの息継ぎ。待てと言われたら待つ
                wait = int(e.headers.get("Retry-After") or "2") + 1
                time.sleep(min(wait, 20))
                continue
            if e.code in (500, 502, 503) and attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError("Spotifyが %d を返しました" % e.code)
    raise RuntimeError("Spotifyが何度も混んでいて読めませんでした")


def _paged(url, tok, cap=10000):
    """next を辿って全部集める。★何百曲でも途中で止めない。"""
    items = []
    while url and len(items) < cap:
        d = _get(url, tok)
        items.extend(d.get("items") or [])
        url = d.get("next")
    return items


def _playlists(tok):
    raw = _paged(API + "/me/playlists?limit=50", tok)
    out = []
    for p in raw:
        if not p:
            continue
        out.append({
            "id": p.get("id"),
            "name": p.get("name") or "",
            "kyokusu": ((p.get("tracks") or {}).get("total")) or 0,
            "url": ((p.get("external_urls") or {}).get("spotify")) or "",
            "owner": ((p.get("owner") or {}).get("display_name")) or "",
        })
    return out


def _tracks(pid, tok):
    fields = ("items(added_at,track(name,duration_ms,explicit,"
              "artists(name),album(name,release_date),external_urls,id)),next")
    url = (API + "/playlists/%s/tracks?limit=100&fields=%s"
           % (pid, urllib.parse.quote(fields, safe="(),")))
    out = []
    for it in _paged(url, tok):
        t = (it or {}).get("track") or {}
        if not t.get("name"):
            continue
        out.append({
            "kyoku": t.get("name") or "",
            "artist": ", ".join(a.get("name") or "" for a in (t.get("artists") or [])),
            "album": ((t.get("album") or {}).get("name")) or "",
            "hatsubai": ((t.get("album") or {}).get("release_date")) or "",
            "url": ((t.get("external_urls") or {}).get("spotify")) or "",
            "spotifyId": t.get("id") or "",
            "byou": round((t.get("duration_ms") or 0) / 1000),
            "iretaHi": (it or {}).get("added_at") or "",
        })
    return out


def _norm(s):
    """突き合わせ用。記号・空白・大小・全半角の違いで別物にしない。"""
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)|\[.*?\]|（.*?）", " ", s)
    s = re.sub(r"\b(feat|ft|featuring|remaster(ed)?|live|version|ver|mix)\b.*", " ", s)
    s = re.sub(r"[^0-9a-z぀-ヿ一-鿿]+", "", s)
    return s


def run_job(payload):
    payload = payload or {}
    op = (payload.get("op") or "shirabe").strip()
    os.makedirs(OUT_DIR, exist_ok=True)

    try:
        tok = _token()
    except SystemExit as e:
        return {"ok": False, "step": "kagi",
                "error": "まだSpotifyの同意が済んでいません（%s）" % str(e)[:80],
                "needsConsent": True, "totalYen": 0.0}
    except Exception as e:
        return {"ok": False, "step": "kagi",
                "error": "鍵が通りませんでした: %s" % str(e)[:160],
                "needsConsent": True, "totalYen": 0.0}

    if op == "shirabe":
        me = _get(API + "/me", tok)
        pls = _playlists(tok)
        return {"ok": True, "op": op,
                "dare": me.get("display_name") or me.get("id") or "",
                "playlistSu": len(pls),
                "gokeiKyoku": sum(p["kyokusu"] for p in pls),
                "namae": [p["name"] for p in pls][:60],
                "totalYen": 0.0}

    if op == "ichiran":
        pls = _playlists(tok)
        p = os.path.join(OUT_DIR, "playlists.json")
        json.dump({"at": _now(), "playlists": pls},
                  io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return {"ok": True, "op": op, "playlistSu": len(pls),
                "file": os.path.relpath(p, REPO), "playlists": pls, "totalYen": 0.0}

    if op == "zenkyoku":
        only = (payload.get("only") or "").strip()
        pls = _playlists(tok)
        if only:
            pls = [p for p in pls if only.lower() in (p["name"] or "").lower()]
        if payload.get("ids"):
            keep = set(payload["ids"])
            pls = [p for p in pls if p["id"] in keep]

        kekka, minna = [], []
        for p in pls:
            try:
                tr = _tracks(p["id"], tok)
            except Exception as e:
                kekka.append({"name": p["name"], "ok": False, "why": str(e)[:120]})
                continue
            kekka.append({"name": p["name"], "ok": True, "kyokusu": len(tr)})
            for t in tr:
                t2 = dict(t)
                t2["playlist"] = p["name"]
                minna.append(t2)

        # 重複（同じ曲が複数のプレイリストに入っている）を1行にまとめた版も作る
        uniq, seen = [], set()
        for t in minna:
            k = t.get("spotifyId") or (_norm(t["kyoku"]) + "|" + _norm(t["artist"]))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(t)

        base = "zenkyoku" + (("_" + re.sub(r"[^\w぀-ヿ一-鿿]+", "", only)) if only else "")
        pj = os.path.join(OUT_DIR, base + ".json")
        json.dump({"at": _now(), "only": only, "playlists": kekka,
                   "kyokusu": len(minna), "juufukuNashi": len(uniq), "kyoku": minna},
                  io.open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        pc = os.path.join(OUT_DIR, base + ".csv")
        import csv
        with io.open(pc, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["プレイリスト", "曲名", "アーティスト", "アルバム",
                        "発売", "長さ(秒)", "SpotifyのURL", "入れた日"])
            for t in minna:
                w.writerow([t["playlist"], t["kyoku"], t["artist"], t["album"],
                            t["hatsubai"], t["byou"], t["url"], t["iretaHi"]])

        pm = os.path.join(OUT_DIR, base + ".md")
        with io.open(pm, "w", encoding="utf-8") as f:
            f.write("# たまごさんのSpotify（%s）\n\n" % _now())
            if only:
                f.write("しぼり込み：名前に「%s」を含むプレイリスト\n\n" % only)
            f.write("全%d曲（重複を除くと%d曲）／プレイリスト%d本\n\n"
                    % (len(minna), len(uniq), len(kekka)))
            cur = None
            for t in minna:
                if t["playlist"] != cur:
                    cur = t["playlist"]
                    f.write("\n## %s\n\n" % cur)
                f.write("- %s ／ %s ／ %s\n" % (t["kyoku"], t["artist"], t["url"]))

        return {"ok": True, "op": op, "only": only,
                "playlists": kekka, "kyokusu": len(minna), "juufukuNashi": len(uniq),
                "files": [os.path.relpath(x, REPO) for x in (pj, pc, pm)],
                "totalYen": 0.0}

    return {"ok": False, "error": "知らない op です: %s" % op, "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"op": sys.argv[1] if len(sys.argv) > 1 else "shirabe",
                              "only": sys.argv[2] if len(sys.argv) > 2 else ""}),
                     ensure_ascii=False, indent=1))
