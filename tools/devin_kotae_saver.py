#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""9/22：Devinが返した答えを「紙」にして残す係（5分ごと・18時まで）。

なぜ要るか：
  ticker（tools/devin_ticker_922b.sh）の台帳は答えを1500字で切ってしまう。
  Devinの答えは本文が本体（PRが出ないことの方が多い）なので、
  APIから丸ごと取り直して status/public/1024_devin_kotae.md に置き直す。
  status/直下は .gitignore:39 で除外されるため、置き場所は必ず status/public/。

止め方：status/.devin_922b_stop を作る（tickerと同じ札で一緒に止まる）。
触らないもの：オンデマンド購入・自動チャージ・請求。読むだけ。
"""
import json
import os
import subprocess
import time
import urllib.request

REPO = os.path.expanduser("~/Desktop/tamago-shinchoku")
DST = os.path.join(REPO, "status", "public", "1024_devin_kotae.md")
LOG = os.path.join(REPO, "status", "devin_kotae_saver.log")
STOP = os.path.join(REPO, "status", ".devin_922b_stop")


def key():
    for line in open(os.path.join(REPO, ".env"), encoding="utf-8"):
        if line.startswith("DEVIN_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def say(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%F %T ") + m + "\n")


def get(sid):
    req = urllib.request.Request("https://api.devin.ai/v1/session/" + sid)
    req.add_header("Authorization", "Bearer " + key())
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": repr(e)}


def build():
    out = []
    for path, binname in [("status/devin_922.json", "第1便"),
                          ("status/devin_922b.json", "第2便")]:
        p = os.path.join(REPO, path)
        if not os.path.exists(p):
            continue
        try:
            st = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for x in st.get("done", []):
            d = get(x["sid"])
            # 実測（2026-09-22 09:37）：こちらの依頼文は type="initial_user_message"。
            # ここで拾ってしまうと「自分の依頼文を答えとして紙に貼る」ことになる。
            # Devinの発言は type == "devin_message" だけ。
            body = ""
            dev = [m for m in (d.get("messages") or [])
                   if str(m.get("type") or "") == "devin_message"]
            for m in reversed(dev):
                t = str(m.get("message") or "")
                if t.strip():
                    body = t
                    break
            if not body:
                body = "（Devinは一言も書かずに終わりました。枠切れの空振りの可能性があります）"
            out.append("## %s %s（%s分）\n\n- セッション: %s\n- PR: %s\n\n%s\n" % (
                binname, x.get("name"), x.get("minutes"), x.get("url"),
                (x.get("pr") or {}).get("url") or "なし", body))
    head = ("# 1024 Devinが実測で出した答え（9/22）\n\n"
            "※ こちらの見立ては一切渡していない。全部Devinが自分で測って出したもの。\n"
            "※ 返ってきたPRは中身を見てから扱う。**自動でマージしない。**\n\n"
            "（最終更新 %s・返ってきた本数 %d）\n\n" % (time.strftime("%F %T"), len(out)))
    return head + "\n---\n\n".join(out)


def commit():
    if os.path.exists(os.path.join(REPO, ".git", "index.lock")):
        say("index.lock があるのでコミットは見送り（消さない）")
        return
    for cmd in (["git", "add", "status/public/1024_devin_kotae.md"],
                ["git", "-c", "user.name=tamago-ai", "-c", "user.email=ai@tamago.local",
                 "commit", "-m", "1024 Devinの答えを紙に反映（自動）"],
                ["git", "push", "origin", "main"]):
        try:
            subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=120)
        except Exception as e:
            say("git失敗 %r" % e)
            return
    say("コミットしました")


def main():
    say("▶ 答え保存係 開始（18:00まで5分ごと）")
    last = ""
    while True:
        if os.path.exists(STOP):
            say("■ 停止札があったので終わります")
            break
        if int(time.strftime("%H%M")) >= 1800:
            say("■ 18:00になったので終わります")
            break
        try:
            body = build()
            core = body.split("\n\n", 3)[-1]
            if core != last:
                with open(DST, "w", encoding="utf-8") as f:
                    f.write(body)
                say("紙を更新しました（%d字）" % len(body))
                commit()
                last = core
        except Exception as e:
            say("失敗 %r" % e)
        time.sleep(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
