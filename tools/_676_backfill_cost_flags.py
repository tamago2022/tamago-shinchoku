#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件#676：既存タスクに一括で costsMoney / costEstimate を付ける（1回だけ実行するスクリプト）。

654番で作った costsMoney（発車待ちの赤字表示）は手打ちの33件にしか付いていなかった。
ここで全件を cost_risk.py の自動判定に通し、まだ人間が手で確定していないものだけ埋める
（すでに costsMoney が入っている項目は、手で確認済みの判定として上書きしない）。
"""
import fcntl
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cost_risk  # noqa: E402

QUEUE = os.path.join(REPO, "status", "queue.json")
QUEUE_LOCK = os.path.join(REPO, "status", ".queue.lock")


def main():
    f = io.open(QUEUE_LOCK, "a+")
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        q = json.load(io.open(QUEUE, encoding="utf-8"))
        items = q.get("items") or []
        changed = 0
        flagged = 0
        for it in items:
            already_set = "costsMoney" in it
            risk = cost_risk.is_cost_risk(it)
            if not already_set:
                if risk:
                    it["costsMoney"] = True
                    it["costEstimate"] = cost_risk.estimate_note(it)
                    changed += 1
            elif it.get("costsMoney") and not it.get("costEstimate"):
                it["costEstimate"] = cost_risk.estimate_note(it)
                changed += 1
            if it.get("costsMoney"):
                flagged += 1
        q["items"] = items
        q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
        tmp = QUEUE + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as out:
            json.dump(q, out, ensure_ascii=False, indent=1)
        os.replace(tmp, QUEUE)
        print("全%d件中・新規に印を付けた%d件・現在お金がかかる印つき%d件" % (len(items), changed, flagged))
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


if __name__ == "__main__":
    main()
