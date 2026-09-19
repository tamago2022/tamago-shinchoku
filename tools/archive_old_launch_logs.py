#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""796番（2026-09-13）：status/直下に auto-launch-*.log / verify-*.log が
何百本も溜まって「重い」原因の一つになっていた（実測：709本・3.7MB）。

進捗表（index.html）はこれらのログを一切読んでいない（読むのは status/*.json だけ）。
読むのは tools/genzaichi.py（今日の行だけ正規表現で数える）と
tools/kenpou_check.py（mtime順で最新25本だけ見る）の2つで、どちらも
3日以上前のファイルを対象にしていない。だから3日より古いものは
安全に倉庫（status/_archive/logs-YYYY-MM-DD/）へ移せる。

★消さない。移すだけ。移した記録は移動先のMANIFEST.mdに必ず残す
（「一度渡したURLは殺さない」と同じ発想＝黙って消して後から探せなくなる事故を繰り返さない）。

使い方: python3 tools/archive_old_launch_logs.py [--days 3]
"""
import argparse
import glob
import os
import shutil
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=3.0, help="これより古いログを倉庫へ移す（既定3日）")
    args = ap.parse_args()

    files = glob.glob(os.path.join(STATUS, "auto-launch-*.log")) + glob.glob(os.path.join(STATUS, "verify-*.log"))
    now = time.time()
    old = [f for f in files if (now - os.path.getmtime(f)) / 86400 >= args.days]
    if not old:
        print("移すものはありません（%d本を確認・%.1f日より新しい）" % (len(files), args.days))
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d")
    dest_dir = os.path.join(STATUS, "_archive", "logs-" + stamp)
    os.makedirs(dest_dir, exist_ok=True)
    moved = []
    for f in old:
        base = os.path.basename(f)
        dest = os.path.join(dest_dir, base)
        # 同名が既にあれば上書きせず連番を振る（何度実行しても安全）
        i = 2
        while os.path.exists(dest):
            dest = os.path.join(dest_dir, base + ".%d" % i)
            i += 1
        shutil.move(f, dest)
        moved.append(os.path.basename(dest))

    manifest = os.path.join(dest_dir, "MANIFEST.md")
    with open(manifest, "a", encoding="utf-8") as m:
        m.write("\n## %s 実行分（%d件）\n" % (datetime.now().strftime("%Y-%m-%d %H:%M"), len(moved)))
        for b in sorted(moved):
            m.write("- %s\n" % b)
    print("moved %d files -> %s" % (len(moved), dest_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
