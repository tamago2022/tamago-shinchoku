#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-01 「@」ログイン退行の戻しを本番に出す（一回きり）。
Lovableが持つコミットに、指定コミットが含まれていることを git で確かめてから deploy_project を押す。
呼ぶのは get_project / deploy_project だけ（kohyou_osu の白名簿）。最大およそ220秒で抜ける。
"""
import os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kohyou_osu import Lovable, MATO  # noqa: E402

REPO = os.path.expanduser("~/Desktop/joy-relief-station")
want = sys.argv[1]
mato = MATO["ごきげん補給所"]
lv = Lovable()
if not lv.ok():
    print("no lovable token"); sys.exit(2)
lv.hello()
t0 = time.time()
while time.time() - t0 < 200:
    o, err = lv.call("get_project", {"project_id": mato["project_id"]})
    sha = (o or {}).get("latest_commit_sha") or ""
    print(time.strftime("%H:%M:%S"), "lovable sha =", sha[:10], err or "")
    if sha:
        subprocess.run(["git", "-C", REPO, "fetch", "-q", "origin", "main"])
        r = subprocess.run(["git", "-C", REPO, "merge-base", "--is-ancestor", want, sha])
        if r.returncode == 0:
            d, err = lv.call("deploy_project", {"project_id": mato["project_id"]})
            print("DEPLOY", d, err or "")
            sys.exit(0)
        print("  not yet contains", want[:10])
    time.sleep(20)
print("TIMEOUT (lovable has not synced yet)")
sys.exit(3)
