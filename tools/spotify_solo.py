#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spotifyプレイリスト「ソロプレナー神回」を作り、日本語音源を入れる（2026-10-15）。

通す経路（上から順に試す。鍵は tools/spotify_ninshou.py の access_token()＝鍵帳から自動・ブラウザ不要）：
  1) プレイリストを作る（2回目以降は同じものを使う）
  2) 元エピソード（Lex Fridman Podcast #440 Pieter Levels）を Web API で入れる（エピソードは API で入れられる）
  3) 日本語音源は「ローカルファイル」：Spotifyアプリが見張っているフォルダ
     （~/Music/Music/Media.localized/Music ＝ watch-sources に登録済み）へ、題名・アーティスト・アルバムを付けて置く
     → アプリの「ローカルファイル」に出る
  4) そのローカル曲を spotify:local:… の形で Web API に入れてみる（公式には不可とされる。通らなければ記録して未確認）
使い方（Mac）：python3 tools/spotify_solo.py --m4a <日本語音源>
結果：status/spotify/solo.json
"""
import argparse, json, os, shutil, subprocess, sys, time, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spotify_ninshou as sn
import spotify_takoukan as st

NAME = "ソロプレナー神回"
DESC = "一人で作って一人で稼ぐ人たちの神回。日本語要約版（ローカル音源）と元の回。"
OUT = os.path.join(os.path.dirname(HERE), "status", "spotify", "solo.json")
LOCAL_ROOT = os.path.expanduser("~/Music/Music/Media.localized/Music")
ARTIST = "ソロプレナー神回"
ALBUM = "日本語要約"
TITLE = "ピーター・レベルズ｜一人で作って一人で稼ぐ（Lex Fridman 440 日本語版）"
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def seconds(p):
    out = subprocess.run(["/usr/bin/afinfo", p], capture_output=True, text=True).stdout
    for ln in out.splitlines():
        if "estimated duration" in ln:
            return float(ln.split(":")[1].split()[0])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m4a", required=True)
    a = ap.parse_args()
    res = {"at": time.strftime("%F %T"), "name": NAME}
    tok = sn.access_token()
    # 1) プレイリスト
    st.NAME, st.DESC = NAME, DESC
    pid = st.get_playlist(tok)
    res["url"] = "https://open.spotify.com/playlist/%s" % pid
    log("プレイリスト", res["url"])
    uris = []
    # 2) 元エピソード
    q = urllib.parse.urlencode({"q": "Lex Fridman Pieter Levels 440", "type": "episode", "limit": 10, "market": "JP"})
    ep = None
    for it in (st.call(tok, "/search?" + q).get("episodes") or {}).get("items") or []:
        if it and "pieter levels" in (it.get("name") or "").lower() and "440" in (it.get("name") or ""):
            ep = it; break
    if ep:
        uris.append(ep["uri"]); res["episode"] = {"name": ep["name"], "url": ep["external_urls"]["spotify"]}
        log("元エピソード", ep["name"])
    else:
        res["episode"] = None; log("元エピソードが見つからない")
    # 3) ローカルファイルとして置く（題名などのタグ付き）
    d = os.path.join(LOCAL_ROOT, ARTIST, ALBUM)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "01 %s.m4a" % TITLE.replace("/", "／"))
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", a.m4a, "-c", "copy",
                        "-metadata", "title=" + TITLE, "-metadata", "artist=" + ARTIST,
                        "-metadata", "album=" + ALBUM, "-metadata", "track=1", dst], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copyfile(a.m4a, dst); log("タグ付けに失敗→そのまま写した", r.stderr[:200])
    sec = int(round(seconds(dst)))
    res["local_file"] = dst.replace(os.path.expanduser("~"), "~")
    res["local_sec"] = sec
    log("ローカルファイルに置いた", res["local_file"], sec, "秒")
    # 先にエピソードだけ入れる（ローカル曲の失敗に巻き込まない）
    if uris:
        st.put_items(tok, pid, uris)
    # 4) ローカル曲を API で
    enc = lambda s: urllib.parse.quote_plus(s)
    local_uri = "spotify:local:%s:%s:%s:%d" % (enc(ARTIST), enc(ALBUM), enc(TITLE), sec)
    res["local_uri"] = local_uri
    added = False
    for path in ("/playlists/%s/items" % pid, "/playlists/%s/tracks" % pid):
        try:
            st.call(tok, path, "POST", {"uris": [local_uri], "position": 0})
            added = True; res["local_added_via"] = path; break
        except urllib.error.HTTPError as e:
            res.setdefault("local_errors", []).append("%s %s %s" % (path, e.code, e.read().decode("utf-8", "replace")[:160]))
    res["local_added"] = added
    pl = st.call(tok, "/playlists/%s" % pid)
    items = ((pl.get("items") or pl.get("tracks") or {}).get("items")) or []
    res["in_playlist"] = [((x.get("item") or x.get("track") or {}) or {}).get("name") for x in items]
    res["in_playlist_local"] = [bool(x.get("is_local")) for x in items]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("RESULT", json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
