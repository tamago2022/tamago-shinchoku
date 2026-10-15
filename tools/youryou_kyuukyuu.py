#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量の救急（2026-10-11・空き668MBの緊急対応）。

たまごさんの指示（2026-10-11）：「作り直せるものだけを消して、最低でも20GBを空ける」
  名指しの対象：~/Library/Caches・ms-playwright・yt-dlpの一時ファイル・pip/npm/Homebrewのキャッシュ・
  工場の一時ファイル・古いビルド成果物。
  触らない：壺と金庫・たまごさん本人のファイル・Obsidian Vault・~/Documents/AI作業 の完成品MP4。

Coworkのサンドボックスからは Mac の ~ に手が届かない（shellも容量不足で起動不能）ため、
心臓(heartbeat.sh)から1回だけ呼ばれる形にした。
  ・status/youryou_kyuukyuu.go がある時だけ動く（動き始めに自分で消す＝1回きり）
  ・許可ポップアップが出る場所（Containers・Group Containers・Downloads・Pictures・Music 等）には降りない
  ・sudo を使わない
結果：status/youryou_kyuukyuu.json（消したもの・測ったもの）／status/youryou_kyuukyuu.log
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_kyuukyuu.go")
LOCK = os.path.join(REPO, "status", ".youryou_kyuukyuu.lock")
OUT = os.path.join(REPO, "status", "youryou_kyuukyuu.json")
LOG = os.path.join(REPO, "status", "youryou_kyuukyuu.log")

# 許可ポップアップ（TCC）が出る／壺と金庫：測るのも降りない
NO_ENTER = [
    "Library/Containers", "Library/Group Containers", "Library/Mail", "Library/Messages",
    "Library/Safari", "Library/Calendars", "Library/Reminders", "Library/HomeKit",
    "Library/Cookies", "Library/Metadata", "Library/Suggestions", "Library/Biome",
    "Library/Accounts", "Library/IdentityServices", "Library/PersonalizationPortrait",
    "Library/Application Support/AddressBook", "Library/Application Support/CallHistoryDB",
    "Library/Application Support/com.apple.TCC", "Library/Application Support/Knowledge",
    "Library/Application Support/MobileSync", "Library/Application Support/FileProvider",
    "Library/Daemon Containers", "Library/Trial", "Library/Sharing",
    "Downloads", "Pictures", "Music", ".Trash",
]
NO_ENTER_ABS = [os.path.join(HOME, p) for p in NO_ENTER]

# 消さない（パスに含まれたら問答無用でスキップ）
FORBIDDEN = ("CloudStorage", "Eagle", "Vault", "tamago_brain", "iCloud", "Mobile Documents",
             "Google Drive", "Photos", ".dmg", "/kagi", "/.ssh", "/.gnupg", "Keychains")


def log(msg):
    line = "%s %s" % (time.strftime("%F %T"), msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def free_gb():
    for p in ("/System/Volumes/Data", "/"):
        try:
            st = os.statvfs(p)
            return round(st.f_bavail * st.f_frsize / 1e9, 2)
        except Exception:
            continue
    return None


def du_kb(path, timeout=240):
    if not os.path.exists(path):
        return None
    try:
        r = subprocess.run(["du", "-skx", path], capture_output=True, text=True, timeout=timeout)
        return int(r.stdout.split()[0])
    except Exception:
        return None


def gb(kb):
    return None if kb is None else round(kb / 1048576, 2)


def forbidden(path):
    return any(k in path for k in FORBIDDEN) or any(path.startswith(a) for a in NO_ENTER_ABS)


def rm(path, kind, deleted):
    if not os.path.lexists(path) or forbidden(path):
        return
    # 2026-10-12：消す前後に du を回すと負荷21のMacで1件数分かかったため、空きの差で測る（目安）
    before = free_gb() or 0
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
    except Exception as e:
        log("消せず %s (%s)" % (path, e))
        return
    freed_gb = max(0.0, round((free_gb() or 0) - before, 2))
    deleted.append({"path": path, "kind": kind, "gb": freed_gb})
    log("消した %.2fGB %s [%s]" % (freed_gb, path, kind))


def children(d):
    try:
        return [os.path.join(d, n) for n in os.listdir(d)]
    except Exception:
        return []


# ---------- ① すぐ消す（名指しされた・作り直せるもの） ----------
def sugu_kesu():
    deleted = []
    caches = os.path.join(HOME, "Library/Caches")
    for c in children(caches):
        name = os.path.basename(c)
        # com.apple.* はOS側。消しても戻るだけで効果が薄く、保護領域でエラーを出すので触らない
        if name.startswith("com.apple."):
            continue
        rm(c, "Library/Caches", deleted)
    for p, kind in [
        (os.path.join(HOME, ".npm/_cacache"), "npm cache"),
        (os.path.join(HOME, ".cache/pip"), "pip cache"),
        (os.path.join(HOME, ".cache/yt-dlp"), "yt-dlp cache"),
        (os.path.join(HOME, ".cache/ms-playwright"), "ms-playwright"),
        (os.path.join(HOME, ".cache/puppeteer"), "puppeteer browsers"),
        (os.path.join(HOME, ".bun/install/cache"), "bun cache"),
        (os.path.join(HOME, ".cache/uv"), "uv cache"),
        (os.path.join(HOME, "Library/pnpm/store"), "pnpm store"),
    ]:
        rm(p, kind, deleted)
    # yt-dlp の書きかけ：~ 配下は youryou_hakaru.py の1回走査で消す。ここでは /tmp だけ見る（軽い）
    now = time.time()
    roots = ["/private/tmp", os.environ.get("TMPDIR", "/tmp")]
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in (".git", "node_modules") and not forbidden(os.path.join(dp, d))]
            for fn in fns:
                low = fn.lower()
                if low.endswith((".part", ".ytdl", ".part-frag", ".temp")) or ".part-frag" in low \
                        or (".temp." in low and low.endswith((".mp4", ".m4a", ".webm", ".mkv"))):
                    fp = os.path.join(dp, fn)
                    try:
                        if now - os.path.getmtime(fp) > 3600:
                            rm(fp, "yt-dlp書きかけ", deleted)
                    except Exception:
                        pass
    # 古いビルド成果物・作業場の node_modules：工場の既存ルール（disk_guardian）をそのまま使う
    try:
        sys.path.insert(0, HERE)
        import disk_guardian
        fr = disk_guardian.cleanup()
        deleted.append({"path": "(disk_guardian.cleanup: 作業場の node_modules/dist/.output・古いログ等)",
                        "kind": "ビルド成果物", "gb": round(float(fr or 0), 2)})
    except Exception as e:
        log("disk_guardian.cleanup 失敗 %s" % e)
    return deleted


# ---------- ② 測る ----------
def hakaru():
    rows = []

    def add(path):
        if os.path.exists(path) and not any(path == a or path.startswith(a + "/") for a in NO_ENTER_ABS):
            k = du_kb(path)
            if k is not None:
                rows.append({"path": path, "gb": gb(k)})

    for d in [HOME, os.path.join(HOME, "Library"), os.path.join(HOME, "Library/Application Support"),
              os.path.join(HOME, "Library/Application Support/Claude"),
              os.path.join(HOME, "Library/Application Support/Claude/local-agent-mode-sessions"),
              os.path.join(HOME, ".tamago"), os.path.join(HOME, ".cache"), os.path.join(HOME, "howitholds"),
              os.path.join(HOME, "Documents"), os.path.join(HOME, "Documents/AI作業"),
              os.path.join(HOME, "Desktop"), os.path.join(HOME, "tamago"), os.path.join(HOME, ".claude"),
              os.path.join(HOME, "Movies")]:
        for c in children(d):
            if os.path.islink(c) or not os.path.isdir(c):
                continue
            if c in NO_ENTER_ABS or forbidden(c) and "Mobile Documents" not in c and "CloudStorage" not in c:
                continue
            add(c)
    # 壺と金庫は「合計だけ」測る（中には降りない）
    for p in ["Library/Mobile Documents", "Library/CloudStorage", ".Trash"]:
        k = du_kb(os.path.join(HOME, p))
        rows.append({"path": os.path.join(HOME, p), "gb": gb(k), "note": "合計だけ（中は触らない）"})
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda r: -(r["gb"] or 0)):
        if r["path"] in seen:
            continue
        seen.add(r["path"])
        uniq.append(r)
    return uniq[:80]


def saikin_ookii(days=14, min_mb=200):
    """この2週間に書かれた大きいファイル（原因探し）。"""
    cut = time.time() - days * 86400
    hits = []
    for root in [HOME]:
        for dp, dns, fns in os.walk(root):
            keep = []
            for d in dns:
                p = os.path.join(dp, d)
                if p in NO_ENTER_ABS or d in (".git",) or "Mobile Documents" in p or "CloudStorage" in p:
                    continue
                keep.append(d)
            dns[:] = keep
            for fn in fns:
                fp = os.path.join(dp, fn)
                try:
                    st = os.lstat(fp)
                except Exception:
                    continue
                if st.st_size >= min_mb * 1048576 and st.st_mtime >= cut:
                    hits.append((st.st_blocks * 512, st.st_mtime, fp))
    hits.sort(reverse=True)
    by_dir = {}
    for size, mt, fp in hits:
        rel = os.path.relpath(fp, HOME).split(os.sep)
        key = os.path.join(HOME, *rel[:3]) if len(rel) > 3 else os.path.dirname(fp)
        by_dir[key] = by_dir.get(key, 0) + size
    return ([{"path": fp, "gb": round(s / 1e9, 2), "mtime": time.strftime("%m-%d %H:%M", time.localtime(mt))}
             for s, mt, fp in hits[:60]],
            sorted([{"dir": k, "gb": round(v / 1e9, 2)} for k, v in by_dir.items()], key=lambda r: -r["gb"])[:40])


def sonota():
    o = {}
    for key, cmd in [("swap", ["sysctl", "vm.swapusage"]),
                     ("tm_snapshots", ["tmutil", "listlocalsnapshots", "/System/Volumes/Data"]),
                     ("df", ["df", "-h", "/System/Volumes/Data"])]:
        try:
            o[key] = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:
            o[key] = "未確認（%s）" % e
    try:
        o["vm_files"] = [{"f": c, "gb": round(os.path.getsize(c) / 1e9, 2)} for c in children("/private/var/vm")]
    except Exception as e:
        o["vm_files"] = "未確認（%s）" % e
    return o


def main():
    if not os.path.exists(GO):
        return
    if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 3600:
        return
    open(LOCK, "w").close()
    try:
        os.remove(GO)
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_before_gb": free_gb(), "state": "消している"}
    log("開始 空き %.2fGB" % (res["free_before_gb"] or -1))

    def save():
        with open(OUT + ".tmp", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        os.replace(OUT + ".tmp", OUT)

    save()
    res["deleted"] = sugu_kesu()
    res["free_after_delete_gb"] = free_gb()
    res["deleted_total_gb"] = round(sum((d.get("gb") or 0) for d in res["deleted"]), 2)
    log("消し終わり 空き %.2fGB" % (res["free_after_delete_gb"] or -1))
    # 2026-10-12：測る工程は tools/youryou_hakaru.py（~ を1回だけ歩く版）へ分けた。
    #   ここで du を何重にも回すと、負荷21のMacで何時間も終わらなかった。
    res["free_end_gb"] = free_gb()
    res["finished"] = time.strftime("%F %T")
    res["state"] = "完了"
    save()
    log("完了 空き %.2fGB" % (res["free_end_gb"] or -1))
    try:
        os.remove(LOCK)
    except Exception:
        pass


if __name__ == "__main__":
    main()
