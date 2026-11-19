#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量作業の子プロセスが生きているかを見るだけ（2026-10-12）。status/youryou_ps.go → status/youryou_ps.json"""
import json, os, subprocess, time
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(REPO, "status", "youryou_ps.go")
if os.path.exists(GO):
    os.remove(GO)
    r = subprocess.run(["ps", "-axo", "pid,ppid,etime,%cpu,stat,command"], capture_output=True, text=True)
    rows = [l[:260] for l in r.stdout.splitlines()
            if any(k in l for k in ("rsync", "hakobu", "taihi", "git gc", "git repack", "git pack", "tar -"))]
    res = {"at": time.strftime("%F %T"), "ps": rows}
    for p in ("/Users/mac/Documents/AI作業/2026-09-02/プロジェクト", "/Users/mac/howitholds/ep01/_build"):
        res[p] = {"islink": os.path.islink(p), "exists": os.path.exists(p)}
    try:
        r = subprocess.run(["tail", "-c", "3000", os.path.join(REPO, "status", "youryou_kyuukyuu.log")],
                           capture_output=True, text=True)
        res["log_tail"] = r.stdout.splitlines()[-15:]
    except Exception:
        pass
    json.dump(res, open(os.path.join(REPO, "status", "youryou_ps.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
