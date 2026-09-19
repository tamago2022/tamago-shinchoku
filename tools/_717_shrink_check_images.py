#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
案件#717：share/ 配下（Eagleギャラリーを除く）の1MB超の静止画（png/jpg/jpeg）を
その場で（同じファイル名・同じ拡張子のまま）縮小する一回きりのバッチ。

拡張子は変えない＝確認ページ側の<img src>を書き換える必要が無い（既存URLを壊さない）。
- jpg/jpeg: 画質を段階的に下げる。それでも収まらなければ長辺を縮小して再試行。
- png    : まず可逆最適化。収まらなければ長辺を縮小、それでも収まらなければ
           adaptiveパレット(256→128→64色)に落として保存（写真調のpng向け）。
"""
import os
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 1_000_000
SKIP_DIRS = ("share/eagle-k7m2xq9p",)


def find_targets():
    out = []
    for root, dirs, files in os.walk(os.path.join(REPO, "share")):
        rel_root = os.path.relpath(root, REPO)
        if any(rel_root == d or rel_root.startswith(d + os.sep) for d in SKIP_DIRS):
            dirs[:] = []
            continue
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                p = os.path.join(root, f)
                try:
                    if os.path.getsize(p) > LIMIT:
                        out.append(p)
                except OSError:
                    pass
    return out


def shrink_jpeg(p):
    im = Image.open(p)
    im.load()
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    q = 85
    while True:
        im.save(p, "JPEG", quality=q, optimize=True)
        if os.path.getsize(p) <= LIMIT or (q <= 40 and max(im.size) <= 800):
            return
        if q > 40:
            q -= 10
        else:
            w, h = im.size
            im = im.resize((max(1, int(w * 0.85)), max(1, int(h * 0.85))), Image.LANCZOS)


def shrink_png(p):
    im = Image.open(p)
    im.load()
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    # 1) まず可逆optimizeだけ試す
    im.save(p, "PNG", optimize=True)
    if os.path.getsize(p) <= LIMIT:
        return
    # 2) 長辺を段階的に縮小しつつ、パレット量子化も試す
    cur = im
    for max_side in (1600, 1200, 900):
        w, h = cur.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            cur = cur.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        for colors in (256, 128, 64):
            q = cur.convert("RGBA") if has_alpha else cur.convert("RGB")
            method = Image.Quantize.FASTOCTREE if has_alpha else Image.Quantize.MEDIANCUT
            pal = q.quantize(colors=colors, method=method, dither=Image.Dither.NONE)
            pal.save(p, "PNG", optimize=True)
            if os.path.getsize(p) <= LIMIT:
                return
    # 3) それでもダメなら最終手段としてJPEGへは変えず、可能な限り小さくして諦める
    return


def main():
    targets = find_targets()
    print("対象: %d件" % len(targets))
    ok, ng = 0, []
    for p in targets:
        before = os.path.getsize(p)
        try:
            if p.lower().endswith((".jpg", ".jpeg")):
                shrink_jpeg(p)
            else:
                shrink_png(p)
            after = os.path.getsize(p)
            status = "OK" if after <= LIMIT else "残"
            if after <= LIMIT:
                ok += 1
            else:
                ng.append((p, after))
            print("%s %8d -> %8d  %s" % (status, before, after, os.path.relpath(p, REPO)))
        except Exception as e:
            ng.append((p, str(e)))
            print("失敗", p, e)
    print("完了: %d/%d件がLIMIT以下に。残り%d件" % (ok, len(targets), len(ng)))
    for p, a in ng:
        print("  残:", p, a)


if __name__ == "__main__":
    sys.exit(main())
