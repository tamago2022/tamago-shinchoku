#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spotifyのプレイリスト1枚の全曲を読む（GETだけ・新しい /items 口を先に試す）。
使い方: python3 tools/houou_sp.py <playlist_id> <out.json>
"""
import json
import os
import sys
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spotify_ninshou as sn  # noqa: E402
import spotify_takoukan as st  # noqa: E402


def main():
    pid, dst = sys.argv[1], sys.argv[2]
    tok = sn.access_token()
    out = {"pid": pid, "tracks": [], "errors": []}
    for first in ("/playlists/%s/items?limit=50" % pid, "/playlists/%s/tracks?limit=50" % pid, "/playlists/%s" % pid):
        try:
            url = first
            got = []
            while url:
                d = st.call(tok, url)
                if "items" in d and isinstance(d["items"], dict):
                    d = d["items"]
                if "tracks" in d and isinstance(d["tracks"], dict):
                    d = d["tracks"]
                for x in d.get("items") or []:
                    t = x.get("item") or x.get("track") or {}
                    got.append({"name": t.get("name"), "artists": [a.get("name") for a in t.get("artists") or []],
                                "artistIds": [a.get("id") for a in t.get("artists") or []],
                                "album": (t.get("album") or {}).get("name"),
                                "release": (t.get("album") or {}).get("release_date"),
                                "id": t.get("id"), "isrc": (t.get("external_ids") or {}).get("isrc")})
                url = d.get("next")
            out["tracks"] = got
            out["via"] = first
            break
        except urllib.error.HTTPError as e:
            out["errors"].append("%s %s %s" % (first, e.code, e.read().decode("utf-8", "replace")[:200]))
        except Exception as e:  # noqa: BLE001
            out["errors"].append("%s %r" % (first, e))
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done", len(out["tracks"]), out["errors"][:3])


if __name__ == "__main__":
    main()
