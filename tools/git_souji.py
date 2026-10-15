#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""git の後片付け（2026-10-14・容量事故の再発防止）。心臓から1時間おき。

実測（2026-10-14）：工場の git が自動gcを始めては心臓のタイムアウト(45/120秒)で途中で打ち切られ、
  書きかけパック(tmp_pack_*／tmp_idx_*)を126個・0.73GB、さらに2GB級のパックを何度も書き直していた
  （この90分で tamago-shinchoku/.git だけ +2.1GB）。1時間に約2GBずつ空きが減っていた主因の1つ。
やること：
  ・1時間おき：2時間以上前の書きかけパックを消す（gcが生きていれば2時間も放置されない）
  ・自動gcは止める（gc.auto=0。youryou_kyuukyuu5.py で設定済み。外れていたら付け直す）
  ・1日1回：git gc を自分のセッションで最後まで走らせる（途中で殺されない＝書きかけを残さない）
"""
import glob, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
REPOS = [REPO, HOME + "/Desktop/joy-relief-station"]
STAMP = os.path.join(REPO, "status", ".git_souji_gc_at")
LOG = os.path.join(REPO, "status", "youryou_kyuukyuu.log")


def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s [git片付け] %s\n" % (time.strftime("%F %T"), m))


def main():
    try:
        os.setsid()
    except Exception:
        pass
    n, b = 0, 0
    for r in REPOS + glob.glob(HOME + "/tamago/*"):
        for p in glob.glob(os.path.join(r, ".git", "objects", "pack", "tmp_*")):
            try:
                if time.time() - os.path.getmtime(p) > 7200:
                    b += os.lstat(p).st_blocks * 512
                    os.remove(p)
                    n += 1
            except Exception:
                pass
    if n:
        log("書きかけパック %d個（%.2fGB）を消した" % (n, b / 1e9))
    for r in REPOS:
        try:
            v = subprocess.run(["git", "config", "--get", "gc.auto"], cwd=r, capture_output=True, text=True,
                               timeout=20).stdout.strip()
            if v != "0":
                subprocess.run(["git", "config", "gc.auto", "0"], cwd=r, timeout=20)
                log("%s の自動gcを止め直した" % os.path.basename(r))
        except Exception:
            pass
    try:
        last = os.path.getmtime(STAMP)
    except Exception:
        last = 0
    if time.time() - last > 20 * 3600:
        open(STAMP, "w").close()
        for r in REPOS:
            t = time.time()
            try:
                os.remove(os.path.join(r, ".git", "gc.log"))  # 前回の警告で止まらないように
            except Exception:
                pass
            rc = subprocess.run(["git", "gc", "--quiet", "--prune=1.day.ago"], cwd=r, capture_output=True, timeout=3 * 3600).returncode
            log("%s git gc rc=%s（%d秒）" % (os.path.basename(r), rc, time.time() - t))


if __name__ == "__main__":
    import fcntl
    lf = open(os.path.join(REPO, "status", ".git_souji.lock"), "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        sys.exit(0)
    main()
