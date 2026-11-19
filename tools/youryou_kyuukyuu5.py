#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量復旧・第5便（2026-10-14）。status/youryou_kyuukyuu5.go → status/youryou_kyuukyuu5.json
  ① Googleドライブの「一時保管場所」の場所と中身を探す（見るだけ・Googleアカウントには触らない）
  ② git の自動gcを止める（gc.auto=0）。実測：工場のgitが自動gcを始めては途中で打ち切られ、
     書きかけパック(tmp_pack)を126個・0.73GB、新しい2.1GBのパックを繰り返し残していた。
     → 自動gcは止め、gcは心臓から1日1回だけ自分のセッションで最後まで走らせる（tools/git_souji.py）
  ③ tamago-shinchoku の git gc を今1回、最後まで（2週間より新しい物は消さない＝走行中の工場を壊さない）
"""
import glob, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_kyuukyuu5.go")
OUT = os.path.join(REPO, "status", "youryou_kyuukyuu5.json")
AS = HOME + "/Library/Application Support"
REPOS = [REPO, HOME + "/Desktop/joy-relief-station"]


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def save(res):
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)


def sh(cmd, t=600, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t, cwd=cwd)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()[-300:]
    except Exception as e:
        return -1, "", str(e)[:300]


def gdrive():
    out = {"dirs": [], "files": [], "log": []}
    for base in (AS + "/Google", HOME + "/Library/CloudStorage"):
        for dp, dns, fns in os.walk(base):
            depth = dp[len(base):].count("/")
            if base.endswith("CloudStorage") and depth >= 1:
                # ドライブの中身には降りない（直下の名前だけ見る）
                for d in dns:
                    if "lost" in d.lower() or "保管" in d:
                        out["dirs"].append(os.path.join(dp, d))
                dns[:] = []
                continue
            for d in list(dns):
                if re.search(r"lost.?(and|&).?found|保管場所", d, re.I):
                    out["dirs"].append(os.path.join(dp, d))
            if depth > 6:
                dns[:] = []
    for d in out["dirs"]:
        for dp, dns, fns in os.walk(d):
            for fn in fns:
                fp = os.path.join(dp, fn)
                try:
                    st = os.lstat(fp)
                    out["files"].append({"path": fp, "bytes": st.st_size,
                                         "mtime": time.strftime("%F %T", time.localtime(st.st_mtime))})
                except Exception:
                    pass
    pat = re.compile(r"lost_and_found/|LostAndFound[A-Z]|MoveToLostAndFound|lost and found|"
                     r"moved to lost|LOST_AND_FOUND_ITEMS_FOUND|unsyncable|DISK_FULL", re.I)
    logs = sorted(glob.glob(AS + "/Google/DriveFS/Logs/drive_fs*.txt"), key=os.path.getmtime)[-8:]
    for lf in logs:
        try:
            with open(lf, "r", errors="replace") as f:
                prev = []
                for line in f:
                    if pat.search(line) and not re.match(r"\s*\w+: (true|false|\d+)$", line.strip()):
                        out["log"].append(os.path.basename(lf) + ": " + " | ".join(prev[-2:])[:200] + " >> " + line.strip()[:400])
                    prev.append(line.strip()[:200])
                    prev = prev[-3:]
        except Exception:
            pass
    out["log"] = out["log"][-60:]
    return out


def git_auto_off():
    r = []
    for p in REPOS:
        if os.path.isdir(os.path.join(p, ".git")):
            rc, o, e = sh(["git", "config", "gc.auto", "0"], 30, p)
            rc2, o2, e2 = sh(["git", "config", "maintenance.auto", "false"], 30, p)
            r.append("%s gc.auto=0 rc=%s" % (os.path.basename(p), rc))
    return r


def gc():
    b = free_gb()
    rc, o, e = sh(["git", "gc", "--quiet"], 3 * 3600, REPO)
    rc2, o2, e2 = sh(["git", "count-objects", "-vH"], 120, REPO)
    return {"rc": rc, "err": e, "count": o2, "gb": round(free_gb() - b, 2)}


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_gb_start": free_gb(), "state": "作業中"}
    save(res)
    try:
        res["gdrive"] = gdrive()
    except Exception as e:
        res["gdrive"] = "失敗 %s" % e
    save(res)
    res["git_auto_off"] = git_auto_off()
    save(res)
    res["gc"] = gc()
    res.update(state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb())
    save(res)


if __name__ == "__main__":
    main()
