#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""9/22：Devinを1本ずつ回す係（得意な型＝「前提が正しいか実測で確かめてくれ」だけを投げる）。

実測に基づく作法（2026-09-20）：
  ・3本同時＝30分で枠が尽きる。だから1本ずつ。
  ・Devinは詰まると「指示を待ちます」と書いて寝る。だから依頼文の先頭で禁じる。
  ・tamago-shinchoku へは push できない（Devin GitHub App 未導入・403）。
    読むのはできる。だから「答え＋diffを本文に貼れ」にする。PRは joy-relief-station のみ。

使い方：status/mac_jobs/pending/ に札を置いて、Macから1回呼ぶ（叩くたびに1歩進む）。
触らないもの：オンデマンド購入・自動チャージ・請求。読むだけ。
"""
import json
import os
import time
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(REPO, "status", "devin_922.json")
API = "https://api.devin.ai/v1"

RULE = """★★この仕事の進め方（最初に読んでください）★★
・途中で環境が壊れても、聞かずに自分で直してください。手を5つ試すまで止まらないでください。
・返事や相談を書かないでください。終わりの合図は、下の【終わりの合図】に書いた1通だけです。
・「指示を待ちます」「ご確認ください」と書いてはいけません。依頼主は外出中で、誰も答えられません。
・迷ったら、あなたが妥当だと思う方を自分で選んで進めてください。
・こちらには見立てがありますが、わざと書きません。あなたが実測で出した答えだけが欲しいです。
━━━━━━━━━━━━━━━━━━━━━━━━

"""

JOB_A = """リポジトリ https://github.com/tamago2022/tamago-shinchoku を読んでください。

【症状】Macの上で常駐している「心臓」（tools/heartbeat.sh）が、数分おきに死んでは
見張り役（tools/heartbeat_watchdog.py）に叩き起こされる、という往復を延々と続けています。
夜のあいだの実際のログを貼ります（このログはリポジトリには入っていません）。

--- status/heartbeat_watchdog.log（抜粋）---
2026-09-22 02:22:26 心臓が83秒（60秒超）touchしていません。launchdへkickstartを依頼します
2026-09-22 02:22:32 → kickstart成功
2026-09-22 02:23:51 心臓が74秒（60秒超）touchしていません。launchdへkickstartを依頼します
2026-09-22 02:23:56 → kickstart成功
2026-09-22 02:27:40 心臓が137秒（60秒超）touchしていません。launchdへkickstartを依頼します
2026-09-22 06:40:38 心臓が68秒（60秒超）touchしていません。launchdへkickstartを依頼します

--- status/heartbeat.log（抜粋）---
2026-09-22 02:27:53 心臓を起動しました（pid 51695）
2026-09-22 02:28:52 auto_launcher.pyが45秒以内に終わらず強制終了しました
2026-09-22 02:29:51 心臓を起動しました（pid 52126）
2026-09-22 03:00:01 心臓は動いています
（03:00〜06:00は「動いています」だけで平穏）
2026-09-22 06:24:19 auto_launcher.pyが45秒以内に終わらず強制終了しました
2026-09-22 06:25:02 心臓を起動しました（pid 89143）
2026-09-22 06:40:16 auto_launcher.pyが45秒以内に終わらず強制終了しました
2026-09-22 06:41:00 心臓を起動しました（pid 94637）

【お願い】
tools/heartbeat.sh と tools/heartbeat_watchdog.py と tools/auto_launcher.py を実際に読んで、
**心臓が60秒以上 touch できなくなる理由**を、コードの行番号で示して特定してください。
「たぶんこれ」ではなく、そのコードだとそうなる、という筋道を書いてください。
02:30〜06:00は静かで、02時台と06時台に集中しているのも、同じ理由で説明できるなら説明してください。

【終わりの合図】次の3つを書いた1通だけを送ってください。
1. 「答え：」で始まる1行（心臓を止めているのは何か）
2. 根拠（ファイル名と行番号。最低3か所）
3. 直し方（そのまま適用できる diff。1つだけ、最小で）

【注意】このリポジトリへは push できません（Devin の GitHub App が入っておらず403になります）。
PRは作らなくていいです。push を試して時間を使わないでください。diffは本文に貼ってください。
日本語で書いてください。
"""

JOB_B = """リポジトリ https://github.com/tamago2022/joy-relief-station を調べてください。

【症状】本番サイトのトップページが、いまだに「重い・表示が出るまで待たされる」状態です。
前回あなたに見てもらったときの指摘は、こちらで既に手を入れて潰しました。
その上で、まだ重いです。

【お願い】
**いま残っている重さの原因のうち、一番大きいものを1つ**、実測で特定してください。
・「大きい」の根拠は、必ず数字（バイト数／リクエスト数／ブロックしている時間）で出してください。
・リポジトリの中身を実際に数えて出してください。推測で順位を付けないでください。
・2番目・3番目があるなら、数字だけ添えてください（直さなくていいです）。

【終わりの合図】
このリポジトリには push できます。直せるものなら **Pull Request を1本** 出して、
そのURLだけを送ってください。PRの説明欄に「答え：」で始まる1行と、前後の数字を書いてください。
直すのが危ない（見た目や機能が変わる）と判断したら、PRは作らず、
「答え：」で始まる1行＋数字＋理由を1通だけ送ってください。

【注意】見た目を変えないでください。日本語で書いてください。
"""

JOB_C = """リポジトリ https://github.com/tamago2022/tamago-shinchoku を調べてください。

【症状】このリポジトリは、clone も、git status も、日に日に遅くなっています。
体感で「何かがひとつ、飛び抜けて大きい」という感じがありますが、それが何かを掴めていません。

【お願い】
**リポジトリを重くしている一番大きい要因を1つ**、実測で特定してください。
・git の履歴に残っている大きいオブジェクト、追跡されているファイル、ディレクトリ数、
　どれが効いているのかを、必ず数字（MB／ファイル数／オブジェクト数）で出してください。
・上位10件を、大きい順に数字付きで並べてください。
・「追跡をやめれば一番効くもの」を1つだけ選んで、なぜそれが一番かを数字で示してください。

【終わりの合図】「答え：」で始まる1行＋上位10件の表＋推奨1つ、を書いた1通だけ送ってください。

【注意】
- 何も削除しないでください。履歴の書き換え（filter-branch / filter-repo）は実行しないでください。
- このリポジトリへは push できません（403）。PRは作らなくていいです。日本語で書いてください。
"""

QUEUE = [
    {"name": "A 心臓が死ぬ理由（結論伏せ）", "prompt": JOB_A},
    {"name": "B joy-relief 残りの重さ最大1つ", "prompt": JOB_B},
    {"name": "C リポジトリ肥大の真犯人", "prompt": JOB_C},
]


def key():
    for line in open(os.path.join(REPO, ".env"), encoding="utf-8"):
        if line.startswith("DEVIN_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def call(path, data=None, timeout=40):
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


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"note": "9/22 Devin 1本ずつ。投げた数と返った数を両方数える。",
                "thrown": 0, "returned": 0, "next": 0, "current": None,
                "done": [], "log": []}


def save(st):
    st["checkedAt"] = time.strftime("%F %T")
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def daicho(direction, topic, ref=None, thread=None):
    """外部AI台帳（tools/ai_daicho.py）に投げ／返りを記録する。
    「投げた>0 なのに 返り=0」はあちらが赤で出してくれる。"""
    import subprocess
    cmd = ["python3", os.path.join(REPO, "tools", "ai_daicho.py"),
           "--out" if direction == "out" else "--in", "--ai", "devin",
           "--topic", topic]
    if ref:
        cmd += ["--ref", ref]
    if thread:
        cmd += ["--thread", thread]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, cwd=REPO)
    except Exception:
        pass


def say(st, msg):
    st["log"] = (st.get("log") or [])[-60:] + [time.strftime("%F %T") + " " + msg]
    print(msg)


def launch(st):
    if st["next"] >= len(QUEUE):
        say(st, "待ち行列が空です。")
        return
    job = QUEUE[st["next"]]
    code, res = call("/sessions", {"prompt": RULE + job["prompt"], "idempotent": False})
    if code != 200:
        say(st, "投げられませんでした HTTP=%s %s" % (code, str(res)[:200]))
        return
    st["thrown"] = st.get("thrown", 0) + 1
    st["current"] = {"name": job["name"], "sid": res.get("session_id"),
                     "url": res.get("url"), "startedTs": int(time.time()),
                     "startedAt": time.strftime("%F %T")}
    st["next"] += 1
    daicho("out", job["name"], ref=res.get("url"),
           thread="devin:" + str(res.get("session_id")))
    say(st, "投げました[%d本目]：%s → %s" % (st["thrown"], job["name"], res.get("url")))


def main():
    st = load()
    cur = st.get("current")
    if not cur:
        launch(st)
        save(st)
        return 0

    code, d = call("/session/" + cur["sid"], timeout=30)
    if code != 200:
        say(st, "様子が見られません HTTP=%s %s" % (code, str(d)[:160]))
        save(st)
        return 0

    stt = d.get("status_enum")
    pr = d.get("pull_request")
    msgs = d.get("messages") or []
    mins = int((time.time() - cur["startedTs"]) / 60)
    cur["status"] = stt
    cur["msgs"] = len(msgs)
    cur["pr"] = pr
    if msgs:
        cur["last"] = str(msgs[-1].get("message") or "")[:1500]

    if stt in ("finished", "blocked", "expired"):
        cur["finishedAt"] = time.strftime("%F %T")
        cur["minutes"] = mins
        got = bool(pr) or (len(msgs) >= 2)
        if got:
            st["returned"] = st.get("returned", 0) + 1
            daicho("in", cur["name"], ref=(pr or {}).get("url") or cur.get("url"),
                   thread="devin:" + str(cur["sid"]))
        st["done"] = st.get("done", []) + [cur]
        st["current"] = None
        say(st, "1本おわり：%s / %d分 / PR=%s / 返り=%s" % (cur["name"], mins, pr, got))
        launch(st)
    else:
        say(st, "まだ working：%s / %d分 / msgs=%d" % (cur["name"], mins, len(msgs)))
    save(st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
