#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""965番【Geminiに仕事を出す】0円。たまごさんのコピペをゼロにするための1行。

たまごさん（2026-09-20・原文）:
  「俺がわざわざ『これジェミニどんな感じ？』と聞いて、ジェミニが出してきたものを
    俺がコピペしてあなたに貼る。もうそういうのはゼロにしたい。」

■ 使い方（サンドボックスからでも工場からでも同じ）
    python3 tools/gemini_ni_tanomu.py "日本のカバー曲紹介サイトで今いちばん伸びているのはどこか"
    python3 tools/gemini_ni_tanomu.py --mite 439        # 返事が来ているか見る

■ 何が起きるか
  1. GitHubに「お題」を1本立てて、Jules（Gemini）の札を貼る
  2. Jules が自分で取りに来て、調べて、答えをファイルにして PR で返す
     （実測：お題を置いてから5秒で返事、9分44秒で提出）
  3. こちらは PR を読むだけ。**たまごさんは1文字もコピペしない**

■ お金
  0円。GitHub REST API は無料で、Jules は Google の月額（無料枠でも1日15本）の中で動く。
  従量課金（API代）は1円も発生しない。

■ 向いていない仕事
  その場で人が待っている会話。1〜2秒で返らないと成立しないものは API を払うしかない。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402

REPO_NAME = "tamago2022/joy-relief-station"

TEMPLATE = """## 頼みたいこと

{q}

## 書き方のお願い

- 名乗ってください（`Gemini(Jules)`）。
- 調べた結果は **`ai-brain/live/` の中に .md ファイル1本** にして提出してください。
- 事実（年号・料金・できる/できない）は、**出典のURL**を必ず添えてください。
  裏が取れなかったものは、埋めずに「取れなかった」と書いてください。
- 長い前置きは要りません。結論から書いてください。

---
*`tools/gemini_ni_tanomu.py` から自動で立てたお題。API代 0円。*
"""


def tanomu(question, title=None):
    payload = {
        "action": "issue",
        "repo": REPO_NAME,
        "title": title or ("【Geminiに頼む】" + question[:48]),
        "body": TEMPLATE.format(q=question),
        "labels": ["jules"],
    }
    jid = gkuchi.enqueue_job("keijiban", payload)
    return gkuchi.wait_job(jid, wait_sec=300, poll=5)


def mite(number):
    jid = gkuchi.enqueue_job("keijiban", {"action": "read", "repo": REPO_NAME, "number": number})
    return gkuchi.wait_job(jid, wait_sec=300, poll=5)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="?", help="Geminiに頼みたいこと（1文でよい）")
    p.add_argument("--title", default=None)
    p.add_argument("--mite", type=int, default=None, help="お題の番号。返事が来ているか見る")
    a = p.parse_args()

    if a.mite:
        r = mite(a.mite)
        print(r.get("title", ""))
        for c in r.get("comments", []):
            print("-" * 40)
            print("%s（%s） %s" % (c["who"], c["type"], c["at"]))
            print(c["text"][:2000])
        return

    if not a.question:
        p.error("頼みたいことを書いてください")

    r = tanomu(a.question, a.title)
    if r.get("ok"):
        print("お題を立てました： %s" % r.get("url"))
        print("返事を見る： python3 tools/gemini_ni_tanomu.py --mite %s" % r.get("number"))
        print("かかった金額： 0円")
    else:
        print("通りませんでした： %s" % r.get("error"))


if __name__ == "__main__":
    main()
