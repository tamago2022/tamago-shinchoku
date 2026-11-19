#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vault をフォルダごと iCloud から落としてもらい（brctl download・非同期）、2分おきに20分、
本体に中身が無いファイルの数が減るかを数える（2026-10-14）。status/obsidian_modosu3.go → .json"""
import json, os, subprocess, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "obsidian_modosu3.go")
OUT = os.path.join(REPO, "status", "obsidian_modosu3.json")
VAULT = HOME + "/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"


def count():
    n = 0
    for dp, dns, fns in os.walk(VAULT):
        for fn in fns:
            try:
                if os.lstat(os.path.join(dp, fn)).st_flags & 0x40000000:
                    n += 1
            except Exception:
                pass
    return n


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "series": []}
    r = subprocess.run(["brctl", "download", VAULT], capture_output=True, text=True, timeout=600)
    res["brctl"] = [r.returncode, (r.stdout + r.stderr)[:300]]
    for dp, dns, fns in os.walk(VAULT):  # サブフォルダも頼む
        for d in dns:
            subprocess.run(["brctl", "download", os.path.join(dp, d)], capture_output=True, timeout=60)
    for i in range(11):
        res["series"].append({"t": time.strftime("%T"), "dataless": count(), "free_gb": free_gb()})
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        time.sleep(120)
    res["state"] = "完了"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
