#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1155番の見張り。ずんだもん読み上げが黙って止まったら、続きから立て直す。

心臓(heartbeat)は再起動のたびに自分のプロセスグループを kill -9 するので、
長い読み上げは必ず途中で死ぬ。progress.json に済みが残るので、
立て直せば続きから走る。top_status.py の末尾から毎周回で呼ばれる。
"""
import io
import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "Desktop", "tamago-shinchoku")
STATE = os.path.join(REPO, "status", "zunda")
PROGRESS = os.path.join(STATE, "progress.json")
STOP = os.path.join(STATE, "stop")          # このファイルを置けば止まる
LOG = os.path.join(STATE, "keeper.log")


def alive():
    try:
        out = subprocess.run(["pgrep", "-f", "1155_zunda.py"],
                             capture_output=True, text=True).stdout.strip()
        return bool(out)
    except Exception:
        return False


def main():
    if os.path.exists(STOP):
        return 0
    if alive():
        return 0
    try:
        with io.open(PROGRESS, encoding="utf-8") as f:
            p = json.load(f)
        if p.get("total") and len(p.get("done", {})) >= p["total"]:
            return 0                        # 全部済んでいる
    except Exception:
        pass
    os.makedirs(STATE, exist_ok=True)
    subprocess.Popen([sys.executable, os.path.join(REPO, "tools", "1144_hanareru.py"),
                      os.path.join(STATE, "run.log"),
                      "/usr/bin/python3", os.path.join(REPO, "tools", "1155_zunda.py")])
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s 立て直しました\n" % time.strftime("%F %T"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
