#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1159番【外への穴】ずんだもん窓口(50023)をスマホからも触れるようにする。

0円の道具だけ使う：localhost.run は ssh だけで穴が開く（登録も課金も無い）。
開いた住所は status/public/zunda_endpoint.json に書く。
このフォルダは tools/pages_publish.sh が gh-pages に載せるので、
ページ側は「いまの住所」をそこから読む。住所が変わっても勝手に追いつく。

使い方: python3 tools/1159_tunnel.py   （開けっぱなしにする。見張りが立て直す）
"""
import io
import json
import os
import re
import signal
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "Desktop", "tamago-shinchoku")
STATE = os.path.join(REPO, "status", "zunda")
PUB = os.path.join(REPO, "status", "public", "zunda_endpoint.json")
PORT = 50023


def log(m):
    os.makedirs(STATE, exist_ok=True)
    with io.open(os.path.join(STATE, "tunnel.log"), "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), m))


def write_endpoint(url):
    tok = io.open(os.path.join(STATE, "token.txt"), encoding="utf-8").read().strip()
    os.makedirs(os.path.dirname(PUB), exist_ok=True)
    with io.open(PUB, "w", encoding="utf-8") as f:
        json.dump({"base": url, "t": tok, "voice": "ずんだもん",
                   "updated": time.strftime("%F %T")}, f, ensure_ascii=False)
    log("住所を書きました %s" % url)
    try:
        subprocess.run(["bash", os.path.join(REPO, "tools", "pages_publish.sh"), "--force"],
                       timeout=300, capture_output=True)
        log("公開しました")
    except Exception as e:
        log("公開でこけた %s" % e)


def main():
    cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new",
           "-o", "ServerAliveInterval=30", "-o", "ExitOnForwardFailure=yes",
           "-R", "80:127.0.0.1:%d" % PORT, "nokey@localhost.run"]
    log("穴を開けます: %s" % " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1)
    url = None
    t0 = time.time()
    while True:
        line = p.stdout.readline()
        if not line:
            if p.poll() is not None:
                log("穴が閉じました rc=%s" % p.returncode)
                return 1
            continue
        line = line.strip()
        if line:
            log("| " + line[:200])
        m = re.search(r"https://[a-z0-9\-]+\.lhr\.life", line)
        if m and m.group(0) != url:
            url = m.group(0)
            write_endpoint(url)
        if url is None and time.time() - t0 > 120:
            log("2分で住所が出ませんでした")
            p.terminate()
            return 1


if __name__ == "__main__":
    sys.exit(main())
