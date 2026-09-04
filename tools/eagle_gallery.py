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

新規ぶんだけ処理するので、毎回まわしても数秒で終わる。5分おきの machine_status_push.sh から呼ぶ。
"""
import io
import json
import os
import shutil
import sys
import time

LIB = "/Volumes/iMac HDD/Eagle_Library_2026-09-02/eagle AI 画像整理.library"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "share", "eagle-k7m2xq9p")
DATA = os.path.join(OUT, "data.json")
THUMBS = os.path.join(OUT, "t")


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
    live, added, updated = set(), 0, 0
    for d in sorted(os.listdir(imgs)):
        if not d.endswith(".info"):
            continue
        p = os.path.join(imgs, d)
        iid = d[:-5]
        live.add(iid)
        old = known.get(iid)
        # 既知でメタの更新も無ければ触らない（差分更新）
        if old is not None:
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
        try:
            item["_s"] = os.path.getmtime(os.path.join(p, "metadata.json"))
        except Exception:
            item["_s"] = time.time()
        if old is None:
            added += 1
        else:
            updated += 1
        known[iid] = item

    removed = [k for k in known if k not in live]
    for k in removed:
        known.pop(k, None)

    items = sorted(known.values(), key=lambda x: -(x.get("mt") or 0))
    json.dump({"count": len(items), "items": items, "updatedAt": time.strftime("%Y-%m-%d %H:%M")},
              io.open(DATA, "w", encoding="utf-8"), ensure_ascii=False)
    if added or updated or removed:
        print("ギャラリー更新: 追加%d / 更新%d / 削除%d / 合計%d" % (added, updated, len(removed), len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
