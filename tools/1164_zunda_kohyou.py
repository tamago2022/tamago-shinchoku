#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1164番【できた声を本番に置く】(2026-09-26)

たまごさん実測：「一覧から選んでも読めない」。
調べた結果、窓口もトンネルもエンジンも生きていた。**声のファイルが106本中1本しか
無かった**のが原因。押すと、その場で作り始めて何分も黙る（＝壊れて見える）。

直し方は2つ。
 1) 出来ているものは **gh-pages に置く**。そうすれば窓口が落ちていても鳴る。
 2) 出来ていないものは一覧に「準備中」と正直に出す（押しても黙らない）。

この係は 1) と、一覧の元になる `status/public/zunda_notes.json` を書く。

置き場所：`share/zunda/<8桁>.mp3`（日本語ファイル名はURLで事故るので中身の名前は使わない）
"""
import hashlib
import io
import json
import os
import re
import shutil
import time

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "Desktop", "tamago-shinchoku")
VAULT = os.path.join(HOME, "Library", "Mobile Documents",
                     "iCloud~md~obsidian", "Documents", "tamago_brain")
AUDIO = os.path.join(VAULT, "AI出力", "40_プロジェクト", "円卓会議🔥", "音声")
PUB_DIR = os.path.join(REPO, "share", "zunda")
NOTES_CACHE = os.path.join(REPO, "status", "zunda", "notes.json")
OUT = os.path.join(REPO, "status", "public", "zunda_notes.json")
LOG = os.path.join(REPO, "status", "zunda", "kohyou.log")
BUDGET = 250 * 1024 * 1024          # 本番に置く合計の上限。太らせすぎない


def log(m):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), m))


def slug(title):
    s = re.sub(r"[\\/:*?\"<>|#\[\]]", "", title)[:60].strip()
    return s


def key_of(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]


def dir_size(p):
    n = 0
    for f in os.listdir(p) if os.path.isdir(p) else []:
        try:
            n += os.path.getsize(os.path.join(p, f))
        except Exception:
            pass
    return n


def main():
    os.makedirs(PUB_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    try:
        notes = json.load(io.open(NOTES_CACHE, encoding="utf-8"))
    except Exception:
        notes = []

    used = dir_size(PUB_DIR)
    rows, copied = [], 0
    for rel in notes:
        title = os.path.basename(rel)[:-3]
        src = os.path.join(AUDIO, "円卓音声_" + slug(title) + ".mp3")
        k = key_of(title)
        dst = os.path.join(PUB_DIR, k + ".mp3")
        have = os.path.exists(dst)
        if not have and os.path.exists(src):
            sz = os.path.getsize(src)
            if sz > 0 and used + sz <= BUDGET:
                shutil.copyfile(src, dst)
                used += sz
                copied += 1
                have = True
                log("本番へ置いた %s（%.1fMB）%s" % (k, sz / 1e6, title[:40]))
            elif used + sz > BUDGET:
                log("置き場の上限に達したので見送り: %s" % title[:40])
        rows.append({
            "title": title,
            "file": ("zunda/" + k + ".mp3") if have else None,
            "bytes": os.path.getsize(dst) if have else 0,
        })

    ready = sum(1 for r in rows if r["file"])
    json.dump({"notes": rows, "ready": ready, "total": len(rows),
               "usedMB": round(used / 1e6, 1),
               "at": time.strftime("%F %T")},
              io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    log("一覧を書いた：鳴らせる %d / %d 本（%.1fMB・今回 %d本追加）"
        % (ready, len(rows), used / 1e6, copied))
    print("鳴らせる %d / %d 本（今回 %d本追加）" % (ready, len(rows), copied))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
