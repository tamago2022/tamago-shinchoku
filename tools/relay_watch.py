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


NAGE_TIMEOUT = 25
RED = os.path.join(REPO, "status", "relay_red.json")


def soutuu(url):
    """★自分で1本投げる。「立ち上げ直した」だけで終わらせないための実測。

    /health の200は根拠にしない。200が返っても受け口の中身が古ければ投げ込みは弾かれる
    ＝**届かないのに緑**になる。ここは実際に /cmd へ空荷を1本通して、
    向こうが done を返したときだけ「届いた」とする。
    通ると受け口側(command_ingest.soutuu)が relay.json に verifiedAt を押す。
    """
    if not url:
        return False, "URLが無い"
    body = json.dumps({"commands": [{"id": "soutuu", "action": "soutuu",
                                     "by": "relay_watch"}]}, ensure_ascii=False)
    try:
        r = subprocess.run(["curl", "-s", "-m", str(NAGE_TIMEOUT),
                            "-X", "POST", url.rstrip("/") + "/cmd",
                            "-H", "content-type: application/json",
                            "-H", "bypass-tunnel-reminder: 1",
                            "--data-binary", body],
                           capture_output=True, text=True, timeout=NAGE_TIMEOUT + 10)
        txt = (r.stdout or "").strip()
    except Exception as e:
        return False, "投げられませんでした（%s）" % e
    try:
        d = json.loads(txt)
        res = (d.get("results") or [{}])[0]
        if res.get("status") == "done":
            return True, res.get("message") or "届いた"
        return False, "受け口が断りました：%s" % (res.get("message") or txt[:120])
    except Exception:
        return False, "返事が読めません：%s" % (txt[:120] or "空っぽ")


def write_red(reason, fixed=False):
    try:
        json.dump({"han": "\U0001F534", "why": reason, "fixedTried": fixed,
                   "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                  io.open(RED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def clear_red():
    try:
        if os.path.exists(RED):
            os.remove(RED)
    except Exception:
        pass


def main():
    # 2026-09-23（1042番）★重いときに黙って帰るのをやめた。
    #   これまでは load>20 で無条件 return していた。**赤が誰にも見えないまま止まる**
    #   （今日3回目の「黙って止まる」の一因）。重いときは立て直しだけ見送り、
    #   赤は赤として必ず残す。
    heavy = False
    try:
        heavy = os.getloadavg()[0] > 40
    except Exception:
        pass
    try:
        if time.time() - os.path.getmtime(STAMP) < INTERVAL:
            return 0
    except Exception:
        pass
    io.open(STAMP, "w").write(str(int(time.time())))

    # 受け口のコードが新しくなっていたら、まず入れ直す（走っているループは読み直さない）
    if restart_server_if_stale():
        return 0

    try:
        d = json.load(io.open(RJSON, encoding="utf-8"))
        url = d.get("url") or ""
    except Exception:
        url = ""

    # ---- ① まず自分で1本投げる。これが唯一の根拠 ----
    ok, msg = soutuu(url)
    if ok:
        clear_red()
        return 0

    # ---- ② 届かない。判定は tools/hantei.py にしか書かない ----
    try:
        sys.path.insert(0, HERE)
        import hantei
        han, why, _ = hantei.relay_han()
    except Exception as e:
        han, why = "\U0001F534", "判定が読めません（%s）" % e
    if han != "\U0001F534":
        # 判子はまだ新しい（さっき誰かの投げ込みが届いている）。一時的な失敗として見送る。
        return 0

    log("%s ／ 自分で投げた結果：%s" % (why, msg))
    if heavy:
        write_red("%s ／ Macが重いので立て直しは見送りました（load>40）" % why)
        log("Macが重いので立て直しは見送ります（赤のまま残します）")
        return 0

    fixstamp = os.path.join(REPO, "status", ".relay_fix_at")
    try:
        if time.time() - os.path.getmtime(fixstamp) < FIX_INTERVAL:
            write_red("%s ／ さきほど立て直したばかりなので次の回まで待ちます" % why, fixed=True)
            return 0
    except Exception:
        pass
    io.open(fixstamp, "w").write(str(int(time.time())))

    # ---- ③ 立て直す ----
    try:
        import command_ingest
        status, fixmsg = command_ingest.relay_fix()
        log("立て直しの結果: %s ／ %s" % (status, fixmsg))
    except Exception as e:
        write_red("立て直しに失敗しました（%s）" % e, fixed=True)
        log("立て直しに失敗: %s" % e)
        return 1

    # ---- ④ ★立て直しただけで終わらせない。もう一度自分で投げて、届くまで緑にしない ----
    try:
        d = json.load(io.open(RJSON, encoding="utf-8"))
        url2 = d.get("url") or ""
    except Exception:
        url2 = ""
    ok2, msg2 = soutuu(url2)
    if ok2:
        clear_red()
        log("立て直したあと、自分で1本投げて届きました（%s）" % url2)
        return 0
    write_red("立て直しましたが、自分で投げた1本が届きません：%s" % msg2, fixed=True)
    log("\u2605立て直しましたが届きません（%s）。赤のまま残します" % msg2)
    return 1


if __name__ == "__main__":
    sys.exit(main())
