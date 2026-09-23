#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1159番の見張り。ずんだもん窓口と外への穴が閉じたら開け直す。

心臓が自分のプロセスグループを kill -9 するので、どちらも必ず落ちる。
落ちたまま放置すると、たまごさんがページを開いたときに声が出ない。
top_status.py の末尾から毎周回で呼ばれる。止めたいときは status/zunda/stop を置く。
"""
import io
import os
import subprocess
import sys
import time
import urllib.request

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "Desktop", "tamago-shinchoku")
STATE = os.path.join(REPO, "status", "zunda")
STOP = os.path.join(STATE, "stop")
HANARERU = os.path.join(REPO, "tools", "1144_hanareru.py")


def running(pat):
    return bool(subprocess.run(["pgrep", "-f", pat], capture_output=True,
                               text=True).stdout.strip())


def log(m):
    os.makedirs(STATE, exist_ok=True)
    with io.open(os.path.join(STATE, "keeper.log"), "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), m))


def engine_ok():
    try:
        urllib.request.urlopen("http://127.0.0.1:50021/version", timeout=3).read()
        return True
    except Exception:
        return False


def main():
    if os.path.exists(STOP):
        return 0
    if not engine_ok() and not running("vv-engine/run"):
        run = "/Applications/VOICEVOX.app/Contents/MacOS/vv-engine/run"
        if os.path.exists(run):
            subprocess.Popen([sys.executable, HANARERU, "/tmp/vv_engine.log",
                              run, "--host", "127.0.0.1", "--port", "50021"])
            log("エンジンを起こしました")
    if not running("1159_zunda_server.py"):
        subprocess.Popen([sys.executable, HANARERU,
                          os.path.join(STATE, "server.out"),
                          "/usr/bin/python3",
                          os.path.join(REPO, "tools", "1159_zunda_server.py")])
        log("窓口を開け直しました")
    if not running("1159_tunnel.py"):
        subprocess.Popen([sys.executable, HANARERU,
                          os.path.join(STATE, "tunnel.out"),
                          "/usr/bin/python3",
                          os.path.join(REPO, "tools", "1159_tunnel.py")])
        log("外への穴を開け直しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
