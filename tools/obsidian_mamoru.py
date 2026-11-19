#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vault（tamago_brain）を本体に置いたままにする見張り（2026-10-14）。心臓から1時間おき。
実測：空きが0GB近くまで落ちた10/12〜13に、macOS が Vault 9,264個のうち 4,229個の中身を
本体から追い出した（iCloudにだけ残る状態）。Obsidian は開くたびに取りに行くため固まり、
索引づくりが50%から始まっていた。brctl download を頼むと iCloud が戻してくれる（実測：毎分約70個）。
・中身が無いファイルが1個でもあれば、空きが30GB以上のときだけ brctl download を頼む（設定は変えない）
・数を status/public/obsidian_mamoru.json に残す"""
import json, os, subprocess, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain")
OUT = os.path.join(REPO, "status", "public", "obsidian_mamoru.json")


def main():
    try:
        os.setsid()
    except Exception:
        pass
    n, dirs = 0, set()
    for dp, dns, fns in os.walk(VAULT):
        for fn in fns:
            try:
                if os.lstat(os.path.join(dp, fn)).st_flags & 0x40000000:
                    n += 1
                    dirs.add(dp)
            except Exception:
                pass
    st = os.statvfs("/System/Volumes/Data")
    free = st.f_bavail * st.f_frsize / 1e9
    asked = False
    if n and free >= 30:
        for d in sorted(dirs)[:500]:
            subprocess.run(["brctl", "download", d], capture_output=True, timeout=60)
        asked = True
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"at": time.strftime("%F %T"), "dataless": n, "free_gb": round(free, 2), "asked": asked},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
