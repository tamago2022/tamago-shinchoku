#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量復旧・第4便（2026-10-14・空き0.04GB）。status/youryou_kyuukyuu4.go → status/youryou_kyuukyuu4.json
  ① git の書きかけパック（tmp_pack_*／tmp_idx_*・1時間以上前）を消す＝失敗したgcの残骸
  ② 作り直せるキャッシュ（~/Library/Caches の com.apple 以外・npm/bun）
  ③ AI作業/2026-09-02/プロジェクト を iMac HDD へ（途中まで写っている分の続き）→確かめて元を消す→別名
  ④ Googleドライブの「一時保管場所(lost_and_found)」の中身と、ログの失敗理由（見るだけ）
  ⑤ iCloudの一時置き場 session/t の月別の量（見るだけ）
  ⑥ この90分で書かれた大きいファイル（見るだけ）
心臓の立て直しで道連れにされないよう、自分のセッションを持つ（os.setsid）。
"""
import glob, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_kyuukyuu4.go")
OUT = os.path.join(REPO, "status", "youryou_kyuukyuu4.json")
AS = HOME + "/Library/Application Support"


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def save(res):
    try:
        with open(OUT + ".tmp", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        os.replace(OUT + ".tmp", OUT)
    except Exception:
        pass


def rm(p):
    try:
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p, ignore_errors=True)
        else:
            os.remove(p)
    except Exception:
        pass


def step(res, name, fn):
    b = free_gb()
    res["now"] = name
    save(res)
    try:
        r = fn()
    except Exception as e:
        r = "失敗 %s" % e
    res["steps"].append({"step": name, "gb": round(free_gb() - b, 2), "result": r, "at": time.strftime("%T")})
    save(res)


def tmp_packs():
    n, b = 0, 0
    repos = [REPO, HOME + "/Desktop/joy-relief-station", HOME + "/.tamago-pages", HOME + "/.tamago/1138-jrs",
             HOME + "/.tamago-brain/repo"] + glob.glob(HOME + "/tamago/*")
    for r in repos:
        for p in glob.glob(os.path.join(r, ".git", "objects", "pack", "tmp_*")) + \
                glob.glob(os.path.join(r, ".git", "objects", "*", "tmp_obj_*")):
            try:
                if time.time() - os.path.getmtime(p) > 3600:
                    b += os.lstat(p).st_blocks * 512
                    rm(p)
                    n += 1
            except Exception:
                pass
    return "%d個 %.2fGB" % (n, b / 1e9)


def caches():
    for c in glob.glob(HOME + "/Library/Caches/*"):
        if not os.path.basename(c).startswith("com.apple."):
            rm(c)
    for p in (HOME + "/.npm/_cacache", HOME + "/.bun/install/cache", HOME + "/.npm/_npx"):
        rm(p)
    return "ok"


def project():
    import youryou_hakobu3
    return youryou_hakobu3.utsusu(HOME + "/Documents/AI作業/2026-09-02/プロジェクト",
                                  "AI作業", "2026-09-02", "プロジェクト")


def gdrive():
    out = {"settings": subprocess.run(["defaults", "read", "com.google.drivefs.settings"],
                                      capture_output=True, text=True, timeout=20).stdout[-1500:]}
    laf = []
    for d in glob.glob(AS + "/Google/DriveFS/*/lost_and_found"):
        for dp, dns, fns in os.walk(d):
            for fn in fns:
                fp = os.path.join(dp, fn)
                try:
                    st = os.lstat(fp)
                    laf.append({"path": fp, "bytes": st.st_size,
                                "mtime": time.strftime("%F %T", time.localtime(st.st_mtime))})
                except Exception:
                    pass
    out["lost_and_found"] = laf
    names = [os.path.basename(x["path"]) for x in laf]
    hits = []
    pat = re.compile(r"lost.?and.?found|LostAndFound|No space|ENOSPC|disk full|insufficient|quota|"
                     r"Bandwidth|bandwidth|failed to (upload|sync)|SyncError", re.I)
    for lf in sorted(glob.glob(AS + "/Google/DriveFS/Logs/drive_fs*.txt"), key=os.path.getmtime)[-6:]:
        try:
            with open(lf, "r", errors="replace") as f:
                for line in f:
                    if pat.search(line) or any(n and n in line for n in names):
                        hits.append(os.path.basename(lf) + ": " + line.strip()[:300])
        except Exception:
            pass
    out["log_hits"] = hits[-120:]
    return out


def icloud_t():
    t = AS + "/CloudDocs/session/t"
    by = {}
    n = 0
    for dp, dns, fns in os.walk(t):
        for fn in fns:
            try:
                st = os.lstat(os.path.join(dp, fn))
            except Exception:
                continue
            n += 1
            k = time.strftime("%Y-%m", time.localtime(st.st_mtime))
            if time.time() - st.st_mtime < 14 * 86400:
                k = time.strftime("%Y-%m-%d", time.localtime(st.st_mtime))
            by[k] = by.get(k, 0) + st.st_blocks * 512
    mob = {}
    for c in glob.glob(HOME + "/Library/Mobile Documents/*"):
        try:
            r = subprocess.run(["du", "-sk", c], capture_output=True, text=True, timeout=300)
            mob[os.path.basename(c)] = round(int(r.stdout.split()[0]) / 1048576, 2)
        except Exception:
            pass
    return {"files": n, "by_date_gb": {k: round(v / 1e9, 2) for k, v in sorted(by.items())},
            "mobile_documents_gb": {k: v for k, v in sorted(mob.items(), key=lambda x: -x[1])[:15]}}


def recent():
    cut = time.time() - 90 * 60
    roots = [HOME + "/tamago", HOME + "/Documents", HOME + "/Library/Application Support", HOME + "/.claude",
             HOME + "/.tamago", HOME + "/Desktop", HOME + "/howitholds", HOME + "/Library/Caches",
             HOME + "/Library/Logs", HOME + "/.cache", "/private/tmp"]
    grow, big = {}, []
    for r in roots:
        for dp, dns, fns in os.walk(r):
            dns[:] = [d for d in dns if not (dp == AS and d in ("AddressBook", "CallHistoryDB", "com.apple.TCC",
                                                                  "Knowledge", "MobileSync", "FileProvider"))]
            for fn in fns:
                fp = os.path.join(dp, fn)
                try:
                    st = os.lstat(fp)
                except Exception:
                    continue
                if st.st_mtime >= cut:
                    b = st.st_blocks * 512
                    k = "/".join(fp.split("/")[:7])
                    grow[k] = grow.get(k, 0) + b
                    if b > 30e6:
                        big.append((b, fp))
    return {"by_dir_gb": [{"d": k, "gb": round(v / 1e9, 2)} for k, v in sorted(grow.items(), key=lambda x: -x[1])[:25]],
            "big": [{"p": p, "gb": round(b / 1e9, 2)} for b, p in sorted(big, reverse=True)[:25]]}


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_gb_start": free_gb(), "state": "作業中", "steps": []}
    save(res)
    step(res, "gitの書きかけパック", tmp_packs)
    step(res, "キャッシュ", caches)
    step(res, "Googleドライブ一時保管場所", gdrive)
    step(res, "iCloud一時置き場", icloud_t)
    step(res, "この90分で増えたもの", recent)
    step(res, "AI作業/2026-09-02/プロジェクト → HDD", project)
    res.pop("now", None)
    res.update(state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb())
    save(res)


if __name__ == "__main__":
    main()
