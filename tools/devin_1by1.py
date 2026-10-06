#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1003番：Devinを「1本ずつ」回す係。

なぜ1本ずつか（2026-09-20 実測）：
  10:33に3本同時に投げた → 30分でACUが尽き、3本とも凍った。PRゼロ。
  だから今日からは **1本走り切ってから次を投げる**。

使い方：
  status/mac_jobs/pending/ に置かれた札(a1003a/b)が3分に1回これを呼ぶ。
  今の1本を見て、終わっていたら結果を記録し、次の1本を投げる。
  待ち行列が空になったら自分で手を引く（札を置き直さない）。

触らないもの：オンデマンド購入・自動チャージ・請求。読むだけ。
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(REPO, "status", "devin_1by1.json")
API = "https://api.devin.ai/v1"

# ★前回の教訓：この作法は依頼文の「最初」に置く。後から言っても効かない。
RULE = """★★この仕事の進め方（最初に読んでください）★★
・途中で環境が壊れても、聞かずに自分で直してください。手を5つ試すまで止まらないでください。
・返事を書かないでください。終わりの合図は、PRのURLか、答えの1行だけです。
・「指示を待ちます」と書いてはいけません。依頼主は外出中で、誰も答えられません。
・迷ったら、あなたが妥当だと思う方を自分で選んで進めてください。
━━━━━━━━━━━━━━━━━━━━━━━━

"""

JOB_B = """リポジトリ https://github.com/tamago2022/tamago-shinchoku を調べてください。

【お題】share/check/ 以下のHTMLページで、CSSの「軸違いの%」を使っている箇所を全部見つけて直す。

【何が悪いのか】
バッジやアイコンの位置・余白を、コンテナに対する % で指定している箇所があります。
top を「高さの%」、left を「幅の%」で指定していると、画面の縦横比が変わったときに
バッジが伸びたり潰れたりズレたりします。これを min(◯cqw, ◯cqh) の形
（＝縦横のうち短い方を基準にする）へ直すと、どんな縦横比でも見た目の比率が崩れません。

【やること】
1. share/check/ 以下の全HTMLを走査し、バッジ・アイコンまわりの位置・余白指定で
   「軸違いの%」になっている箇所を洗い出す。
2. それを min(◯cqw, ◯cqh) へ置き換える。標準的な縦横比のときの見た目が変わらない数値にすること。
3. Pull Request を1本出す。

【報告してほしいこと（★必ず数字で）】
- 走査したファイル数 / 見つかった該当箇所の数 / 実際に直した箇所の数
- 直さなかった箇所があるなら、その数と理由

【注意】
- 標準的な縦横比での見た目は1ピクセルも変えないでください。
- 該当しないものまで巻き込んで置換しないでください。日本語で報告してください。
"""

JOB_C = """リポジトリ https://github.com/tamago2022/tamago-shinchoku を調べてください。

【お題】tools/ の中のスクリプトを全部読んで、棚卸しの表を作ってください。

【やること】
1. tools/ の中のスクリプトを全部読む。
2. 「用途」でグループ分けし、同じ用途のものが何本あるかを数える。
3. 「死んでいるもの」を特定する。死んでいる＝どこからも呼ばれていない、
   参照先のファイル・設定が存在しない、明らかに一度きりの使い捨て、など。
   なぜそう判断したのか、どこを検索して呼び出しが無かったかを必ず添える。

【出してほしいもの】
- 表① 用途別：用途 / 本数 / ファイル名の一覧 / 代表はどれか
- 表② 死活：ファイル名 / 生きている・死んでいる / 判断の根拠（1行）
- まとめ：同じ用途で重複している本数が一番多いのはどの用途で、何本か

【出し方】docs/ の下に Markdown で1枚置いて、Pull Request を出してください。

【注意】
- 推測で「死んでいる」と書かないでください。呼び出し元を実際に検索した結果だけで判断してください。
- 何も削除しないでください。日本語で報告してください。
"""

QUEUE = [
    {"name": "①一括置換 軸違いの%→min(cqw,cqh)", "prompt": JOB_B},
    {"name": "②コードの読解 tools/の棚卸し", "prompt": JOB_C},
]


def key():
    with open(os.path.join(REPO, ".env"), encoding="utf-8") as f:
        for line in f:
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
        return {"note": "Devinを1本ずつ回す台帳。3本同時は禁止（2026-09-20の事故）。",
                "active": True, "next": 0, "current": None, "done": [], "log": []}


def save(st):
    st["checkedAt"] = time.strftime("%F %T")
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def say(st, msg):
    st["log"] = (st.get("log") or [])[-40:] + [time.strftime("%F %T") + " " + msg]
    print(msg)


def launch(st):
    if st["next"] >= len(QUEUE):
        st["active"] = False
        say(st, "待ち行列が空になりました。1本ずつの係は手を引きます。")
        return
    job = QUEUE[st["next"]]
    code, res = call("/sessions", {"prompt": RULE + job["prompt"], "idempotent": False})
    if code != 200:
        say(st, "投げられませんでした HTTP=%s %s" % (code, str(res)[:160]))
        return
    st["current"] = {"name": job["name"], "sid": res.get("session_id"),
                     "url": res.get("url"), "startedTs": int(time.time()),
                     "startedAt": time.strftime("%F %T")}
    st["next"] += 1
    say(st, "投げました：%s → %s" % (job["name"], res.get("url")))


def main():
    st = load()
    if not st.get("active"):
        print("stop")
        return 9
    # 日をまたいだら手を引く
    if time.strftime("%Y%m%d") not in ("20260920", "20260921"):
        st["active"] = False
        say(st, "日が変わったので手を引きます。")
        save(st)
        return 9

    cur = st.get("current")
    if not cur:
        launch(st)
        save(st)
        return 0

    code, d = call("/session/" + cur["sid"], timeout=30)
    if code != 200:
        say(st, "様子が見られません HTTP=%s %s" % (code, str(d)[:120]))
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
        cur["last"] = str(msgs[-1].get("message") or "")[:300]

    if stt in ("finished", "blocked", "expired"):
        cur["finishedAt"] = time.strftime("%F %T")
        cur["minutes"] = mins
        st["done"] = st.get("done", []) + [cur]
        st["current"] = None
        say(st, "1本おわり：%s / %d分 / PR=%s" % (cur["name"], mins, pr))
        launch(st)
    else:
        say(st, "まだ working：%s / %d分 / msgs=%d" % (cur["name"], mins, len(msgs)))
    save(st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
