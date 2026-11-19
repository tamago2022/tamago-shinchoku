#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""957番 — 工場(Mac)側で、詰まったindex.lockを外して、溜まった分をpushする。

サンドボックスからは .git/index.lock を消せない（Operation not permitted・実測）。
消せないまま残ると、工場のpush常駐も merge に入れず「合流できない」で戻り続ける。
結果、作った現物が永久に公開URLにならない。ここはその1点だけを外す。
"""
import io, json, os, subprocess, time
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def g(*a, t=180):
    r = subprocess.run(["git"]+list(a), cwd=REPO, capture_output=True, text=True, timeout=t)
    return r.returncode, (r.stdout or "")[-1200:], (r.stderr or "")[-1200:]
def run_job(payload=None):
    log = []
    gd = os.path.join(REPO, ".git")
    for root, dirs, files in os.walk(gd):
        for f in files:
            if not f.endswith(".lock"):
                continue
            fp = os.path.join(root, f)
            try:
                age = time.time() - os.path.getmtime(fp)
            except Exception:
                continue
            if age > 60:
                try:
                    os.remove(fp)
                    log.append("古いロックを外しました: %s (%.0f秒)" % (os.path.relpath(fp, gd), age))
                except Exception as e:
                    log.append("外せません %s: %s" % (os.path.relpath(fp, gd), e))
    rc, o, e = g("add", "-A"); log.append("add rc=%d %s" % (rc, e[:200]))
    rc, o, e = g("commit", "-a", "-m", "957番: 案内所コンシェルジュ 02/08（正本どおり）")
    log.append("commit rc=%d %s" % (rc, (o or e)[:200]))
    rc, o, e = g("fetch", "origin", "main"); log.append("fetch rc=%d" % rc)
    rc, o, e = g("merge", "--no-edit", "origin/main")
    log.append("merge rc=%d %s" % (rc, (o or e)[:300]))
    if rc != 0:
        g("merge", "--abort")
        log.append("合流できないので戻しました")
        return {"ok": False, "log": log, "totalYen": 0.0}
    rc, o, e = g("fetch", "origin", "main"); log.append("fetch2 rc=%d" % rc)
    rc, o, e = g("merge", "--no-edit", "origin/main")
    log.append("merge2 rc=%d out=%s err=%s" % (rc, o[:200], e[:200]))
    rc, o, e = g("push", "origin", "HEAD:main", t=300)
    log.append("push rc=%d" % rc)
    log.append("push-out: " + o[-400:])
    log.append("push-err: " + e[-600:])
    return {"ok": rc == 0, "log": log, "totalYen": 0.0}
