#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量の犯人探し・第3版（2026-10-12）。

第2版（youryou_hakaru.py：pythonで ~ を1回歩く）は60万ファイルを過ぎたところで
25分以上進まなくなった（どのフォルダで固まったか外から見えない作りだった）。
第3版は「上のフォルダ1つずつ」を du / find（C製で速い）の子プロセスに任せ、
1つにつき上限時間を付ける。固まったものは「未確認（時間切れ）」と書いて次へ進む。
  ・消さない。測るだけ。
  ・許可ポップアップが出る場所（Containers・Group Containers・Downloads・Pictures・Music 等）は測らない
status/youryou_hakaru2.go がある時だけ1回動く。結果：status/youryou_hakaru2.json（1つ測るごとに書く）
"""
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_hakaru2.go")
LOCK = os.path.join(REPO, "status", ".youryou_hakaru2.lock")
OUT = os.path.join(REPO, "status", "youryou_hakaru2.json")

NO_ENTER = set(os.path.join(HOME, p) for p in [
    "Library/Containers", "Library/Group Containers", "Library/Mail", "Library/Messages",
    "Library/Safari", "Library/Calendars", "Library/Reminders", "Library/HomeKit",
    "Library/Cookies", "Library/Metadata", "Library/Suggestions", "Library/Biome",
    "Library/Accounts", "Library/IdentityServices", "Library/PersonalizationPortrait",
    "Library/Daemon Containers", "Library/Trial", "Library/Sharing", "Library/Autosave Information",
    "Library/Application Support/AddressBook", "Library/Application Support/CallHistoryDB",
    "Library/Application Support/com.apple.TCC", "Library/Application Support/Knowledge",
    "Library/Application Support/MobileSync", "Library/Application Support/FileProvider",
    "Library/Application Support/com.apple.sharedfilelist",
    "Library/Mobile Documents", "Library/CloudStorage",
    "Downloads", "Pictures", "Music", "Movies", ".Trash", "Library", "Library/Application Support",
])
# 中身ごとではなく「合計だけ」測る（壺と金庫）
SUM_ONLY = [os.path.join(HOME, p) for p in ("Library/Mobile Documents", "Library/CloudStorage", ".Trash")]


def free_gb():
    try:
        st = os.statvfs("/System/Volumes/Data")
        return round(st.f_bavail * st.f_frsize / 1e9, 2)
    except Exception:
        return None


def save(res):
    try:
        with open(OUT + ".tmp", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        os.replace(OUT + ".tmp", OUT)
    except Exception:
        pass


def kids(d):
    try:
        return sorted(os.path.join(d, n) for n in os.listdir(d))
    except Exception:
        return []


def du_tree(path, depth, timeout):
    """du -xk -d depth。戻り：[(kb, path)] or None(時間切れ)"""
    try:
        r = subprocess.run(["du", "-xk", "-d", str(depth), path], capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    rows = []
    for line in r.stdout.splitlines():
        try:
            kb, p = line.split("\t", 1)
            rows.append((int(kb), p))
        except Exception:
            pass
    return rows


def find_recent(path, timeout):
    try:
        r = subprocess.run(["find", "-x", path, "-type", "f", "-size", "+400000", "-mtime", "-14",
                            "-not", "-path", "*/.git/*"],
                           capture_output=True, text=True, timeout=timeout)  # +400000ブロック≒200MB
    except subprocess.TimeoutExpired:
        return None
    out = []
    for p in r.stdout.splitlines():
        try:
            st = os.lstat(p)
            out.append({"path": p, "gb": round(st.st_blocks * 512 / 1e9, 2),
                        "mtime": time.strftime("%m-%d %H:%M", time.localtime(st.st_mtime))})
        except Exception:
            pass
    return out


def main():
    if not os.path.exists(GO):
        return
    if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 3 * 3600:
        return
    open(LOCK, "w").close()
    try:
        os.remove(GO)
    except Exception:
        pass
    try:
        subprocess.run(["pkill", "-f", "tools/youryou_hakaru.py"], timeout=10)
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "state": "測っている", "free_gb_start": free_gb(),
           "dirs": [], "timeout": [], "recent_big_files": []}
    save(res)
    targets = []
    for base in (HOME, os.path.join(HOME, "Library"), os.path.join(HOME, "Library/Application Support")):
        for c in kids(base):
            if c in NO_ENTER or os.path.islink(c) or not os.path.isdir(c):
                continue
            targets.append(c)
    for c in targets:
        res["now"] = c
        save(res)
        rows = du_tree(c, 2, 900)
        if rows is None:
            res["timeout"].append(c)
        else:
            for kb, p in rows:
                if kb >= 300 * 1024:
                    res["dirs"].append({"path": p.replace(HOME, "~", 1), "gb": round(kb / 1048576, 2)})
        rec = find_recent(c, 600)
        if rec is None:
            res["timeout"].append("find:" + c)
        else:
            res["recent_big_files"].extend(rec)
        res["dirs"].sort(key=lambda r: -r["gb"])
        res["recent_big_files"].sort(key=lambda r: -r["gb"])
    for p in SUM_ONLY:
        rows = du_tree(p, 0, 900)
        res["dirs"].append({"path": p.replace(HOME, "~", 1), "gb": round(rows[0][0] / 1048576, 2) if rows else None,
                            "note": "合計だけ（中は触らない）"})
    other = {}
    for key, cmd in [("swap", ["sysctl", "vm.swapusage"]),
                     ("tm_snapshots", ["tmutil", "listlocalsnapshots", "/System/Volumes/Data"]),
                     ("df", ["df", "-h", "/System/Volumes/Data"])]:
        try:
            other[key] = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception as ex:
            other[key] = "未確認（%s）" % ex
    try:
        other["vm_files_gb"] = round(sum(os.path.getsize(p) for p in kids("/private/var/vm")
                                         if os.path.isfile(p)) / 1e9, 2)
    except Exception as ex:
        other["vm_files_gb"] = "未確認（%s）" % ex
    res["dirs"].sort(key=lambda r: -(r["gb"] or 0))
    res.update(state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb(), other=other)
    res.pop("now", None)
    save(res)
    try:
        os.remove(LOCK)
    except Exception:
        pass


if __name__ == "__main__":
    main()
