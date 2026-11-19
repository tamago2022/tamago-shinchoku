#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量復旧・第3便（2026-10-12・たまごさん指示「いらないもの・影響のないものは捨てる。溜まるものはiMac HDDへ」）。
status/youryou_hakobu3.go がある時だけ1回。結果 status/youryou_hakobu3.json
  ① ゴミ箱を空にする（たまごさん許可済み）
  ② 作業場：tools/worktree_taihi.py を「1時間以上さわられていない」で1回回す
  ③ ~/Documents/AI作業/2026-09-02/プロジェクト を iMac HDD へ写す→数を確かめる→元を消す→元の場所にHDDへの別名
  ④ ~/howitholds/ep01/_build も同じ（worktree_taihi の③を今すぐ）
  ⑤ tamago-shinchoku の git gc（既定の2週間猶予つき＝走行中の工場のgitを壊さない）
"""
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
GO = os.path.join(REPO, "status", "youryou_hakobu3.go")
OUT = os.path.join(REPO, "status", "youryou_hakobu3.json")


def sh(cmd, t=600, cwd=None, env=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t, cwd=cwd, env=env)
        return r.returncode, (r.stdout or "").strip()[-500:], (r.stderr or "").strip()[-300:]
    except Exception as e:
        return -1, "", str(e)[:300]


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def save(res):
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)


def step(res, name, fn):
    b = free_gb()
    res["now"] = name
    save(res)
    try:
        r = fn()
    except Exception as e:
        r = "失敗 %s" % e
    res["steps"].append({"step": name, "gb": round(free_gb() - b, 2), "result": r})
    save(res)


def gomibako():
    t = os.path.join(HOME, ".Trash")
    n = 0
    for c in os.listdir(t):
        p = os.path.join(t, c)
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
            n += 1
        except Exception:
            pass
    return "%d個" % n


def worktrees():
    env = dict(os.environ, TAIHI_MIN_AGE_H="1")
    rc, o, e = sh([sys.executable, os.path.join(HERE, "worktree_taihi.py")], 6 * 3600, env=env)
    try:
        j = json.load(open(os.path.join(REPO, "status", "worktree_taihi.json"), encoding="utf-8"))
        return {"消した": len(j["removed"]), "HDDへ写して消した": len(j["archived"]),
                "残した": j["skipped"], "制作中間ファイル": j["moved"]}
    except Exception:
        return "rc=%s %s" % (rc, e)


def utsusu(src, *dst_parts):
    if os.path.islink(src) or not os.path.isdir(src):
        return "対象なし（既に移動済み or 無い）"
    if not hdd_okiba.ok():
        return "HDDが無いのでやらない"
    d = hdd_okiba.dest(*dst_parts)
    rc, o, e = sh(["rsync", "-rt", src + "/", d + "/"], 6 * 3600)
    n_src = sum(len(f) for _, _, f in os.walk(src))
    b_src = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(src) for f in fs
                if not os.path.islink(os.path.join(dp, f)))
    n_dst = sum(len(f) for _, _, f in os.walk(d))
    b_dst = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(d) for f in fs)
    if rc != 0 or n_dst < n_src or b_dst < b_src:
        return "確認NGなので元は残した rc=%s files %d/%d bytes %d/%d %s" % (rc, n_dst, n_src, b_dst, b_src, e)
    shutil.rmtree(src, ignore_errors=True)
    if not os.path.exists(src):
        os.symlink(d, src)
    return "移した %d個→%s（元の場所にHDDへの別名）" % (n_src, d)


def gc():
    out = []
    for args in (["worktree", "prune"], ["gc", "--quiet"]):
        rc, o, e = sh(["git"] + args, 3 * 3600, REPO)
        out.append("%s rc=%s %s" % (" ".join(args), rc, e[:120]))
    return out


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    # 2026-10-12 実測：心臓のlaunchd便が立て直される(kickstart -k)たびに、心臓から生まれた
    #   長い処理がプロセスグループごと道連れで消えていた（この便が3回、黙って途中で消えた）。
    #   自分のセッションを持って、道連れにされないようにする。
    try:
        os.setsid()
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_gb_start": free_gb(), "hdd": hdd_okiba.ok(),
           "state": "作業中", "steps": []}
    save(res)
    step(res, "ゴミ箱を空にする", gomibako)
    step(res, "作業場（push済みは消す・未保存はHDDへ写して消す）", worktrees)
    step(res, "AI作業/2026-09-02/プロジェクト → HDD",
         lambda: utsusu(os.path.join(HOME, "Documents", "AI作業", "2026-09-02", "プロジェクト"),
                        "AI作業", "2026-09-02", "プロジェクト"))
    step(res, "howitholds/ep01/_build → HDD",
         lambda: utsusu(os.path.join(HOME, "howitholds", "ep01", "_build"), "howitholds", "ep01", "_build"))
    step(res, "tamago-shinchoku の git gc", gc)
    res.pop("now", None)
    res.update(state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb())
    save(res)


if __name__ == "__main__":
    main()
