#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1046番：プレイリスト「AI　作曲」に、grok調べの曲を**足すだけ**。

■ これがやること
  1. プレイリストの中身を**API で全件**取る（★スクショを正にしない）
  2. status/1046_ai_sakkyoku_tsuika_list.json の曲を1曲ずつ検索
  3. 曲名＋アーティスト名が一致したら足す。ダブりは飛ばす。無ければ「見つからなかった」
  4. **足した分だけ**を status/1046_ireta.json に控える → --modoshi で1コマンドで戻せる

■ 絶対にしないこと
  ・曲を消さない（--modoshi のときだけ、**この便で足した分だけ**を消す）
  ・パスワードを扱わない
  ・課金しない

■ 鍵（★ブラウザを開かない）
  tools/spotify_ninshou.py が ~/.tamago/spotify.json に置いた refresh_token から
  access_token を作る。**たまごさんのログインは今回1回だけ。以後ゼロ。**
  まだ同意が済んでいなければ「先に --hajime を」と言って何もしない。

  ★プレイリストに書き込むのに要る scope（公式で確認・推測ではない）：
    playlist-modify-public / playlist-modify-private
  （https://developer.spotify.com/documentation/web-api/reference/add-tracks-to-playlist）

使い方（Mac側で）:
  python3 tools/spotify_tsuika.py --shirabe     # 調べるだけ。1曲も足さない
  python3 tools/spotify_tsuika.py --ireru       # 実際に足す
  python3 tools/spotify_tsuika.py --modoshi     # この便で足した分だけ戻す
"""
import argparse

import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LIST_JSON = os.path.join(REPO, "status", "1046_ai_sakkyoku_tsuika_list.json")
IRETA_JSON = os.path.join(REPO, "status", "1046_ireta.json")
PLAYLIST_NAME = "AI　作曲"
API = "https://api.spotify.com/v1"


def token():
    """★ブラウザを開かない。~/.tamago/spotify.json の refresh_token から作る。"""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import spotify_ninshou
    return spotify_ninshou.access_token()


def call(tok, path, method="GET", payload=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Content-Type": "application/json"})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "2")) + 1)
                continue
            raise
    raise SystemExit("Spotifyが混んでいて通りませんでした: " + path)


def norm(s):
    """曲名・アーティスト名を突き合わせる用にそろえる。"""
    s = (s or "").lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("　", " ")):
        s = s.replace(a, b)
    keep = [c for c in s if c.isalnum() or c == " "]
    return " ".join("".join(keep).split())


def find_playlist(tok):
    url = "/me/playlists?limit=50"
    while url:
        d = call(tok, url)
        for p in d.get("items", []):
            if norm(p["name"]) == norm(PLAYLIST_NAME):
                return p
        url = d.get("next")
    raise SystemExit("プレイリスト「%s」が見つかりません" % PLAYLIST_NAME)


def playlist_tracks(tok, pid):
    """★全件取る。スクショを正にしない。"""
    out = []
    url = "/playlists/%s/tracks?limit=100&fields=next,items(track(id,uri,name,artists(name)))" % pid
    while url:
        d = call(tok, url)
        for it in d.get("items", []):
            t = it.get("track") or {}
            if t.get("id"):
                out.append({"id": t["id"], "uri": t["uri"], "name": t["name"],
                            "artists": [a["name"] for a in t.get("artists", [])]})
        url = d.get("next")
    return out


def search(tok, artist, title):
    q = urllib.parse.quote('track:"%s" artist:"%s"' % (title, artist))
    d = call(tok, "/search?q=%s&type=track&limit=10" % q)
    hits = (d.get("tracks") or {}).get("items") or []
    if not hits:  # 引用符つきで出なければ素の言葉でもう一度
        d = call(tok, "/search?q=%s&type=track&limit=10"
                 % urllib.parse.quote("%s %s" % (artist, title)))
        hits = (d.get("tracks") or {}).get("items") or []
    for t in hits:
        # ★同名の別人よけ：アーティスト名も一致していることを必ず見る
        if norm(t["name"]) == norm(title) and any(
                norm(a["name"]) == norm(artist) for a in t["artists"]):
            return t
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shirabe", action="store_true", help="調べるだけ。1曲も足さない")
    ap.add_argument("--ireru", action="store_true", help="実際に足す")
    ap.add_argument("--modoshi", action="store_true", help="この便で足した分だけ戻す")
    a = ap.parse_args()
    if not (a.shirabe or a.ireru or a.modoshi):
        ap.error("--shirabe / --ireru / --modoshi のどれかを付けてください")

    tok = token()
    pl = find_playlist(tok)
    pid = pl["id"]

    if a.modoshi:
        if not os.path.exists(IRETA_JSON):
            raise SystemExit("控えがありません: " + IRETA_JSON)
        rec = json.load(io.open(IRETA_JSON, encoding="utf-8"))
        uris = [x["uri"] for x in rec.get("ireta", [])]
        if not uris:
            print("戻すものはありません")
            return
        call(tok, "/playlists/%s/tracks" % pid, "DELETE",
             {"tracks": [{"uri": u} for u in uris]})
        print("戻しました: %d曲" % len(uris))
        return

    now = playlist_tracks(tok, pid)
    have = set((norm(t["name"]), norm(t["artists"][0] if t["artists"] else ""))
               for t in now)
    have_id = set(t["id"] for t in now)
    print("いまプレイリストに %d曲（API実測 %s）" % (len(now), time.strftime("%H:%M")))

    want = json.load(io.open(LIST_JSON, encoding="utf-8"))["kyoku"]
    ireru, dup, nashi = [], [], []
    for k in want:
        t = search(tok, k["artist"], k["title"])
        if not t:
            nashi.append(k)
            continue
        if t["id"] in have_id or (norm(t["name"]),
                                  norm(t["artists"][0]["name"])) in have:
            dup.append({"artist": k["artist"], "title": k["title"], "id": t["id"]})
            continue
        ireru.append({"artist": k["artist"], "title": k["title"],
                      "id": t["id"], "uri": t["uri"],
                      "found": "%s / %s" % (t["name"], t["artists"][0]["name"])})
        have_id.add(t["id"])

    print("\n--- 足すもの %d曲 ---" % len(ireru))
    for x in ireru:
        print("  + %s ／ %s" % (x["title"], x["artist"]))
    print("--- ダブりで飛ばす %d曲 ---" % len(dup))
    for x in dup:
        print("  = %s ／ %s" % (x["title"], x["artist"]))
    print("--- 見つからなかった %d曲 ---" % len(nashi))
    for x in nashi:
        print("  ? %s ／ %s" % (x["title"], x["artist"]))

    if a.shirabe or not ireru:
        return

    for i in range(0, len(ireru), 100):
        call(tok, "/playlists/%s/tracks" % pid, "POST",
             {"uris": [x["uri"] for x in ireru[i:i + 100]]})
    with io.open(IRETA_JSON, "w", encoding="utf-8") as f:
        json.dump({"bin": "1046", "at": time.strftime("%F %T"),
                   "playlistId": pid, "playlistName": pl["name"],
                   "ireta": ireru, "dup": dup, "nashi": nashi},
                  f, ensure_ascii=False, indent=1)
    print("\n入れました: %d曲 ／ ダブり %d曲 ／ 見つからなかった %d曲"
          % (len(ireru), len(dup), len(nashi)))
    print("戻すとき: python3 tools/spotify_tsuika.py --modoshi")


if __name__ == "__main__":
    sys.exit(main())
