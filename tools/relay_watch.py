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


SERVER_STAMP = os.path.join(REPO, "status", ".relay_server_started")
RESTART_COOLDOWN = 120   # 入れ直しは2分に1回まで（連続で書き換えても暴れない）


def _tools_newest_mtime():
    """受け口が読むコードのうち、いちばん新しい更新時刻。

    relay_server.py は command_ingest を import し、command_ingest は
    その場で他の tools/*.py を import する。どれが増えるか先に決められないので、
    **tools/ の .py 全部**でいちばん新しいものを見る（数十ファイルの stat だけ・軽い）。
    """
    newest = 0.0
    tools = os.path.join(REPO, "tools")
    try:
        for name in os.listdir(tools):
            if not name.endswith(".py"):
                continue
            try:
                m = os.path.getmtime(os.path.join(tools, name))
            except OSError:
                continue
            if m > newest:
                newest = m
    except OSError:
        pass
    return newest


def restart_server_if_stale():
    """受け口のコードが起動時より新しければ、受け口だけ入れ直す。"""
    try:
        started = os.path.getmtime(SERVER_STAMP)
    except OSError:
        started = 0.0
    newest = _tools_newest_mtime()
    if newest <= started:
        return False
    if time.time() - started < RESTART_COOLDOWN:
        return False   # さっき入れ直したばかり
    log("受け口のコードが新しくなっています（コード %s ＞ 起動 %s）。受け口だけ入れ直します"
        % (time.strftime("%H:%M:%S", time.localtime(newest)),
           time.strftime("%H:%M:%S", time.localtime(started)) if started else "不明"))
    try:
        subprocess.run(["pkill", "-f", "relay_server.py"], timeout=10)
    except Exception:
        pass
    time.sleep(1)
    # ★先に判子を押す。起こすのに失敗しても、判子が古いまま毎回 pkill し続ける事故を防ぐ。
    io.open(SERVER_STAMP, "w").write(str(int(time.time())))
    try:
        subprocess.Popen([sys.executable, os.path.join(REPO, "tools", "relay_server.py")],
                         stdout=open(LOG, "a"), stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    except Exception as e:
        log("受け口の入れ直しに失敗: %s" % e)
        return False
    for _ in range(10):
        time.sleep(1)
        try:
            r = subprocess.run(["curl", "-s", "-m", "3", "-o", "/dev/null",
                                "-w", "%{http_code}", "http://127.0.0.1:8788/health"],
                               capture_output=True, text=True, timeout=8)
            if (r.stdout or "").strip() == "200":
                log("受け口を入れ直しました（ローカル200・実測）")
                return True
        except Exception:
            pass
    log("★受け口を入れ直しましたが、ローカルで200が返りません")
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

    # ★2026-09-23（1038番）**「直したのに反映されない」を根から止める。**
    #   relay_server.py は起動時に command_ingest を import する。走り続けている限り
    #   コードを読み直さないので、新しい指示（例：nagekomi）を足しても
    #   「使えない指示」で弾かれ続ける。今日までの見張りは「外から200が返るか」しか
    #   見ていなかったので、**繋がっている限り永遠に古いまま**だった。
    #   → 受け口のコードが起動時より新しければ、受け口だけ入れ直す。
    #     トンネル（localtunnel）は localhost:8788 を見ているだけなので URL は変わらない。
    #   ★入れ直した回は、そこで終わる。すぐ下の「外から200が返るか」を続けてやると、
    #     立ち上がりの数秒を「トンネルが死んだ」と誤読してトンネルまで張り直してしまう
    #     （13:26 に実際に1回起きた）。生死は次の回（2分後）に見れば足りる。
    if restart_server_if_stale():
        return 0

    url, lan = "", ""
    try:
        d = json.load(io.open(RJSON, encoding="utf-8"))
        url, lan = d.get("url") or "", d.get("lanUrl") or ""
    except Exception:
        pass
    # 2026-09-11 修正（753番）：以前は lan（家の中の道）が生きていれば
    # url（外の道＝トンネル）が死んでいても「生きている」と判定していた。
    # 家の中は進捗表が動き続けるので気づかないが、**比較ページ「これにする」
    # ボタンはスマホ（外のネットワーク）から relay.json の url へ直接POSTする
    # 実装のため、外の道が切れているとスマホから押しても永久に届かなくなる。
    # → 外の道は外の道で独立して生死を見て、死んでいたら立て直す。
    if alive(url):
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
