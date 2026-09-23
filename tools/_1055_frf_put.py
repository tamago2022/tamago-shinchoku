#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1055番：FRF'26 公式アーティストページ1枚から、門0の証拠を1件書く。

★出どころは公式ページ1つに絞る（誰が出るかを決めているのは主催者だから）。
★曲は1曲も書かない。公式の動画と公式チャンネルのURLだけ控える。
"""
import io, json, os, datetime, re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "status", "shiire_shoko")
FRF = "https://www.fujirockfestival.com/artist/detail/%s"


def slug(name):
    s = re.sub(r"[^0-9a-zA-Z぀-ヿ一-鿿]+", "-", name).strip("-").lower()
    return s or "noname"


def frf(name, fid, kuni, yt=None, site=None, mv=None, memo="", slug_=None, hantei="本人確定"):
    os.makedirs(OUT, exist_ok=True)
    d = {
        "slug": slug_ or slug(name),
        "name": name,
        "decidedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hantei": hantei,
        "honnin": {"name": name, "kuni": kuni, "mbid": None},
        "shoko": [{"nani": "FRF'26 公式アーティストページ（国・メンバー・公式リンクが載っている）",
                   "url": FRF % fid}],
        "kokishiki": {"youtube": yt or "", "site": site or "",
                      "kokaiDouga": mv or ""},
        "memo": memo,
        "★まだやっていないこと": (
            "曲を1曲も引いていない。公式チャンネルの中身（素人カバー・静止画だけの動画）も未検品。"),
    }
    if yt:
        d["shoko"].append({"nani": "公式YouTubeチャンネル（公式ページのAudio/Video欄から）", "url": yt})
    if site:
        d["shoko"].append({"nani": "公式サイト", "url": site})
    p = os.path.join(OUT, d["slug"] + ".json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    return p
