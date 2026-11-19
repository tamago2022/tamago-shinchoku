#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1133番【空っぽ判定】OG画像を機械で見て「これは顔が無い」を出す。

たまごさん（2026-09-25）:
  「8割が空っぽのクリーム色のグラデーション。真ん中に卵が豆粒サイズで1つ。
    何のカードか分からない。」
  「検品を自動にする。空っぽ判定（画像の大半が単色／主要被写体が小さすぎる）を
    機械で出せるようにして、tools/kakunin.py に組み込む。」

■ 見るもの（全部その場で数える。目で見ない）
  1. 単色率      … いちばん多い色（24階調に丸めた）が画面の何%を占めるか
  2. 墨の量      … 地の色から十分に離れた画素（＝文字や絵）の割合
  3. いちばん大きい塊の高さ … 文字が豆粒サイズでないか（400px幅で読めるかの当たり）
  4. 大きさ      … 1200x630 相当か（小さい画像はXで大きい絵にならない）

■ 判定
  ✕ 空っぽ … 単色率 >= 72%  または  墨の量 < 1.8%  または  塊の高さ < 画面の8%
  ✕ 小さい … 幅 < 600
  ○ それ以外

■ 使い方
    python3 tools/1133_og_karappo.py <画像ファイル|URL> [...]
    from _1133_og_karappo import judge_bytes
  rc=0 … 全部○ ／ rc=1 … 1枚でも✕
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request
from collections import Counter

from PIL import Image

# ★閾値は実測で決めた（2026-09-25）。
#   今の空っぽ型（クリーム地＋豆粒の卵＋下の黒帯）… 墨7.1% / 塊 7% → 塊で落ちる
#   新しいカード（余白は広いが曲名が大きい）    … 墨3.2-3.7% / 塊 14-19% → 通る
#   ＝「単色率が高い」は落とす理由にしない。余白の広さはこちらの作風だから。
#     落とす理由は**顔（大きな塊）が無いこと**。
TANSHOKU_MAX = 0.90     # ここまで同じ色＋墨も薄いなら、さすがに空っぽ
SUMI_MIN = 0.020        # 墨（文字・絵）の量がこれ未満なら空っぽ
KATAMARI_MIN = 0.10     # いちばん大きい塊の高さ（画面比）がこれ未満なら豆粒
HABA_MIN = 600
# 全曲で同じ絵＝曲の顔ではない。住所で分かるものはここで落とす。
KYOUTSUU = ("og-four-doors", "og-default", "ogp-default")
YOSO = ("pbs.twimg.com", "img.youtube.com")


def judge_bytes(raw: bytes) -> dict:
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    r = {"size": [w, h], "bytes": len(raw)}
    small = im.resize((160, 84), Image.LANCZOS)
    px = list(small.getdata())
    q = [(a // 24, b // 24, c // 24) for a, b, c in px]
    cnt = Counter(q)
    (top, n) = cnt.most_common(1)[0]
    r["tanshoku"] = round(n / len(q), 3)
    ji = tuple(v * 24 + 12 for v in top)            # 地の色

    def far(p):
        return sum(abs(p[i] - ji[i]) for i in range(3)) > 150

    ink = [far(p) for p in px]
    r["sumi"] = round(sum(ink) / len(ink), 4)

    # 墨のある行の、いちばん長い連なり＝文字の塊の高さ
    rows = [any(ink[y * 160 + x] for x in range(160)) for y in range(84)]
    best = cur = 0
    for v in rows:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    r["katamari"] = round(best / 84, 3)

    riyuu = []
    if w < HABA_MIN:
        riyuu.append("小さすぎる（幅%d）" % w)
    if r["tanshoku"] >= TANSHOKU_MAX and r["sumi"] < 0.04:
        riyuu.append("画面の%d%%が同じ色で墨も薄い＝空っぽ" % round(r["tanshoku"] * 100))
    if r["sumi"] < SUMI_MIN:
        riyuu.append("文字も絵もほぼ無い（墨%.1f%%）" % (r["sumi"] * 100))
    if r["katamari"] < KATAMARI_MIN:
        riyuu.append("いちばん大きい塊が画面の%d%%＝豆粒" % round(r["katamari"] * 100))
    r["karappo"] = bool(riyuu)
    r["riyuu"] = riyuu
    return r


def judge(src: str) -> dict:
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "tamago-og-kenpin/1.0"})
        with urllib.request.urlopen(req, timeout=25) as res:
            raw = res.read()
    else:
        raw = open(src, "rb").read()
    out = judge_bytes(raw)
    out["src"] = src
    if any(k in src for k in KYOUTSUU):
        out["riyuu"].insert(0, "全曲で同じ扉の絵＝曲の顔ではない")
        out["karappo"] = True
    if any(k in src for k in YOSO):
        out["riyuu"].insert(0, "よその倉庫の画像（消える／小さい）")
        out["karappo"] = True
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ng = 0
    for s in sys.argv[1:]:
        try:
            r = judge(s)
        except Exception as e:
            r = {"src": s, "karappo": True, "riyuu": ["取れない: %s" % repr(e)[:80]]}
        ng += 1 if r["karappo"] else 0
        print(("✕ " if r["karappo"] else "○ ") + os.path.basename(s), json.dumps(
            r, ensure_ascii=False))
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
