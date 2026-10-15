#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量の犯人探し（2026-10-12・youryou_kyuukyuu.py の測る部分を1回の走査に縮めたもの）。

youryou_kyuukyuu.py は du を何度も重ねて回すため、負荷21のMacでは何時間もかかると分かった。
こちらは ~ を1回だけ歩いて、
  ・深さ4までのフォルダごとの合計
  ・この14日に書かれた200MB以上のファイル
を同時に数える。消さない（yt-dlpの書きかけ .part/.ytdl だけは、名指しの対象なので消す）。
許可ポップアップが出る場所（Containers・Group Containers・Downloads・Pictures・Music 等）には降りない。
status/youryou_hakaru.go がある時だけ1回動く。結果：status/youryou_hakaru.json（途中経過も書く）
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_hakaru.go")
LOCK = os.path.join(REPO, "status", ".youryou_hakaru.lock")
OUT = os.path.join(REPO, "status", "youryou_hakaru.json")
LOG = os.path.join(REPO, "status", "youryou_kyuukyuu.log")

NO_ENTER = set(os.path.join(HOME, p) for p in [
    "Library/Containers", "Library/Group Containers", "Library/Mail", "Library/Messages",
    "Library/Safari", "Library/Calendars", "Library/Reminders", "Library/HomeKit",
    "Library/Cookies", "Library/Metadata", "Library/Suggestions", "Library/Biome",
    "Library/Accounts", "Library/IdentityServices", "Library/PersonalizationPortrait",
    "Library/Application Support/AddressBook", "Library/Application Support/CallHistoryDB",
    "Library/Application Support/com.apple.TCC", "Library/Application Support/Knowledge",
    "Library/Application Support/MobileSync", "Library/Application Support/FileProvider",
    "Library/Daemon Containers", "Library/Trial", "Library/Sharing",
    "Library/Mobile Documents", "Library/CloudStorage",
    "Downloads", "Pictures", "Music", ".Trash",
])
PART_ROOTS = tuple(os.path.join(HOME, p) + "/" for p in (".tamago", "howitholds", "tamago"))
DEPTH = 4
RECENT = 14 * 86400
BIG = 200 * 1048576


def log(m):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [測る] %s\n" % (time.strftime("%F %T"), m))
    except Exception:
        pass


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
    # 先に走っていた重い版（du を何重にも回す）を止める。消す工程はもう終わっている。
    try:
        subprocess.run(["pkill", "-f", "tools/youryou_kyuukyuu.py"], timeout=10)
        os.remove(os.path.join(REPO, "status", ".youryou_kyuukyuu.lock"))
    except Exception:
        pass
    log("開始 空き %s GB" % free_gb())
    now = time.time()
    sizes = {}
    recent = []
    parts_freed = 0
    parts = []
    res = {"started": time.strftime("%F %T"), "state": "測っている", "free_gb_start": free_gb()}
    save(res)
    last_save = time.time()
    nfiles = 0
    hl = len(HOME.rstrip("/").split("/"))
    stack = [HOME]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except Exception:
            continue
        with it:
            for e in it:
                p = e.path
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir(follow_symlinks=False):
                        if p in NO_ENTER or e.name == ".git" and False:
                            continue
                        stack.append(p)
                        continue
                    st = e.stat(follow_symlinks=False)
                except Exception:
                    continue
                nfiles += 1
                b = st.st_blocks * 512
                # yt-dlp の書きかけ（1時間以上前）だけは消す
                low = e.name.lower()
                if p.startswith(PART_ROOTS) and (low.endswith((".part", ".ytdl")) or ".part-frag" in low) \
                        and now - st.st_mtime > 3600:
                    try:
                        os.remove(p)
                        parts_freed += b
                        parts.append(p)
                        continue
                    except Exception:
                        pass
                comps = p.split("/")[hl:-1]
                for i in range(0, min(DEPTH, len(comps)) + 1):
                    k = "/".join(comps[:i])
                    sizes[k] = sizes.get(k, 0) + b
                if b >= BIG and st.st_mtime >= now - RECENT:
                    recent.append((b, st.st_mtime, p))
        if time.time() - last_save > 120:
            last_save = time.time()
            res.update(progress_files=nfiles, progress_dir=d,
                       top_now=[{"path": "~/" + k, "gb": round(v / 1e9, 2)}
                                for k, v in sorted(sizes.items(), key=lambda x: -x[1])[:40]])
            save(res)
    recent.sort(reverse=True)
    by_dir = {}
    for b, mt, p in recent:
        k = "/".join(p.split("/")[:hl + 3])
        by_dir[k] = by_dir.get(k, 0) + b
    other = {}
    for key, cmd in [("swap", ["sysctl", "vm.swapusage"]),
                     ("tm_snapshots", ["tmutil", "listlocalsnapshots", "/System/Volumes/Data"]),
                     ("df", ["df", "-h", "/System/Volumes/Data"])]:
        try:
            other[key] = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception as ex:
            other[key] = "未確認（%s）" % ex
    for key, p in [("Mobile Documents", "Library/Mobile Documents"), ("CloudStorage", "Library/CloudStorage")]:
        try:
            r = subprocess.run(["du", "-skx", os.path.join(HOME, p)], capture_output=True, text=True, timeout=600)
            other[key + "_gb"] = round(int(r.stdout.split()[0]) / 1048576, 2)
        except Exception as ex:
            other[key + "_gb"] = "未確認（%s）" % ex
    res.update(
        state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb(), files=nfiles,
        ytdlp_part_deleted_gb=round(parts_freed / 1e9, 2), ytdlp_part_deleted=parts[:50],
        dirs=[{"path": "~/" + k, "depth": (k.count("/") + 1 if k else 0), "gb": round(v / 1e9, 2)}
              for k, v in sorted(sizes.items(), key=lambda x: -x[1]) if v >= 1e9][:200],
        recent_big_files=[{"path": p, "gb": round(b / 1e9, 2),
                           "mtime": time.strftime("%m-%d %H:%M", time.localtime(mt))} for b, mt, p in recent[:80]],
        recent_by_dir=sorted([{"dir": k, "gb": round(v / 1e9, 2)} for k, v in by_dir.items()],
                             key=lambda r: -r["gb"])[:40],
        other=other)
    res.pop("top_now", None)
    save(res)
    log("完了 空き %s GB / %d files" % (free_gb(), nfiles))
    try:
        os.remove(LOCK)
    except Exception:
        pass


if __name__ == "__main__":
    main()
