#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中継所（進捗表→Mac）が本当に外から繋がるか見張り、切れていたら立て直す（2026-09-05）。

たまごさんの言葉：「今すぐ押しても入らない。今何も動いてませんてなる。」

その日の実測で分かったこと：
  - cloudflared のクイックトンネルは**プロセスを残したまま無言で死ぬ。**
    見回りが `pgrep` で生死を見ていたので、毎回「生きている」と誤判定して素通りしていた。
  - たまごさんの回線は **7844番（QUIC/TCP）が塞がれている**（cloudflared の自己診断が hard_fail）。
    そもそも cloudflared が張れない日がある。
  - だから **生死は「外から叩いて200が返るか」で見る**。そして**道を2本持つ**
    （cloudflared → 駄目なら localtunnel）。1本しか無いのが詰まりの原因だった。

心臓（15秒）から**投げっぱなし**で呼ばれる。こちらは何も待たせない。
"""
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
RJSON = os.path.join(REPO, "status", "relay.json")
STAMP = os.path.join(REPO, "status", ".relay_watch_at")
LOG = os.path.join(REPO, "status", "relay.log")
INTERVAL = 120  # 2分に1回だけ見る（無駄打ちしない）


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def alive(url):
    """外から実際に叩く。プロセスの有無では判断しない。"""
    if not url:
        return False
    try:
        r = subprocess.run(["curl", "-s", "-m", "10", "-o", "/dev/null",
                            "-w", "%{http_code}",
                            "-H", "bypass-tunnel-reminder: 1",
                            url.rstrip("/") + "/health"],
                           capture_output=True, text=True, timeout=20)
        return (r.stdout or "").strip() == "200"
    except Exception:
        return False


def main():
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w").write(str(int(time.time())))

    url = ""
    try:
        url = json.load(io.open(RJSON, encoding="utf-8")).get("url") or ""
    except Exception:
        pass
    if alive(url):
        return 0

    log("中継所が外から繋がりません（%s）。立て直します" % (url or "URL未設定"))
    try:
        import command_ingest
        status, msg = command_ingest.relay_fix()
        log("立て直しの結果: %s ／ %s" % (status, msg))
    except Exception as e:
        log("立て直しに失敗: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
