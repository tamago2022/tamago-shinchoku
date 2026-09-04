#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eagleライブラリ → スマホ用Webギャラリーを差分更新する。

2026-09-03 たまごさん：
  「データ、例えばこれを追加しても更新されるのかな、自動的に。それだと助かる」
  「iPhoneでツイート見てていいなと思ったスクショを、すかさずここに入れられるのかな。そういうスピード感だと助かる」

やること:
  1. Eagleライブラリの images/*.info を読む
  2. まだギャラリーに無いものだけ、サムネをコピーして data.json に足す
  3. Eagle側で消えたものはギャラリーからも消す（サムネのファイルは残す＝復活が速い）
  4. 画像（png/jpg/jpeg/webp/gif）は、サムネとは別に「受け渡し用」画像も o/ に作る。
     長辺1600pxまでに抑えた実物（それ以下ならそのまま）＝「元の全データ」そのものではないが、
     保存・共有に十分な画質。動画(mov/mp4)やpdf等は対象外（サムネ表示のみ・今回は見送り）。

新規ぶんだけ処理するので、毎回まわしても数秒〜数分で終わる。1日1回 machine_status_push.sh から呼ぶ。
"""
import io
import json
import os
import shutil
import sys
import time

try:
    from PIL import Image
except Exception:
    Image = None

LIB = "/Volumes/iMac HDD/Eagle_Library_2026-09-02/eagle AI 画像整理.library"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "share", "eagle-k7m2xq9p")
DATA = os.path.join(OUT, "data.json")
THUMBS = os.path.join(OUT, "t")
HANDOFF = os.path.join(OUT, "o")
HANDOFF_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}
HANDOFF_MAX = 1600  # 長辺の上限px
HANDOFF_GIF_LIMIT = 8 * 1024 * 1024  # gifはアニメ崩れを避け、そのままコピー。大きすぎる分は見送り


def folder_names(lib):
    """フォルダIDから「親 / 子」形式の名前を引く表"""
    out = {}
    try:
        md = json.load(io.open(os.path.join(lib, "metadata.json"), encoding="utf-8"))
    except Exception:
        return out

    def walk(fs, path=""):
        for f in fs or []:
            name = f.get("name") or ""
            full = (path + " / " + name) if path else name
            out[f.get("id")] = full
            walk(f.get("children"), full)

    walk(md.get("folders"))
    return out


def find_original(p):
    """サムネ(_thumbnail.*)ではなく、本物のファイルを探す"""
    for f in os.listdir(p):
        if f == "metadata.json" or f.startswith("."):
            continue
        if "_thumbnail." in f:
            continue
        return os.path.join(p, f)
    return None


def make_handoff(orig_path, ext, item_id):
    """受け渡し用画像を o/ に作る。戻り値は保存した拡張子（作れなければNone）"""
    ext = (ext or "").lower()
    if ext not in HANDOFF_EXTS or Image is None:
        return None
    os.makedirs(HANDOFF, exist_ok=True)
    try:
        if ext == "gif":
            if os.path.getsize(orig_path) > HANDOFF_GIF_LIMIT:
                return None
            dst = os.path.join(HANDOFF, item_id + ".gif")
            if not os.path.exists(dst):
                shutil.copyfile(orig_path, dst)
            return ".gif"
        im = Image.open(orig_path)
        im.load()
        w, h = im.size
        if max(w, h) <= HANDOFF_MAX:
            # すでに小さい＝原本のバイト列をそのままコピー（劣化なし）
            dst_ext = "." + (ext if ext in ("png", "jpg", "jpeg", "webp") else "png")
            dst = os.path.join(HANDOFF, item_id + dst_ext)
            if not os.path.exists(dst):
                shutil.copyfile(orig_path, dst)
            return dst_ext
        if im.mode in ("P", "RGBA", "LA"):
            im = im.convert("RGB")
        scale = HANDOFF_MAX / float(max(w, h))
        im2 = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        dst = os.path.join(HANDOFF, item_id + ".jpg")
        if not os.path.exists(dst):
            im2.save(dst, "JPEG", quality=82, optimize=True)
        return ".jpg"
    except Exception:
        return None


def read_item(p, folders):
    try:
        m = json.load(io.open(os.path.join(p, "metadata.json"), encoding="utf-8"))
    except Exception:
        return None, None
    iid = m.get("id") or os.path.basename(p)[:-5]
    tags = m.get("tags") or []
    src = None
    for f in os.listdir(p):
        if "_thumbnail." in f:
            src = os.path.join(p, f)
            break
    if src is None:
        for f in os.listdir(p):
            if f != "metadata.json" and not f.startswith("."):
                src = os.path.join(p, f)
                break
    if src is None:
        return None, None
    item = {
        "id": iid,
        "n": m.get("name") or "",
        "e": (m.get("ext") or "").lower(),
        "t": [t for t in tags if not t.startswith("_")],
        "h": [t for t in tags if t.startswith("_")],
        "f": [folders.get(x) for x in (m.get("folders") or []) if folders.get(x)],
        "w": m.get("width"),
        "hgt": m.get("height"),
        "te": os.path.splitext(src)[1].lower() or ".png",
        "mt": m.get("modificationTime") or m.get("btime") or 0,
    }
    return item, src


def main():
    if not os.path.isdir(LIB):
        print("ライブラリが見つからない（外付けが外れている？）:", LIB)
        return 1
    os.makedirs(THUMBS, exist_ok=True)
    try:
        cur = json.load(io.open(DATA, encoding="utf-8"))
    except Exception:
        cur = {"count": 0, "items": []}
    known = {it["id"]: it for it in cur.get("items", [])}

    folders = folder_names(LIB)
    imgs = os.path.join(LIB, "images")
    live, added, updated, handoff_made = set(), 0, 0, 0
    for d in sorted(os.listdir(imgs)):
        if not d.endswith(".info"):
            continue
        p = os.path.join(imgs, d)
        iid = d[:-5]
        live.add(iid)
        old = known.get(iid)
        # 既知でメタの更新も無ければ触らない（差分更新）。
        # ただし画像なのに受け渡し用(o)がまだ無い分（既存の未対応ぶん）は、初回だけ穴埋めで通す。
        needs_handoff_backfill = bool(
            old is not None
            and (old.get("e") or "").lower() in HANDOFF_EXTS
            and not old.get("o")
        )
        if old is not None and not needs_handoff_backfill:
            try:
                mtime = os.path.getmtime(os.path.join(p, "metadata.json"))
            except Exception:
                mtime = 0
            if old.get("_s") and mtime <= old["_s"]:
                continue
        item, src = read_item(p, folders)
        if item is None:
            continue
        dst = os.path.join(THUMBS, item["id"] + item["te"])
        if not os.path.exists(dst):
            try:
                shutil.copyfile(src, dst)
            except Exception:
                continue
        orig = find_original(p)
        if orig is not None:
            oext = make_handoff(orig, item["e"], item["id"])
            if oext:
                item["o"] = oext
                if not (old and old.get("o")):
                    handoff_made += 1
        elif old is not None and old.get("o"):
            item["o"] = old["o"]  # 原本を見失っても既存の受け渡し画像は保つ
        try:
            item["_s"] = os.path.getmtime(os.path.join(p, "metadata.json"))
        except Exception:
            item["_s"] = time.time()
        if old is None:
            added += 1
        elif not needs_handoff_backfill:
            updated += 1
        known[iid] = item

    removed = [k for k in known if k not in live]
    for k in removed:
        known.pop(k, None)

    items = sorted(known.values(), key=lambda x: -(x.get("mt") or 0))
    json.dump({"count": len(items), "items": items, "updatedAt": time.strftime("%Y-%m-%d %H:%M")},
              io.open(DATA, "w", encoding="utf-8"), ensure_ascii=False)
    if added or updated or removed or handoff_made:
        print("ギャラリー更新: 追加%d / 更新%d / 削除%d / 受け渡し画像%d / 合計%d" % (added, updated, len(removed), handoff_made, len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
