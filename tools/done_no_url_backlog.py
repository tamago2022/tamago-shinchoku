#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""679番：既存の完了済み(done)で urls が空のものを一覧化する。

たまごさん「既存の完了済みで urls が空のものを一覧にして、後から埋められるようにする」への対応。
668番で過去分の記録ミス(10本)は既に urls を復元済み・2本は証拠なしで waiting へ差し戻し済み
（status/failures.md の19番を参照）。本スクリプトはその後も同種の抜けが増えないよう、
いつでも再実行して現在の一覧を作り直せる「生きた台帳」として置く。

使い方: python3 tools/done_no_url_backlog.py
出力  : status/done_no_url_backlog.md（実行するたびに作り直す＝追記ではなく上書き）
"""
import io
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUEUE = os.path.join(REPO, "status", "queue.json")
OUT = os.path.join(REPO, "status", "done_no_url_backlog.md")


def main():
    q = json.load(io.open(QUEUE, encoding="utf-8"))
    items = q.get("items", []) if isinstance(q, dict) else q
    rows = [it for it in items if it.get("status") == "done" and not (it.get("urls") or [])]
    lines = [
        "# 完了済みで urls が空の一覧（679番・自動生成）",
        "",
        "`python3 tools/done_no_url_backlog.py` を実行するたびに作り直します。",
        "件数: %d件（%s 時点）" % (len(rows), time.strftime("%Y-%m-%d %H:%M")),
        "",
    ]
    if not rows:
        lines.append("いまは0件です。")
    for it in rows:
        n = it.get("n")
        title = it.get("title") or ""
        checked = it.get("checkedAt") or it.get("finishedAt") or ""
        lines.append("- #%s %s（%s）" % (n, title, checked))
    io.open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("wrote %s (%d rows)" % (OUT, len(rows)))


if __name__ == "__main__":
    main()
