#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""queue.json の控え箱（status/_1142_gomi/）を太らせない係（2026-10-12・空き668MB事故の主犯）。

実測（2026-10-12）：1142_fukkyuu.py が「触る前に控え」として queue.json（約10MB）を
毎回まるごと _1142_gomi/ へコピーし、上限も片付けも無かったため、1,047個・約10.8GBに太っていた。

やること（消さずに縮める＝中身は1バイトも失わない）：
  ・新しい20個はそのまま残す（すぐ戻せる）
  ・それより古い queue.json.bak-* / *.EMPTY-* / *.tmp.* は gzip で圧縮（JSONは約1/10になる）
  ・圧縮済み(.gz)が30日を超えたものだけ消す（2026-10-12 たまごさん指示「原因の処理に後片付けを付ける」）
1142_fukkyuu.py が控えを取った直後に呼ぶ＋心臓から1時間に1回。
"""
import glob
import gzip
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BOX = os.path.join(REPO, "status", "_1142_gomi")
KEEP_RAW = 20
GZ_DAYS = 30
LOG = os.path.join(REPO, "status", "youryou_kyuukyuu.log")


def log(m):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [控え箱] %s\n" % (time.strftime("%F %T"), m))
    except Exception:
        pass


def run(max_files=None):
    if not os.path.isdir(BOX):
        return 0
    raw = [p for p in glob.glob(os.path.join(BOX, "*")) if not p.endswith(".gz") and os.path.isfile(p)]
    raw.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    saved = 0
    done = 0
    for p in raw[KEEP_RAW:]:
        if max_files and done >= max_files:
            break
        try:
            before = os.path.getsize(p)
            st = os.stat(p)
            with open(p, "rb") as fi, gzip.open(p + ".gz.tmp", "wb", compresslevel=6) as fo:
                shutil.copyfileobj(fi, fo, 1 << 20)
            os.utime(p + ".gz.tmp", (st.st_atime, st.st_mtime))
            os.replace(p + ".gz.tmp", p + ".gz")
            os.remove(p)
            saved += before - os.path.getsize(p + ".gz")
            done += 1
        except Exception as e:
            try:
                os.remove(p + ".gz.tmp")
            except Exception:
                pass
            log("圧縮できず %s (%s)" % (os.path.basename(p), e))
            if "No space" in str(e):
                break
    # 2026-10-12 たまごさん「溜まるものはiMac HDDへ。本体には溜めない」→ 圧縮済みはHDDへ移す
    moved = 0
    try:
        sys.path.insert(0, HERE)
        import hdd_okiba
        if hdd_okiba.ok():
            d = hdd_okiba.dest("控え", "_1142_gomi")
            for p in glob.glob(os.path.join(BOX, "*.gz")):
                try:
                    shutil.move(p, os.path.join(d, os.path.basename(p)))
                    moved += 1
                except Exception:
                    pass
    except Exception:
        pass
    if moved:
        log("圧縮済み %d個を iMac HDD（Mac標準置き場/控え/_1142_gomi）へ移した" % moved)
    old = 0
    cut = time.time() - GZ_DAYS * 86400
    for p in glob.glob(os.path.join(BOX, "*.gz")):
        try:
            if os.path.getmtime(p) < cut:
                os.remove(p)
                old += 1
        except Exception:
            pass
    if done or old:
        log("圧縮 %d個（%.2fGB縮んだ）／30日超の圧縮済みを %d個消した" % (done, saved / 1e9, old))
    return saved


def run_locked(max_files=None):
    import fcntl
    try:
        lf = open(os.path.join(REPO, "status", ".gomi_assyuku.lock"), "w")
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        return 0  # 誰かが圧縮中
    try:
        return run(max_files)
    finally:
        try:
            fcntl.flock(lf, fcntl.LOCK_UN)
        except Exception:
            pass


if __name__ == "__main__":
    run_locked()
