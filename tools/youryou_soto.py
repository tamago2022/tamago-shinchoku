#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ホームの外・一時領域で何が増えたか（2026-10-14・見るだけ）。status/youryou_soto.go → .json"""
import json, os, subprocess, tempfile, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_soto.go")
OUT = os.path.join(REPO, "status", "youryou_soto.json")


def sh(cmd, t=900):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        return r.stdout.strip()
    except Exception as e:
        return "未確認 %s" % e


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    tmp = tempfile.gettempdir()           # /var/folders/xx/yyy/T
    user_vf = os.path.dirname(tmp)        # /var/folders/xx/yyy （C・T・0 を含む）
    res = {"at": time.strftime("%F %T"), "tmpdir": tmp}
    res["df"] = sh(["df", "-h", "/System/Volumes/Data"])
    res["snapshots"] = sh(["tmutil", "listlocalsnapshots", "/System/Volumes/Data"])
    res["purgeable"] = [l.strip() for l in sh(["diskutil", "info", "/System/Volumes/Data"]).splitlines()
                        if "Free" in l or "Purgeable" in l or "Used" in l]
    res["du"] = {}
    for p in [user_vf, tmp, "/private/tmp", HOME + "/Movies", "/Users/Shared",
              "/Library/Caches", "/private/var/vm", "/private/var/log"]:
        res["du"][p] = sh(["du", "-sh", p]).split("\t")[0]
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    res["du_vf_children"] = sh(["/bin/sh", "-c", 'du -sk "$1"/* "$1"/T/* 2>/dev/null | sort -rn | head -25',
                                "x", user_vf]).splitlines()
    res["big_recent_tmp"] = sh(["find", "-x", user_vf, "/private/tmp", HOME + "/Movies",
                                "-type", "f", "-size", "+200000", "-mmin", "-900"]).splitlines()[:40]
    res["state"] = "完了"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
