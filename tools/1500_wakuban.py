#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1500番 枠番（わくばん）＝「含まれてる枠が空いた瞬間に、勝手に発車する係」。

■ なぜ要るか（2026-09-28 実測）
  Devin Pro（月20ドル）の Daily / Weekly の含まれてる枠が 0% used のまま放置されていた。
  枠は使わなければ消えるだけ。空いているのに投げないのは、そのまま損。

■ 仕組み（これが肝。他の「枠もの」にもそのまま効く）
  リセット時刻を当てにいかない。**ただ投げてみる。**
    - 枠が無いとき POST /sessions は 403 out_of_quota を返す。**この空振りは0円。**
    - 枠が戻った周回で、同じ POST が 200 を返す＝その瞬間が発車。
  つまり「リセット時刻を調べて狙う」のではなく「空振りを繰り返して、通った瞬間に乗る」。
  時刻表の要らない設計なので、GitHub Actions・Jules・Genspark など
  「枠があるのに気づけない」もの全部に同じ形で使える。

■ 絶対に守ること
  - 同時は1本だけ（2026-09-20の事故：3本同時→30分でACU尽きてPRゼロ）
  - 従量（on-demand）は残高マイナス。**1円も使わせない。**
    → ACUを買う・自動チャージを触る口はこの係に1つも書いていない。読むのと投げるのだけ。
  - 依頼文の頭に必ず RULE を置く（後ろに置くと効かない・実測）
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.devin.ai/v1"
STATE = os.path.join(REPO, "status", "1500_wakuban.json")
QUEUE = os.path.join(REPO, "status", "1500_queue.json")
LOG = os.path.join(REPO, "status", "1500_wakuban.log")

MAX_RUNNING = 1          # 同時は1本だけ
POLL_MIN = 4             # 走っている1本の様子を見る間隔（分）
RETRY_MIN = 10           # 枠切れで空振りしたあと、次に投げてみるまで（分）。空振りは0円
STALL_MIN = 150          # これ以上「働いてる」と言ったまま動かない1本は見捨てて次へ


def say(msg):
    line = time.strftime("%F %T") + " " + msg
    print(line)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def key():
    try:
        with io.open(os.path.join(REPO, ".env"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("DEVIN_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def call(path, data=None, timeout=45):
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", "Bearer " + key())
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data, ensure_ascii=False).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": repr(e)}


def jload(path, default):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jsave(path, obj):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


RULE = u"""★★最初に読んでください（これが守れないと、この仕事は失敗になります）★★
・**返事を書かないでください。**終わりの合図は Pull Request の URL だけです。
・「指示を待ちます」「確認をお願いします」と書いてはいけません。依頼主は見ていません。誰も答えません。
・途中で環境が壊れても、聞かずに自分で直してください。手を5つ試すまで止まらないでください。
・迷ったら、あなたが妥当だと思う方を自分で選んで進めてください。
・完了の条件は「Pull Request が出ていること」です。調べただけ・書いただけは未完了です。
━━━━━━━━━━━━━━━━━━━━━━━━

"""


def launch(st, q):
    jobs = q.get("jobs") or []
    idx = st.get("next", 0)
    while idx < len(jobs) and jobs[idx].get("skip"):
        idx += 1
    if idx >= len(jobs):
        st["next"] = idx
        say(u"待ち行列が空。投げるものが無いので待機（0円）。")
        return
    job = jobs[idx]
    code, res = call("/sessions", {"prompt": RULE + job["prompt"], "idempotent": False})
    if code == 200:
        st["next"] = idx + 1
        st["current"] = {
            "name": job["name"], "kawaru": job.get("kawaru", ""),
            "sid": res.get("session_id"), "url": res.get("url"),
            "startedTs": int(time.time()), "startedAt": time.strftime("%F %T"),
        }
        st["retryAt"] = 0
        st["firedTotal"] = st.get("firedTotal", 0) + 1
        say(u"発車：%s → %s" % (job["name"], res.get("url")))
        return
    detail = str((res or {}).get("detail") or res)[:140]
    if code == 403 and "quota" in detail.lower():
        st["retryAt"] = int(time.time()) + RETRY_MIN * 60
        st["emptySwings"] = st.get("emptySwings", 0) + 1
        say(u"枠が無い（空振り・0円）。%d分後にもう一度投げてみる。%s" % (RETRY_MIN, detail))
    else:
        st["retryAt"] = int(time.time()) + RETRY_MIN * 60
        say(u"投げられなかった HTTP=%s %s" % (code, detail))


def main():
    st = jload(STATE, {"note": u"枠が空いた瞬間に発車する係の控え。同時1本・従量0円。",
                       "next": 0, "current": None, "done": [],
                       "firedTotal": 0, "emptySwings": 0, "retryAt": 0})
    q = jload(QUEUE, {"jobs": []})

    cur = st.get("current")
    if cur:
        # 走っている1本の様子を見る（間隔を守る＝APIを叩きすぎない）
        if int(time.time()) - int(st.get("polledTs", 0)) < POLL_MIN * 60:
            return 0
        st["polledTs"] = int(time.time())
        code, d = call("/session/" + str(cur.get("sid")), timeout=40)
        if code != 200:
            say(u"様子が見られない HTTP=%s" % code)
            jsave(STATE, st)
            return 0
        stt = d.get("status_enum")
        pr = d.get("pull_request")
        mins = int((time.time() - cur["startedTs"]) / 60)
        cur["status"] = stt
        cur["pr"] = pr
        cur["minutes"] = mins
        msgs = d.get("messages") or []
        if msgs:
            cur["last"] = str(msgs[-1].get("message") or "")[:400]
        if stt in ("finished", "blocked", "expired") or mins > STALL_MIN:
            cur["finishedAt"] = time.strftime("%F %T")
            cur["gaveup"] = bool(stt not in ("finished", "blocked", "expired"))
            st["done"] = (st.get("done") or []) + [cur]
            st["current"] = None
            say(u"1本おわり：%s / %d分 / PR=%s" % (cur["name"], mins, pr))
            launch(st, q)          # 空いた枠を放置しない＝すぐ次を着火
        else:
            say(u"まだ走っている：%s / %d分" % (cur["name"], mins))
        jsave(STATE, st)
        return 0

    if int(st.get("retryAt", 0)) > int(time.time()):
        return 0                   # 空振りの待ち時間中。何も叩かない＝0円
    launch(st, q)
    jsave(STATE, st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
