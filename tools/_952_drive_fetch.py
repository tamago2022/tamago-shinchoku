#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""952番その2 — デザイン正本の画像（02/08）を工場(Mac)側で手元に落とす。

正本 docs/design/concierge-concept-02-08.md は「画像がデザイン正本」と言っている。
見ずに作ると「勝手なアレンジ」になる。だから先に見る。

経路は2つだけ。どちらも読むだけ。
  1. joy-relief-station の clone の中に既に置かれていないか探す
  2. Google Drive の公開リンク（uc?export=download）から落とす

落とし先は status/952_seihon/img/。share/ には置かない（公開の棚を汚さない）。
"""
import io
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "952_seihon", "img")

WANT = [
    ("02_shizukana_record.png", "1DpDan3A9m_QBovQToYuytImnnI_HHa6A"),
    ("08_salon.png", "1syfiUr7u2ki9BRRDhHHAIIPJuz36463P"),
]


def _drive(fid, dest, log):
    import urllib.request
    for url in ("https://drive.google.com/uc?export=download&id=" + fid,
                "https://drive.usercontent.google.com/download?id=%s&export=download" % fid):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff":
                io.open(dest, "wb").write(data)
                log.append("Drive から落とせました: %s (%d bytes)" % (os.path.basename(dest), len(data)))
                return True
            log.append("Drive が画像でないものを返しました（%d bytes・おそらく確認ページ）" % len(data))
        except Exception as e:
            log.append("Drive 失敗 %s: %s" % (url[:60], e))
    return False


def run_job(payload=None):
    log = []
    os.makedirs(OUT, exist_ok=True)
    got = []

    clone = os.path.expanduser("~/Desktop/joy-relief-station")
    if os.path.isdir(clone):
        try:
            r = subprocess.run(["git", "grep", "-l", "-i", "-e", "concept", "--", "*.png", "*.jpg"],
                               cwd=clone, capture_output=True, text=True, timeout=30)
            r2 = subprocess.run(["find", clone, "-maxdepth", "4", "-iname", "*_*.png",
                                 "-path", "*concept*"], capture_output=True, text=True, timeout=30)
            if r2.stdout.strip():
                log.append("clone 内の候補:\n" + r2.stdout.strip()[:1000])
        except Exception as e:
            log.append("clone 内の探索で例外: %s" % e)

    for name, fid in WANT:
        dest = os.path.join(OUT, name)
        if os.path.isfile(dest) and os.path.getsize(dest) > 10000:
            log.append("既にあります: %s" % name)
            got.append(dest)
            continue
        if _drive(fid, dest, log):
            got.append(dest)

    io.open(os.path.join(OUT, "_log.txt"), "w", encoding="utf-8").write(
        "%s\n\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), "\n".join(log)))
    return {"ok": bool(got), "got": got, "log": log, "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({}), ensure_ascii=False, indent=1))
