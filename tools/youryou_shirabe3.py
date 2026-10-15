#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量復旧・第3便の下調べ（2026-10-12）。消さない・動かさない。測って書くだけ。
status/youryou_shirabe3.go がある時だけ1回。結果 status/youryou_shirabe3.json
"""
import json, os, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_shirabe3.go")
OUT = os.path.join(REPO, "status", "youryou_shirabe3.json")
HDD = "/Volumes/iMac HDD"
WTB = HOME + "/Documents/AI作業/.worktrees"
AIW = HOME + "/Documents/AI作業"
MEDIA = (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".wav", ".mp3", ".m4a", ".aac", ".flac",
         ".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".psd", ".tif", ".tiff", ".zip", ".prproj")


def sh(cmd, t=120, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t, cwd=cwd)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()[:300]
    except Exception as e:
        return -1, "", str(e)[:300]


def free_gb(p="/System/Volumes/Data"):
    try:
        st = os.statvfs(p)
        return round(st.f_bavail * st.f_frsize / 1e9, 2)
    except Exception:
        return None


def du_gb(p, t=600):
    rc, o, e = sh(["du", "-skx", p], t)
    try:
        return round(int(o.split()[0]) / 1048576, 3)
    except Exception:
        return None


def save(res):
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    res = {"started": time.strftime("%F %T"), "free_gb": free_gb(), "state": "調べている"}
    # HDD
    h = {"mounted": os.path.isdir(HDD)}
    if h["mounted"]:
        rc, o, e = sh(["diskutil", "info", HDD], 60)
        h["diskutil"] = [l.strip() for l in o.splitlines()
                         if any(k in l for k in ("File System Personality", "Type (Bundle)", "Volume Free Space",
                                                  "Container Free Space", "Disk Size", "Read-Only Volume",
                                                  "Owners", "Protocol", "Solid State", "Device Location"))]
        h["free_gb"] = free_gb(HDD)
        try:
            t = os.path.join(HDD, "Mac標準置き場", ".kakikomi_test")
            os.makedirs(os.path.dirname(t), exist_ok=True)
            open(t, "w").write("ok")
            os.remove(t)
            h["writable"] = True
        except Exception as ex:
            h["writable"] = "NG %s" % ex
        try:
            h["top"] = sorted(os.listdir(os.path.join(HDD, "Mac標準置き場")))[:50]
        except Exception as ex:
            h["top"] = str(ex)
    res["hdd"] = h
    save(res)
    # iCloud（設定・ファイルには触らない。見るだけ）
    ic = {}
    for name in ("Documents", "Desktop"):
        p = os.path.join(HOME, name)
        ic[name] = {"islink": os.path.islink(p), "realpath": os.path.realpath(p)}
        rc, o, e = sh(["xattr", p], 20)
        ic[name]["xattr"] = o.splitlines()
    cd = HOME + "/Library/Mobile Documents/com~apple~CloudDocs"
    for name in ("Documents", "Desktop"):
        q = os.path.join(cd, name)
        ic["CloudDocs/" + name] = {"exists": os.path.lexists(q), "islink": os.path.islink(q),
                                   "realpath": os.path.realpath(q) if os.path.lexists(q) else None}
    for key in ("FXICloudDriveDesktop", "FXICloudDriveDocuments", "FXICloudDriveEnabled"):
        rc, o, e = sh(["defaults", "read", "com.apple.finder", key], 20)
        ic["finder." + key] = o if rc == 0 else "（無し）"
    # session/t の中身（名前・大きさ・時刻だけ）
    t = HOME + "/Library/Application Support/CloudDocs/session/t"
    files, ext, n, tot = [], {}, 0, 0
    for dp, dns, fns in os.walk(t):
        for fn in fns:
            fp = os.path.join(dp, fn)
            try:
                st = os.lstat(fp)
            except Exception:
                continue
            n += 1
            b = st.st_blocks * 512
            tot += b
            x = os.path.splitext(fn)[1].lower() or "(なし)"
            ext[x] = ext.get(x, 0) + b
            files.append((b, st.st_mtime, fp))
    files.sort(reverse=True)
    ic["session_t"] = {"files": n, "gb": round(tot / 1e9, 2),
                       "by_ext_gb": {k: round(v / 1e9, 2) for k, v in sorted(ext.items(), key=lambda x: -x[1])[:15]},
                       "top": [{"p": p.replace(t, "t"), "gb": round(b / 1e9, 3),
                                "mtime": time.strftime("%m-%d %H:%M", time.localtime(m))} for b, m, p in files[:40]],
                       "oldest": time.strftime("%m-%d %H:%M", time.localtime(min(f[1] for f in files))) if files else None}
    rc, o, e = sh(["brctl", "quota"], 30)
    ic["brctl_quota"] = o or e
    res["icloud"] = ic
    save(res)
    # 作業場の仕分け（見るだけ）
    wts = []
    now = time.time()
    for name in sorted(os.listdir(WTB)) if os.path.isdir(WTB) else []:
        p = os.path.join(WTB, name)
        if not os.path.isdir(p) or os.path.islink(p):
            continue
        w = {"name": name, "age_h": round((now - os.path.getmtime(p)) / 3600, 1)}
        if not os.path.exists(os.path.join(p, ".git")):
            w["git"] = False
        else:
            rc, o, e = sh(["git", "status", "--porcelain", "--untracked-files=normal"], 60, p)
            w["dirty"] = None if rc != 0 else len([l for l in o.splitlines() if l.strip()])
            rc, o, e = sh(["git", "branch", "-r", "--contains", "HEAD"], 60, p)
            w["pushed"] = (rc == 0 and bool(o.strip()))
            rc, o, e = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], 20, p)
            w["branch"] = o
        w["gb"] = du_gb(p, 300)
        wts.append(w)
    res["worktrees"] = wts
    res["worktrees_sum"] = {
        "count": len(wts), "gb": round(sum(w.get("gb") or 0 for w in wts), 2),
        "clean_pushed": sum(1 for w in wts if w.get("dirty") == 0 and w.get("pushed")),
        "clean_pushed_gb": round(sum(w.get("gb") or 0 for w in wts if w.get("dirty") == 0 and w.get("pushed")), 2)}
    save(res)
    # AI作業 の大きい動画・画像（.worktrees とgitリポジトリの中は除く）
    big, by_top = [], {}
    for dp, dns, fns in os.walk(AIW):
        if ".git" in dns or ".git" in fns:
            dns[:] = []
            continue
        dns[:] = [d for d in dns if d not in (".worktrees", "node_modules")]
        for fn in fns:
            if not fn.lower().endswith(MEDIA):
                continue
            fp = os.path.join(dp, fn)
            try:
                b = os.lstat(fp).st_blocks * 512
            except Exception:
                continue
            top = os.path.relpath(fp, AIW).split(os.sep)[0]
            by_top[top] = by_top.get(top, 0) + b
            if b >= 50 * 1048576:
                big.append((b, fp))
    big.sort(reverse=True)
    res["aiw_media_by_top_gb"] = {k: round(v / 1e9, 2) for k, v in sorted(by_top.items(), key=lambda x: -x[1])[:30]}
    res["aiw_media_big"] = [{"p": p.replace(HOME, "~"), "gb": round(b / 1e9, 2)} for b, p in big[:30]]
    res["sizes"] = {k: du_gb(v) for k, v in {
        "trash": HOME + "/.Trash", "howitholds_build": HOME + "/howitholds/ep01/_build",
        "aiw_2026-09-02_project": AIW + "/2026-09-02/プロジェクト", "aiw": AIW,
        "shinchoku_git": REPO + "/.git"}.items()}
    rc, o, e = sh(["tmutil", "listlocalsnapshotdates", "/"], 60)
    res["tm"] = o or e
    res["state"] = "完了"
    res["finished"] = time.strftime("%F %T")
    save(res)


if __name__ == "__main__":
    main()
