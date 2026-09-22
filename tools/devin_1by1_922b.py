#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""9/22 第2便：Devinを1本ずつ回す係（得意な型＝「前提が正しいか実測で確かめてくれ」だけを投げる）。

第1便（tools/devin_1by1_922.py）の待ち行列A/B/Cが空になったので、新しい3本を積む。

実測に基づく作法（2026-09-20〜22）：
  ・3本同時＝30分で枠が尽きる。だから1本ずつ。
  ・Devinは詰まると「指示を待ちます」と書いて寝る。だから依頼文の先頭で禁じる。
  ・tamago-shinchoku へは push できない（Devin GitHub App 未導入・403）。
    読むのはできる。だから「答え＋diffを本文に貼れ」にする。PRは joy-relief-station のみ。
  ・こちらの見立ては渡さない。渡すのは症状と、ログの置き場所だけ。

使い方：status/mac_jobs/pending/ に札を置いて、Macから1回呼ぶ（叩くたびに1歩進む）。
触らないもの：オンデマンド購入・自動チャージ・請求。読むだけ。
"""
import json
import os
import time
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(REPO, "status", "devin_922b.json")
API = "https://api.devin.ai/v1"

RULE = """★★この仕事の進め方（最初に読んでください）★★
・途中で環境が壊れても、聞かずに自分で直してください。手を5つ試すまで止まらないでください。
・返事や相談を書かないでください。終わりの合図は、下の【終わりの合図】に書いた1通だけです。
・「指示を待ちます」「ご確認ください」「再開します」と書いてはいけません。
　依頼主は外出中で、誰も答えられません。書いても誰も読みません。
・迷ったら、あなたが妥当だと思う方を自分で選んで進めてください。
・こちらには見立てがありますが、わざと書きません。あなたが実測で出した答えだけが欲しいです。
・推測で順位を付けないでください。数字を出してから順位を付けてください。
━━━━━━━━━━━━━━━━━━━━━━━━

"""

JOB_D = """リポジトリ https://github.com/tamago2022/joy-relief-station を調べてください。

【症状】外部から（サイトの外側から）YouTubeの動画を1本追加しようとすると、
**途中で落ちることがあります。毎回ではありません。**同じ操作をしても、通る時と落ちる時があります。
落ちたときに何が起きているのか、こちらでは掴めていません。

【お願い】
1. まず「外部からYouTubeを1本追加する」経路が、このリポジトリのどのコードなのかを特定してください。
   （入口のスクリプト／APIハンドラ／ビルド時に走るもの、どれなのかを含めて）
2. その経路を **実際に複数回（最低10回）動かして**、落ちる／通るを数えてください。
   落ちた回の入力と、落ちた場所（ファイル名と行番号）を出してください。
3. 「毎回ではない」の正体を、実測で説明してください。
   何が違うと落ちるのか（入力の違い／順番／同時実行／外部への通信／キャッシュ／サイズ）を、
   数字（成功n回・失敗m回、バイト数、秒数）で示してください。

【終わりの合図】
このリポジトリには push できます。直せるものなら **Pull Request を1本** 出して、
そのURLだけを送ってください。PRの説明欄に「答え：」で始まる1行と、実測の数字を書いてください。
直すのが危ない（見た目や既存の動きが変わる）と判断したら、PRは作らず、
「答え：」で始まる1行＋実測の数字＋落ちた場所の行番号＋理由を、1通だけ送ってください。

【注意】見た目を変えないでください。このリポジトリを公開設定に変えないでください。
既存のデータを消さないでください。日本語で書いてください。
"""

JOB_E = """リポジトリ https://github.com/tamago2022/tamago-shinchoku を読んでください。

【症状】このリポジトリの上で、いくつもの処理が同時に git を触ります。
その結果 `.git/index.lock` の取り合いが起き、**コミットできずに詰まる処理が出ます。**
片付け係（tools/git_lock_reaper.py）が後から掃除していますが、取り合い自体は止まっていません。

【ログと痕跡の置き場所（リポジトリの中にあります）】
- status/failures.md の 420行目付近・461行目付近（過去に取り残した実例と、その時の対処）
- tools/git_lock_reaper.py の冒頭コメント（424,056バイトの index.lock と next-index-20.lock が残った経緯）
- tools/nikki_generator.py の 408〜455行目付近（古いlockを消してリトライする自前の処理）
- tools/command_ingest.py の 1130行目付近
- tools/_957_push.py の冒頭（Mac側で詰まったlockを外して溜まった分をpushする係）
- tools/launch_watchdog.py の 36行目付近
- tools/gaibu_runner.py の 77行目付近
- status/git_rebase_incidents.log

【お願い】
**index.lock の取り合いの根本原因を1つ**、実測で特定してください。
1. このリポジトリで git を触るプロセスを全部数え上げてください（ファイル名と、触る箇所の行番号の表）。
   どれが `git add` / `git commit` / `git update-ref` のような **index を掴む** 操作かを分けてください。
2. そのうち、**どれとどれが同時に走り得るのか**を、コードの筋道（起動元・間隔・ロックの有無）で示してください。
   「たぶん同時に走る」ではなく、「このコードだと必ずこの窓で重なる」という形で書いてください。
3. 重なりを生んでいる一番大きい原因を1つだけ選び、なぜそれが一番かを数字（本数・秒数・間隔）で示してください。

【終わりの合図】次の4つを書いた1通だけを送ってください。
1. 「答え：」で始まる1行（取り合いを起こしている一番大きい原因は何か）
2. gitを触るプロセスの一覧表（ファイル名・行番号・indexを掴むか否か・起動元・間隔）
3. 根拠（最低3か所の行番号と、重なる時間の窓）
4. 直し方（そのまま適用できる diff。1つだけ、最小で）

【注意】
- 何も削除しないでください。履歴の書き換え（filter-branch / filter-repo）は実行しないでください。
- このリポジトリへは push できません（403）。PRは作らなくていいです。
- push を試して時間を使わないでください。diffは本文に貼ってください。日本語で書いてください。
"""

JOB_F = """リポジトリ https://github.com/tamago2022/joy-relief-station を調べてください。

【症状】本番サイトのトップページが、まだ「重い・表示が出るまで待たされる」状態です。

【前提として渡しておくこと（これ以外の見立ては渡しません）】
- 未取り込みの Pull Request #455 が出ています。**#455 が触っている部分は、もう分かっているものとして扱ってください。**
- 知りたいのは、**#455 を取り込んだ後に残る重さのうち、一番大きいもの1つ**です。

【お願い】
1. #455 の中身を読んで、それが減らすバイト数／リクエスト数を数字で出してください。
2. その上で、**残る重さの最大の1つ**を実測で特定してください。
   ・根拠は必ず数字（バイト数／リクエスト数／ブロックしている秒数）。
   ・リポジトリの中身を実際に数えて出してください。推測で順位を付けないでください。
3. 2番目・3番目があるなら、数字だけ添えてください（直さなくていいです）。

【終わりの合図】
直せるものなら **Pull Request を1本** 出して、そのURLだけを送ってください
（#455 とは別の枝にしてください。#455 を取り込んだり閉じたりしないでください）。
PRの説明欄に「答え：」で始まる1行と、前後の数字を書いてください。
直すのが危ないと判断したら、PRは作らず「答え：」＋数字＋理由を1通だけ送ってください。

【注意】見た目を変えないでください。このリポジトリを公開設定に変えないでください。
他人のPRをマージしないでください。日本語で書いてください。
"""

QUEUE = [
    {"name": "D YouTube外部追加が時々落ちる", "prompt": JOB_D},
    {"name": "E index.lock取り合いの根本原因", "prompt": JOB_E},
    {"name": "F 455の後に残る重さ最大1つ", "prompt": JOB_F},
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
        return {"note": "9/22 第2便 Devin 1本ずつ。投げた数と返った数を両方数える。",
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
