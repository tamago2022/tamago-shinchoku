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


HIKAE = os.path.join(HOME, ".tamago", "sagyouba_hikae")


def small_hikae(p, name, root, res):
    """未保存の差分（git diff --binary HEAD）と未追跡ファイル（node_modules除く）だけを本体に小さく控える。"""
    d = os.path.join(HIKAE, "%s_%s" % (name, time.strftime("%Y%m%d-%H%M")))
    os.makedirs(d, exist_ok=True)
    rc, head, e = sh(["git", "log", "-1", "--format=%H %s"], 60, p)
    rc2, br, e2 = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], 30, p)
    with open(os.path.join(d, "head.txt"), "w", encoding="utf-8") as f:
        f.write("元の場所: %s\nブランチ: %s\nHEAD: %s\n" % (p, br, head))
    try:
        with open(os.path.join(d, "diff.patch"), "wb") as f:
            r = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=p, stdout=f, timeout=600)
        rc3, ut, e3 = sh(["git", "ls-files", "--others", "--exclude-standard"], 300, p)
        files = [x for x in ut.splitlines() if x and "node_modules/" not in x]
        if files:
            lst = os.path.join(d, "untracked.txt")
            with open(lst, "w", encoding="utf-8") as f:
                f.write("\n".join(files))
            r2 = subprocess.run(["tar", "-czf", os.path.join(d, "untracked.tar.gz"), "-T", lst], cwd=p,
                                capture_output=True, timeout=1800)
            if r2.returncode != 0:
                raise RuntimeError("tar失敗")
        size = sum(os.path.getsize(os.path.join(d, x)) for x in os.listdir(d))
        if size > 100 * 1048576:
            shutil.rmtree(d, ignore_errors=True)
            return False
        return True
    except Exception as ex:
        shutil.rmtree(d, ignore_errors=True)
        res["skipped"].append("%s（差分の控えに失敗：%s）" % (name, str(ex)[:60]))
        return False


def main():
    res = {"at": time.strftime("%F %T"), "free_gb_before": free_gb(), "hdd": hdd_okiba.ok(),
           "removed": [], "archived": [], "moved": [], "skipped": [], "state": "作業中"}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if res["hdd"] and os.path.isdir(HIKAE):  # HDDが戻ったら、本体に控えた差分をHDDへ移す
        for n in os.listdir(HIKAE):
            try:
                shutil.move(os.path.join(HIKAE, n), os.path.join(hdd_okiba.dest("作業場の控え", "差分だけ"), n))
            except Exception:
                pass
    run = running()
    if run is None:
        res["skipped"].append("走行中の一覧が読めないので今回は何もしない")
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    now = time.time()
    # 2026-10-14 実測：子セッションが push 用に /private/tmp へ作業場・まるごとの複製を作っては
    #   置きっぱなしにしていた（10/10〜10/14で48個・約43GB。今日だけで約7GB）。ここも同じ規則で片付ける。
    places = []
    for root in (WTB, "/private/tmp"):
        if os.path.isdir(root):
            places += [(root, n) for n in sorted(os.listdir(root))]
    for root, name in places:
        p = os.path.join(root, name)
        if root == "/private/tmp" and name.startswith("claude-"):
            continue
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
            # 2026-10-14 HDDが無い間は、未保存の「差分だけ」を小さく控えて消す（作業場まるごと＝約0.9GBは写さない）。
            #   コミット済みの中身は元のリポジトリに残っている。差分＋未追跡ファイルが100MBを超えるものは保留。
            if small_hikae(p, name, root, res):
                if remove_worktree(p):
                    res["archived"].append({"name": name, "to": "~/.tamago/sagyouba_hikae（差分だけ）",
                                            "gb": round(free_gb() - before, 2)})
            else:
                res["skipped"].append(name + "（未保存が大きい・HDDが無いので保留）")
            continue
        d = hdd_okiba.dest("作業場の控え", time.strftime("%Y-%m"))
        tgz = os.path.join(d, name + "_" + time.strftime("%Y%m%d-%H%M") + ".tar.gz")
        rc, o, e = sh(["tar", "-czf", tgz, "--exclude", "node_modules", "-C", root, name], 3600)
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
    # ②' /private/tmp 直下に置き去りの一時ファイル（1日以上前の動画・画像・zip）は消す
    for fn in os.listdir("/private/tmp"):
        p = os.path.join("/private/tmp", fn)
        try:
            if os.path.isfile(p) and not os.path.islink(p) and now - os.path.getmtime(p) > 86400 \
                    and fn.lower().endswith((".mp4", ".mov", ".png", ".jpg", ".webp", ".wav", ".mp3", ".zip", ".tar", ".gz")):
                os.remove(p)
                res["removed"].append({"name": p, "gb": 0})
        except Exception:
            pass
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
    # ④ 2026-10-14 AI作業の直下に溜まる完成品の動画・音・画像（3日以上前）→ HDDへ移し、元の場所に別名
    #   ★たまごさんが探せるよう、同じ名前の別名（シンボリックリンク）を元の場所に残す
    if res["hdd"]:
        aiw = os.path.join(HOME, "Documents", "AI作業")
        media = (".mp4", ".mov", ".m4v", ".webm", ".wav", ".mp3", ".m4a", ".png", ".jpg", ".jpeg", ".zip")
        for fn in (os.listdir(aiw) if os.path.isdir(aiw) else []):
            p = os.path.join(aiw, fn)
            if os.path.islink(p) or not os.path.isfile(p) or not fn.lower().endswith(media):
                continue
            try:
                if now - os.path.getmtime(p) < 3 * 86400:
                    continue
                d = hdd_okiba.dest("AI作業", "完成品")
                q = os.path.join(d, fn)
                shutil.copyfile(p, q)
                if os.path.getsize(q) == os.path.getsize(p):
                    os.remove(p)
                    os.symlink(q, p)
                    res["moved"].append({"from": p, "to": q})
            except Exception as e:
                res["skipped"].append("%s（%s）" % (fn, str(e)[:60]))
    res["free_gb_after"] = free_gb()
    res["state"] = "完了"
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
