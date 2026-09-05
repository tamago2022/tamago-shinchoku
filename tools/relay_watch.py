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
# 2026-09-05 追記：**立て直しすぎるのも害だった。**
#   2分おきに張り直したら、そのたびトンネルのURLが変わり、進捗表がどれを見ればいいか
#   分からなくなった（10:15〜10:39で5回変わった）。見るのは2分おきでよいが、
#   **立て直しは10分に1回まで**にする。家の中の道（LAN直結）は切れないので、
#   トンネルが多少切れていても進捗表は動き続ける。
INTERVAL = 120        # 見るのは2分おき
FIX_INTERVAL = 600    # 立て直すのは10分に1回まで


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
    # 2026-09-05 17:02 **重いときは何もしない。**
    #   実測：Macの5分平均ロードが238まで上がった。原因のひとつが、この見張りが呼ぶ
    #   立て直し（npx localtunnel / cloudflared の起動）が重なって積み上がったこと。
    #   重いときにさらにプロセスを起こすのは、火に油。ロードが高い間は黙って見送る。
    try:
        if os.getloadavg()[0] > 20:
            return 0
    except Exception:
        pass
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w").write(str(int(time.time())))

    url, lan = "", ""
    try:
        d = json.load(io.open(RJSON, encoding="utf-8"))
        url, lan = d.get("url") or "", d.get("lanUrl") or ""
    except Exception:
        pass
    if alive(url) or alive(lan):
        return 0

    fixstamp = os.path.join(REPO, "status", ".relay_fix_at")
    try:
        if time.time() - os.path.getmtime(fixstamp) < FIX_INTERVAL:
            return 0   # さっき立て直したばかり。URLを変えすぎない
    except Exception:
        pass
    io.open(fixstamp, "w").write(str(int(time.time())))
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
