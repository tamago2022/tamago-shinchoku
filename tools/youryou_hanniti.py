#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""この半日で何が増えたか＋作り直せるものを消す（2026-10-14・空き40→15GB）。
status/youryou_hanniti.go → status/youryou_hanniti.json。許可ポップアップの出る場所には降りない。"""
import glob, json, os, shutil, subprocess, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_hanniti.go")
OUT = os.path.join(REPO, "status", "youryou_hanniti.json")
AS = HOME + "/Library/Application Support"
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


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def du(p):
    try:
        r = subprocess.run(["du", "-skx", p], capture_output=True, text=True, timeout=900)
        return round(int(r.stdout.split()[0]) / 1048576, 2)
    except Exception:
        return None


def save(res):
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)


def rm(p):
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.lexists(p):
        try:
            os.remove(p)
        except Exception:
            pass


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_gb_start": free_gb(), "state": "測っている"}
    res["swap"] = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True).stdout.strip()
    sizes = {}
    for k, p in {"iCloud送信待ち session/t": AS + "/CloudDocs/session/t", "iCloud CloudDocs全体": AS + "/CloudDocs",
                 "Googleドライブ DriveFS": AS + "/Google/DriveFS", "Claude仮想マシン": AS + "/Claude/vm_bundles",
                 "Claude全体": AS + "/Claude", "Spotify": AS + "/Spotify", "Spotifyキャッシュ": HOME + "/Library/Caches/com.spotify.client",
                 "~/Library/Caches": HOME + "/Library/Caches", "Claude会話ログ ~/.claude": HOME + "/.claude",
                 "工場 status": REPO + "/status", "工場 .git": REPO + "/.git", "AI作業": HOME + "/Documents/AI作業",
                 "~/.tamago": HOME + "/.tamago", "Obsidianアプリ": AS + "/obsidian",
                 "Vault（中身がある分）": HOME + "/Library/Mobile Documents/iCloud~md~obsidian"}.items():
        sizes[k] = du(p)
        res["sizes_gb"] = sizes
        save(res)
    try:
        res["vm_bundle_files"] = {os.path.basename(p): round(os.lstat(p).st_blocks * 512 / 1e9, 2)
                                  for p in glob.glob(AS + "/Claude/vm_bundles/*/*")}
    except Exception:
        pass
    # この12時間に書かれたもの
    cut = time.time() - 12 * 3600
    grow, big = {}, []
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
                    k = "/".join(e.path.split("/")[:7])
                    grow[k] = grow.get(k, 0) + b
                    if b > 100e6:
                        big.append((b, e.path, time.strftime("%H:%M", time.localtime(s.st_mtime))))
    res["new_12h_by_dir_gb"] = [{"d": k, "gb": round(v / 1e9, 2)} for k, v in sorted(grow.items(), key=lambda x: -x[1])[:30]]
    res["new_12h_big"] = [{"p": p, "gb": round(b / 1e9, 2), "t": t} for b, p, t in sorted(big, reverse=True)[:30]]
    res["state"] = "消している"
    save(res)
    # 作り直せるものだけ消す
    b0 = free_gb()
    for c in glob.glob(HOME + "/Library/Caches/*"):
        if not os.path.basename(c).startswith("com.apple."):
            rm(c)
    for p in (HOME + "/.npm/_cacache", HOME + "/.npm/_npx", HOME + "/.bun/install/cache",
              AS + "/Spotify/PersistentCache", AS + "/Google/GoogleUpdater/crx_cache",
              AS + "/discord/Cache", AS + "/Notion/Partitions/notion/Cache",
              AS + "/Notion/Partitions/notion/Service Worker/CacheStorage"):
        rm(p)
    for p in glob.glob(REPO + "/.git/objects/pack/tmp_*") + glob.glob(HOME + "/Desktop/joy-relief-station/.git/objects/pack/tmp_*"):
        try:
            if time.time() - os.path.getmtime(p) > 3600:
                rm(p)
        except Exception:
            pass
    res["deleted_gb"] = round(free_gb() - b0, 2)
    res.update(state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb())
    save(res)


if __name__ == "__main__":
    main()
