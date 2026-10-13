#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""990番：Devinの「人の返事待ち」を自動で押し戻す係。

■ なぜ要るか（2026-09-20 実測）
  たまごさんの採点：15本投げて本番の画面が変わったのは1本（6.7%）。
  その原因を今日はじめて実測で掴んだ。**枠（週次上限）のせいではなかった。**
    10:33 3本を投げる → 3本とも2〜4分で status=finished / suspended、PRなし、成果ゼロ。
    「上限だろう」と思って既存セッションへ1行話しかけたら、**普通に返事が来た**：
      「システム再起動で計測用サーバー(wrangler dev)とシェルが落ちたため一時停止していました。
        指示があるまで再開は待ちます。」
  → Devinは詰まると**人に聞いて止まる**。誰も答えないと、そのまま finished になって終わる。
    たまごさんが外出していれば誰も答えない。＝**投げっぱなしだと必ずゼロになる。**
    6.7%の正体はこれ。能力ではなく、待ち方の問題。

■ 何をするか
  3分に1回、預かったセッションを見る。
    blocked（＝人待ち）なら「自分で決めて最後まで進めろ」と押し戻す。
    PRが出たら台帳へ記録して、そのセッションからは手を引く。
  新しい常駐は1つも増やさない。既存の使い走り窓口(status/mac_jobs)に自分を置き直して回る。

■ 止まるとき
  預かった全部が「PRあり」か「期限切れ」になったら、自分を置き直すのをやめる（＝自然に消える）。
"""
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(REPO, "status", "devin_babysitter.json")
REPORT = os.path.join(REPO, "status", "devin_990_report.md")
API = "https://api.devin.ai/v1"

NUDGE = (
    "再開してください。★以後、こちらへ確認を取らずに最後まで進めてください"
    "（依頼主は不在で、質問には誰も答えられません）。"
    "判断に迷ったら、あなたが妥当だと思う方を選んで進め、選んだ理由を最後の報告に1行で書いてください。"
    "途中で環境（サーバー・シェル）が落ちたら、止まらずに自分で立て直して続けてください。"
    "完了の条件は「Pull Requestが出ていること」と"
    "「依頼文の【報告してほしいこと】に数字で答えていること」の2つです。"
    "この2つが揃うまで止まらないでください。"
)


def key():
    p = os.path.join(REPO, ".env")
    for line in io.open(p, encoding="utf-8"):
        if line.startswith("DEVIN_API_KEY="):
            return line.strip().split("=", 1)[1]
    return None


def call(path, k, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method="POST" if data else "GET",
        headers={"Authorization": "Bearer " + k, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
            raw = r.read().decode("utf-8", "ignore")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        return {"_err": "%s %s" % (e.code, e.read().decode("utf-8", "ignore")[:200])}
    except Exception as e:
        return {"_err": repr(e)[:200]}


def load():
    try:
        return json.load(io.open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def save(st):
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(st, ensure_ascii=False, indent=1))
    os.replace(tmp, STATE)


def main():
    st = load()
    jobs = st.get("jobs") or {}
    if not jobs:
        print("預かっているものがありません")
        return 0
    if time.time() > st.get("deadline", 0):
        print("期限切れ。手を引きます")
        st["active"] = False
        save(st)
        return 0

    k = key()
    if not k:
        print("鍵なし")
        return 1

    rows = []
    alldone = True
    for sid, job in jobs.items():
        if job.get("pr"):
            rows.append(job)
            continue
        d = call("/session/devin-%s" % sid, k)
        if d.get("_err"):
            alldone = False
            job["last"] = "API: " + d["_err"]
            rows.append(job)
            continue
        se = d.get("status_enum")
        pr = (d.get("pull_request") or {}).get("url")
        ms = d.get("messages") or []
        last = ""
        for m in ms:
            if m.get("type") == "devin_message":
                last = str(m.get("message") or "")[:400]
        job["status"] = se
        job["msgs"] = len(ms)
        job["last"] = last
        if pr:
            job["pr"] = pr
            job["doneAt"] = time.strftime("%F %T")
            job["minutes"] = round((time.time() - job.get("startedTs", time.time())) / 60.0, 1)
            print("%s PRが出ました: %s" % (job["name"], pr))
        else:
            alldone = False
            # 人待ちで止まっている／勝手に終わってしまった → 押し戻す
            if se in ("blocked", "finished", "expired", "suspended"):
                n = job.get("nudges", 0)
                if n < 12:
                    r = call("/session/devin-%s/message" % sid, k, {"message": NUDGE})
                    job["nudges"] = n + 1
                    job["lastNudge"] = time.strftime("%F %T")
                    print("%s %s なので押し戻しました(%d回目) %s"
                          % (job["name"], se, n + 1, r.get("_err", "ok")))
        rows.append(job)

    st["jobs"] = jobs
    st["checkedAt"] = time.strftime("%F %T")
    st["active"] = not alldone
    save(st)

    # たまごさんが読む1枚
    with io.open(REPORT, "w", encoding="utf-8") as f:
        f.write("# 990番 Devin 3本の様子（%s 時点・自動更新）\n\n" % st["checkedAt"])
        f.write("| 仕事 | 状態 | 押し戻し | 何分 | PR |\n|---|---|---|---|---|\n")
        for j in rows:
            f.write("| %s | %s | %s回 | %s | %s |\n" % (
                j.get("name"), j.get("status") or "-", j.get("nudges", 0),
                j.get("minutes", "—"), j.get("pr") or "まだ"))
        f.write("\n## 最後にDevinが言ったこと\n\n")
        for j in rows:
            f.write("**%s**\n\n> %s\n\n" % (j.get("name"), (j.get("last") or "（なし）")))
    print("全部おわった: %s" % alldone)
    return 0


if __name__ == "__main__":
    sys.exit(main())
