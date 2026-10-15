# -*- coding: utf-8 -*-
"""1051番【別人混入を機械で判定する】保留になった曲の動画を、
YouTube Data API で「どのチャンネルが上げたか」だけ取ってくる。

なぜ要るか（実測 2026-09-24）：
  関所 gate_artist_song.py が 2230件を「保留」にした。中身を見ると
  「Uptown Funk (feat. Bruno Mars)」がマーク・ロンソンの棚で保留、のような
  **正しいのに引っかかっているもの**が大量にある。曲名の文字だけでは判定できない。
  ★動画を上げたチャンネル名が分かれば、「演っているのは誰か」が機械で当たる。
  （Topicチャンネルは演者名そのもの。公式チャンネルも本人名。）

課金：YouTube Data API の videos.list は **1回1ユニット・1回に50件**。
  2230件なら45ユニット。1日の枠は10000ユニット＝**0円**（枠内・課金なし）。

使い方（★Macの上で走らせる。サンドボックスからYouTubeへは出られない）：
  python3 tools/sekisho/yt_channel_shiraberu.py \
      --in status/_1051/yt_ids.json --out status/_1051/yt_channels.json
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
API = "https://www.googleapis.com/youtube/v3/videos"


def _key():
    k = os.environ.get("YOUTUBE_DATA_API_KEY")
    if k:
        return k.strip()
    p = os.path.join(REPO, ".env")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            m = re.match(r"\s*YOUTUBE_DATA_API_KEY\s*=\s*(.+?)\s*$", ln)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return ""


def fetch(ids, key):
    """50件までの動画idを1回で引く。{id: {channelTitle, channelId, title}}"""
    q = urllib.parse.urlencode({
        "part": "snippet", "id": ",".join(ids), "key": key, "maxResults": 50})
    req = urllib.request.Request(API + "?" + q)
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read().decode("utf-8", "ignore"))
    out = {}
    for it in j.get("items") or []:
        sn = it.get("snippet") or {}
        out[it.get("id")] = {
            "channelTitle": sn.get("channelTitle") or "",
            "channelId": sn.get("channelId") or "",
            "videoTitle": sn.get("title") or "",
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--max-units", type=int, default=160,
                    help="使う上限ユニット数（1回50件）。既定160=8000件まで")
    a = ap.parse_args()

    key = _key()
    if not key:
        print("NG: YOUTUBE_DATA_API_KEY が見つかりません")
        return 2

    inp = a.inp if os.path.isabs(a.inp) else os.path.join(REPO, a.inp)
    outp = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    ids = json.load(open(inp, encoding="utf-8"))
    ids = [i for i in dict.fromkeys(ids) if re.fullmatch(r"[\w-]{11}", i or "")]

    known = {}
    if os.path.exists(outp):
        try:
            known = json.load(open(outp, encoding="utf-8"))
        except Exception:
            known = {}
    todo = [i for i in ids if i not in known]
    print("引く件数 %d（済み %d ／ 全 %d）" % (len(todo), len(known), len(ids)))

    units = 0
    for i in range(0, len(todo), 50):
        if units >= a.max_units:
            print("上限ユニットに達したので止めます（%d）" % units)
            break
        chunk = todo[i:i + 50]
        try:
            got = fetch(chunk, key)
        except Exception as e:
            print("NG chunk %d: %s" % (i, e))
            break
        units += 1
        for vid in chunk:
            known[vid] = got.get(vid) or {"channelTitle": "", "channelId": "",
                                          "videoTitle": "", "missing": True}
        json.dump(known, open(outp, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        time.sleep(0.2)

    got = sum(1 for v in known.values() if v.get("channelTitle"))
    print("取れた %d ／ 消えている動画 %d ／ 使ったユニット %d（=0円・1日枠10000）"
          % (got, len(known) - got, units))
    print("書いた: %s" % outp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
