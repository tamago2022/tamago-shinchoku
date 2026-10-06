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
THUMB_MAX = 480  # グリッド表示用サムネの長辺上限px（2026-09-12・案件#717）
BYTE_CAP = 950_000  # kenpou_check.py BIG_FILE_LIMIT(1MB)に対する安全マージン


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


def make_thumb(src, dst):
    """グリッド表示用サムネを作る。2026-09-12(案件#717)まではEagle自身の_thumbnail.*を
    そのままコピーしていたため、Eagle側のサムネがそもそも大きい場合はそのまま巨大ファイルになっていた
    （実測：t/配下だけで1MB超が5件）。ここで必ず長辺THUMB_MAX以下へ縮小してから保存する。
    """
    ext = os.path.splitext(src)[1].lower()
    if Image is None or ext not in (".png", ".jpg", ".jpeg", ".webp"):
        # 動画のサムネ・gif等、扱えない形式はこれまで通り無劣化コピー
        shutil.copyfile(src, dst)
        return
    try:
        im = Image.open(src)
        im.load()
        w, h = im.size
        if max(w, h) > THUMB_MAX:
            scale = THUMB_MAX / float(max(w, h))
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        if ext == ".png" and im.mode in ("RGBA", "LA", "P"):
            im.save(dst, "PNG", optimize=True)
        else:
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(dst, "JPEG" if ext in (".jpg", ".jpeg") else "WEBP", quality=78)
    except Exception:
        shutil.copyfile(src, dst)


def _save_jpeg_under_cap(im, dst, cap=BYTE_CAP, start_q=82, min_q=45):
    """JPEGで保存し、capバイトを超えたら品質→サイズの順に下げて収める（案件#717：1MB超ガードの再発防止）。"""
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    q = start_q
    cur = im
    while True:
        cur.save(dst, "JPEG", quality=q, optimize=True)
        if os.path.getsize(dst) <= cap or (q <= min_q and max(cur.size) <= 640):
            return
        if q > min_q:
            q -= 10
        else:
            w, h = cur.size
            scale = 0.85
            cur = cur.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


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
        if max(w, h) <= HANDOFF_MAX and os.path.getsize(orig_path) <= BYTE_CAP:
            # すでに小さい＝原本のバイト列をそのままコピー（劣化なし）
            dst_ext = "." + (ext if ext in ("png", "jpg", "jpeg", "webp") else "png")
            dst = os.path.join(HANDOFF, item_id + dst_ext)
            if not os.path.exists(dst):
                shutil.copyfile(orig_path, dst)
            return dst_ext
        # 2026-09-12(案件#717)：長辺は小さくても「原本のバイト列コピー」だと1MBを超えることがある
        #   （検出量：eagle-k7m2xq9p/o配下だけで232件）。長辺基準の分岐をやめ、
        #   常にJPEGへ再エンコードしてBYTE_CAPに収める一本化した経路にする。
        if im.mode in ("P", "RGBA", "LA"):
            im = im.convert("RGB")
        if max(w, h) > HANDOFF_MAX:
            scale = HANDOFF_MAX / float(max(w, h))
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        dst = os.path.join(HANDOFF, item_id + ".jpg")
        if not os.path.exists(dst):
            _save_jpeg_under_cap(im, dst)
            return ".jpg"
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
                make_thumb(src, dst)
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
