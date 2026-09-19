#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""965番【仕事を振る】1つの形で、6社ぜんぶに仕事を出す。GitHubが仕事場。

たまごさん（2026-09-20・原文）:
  「とにかく全部とつながれるようにしておいて、全部に仕事を割り当てられるようにしておいて。
    チャッピーにも、Grokにも、Geminiにも、Genspark、Devinにも振れるようにしておいて。
    逆もできるように。Grokからクロードコードに指令がいけるようにもしといて。
    両方、一方通行にしないで。」

■ 行き（こちら → 他社AI）
    python3 tools/shigoto_furu.py gemini   "お題"
    python3 tools/shigoto_furu.py codex    "お題"
    python3 tools/shigoto_furu.py claude   "お題"
    python3 tools/shigoto_furu.py grok     "お題"
    python3 tools/shigoto_furu.py genspark "お題"
    python3 tools/shigoto_furu.py --mite 443     ← 返事が来ているか見る

  ★呼び方は**各社が公式に決めている形をそのまま使う。**こちらで発明しない。
      Gemini   … Issueに「jules」の札を貼る（jules.google/docs/running-tasks）
      ChatGPT  … Issueに「@codex」と書く（developers.openai.com/codex/integrations/github）
      Devin    … Issueに「@Devin」と書く（★有料。ACUを食うので既定では出さない）
      Claude   … Issueを立てるだけ。github_watch.py が拾って発車待ちへ積む
      Grok     … Issueに「grok」の札。向こうはGitHubアプリではないので、
                 たまごさんが画面で1行言うまで来ない（xAI公式「within a conversation」）
      Genspark … 同上（「genspark」の札）

■ 帰り（他社AI → こちら）★もう動いています。新しい常駐は1つも増やしていません。
    tools/github_watch.py が joy-relief-station を60秒ごとに見張っていて、
    **Issueでもコメントでも、新しく置かれたものを自動で「発車待ち」へ積みます。**
    実測：Jules が立てた PR #440 → 987番、PR #442 → 990番として、
    誰も何も言わないうちに列へ入りました。
    つまり、たまごさんがGrokに「クロードコードに言っといて」と言って
    Grokがここに書けば、そのまま作業列に入ります。

■ お金
    Gemini / ChatGPT / Grok / Genspark / Claude … **0円**（各社の月額の中）。
    Devin だけ ACU（従量）を食うので、既定では出しません。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gaibu_kuchi as gkuchi  # noqa: E402

REPO_NAME = "tamago2022/joy-relief-station"

# 社ごとの「呼び方」。全部、向こうが公式に決めている形。こちらの発明は1つも無い。
AITE = {
    "gemini":   {"label": "jules",    "mention": None,
                 "name": "Gemini(Jules)", "yen": 0, "auto": True,
                 "doc": "https://jules.google/docs/running-tasks/"},
    "codex":    {"label": "codex",    "mention": "@codex",
                 "name": "ChatGPT(Codex)", "yen": 0, "auto": True,
                 "doc": "https://developers.openai.com/codex/integrations/github"},
    "claude":   {"label": "claude",   "mention": None,
                 "name": "Claude Code", "yen": 0, "auto": True,
                 "doc": "tools/github_watch.py（こちらの見張り番）"},
    "grok":     {"label": "grok",     "mention": None,
                 "name": "Grok", "yen": 0, "auto": False,
                 "doc": "https://docs.x.ai/grok/connectors"},
    "genspark": {"label": "genspark", "mention": None,
                 "name": "Genspark", "yen": 0, "auto": False,
                 "doc": "https://www.genspark.ai/helpcenter/connectors-and-integrations"},
    "devin":    {"label": "devin",    "mention": "@Devin",
                 "name": "Devin", "yen": None, "auto": True,
                 "doc": "https://docs.devin.ai/"},
}
AITE["chatgpt"] = AITE["codex"]

HONBUN = """## 頼みたいこと（{name} へ）

{q}

## 書き方のお願い

- 先頭に名乗ってください（`{name}`）。
- 結論から書いてください。長い前置きは要りません。
- 事実（年号・料金・できる/できない）は**出典のURL**を添えてください。
  裏が取れなかったものは、埋めずに「取れなかった」と書いてください。
- 答えは**このIssueにコメントで直接**貼るか、`ai-brain/live/` に .md 1本を置いてPRにしてください。

## 返し方（大事）

ここに書かれたものは、こちらの見張り番が**60秒以内に拾って作業列へ入れます**。
たまごさんに「書いたよ」と言う必要はありません。**置けば届きます。**

---
*`tools/shigoto_furu.py` から自動で立てたお題。API代 0円。呼び方の出典: {doc}*
"""


def _job(payload, wait=240):
    return gkuchi.wait_job(gkuchi.enqueue_job("keijiban", payload), wait_sec=wait, poll=5) or \
        {"ok": False, "error": "工場からの返事が待ち切れませんでした"}


def furu(who, question, title=None):
    a = AITE[who]
    r = _job({"action": "issue", "repo": REPO_NAME,
              "title": title or ("【%sに頼む】%s" % (a["name"], question[:40])),
              "body": HONBUN.format(name=a["name"], q=question, doc=a["doc"]),
              "labels": [a["label"]]})
    if r.get("ok") and a["mention"]:
        _job({"action": "comment", "repo": REPO_NAME, "number": r["number"],
              "body": "%s 上のお題をお願いします。" % a["mention"]})
    return r


def mite(number):
    return _job({"action": "read", "repo": REPO_NAME, "number": number})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("who", nargs="?", choices=sorted(AITE.keys()))
    p.add_argument("question", nargs="?")
    p.add_argument("--title", default=None)
    p.add_argument("--mite", type=int, default=None)
    p.add_argument("--yes", action="store_true", help="Devinだけ。お金がかかるので明示が要る")
    a = p.parse_args()

    if a.mite:
        r = mite(a.mite)
        print(r.get("title", ""))
        for c in r.get("comments", []):
            print("-" * 50)
            print("%s（%s） %s" % (c["who"], c["type"], c["at"]))
            print(c["text"][:2500])
        if not r.get("comments"):
            print("（まだ誰も書いていません）")
        return

    if not a.who or not a.question:
        p.error("誰に何を頼むかを書いてください。例: python3 tools/shigoto_furu.py gemini \"…\"")

    if a.who == "devin" and not a.yes:
        print("Devin は ACU（従量課金）を食います。0円ではありません。")
        print("それでも出すなら --yes を付けてください。金額はDevinの画面で確認してください。")
        return

    r = furu(a.who, a.question, a.title)
    if not r.get("ok"):
        print("通りませんでした： %s" % r.get("error"))
        return

    info = AITE[a.who]
    print("お題を立てました： %s" % r.get("url"))
    print("返事を見る： python3 tools/shigoto_furu.py --mite %s" % r.get("number"))
    print("かかった金額： %s" % ("0円" if info["yen"] == 0 else "Devinの従量（ACU）"))
    if not info["auto"]:
        print("★%s はGitHubアプリではないので、自分からは見に来ません。" % info["name"])
        print("  たまごさんが向こうの画面でこの1行を言えば通ります：")
        print("  「joy-relief-station の Issue #%s を見て、そこにコメントで答えて」" % r.get("number"))


if __name__ == "__main__":
    main()
