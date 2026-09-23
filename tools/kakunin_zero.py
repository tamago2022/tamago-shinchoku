#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""確認ゼロの関所 ― たまごさんに確認ポップアップを出させない仕組み

━━ なぜ作ったか（2026-09-25・たまごさん原文）━━
  「確認が相変わらず多いので、それを少なくしてほしい。」

━━ 決め（出してよい確認は4つだけ）━━
  ① 作り直せないデータの削除
  ② 課金（お金が動く）
  ③ 外部公開（世の中から見える所に出す）
  ④ パスワード／鍵の入力
  この4つ以外の確認は「仕組みで塞ぐ」。気をつけるでは塞がらない。

━━ この道具がやること ━━
  外へ出す指示文（引き継ぎ・Dispatchの指示・oneshotの票）を先に読んで、
  ★たまごさんにポップアップを出す命令が混ざっていたら、出す前に止める。

  python3 tools/kakunin_zero.py            # 全部見て、見つかった数を出す
  python3 tools/kakunin_zero.py <file>     # 1枚だけ見る（0=通す / 1=止める）
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# ★ここに載っているものは「たまごさんの画面にポップアップを出す」命令。
#   指示文の中に書いてあったら、その便は必ず止まる。
DAME = {
    "request_access": "コンピュータ操作の許可ダイアログが出る。→ 代わりに gsk / curl / gh / 心臓(oneshot) を使う",
    "request_cowork_directory": "フォルダ選択のダイアログが出る。→ 既に繋がっている /Users/mac/Desktop/tamago-shinchoku を使う",
    "request_teach_access": "画面操作の許可ダイアログが出る。→ 文章で手順を書く",
    "AskUserQuestion": "選択肢のポップアップが出る。→ 自分で決めて、決めた理由を報告に1行書く",
    "start_code_task": "別の許可を要求する。→ 使わない",
    "mcp__Claude_Browser__request_access": "内蔵ブラウザのサイト許可がページごとに出る。→ ブラウザを使わない道（gsk/curl/gh）に替える",
}
# 見に行く場所（外へ出る文章）
MIRU = [
    ("status", re.compile(r"(hikitsugi|引き継ぎ|dispatch|shiji|指示).*\.(md|txt|json)$", re.I)),
    (os.path.join("status", "oneshot", "pending"), re.compile(r"\.sh$")),
    (os.path.join("status", "mac_jobs", "pending"), re.compile(r"\.sh$")),
]


# 「使うな」と書いてある行は禁止の記述であって、命令ではない。数えない。
KINSHI = re.compile(r"(禁止|使わない|使わず|呼ばない|呼んでいない|呼ばず|触らない|使っていない|NG|不可|ダメ)")


def mitsukeru(text: str):
    hits = []
    for k, v in DAME.items():
        for line in text.splitlines():
            if k in line and not KINSHI.search(line):
                hits.append((k, v))
                break
    return hits


def one(path: str) -> int:
    try:
        t = open(path, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print("読めない: %s (%s)" % (path, e))
        return 0
    hits = mitsukeru(t)
    for k, v in hits:
        print("★止める %s ← 「%s」が書いてある。%s" % (path, k, v))
    return 1 if hits else 0


def main():
    if len(sys.argv) > 1:
        sys.exit(one(sys.argv[1]))
    n = 0
    mita = 0
    for base, pat in MIRU:
        root = os.path.join(REPO, base)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in (".git", "chrome-profile", "node_modules", "done", "queue_history")]
            for fn in filenames:
                if not pat.search(fn):
                    continue
                p = os.path.join(dirpath, fn)
                mita += 1
                n += one(p)
    print("見た紙 %d 枚 / ★ポップアップを出す命令が入っていた紙 %d 枚" % (mita, n))
    print("出してよい確認は4つだけ：①消す ②課金 ③外部公開 ④パスワード入力")
    sys.exit(0)


if __name__ == "__main__":
    main()
