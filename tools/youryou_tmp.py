#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""/private/tmp と自分用一時領域(TMPDIR)の中身を大きい順に（2026-10-14・見るだけ）。status/youryou_tmp.go → .json"""
import json, os, subprocess, tempfile, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(REPO, "status", "youryou_tmp.go")
OUT = os.path.join(REPO, "status", "youryou_tmp.json")


def kids(d, n=40):
    rows = []
    try:
        names = os.listdir(d)
    except Exception as e:
        return [str(e)]
    for name in names:
        p = os.path.join(d, name)
        if os.path.islink(p):
            continue
        try:
            r = subprocess.run(["du", "-skx", p], capture_output=True, text=True, timeout=600)
            kb = int(r.stdout.split()[0])
        except Exception:
            continue
        try:
            mt = os.path.getmtime(p)
        except Exception:
            mt = 0
        git = os.path.isdir(os.path.join(p, ".git"))
        rows.append((kb, p, time.strftime("%m-%d %H:%M", time.localtime(mt)), git))
    rows.sort(reverse=True)
    return [{"p": p, "gb": round(kb / 1048576, 2), "mtime": m, "git": g} for kb, p, m, g in rows[:n]]


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    tmp = tempfile.gettempdir()
    res = {"at": time.strftime("%F %T")}
    res["private_tmp"] = kids("/private/tmp", 60)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    res["T"] = kids(tmp, 30)
    res["C"] = kids(os.path.join(os.path.dirname(tmp), "C"), 15)
    res["state"] = "完了"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
