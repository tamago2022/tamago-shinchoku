#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tamago-shinchoku の git を縮める（2026-10-14）。status/youryou_gc7.go → status/youryou_gc7.json
実測：.git/gc.log に「unreachable loose objects が多すぎる」。打ち切られ続けた自動gcが、
到達できない古いオブジェクトをパックからばらして書き出し続けていた（＝空きが毎時減る）。
1日より古い到達不能オブジェクトだけ消す（走行中の工場が今まさに作ったものは残る）。"""
import json, os, subprocess, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(REPO, "status", "youryou_gc7.go")
OUT = os.path.join(REPO, "status", "youryou_gc7.json")


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def sh(cmd, t):
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=t)
        return r.returncode, (r.stdout or "").strip()[-1500:], (r.stderr or "").strip()[-500:]
    except Exception as e:
        return -1, "", str(e)


def save(res):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_gb_start": free_gb(), "state": "作業中"}
    res["ps_git"] = [l[:200] for l in subprocess.run(["ps", "-axo", "pid,etime,command"], capture_output=True,
                                                    text=True).stdout.splitlines()
                     if "git" in l and ("gc" in l or "repack" in l or "prune" in l or "pack-objects" in l)]
    res["before"] = sh(["git", "count-objects", "-vH"], 600)[1]
    save(res)
    try:
        os.remove(os.path.join(REPO, ".git", "gc.log"))
    except Exception:
        pass
    res["gc"] = sh(["git", "gc", "--prune=1.day.ago"], 4 * 3600)
    res["after"] = sh(["git", "count-objects", "-vH"], 600)[1]
    res.update(state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb())
    save(res)


if __name__ == "__main__":
    main()
