#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
案件#717：既存のEagleギャラリー画像（share/eagle-k7m2xq9p/o, /t）のうち
1MB超のものを、eagle_gallery.py に入れた新ロジック（make_thumb/_save_jpeg_under_cap）で
その場で縮小する一回きりのバッチ。data.json の "o" 拡張子も合わせて更新する。

一度だけ手で実行する想定（今後の新規分は eagle_gallery.py 本体の修正で自動的に収まる）。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eagle_gallery as eg  # noqa: E402

LIMIT = 1_000_000
OUT = eg.OUT
DATA = eg.DATA
THUMBS = eg.THUMBS
HANDOFF = eg.HANDOFF


def main():
    data = json.load(io.open(DATA, encoding="utf-8"))
    items = data.get("items", [])
    by_id = {it["id"]: it for it in items}

    shrunk_o = 0
    shrunk_t = 0
    failed = []

    # --- o/（受け渡し用） ---
    for fn in sorted(os.listdir(HANDOFF)):
        p = os.path.join(HANDOFF, fn)
        if not os.path.isfile(p):
            continue
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz <= LIMIT:
            continue
        iid, ext = os.path.splitext(fn)
        item = by_id.get(iid)
        try:
            im = eg.Image.open(p)
            im.load()
            w, h = im.size
            if max(w, h) > eg.HANDOFF_MAX:
                scale = eg.HANDOFF_MAX / float(max(w, h))
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), eg.Image.LANCZOS)
            if im.mode in ("P", "RGBA", "LA"):
                im = im.convert("RGB")
            new_dst = os.path.join(HANDOFF, iid + ".jpg")
            eg._save_jpeg_under_cap(im, new_dst)
            if new_dst != p and os.path.exists(p):
                os.remove(p)
            if item is not None:
                item["o"] = ".jpg"
            shrunk_o += 1
        except Exception as e:
            failed.append((p, str(e)))

    # --- t/（サムネ） ---
    for fn in sorted(os.listdir(THUMBS)):
        p = os.path.join(THUMBS, fn)
        if not os.path.isfile(p):
            continue
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz <= LIMIT:
            continue
        try:
            eg.make_thumb(p, p)
            shrunk_t += 1
        except Exception as e:
            failed.append((p, str(e)))

    json.dump(data, io.open(DATA, "w", encoding="utf-8"), ensure_ascii=False)
    print("o/縮小: %d件 / t/縮小: %d件 / 失敗: %d件" % (shrunk_o, shrunk_t, len(failed)))
    for p, e in failed[:20]:
        print("  失敗:", p, e)


if __name__ == "__main__":
    main()
