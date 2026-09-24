#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""969番の関所：**たまごさんに頼む前に、必ずここを通る。**

たまごさん（2026-09-20）：
  「セッションがたまごさんに情報や操作を頼もうとしたら、先にこの台帳を見る。
    台帳に『ある』と書いてあれば、頼まずにそれを使う。」

今日の実害：
  本人のChromeにはログイン済みのタブがあったのに、**それを見もせず**
  「無いので用意してください」とたまごさんに頼んだ。
  たまごさんは外出中で、頼まれても押せない。工場はその間ずっと止まる。

使い方（人もAIも同じ）：
    python3 tools/kagi_gate.py "Lovableにログインしてほしい"
    python3 tools/kagi_gate.py --list

返す答えは3つだけ：
    HAVE  … 台帳にある。頼まずにこれを使え（＝頼むのは禁止）
    NEED  … 台帳にあるが今は通っていない。本人にしかできない1点だけを、この1行で頼め
    UNKNOWN … 台帳に無い。まず台帳に足してから考えろ（＝いきなり頼むな）
終了コード：HAVE=0 / NEED=2 / UNKNOWN=3
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DAICHO = os.path.join(REPO, "status", "public", "kagi_daicho.json")

# 言葉 → 台帳の項目。頼みごとの言い回しは揺れるので、広めに拾う。
WORDS = {
    "claude": ["claude", "クロード", "ログイン", "認証", "発車できない", "oauth", "トークン"],
    "gmail": ["gmail", "メール", "imap", "受信", "返信を見", "アプリパスワード"],
    "github": ["github", "ギットハブ", "issue", "プッシュ", "push", "リポジトリ"],
    "openai": ["openai", "chatgpt", "チャッピー", "gpt"],
    "gemini": ["gemini", "ジェミニ", "google ai"],
    "xai": ["grok", "グロック", "xai", "x.ai"],
    "fal": ["fal", "画像生成", "動画生成", "ナノバナナ", "nano-banana"],
    "devin": ["devin", "デヴィン", "デビン"],
    "lovable": ["lovable", "ラバブル", "本番に出", "公開して", "デプロイ"],
    "heart": ["心臓", "heartbeat", "常駐"],
    "gobun": ["5分便", "launchd", "machine_status"],
    "hassha": ["発車", "着火", "キュー", "queue"],
    "relay": ["中継", "relay", "ボタンが効かない", "スマホから"],
}

# 鍵ではないが「もう持っているもの」。今日の事故（本人のChromeを見ずに頼んだ）を止める。
ALREADY_HAVE = {
    "chrome": (["chrome", "クローム", "ブラウザ", "タブ", "ログイン済み"],
               "たまごさんのChromeは既にログイン済みです。"
               "claude-in-chrome のツールで**自分で見に行けます**。"
               "『用意してください』は禁止。まず tabs_context で今あるタブを見ること。"),
    "folder": (["フォルダ", "ファイルを見せて", "パスを教えて", "どこにある"],
               "/Users/mac/Desktop/tamago-shinchoku は既にマウント済みです。"
               "自分で ls して探すこと。たまごさんに場所を聞かない。"),
    "buffer": (["buffer", "バッファー", "予約投稿", "xに予約", "bufferにログイン"],
               "Bufferに「ログインして」と頼むのは**禁止**。"
               "鍵は ~/.tamago/keys/api_keys.env の BUFFER_ACCESS_TOKEN にあります。"
               "予約は status/buffer_queue/ に注文票(JSON)を1枚置くだけ："
               "5分便が tools/buffer_yoyaku.py を回して予約を入れ、"
               "予約一覧で照合した結果を status/buffer_queue/done/ に書き戻します。"
               "鍵がまだ無いときだけ、**1回きり**『publish.buffer.com/settings/api で"
               "鍵を作って ~/Desktop/buffer_token.txt に貼る』を頼む。"
               "★『ログインして』の形では二度と頼まない。",),
    "mac": (["ターミナル", "コマンドを打って", "実行して"],
            "5分便(machine_status_push.sh)と心臓(heartbeat.sh)が"
            "リポジトリの中のスクリプトを勝手に拾って走らせます。"
            "たまごさんにターミナルを開かせない。"),
}


def load_daicho():
    try:
        with io.open(DAICHO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def check(text):
    t = (text or "").lower()
    for _id, (words, msg) in ALREADY_HAVE.items():
        for w in words:
            if w in t:
                return "HAVE", msg
    d = load_daicho()
    rows = {r.get("id"): r for r in d.get("rows", [])}
    if d.get("notMeasuredYet") or not rows:
        return "UNKNOWN", ("台帳がまだ1回も実測していません。"
                           "`python3 tools/kagi_daicho.py --force` を先に通すこと。")
    for _id, words in WORDS.items():
        for w in words:
            if w in t:
                r = rows.get(_id)
                if not r:
                    continue
                if r.get("status") == "ok":
                    return "HAVE", ("【%s】は**今、叩いて通っています**（%s）。"
                                    "置き場は %s。頼まずにこれを使ってください。"
                                    % (r["what"], r["detail"], r["where"]))
                if r.get("status") == "ng":
                    return "NEED", ("【%s】は通っていません（%s）。"
                                    "止まるもの：%s ／ 本人にしかできない1点：%s"
                                    % (r["what"], r["detail"], r["stops"], r["fix"]))
                return "UNKNOWN", ("【%s】はまだ実測できていません（%s）。"
                                   "頼む前に、まず実測すること。"
                                   % (r["what"], r["detail"]))
    return "UNKNOWN", ("台帳に載っていません。いきなりたまごさんに頼まないこと。"
                       "tools/kagi_daicho.py の LEDGER に足してから、実測して判断する。")


def main():
    args = [a for a in sys.argv[1:] if a != "--list"]
    if "--list" in sys.argv:
        d = load_daicho()
        if d.get("notMeasuredYet"):
            print("台帳はまだ実測していません。")
            return 3
        for r in d.get("rows", []):
            mark = {"ok": "○ 使える", "ng": "✕ 切れている"}.get(r.get("status"), "△ 未実測")
            print("%-10s %-26s %s" % (mark, r.get("what", "")[:26], r.get("detail", "")))
        return 0
    if not args:
        print(__doc__)
        return 3
    kind, msg = check(" ".join(args))
    print("%s: %s" % (kind, msg))
    return {"HAVE": 0, "NEED": 2}.get(kind, 3)


if __name__ == "__main__":
    sys.exit(main())
