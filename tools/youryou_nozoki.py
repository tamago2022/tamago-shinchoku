#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量：いま何が動いていて、この3時間で何が増えたか（2026-10-12・見るだけ）。
status/youryou_nozoki.go がある時だけ1回。結果 status/youryou_nozoki.json"""
import json, os, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_nozoki.go")
OUT = os.path.join(REPO, "status", "youryou_nozoki.json")
SKIP = set(os.path.join(HOME, p) for p in [
    "Library/Containers", "Library/Group Containers", "Library/Mail", "Library/Messages", "Library/Safari",
    "Library/Calendars", "Library/Reminders", "Library/HomeKit", "Library/Cookies", "Library/Metadata",
    "Library/Suggestions", "Library/Biome", "Library/Accounts", "Library/IdentityServices",
    "Library/PersonalizationPortrait", "Library/Daemon Containers", "Library/Trial", "Library/Sharing",
    "Library/Mobile Documents", "Library/CloudStorage", "Downloads", "Pictures", "Music", "Movies", ".Trash",
    "Library/Application Support/AddressBook", "Library/Application Support/CallHistoryDB",
    "Library/Application Support/com.apple.TCC", "Library/Application Support/Knowledge",
    "Library/Application Support/MobileSync", "Library/Application Support/FileProvider",
    "Library/Autosave Information", "Library/Application Support/com.apple.sharedfilelist"])


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    res = {"at": time.strftime("%F %T")}
    r = subprocess.run(["ps", "-axo", "pid,ppid,etime,%cpu,rss,command"], capture_output=True, text=True)
    res["ps"] = [l[:220] for l in r.stdout.splitlines()
                 if any(k in l for k in ("rsync", "hakobu", "taihi", "git gc", "git ", "tar ", "bun ", "npm ",
                                         "ffmpeg", "yt-dlp", "youryou"))][:60]
    st = os.statvfs("/System/Volumes/Data")
    res["free_gb"] = round(st.f_bavail * st.f_frsize / 1e9, 2)
    r = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True)
    res["swap"] = r.stdout.strip()
    cut = time.time() - 3 * 3600
    grow = {}
    big = []
    stack = [HOME]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except Exception:
            continue
        with it:
            for e in it:
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir(follow_symlinks=False):
                        if e.path not in SKIP:
                            stack.append(e.path)
                        continue
                    s = e.stat(follow_symlinks=False)
                except Exception:
                    continue
                if s.st_mtime >= cut:
                    b = s.st_blocks * 512
                    parts = os.path.relpath(e.path, HOME).split(os.sep)
                    k = "~/" + "/".join(parts[:4][:-1] if len(parts) > 1 else parts)
                    grow[k] = grow.get(k, 0) + b
                    if b > 100 * 1048576:
                        big.append((b, e.path))
    res["new_in_3h_by_dir_gb"] = [{"dir": k, "gb": round(v / 1e9, 2)}
                                  for k, v in sorted(grow.items(), key=lambda x: -x[1])[:40] if v > 50e6]
    res["new_big_files"] = [{"p": p, "gb": round(b / 1e9, 2)} for b, p in sorted(big, reverse=True)[:30]]
    try:
        r = subprocess.run(["du", "-sk", "/Volumes/iMac HDD/Mac標準置き場/AI作業/2026-09-02/プロジェクト"],
                           capture_output=True, text=True, timeout=600)
        res["hdd_project_gb"] = round(int(r.stdout.split()[0]) / 1048576, 2)
    except Exception as ex:
        res["hdd_project_gb"] = str(ex)
    res["vm_files"] = sorted(os.listdir("/private/var/vm")) if os.path.isdir("/private/var/vm") else None
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
