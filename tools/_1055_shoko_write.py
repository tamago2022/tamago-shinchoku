#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1055番：門0（本人の証拠）を1件ずつ status/shiire_shoko/<slug>.json に書く。

★ここに書くのは「誰なのか」と「その出どころURL」だけ。曲は1曲も書かない。
★回線の要る所（MusicBrainzのworks）はここでは触らない。
★判定は 本人確定 / 保留 の2つだけ。「たぶん」は保留に倒す（skill sekisho-artist-song 掟4）。
"""
import io, json, os, sys, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "status", "shiire_shoko")


def put(slug, name, hantei, honnin, shoko, memo=""):
    assert hantei in ("本人確定", "保留"), hantei
    os.makedirs(OUT, exist_ok=True)
    d = {
        "slug": slug,
        "name": name,
        "decidedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hantei": hantei,
        "honnin": honnin,     # {"name":..,"kuni":..,"mbid":..|None}
        "shoko": shoko,       # [{"nani":..,"url":..}]
        "memo": memo,
        "★まだやっていないこと": (
            "曲を1曲も引いていない（MusicBrainzのworksは回線が要る）。"
            "動画の検品（素人カバー・静止画だけの動画を弾く）もまだ。"),
    }
    p = os.path.join(OUT, slug + ".json")
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    return p


if __name__ == "__main__":
    print(OUT)
