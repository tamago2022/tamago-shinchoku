#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業場（~/Documents/AI作業/.worktrees）と制作の中間ファイルを本体に溜めない係（2026-10-12）。

実測（2026-10-12）：作業場が104個・18.6GB溜まっていた（うち58個はコミット済み・push済み）。
worktree_reaper.py は「3日放置」までは残す設計で、走行本数が多い日は溜まる一方だった。

1時間に1回（心臓から）：
  ① コミット済み・push済み・未保存の変更なし・2時間以上触られていない → 消す
  ② 未保存の変更 or 未pushがある・2時間以上触られていない → iMac HDD へ tar.gz で写して確かめてから消す
     （コミットは本体リポジトリに残るので失われない。node_modules は写さない＝作り直せる）
     HDDが外れているときは②はやらない（消さない・本体にも増やさない＝工場は auto_launcher 側で止まる）
  ③ ~/howitholds/ep*/_build（制作の中間ファイル）が6時間以上触られていなければ HDD へ移して、
     元の場所には HDD への別名（シンボリックリンク）を置く＝たまごさんが探せる
走っている仕事の作業場には触らない（worktree_reaper.running_paths）。
結果：status/worktree_taihi.json（何を・どこへ・何GB）
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import hdd_okiba  # noqa: E402

HOME = os.path.expanduser("~")
WTB = os.path.join(HOME, "Documents", "AI作業", ".worktrees")
OUT = os.path.join(REPO, "status", "worktree_taihi.json")
MIN_AGE = float(os.environ.get("TAIHI_MIN_AGE_H", "2")) * 3600
BUILD_AGE = 6 * 3600


def sh(cmd, t=600, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t, cwd=cwd)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()[:300]
    except Exception as e:
        return -1, "", str(e)[:300]


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def newest_mtime(p, limit=4000):
    m = os.path.getmtime(p)
    n = 0
    for dp, dns, fns in os.walk(p):
        dns[:] = [d for d in dns if d not in ("node_modules", ".git")]
        for fn in fns:
            try:
                m = max(m, os.lstat(os.path.join(dp, fn)).st_mtime)
            except Exception:
                pass
            n += 1
            if n > limit:
                return m
    return m


def running():
    try:
        import worktree_reaper
        return worktree_reaper.running_paths()
    except Exception:
        return None


def is_running(name, run):
    for r in run:
        if name == r or name.startswith(r + "-") or name.startswith(r + "_"):
            return True
    return False


def remove_worktree(p):
    rc, common, e = sh(["git", "rev-parse", "--git-common-dir"], 60, p)
    if rc == 0 and common:
        common = os.path.abspath(os.path.join(p, common))
        rc2, o, e2 = sh(["git", "--git-dir", common, "worktree", "remove", "--force", p], 600)
        if rc2 == 0 and not os.path.exists(p):
            return True
    shutil.rmtree(p, ignore_errors=True)
    if rc == 0 and common:
        sh(["git", "--git-dir", common, "worktree", "prune"], 120)
    return not os.path.exists(p)


def main():
    res = {"at": time.strftime("%F %T"), "free_gb_before": free_gb(), "hdd": hdd_okiba.ok(),
           "removed": [], "archived": [], "moved": [], "skipped": []}
    run = running()
    if run is None:
        res["skipped"].append("走行中の一覧が読めないので今回は何もしない")
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    now = time.time()
    for name in sorted(os.listdir(WTB)) if os.path.isdir(WTB) else []:
        p = os.path.join(WTB, name)
        if not os.path.isdir(p) or os.path.islink(p) or not os.path.exists(os.path.join(p, ".git")):
            continue
        if is_running(name, run):
            res["skipped"].append(name + "（走行中）")
            continue
        try:
            if now - newest_mtime(p) < MIN_AGE:
                res["skipped"].append(name + "（最近さわられた）")
                continue
        except Exception:
            continue
        rc, st, e = sh(["git", "status", "--porcelain"], 120, p)
        if rc != 0:
            res["skipped"].append(name + "（git status 失敗）")
            continue
        dirty = bool(st.strip())
        rc, br, e = sh(["git", "branch", "-r", "--contains", "HEAD"], 120, p)
        pushed = rc == 0 and bool(br.strip())
        before = free_gb()
        if not dirty and pushed:
            if remove_worktree(p):
                res["removed"].append({"name": name, "gb": round(free_gb() - before, 2)})
            continue
        if not res["hdd"]:
            res["skipped"].append(name + "（未保存あり・HDDが無いので保留）")
            continue
        d = hdd_okiba.dest("作業場の控え", time.strftime("%Y-%m"))
        tgz = os.path.join(d, name + "_" + time.strftime("%Y%m%d-%H%M") + ".tar.gz")
        rc, o, e = sh(["tar", "-czf", tgz, "--exclude", "node_modules", "-C", WTB, name], 3600)
        rc2, o2, e2 = sh(["tar", "-tzf", tgz], 1800) if rc == 0 else (1, "", "")
        if rc != 0 or rc2 != 0 or not o2:
            res["skipped"].append("%s（HDDへの写しに失敗：%s）" % (name, (e or e2)[:80]))
            try:
                os.remove(tgz)
            except Exception:
                pass
            continue
        if remove_worktree(p):
            res["archived"].append({"name": name, "to": tgz, "dirty": dirty, "pushed": pushed,
                                    "gb": round(free_gb() - before, 2)})
    # ③ 制作の中間ファイル
    if res["hdd"]:
        for b in glob.glob(os.path.join(HOME, "howitholds", "ep*", "_build")):
            if os.path.islink(b) or not os.path.isdir(b):
                continue
            try:
                if now - newest_mtime(b, 20000) < BUILD_AGE:
                    continue
            except Exception:
                continue
            ep = os.path.basename(os.path.dirname(b))
            d = hdd_okiba.dest("howitholds", ep, "_build")
            before = free_gb()
            rc, o, e = sh(["rsync", "-rt", b + "/", d + "/"], 7200)
            n_src = sum(len(f) for _, _, f in os.walk(b))
            n_dst = sum(len(f) for _, _, f in os.walk(d))
            if rc == 0 and n_dst >= n_src:
                shutil.rmtree(b, ignore_errors=True)
                if not os.path.exists(b):
                    os.symlink(d, b)
                    res["moved"].append({"from": b, "to": d, "files": n_src, "gb": round(free_gb() - before, 2)})
            else:
                res["skipped"].append("%s（HDDへのコピー確認NG rc=%s %d/%d）" % (b, rc, n_dst, n_src))
    res["free_gb_after"] = free_gb()
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    try:
        os.setsid()  # 心臓の立て直しで道連れにされない（tar/rsync の途中で消えると写しが半端になる）
    except Exception:
        pass
    import fcntl
    _lf = open(os.path.join(REPO, "status", ".worktree_taihi.lock"), "w")
    try:
        fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        sys.exit(0)  # 前の回がまだ動いている
    main()
