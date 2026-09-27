#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1433番【優先度・候補を1回10〜20個まとめてリストで出す】

たまごさん（2026-09-18 08:48・原文）:
  「優先度、こういうのは全然次でもないんだよ…1回10個でも20個でもいいから…リストで出してみて」

意味:
  発車待ち（status/queue.json）を「次はこれ」と1件ずつ出すのではなく、
  まだ優先度が「普通（3＝未定）」のまま止まっている案件を、古い順に
  10〜20件まとめてリストにして出す。たまごさんはそれを見て、進捗表の
  「🚏 次に発車」にある各行のPボタン（A〜F）でまとめて優先度を付けられる
  （このタップ機構自体は2026-09-04/05に実装済み・本番稼働中）。

このツールが作るもの:
  - status/public/1433_yusen_kouho.json … 候補リスト（既定20件・再実行のたびに最新化）
  - 呼び出し元（見回り係・心臓）が好きなタイミングで再実行してよい。
    1回で出す件数は --n で変えられる（既定20、目安は10〜20）。

選び方（何を「候補」とするか）:
  status=="waiting" かつ priority==3（＝未定・普通のまま止まっている）を、
  番号(n)の古い順に並べる。1〜2（すでに急ぎと決めた）・4〜6（すでに後回しと決めた）は
  もう決定済みなので候補に出さない。
"""
from __future__ import annotations
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUEUE = os.path.join(REPO, "status", "queue.json")
OUT = os.path.join(REPO, "status", "public", "1433_yusen_kouho.json")

MITEI_PRIORITY = 3


def load_queue(path=QUEUE):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def build(n=20, queue_path=QUEUE, out_path=OUT):
    q = load_queue(queue_path)
    items = q.get("items") or []
    waiting = [it for it in items if it.get("status") == "waiting"]
    candidates = [it for it in waiting if it.get("priority") == MITEI_PRIORITY]
    candidates.sort(key=lambda it: it.get("n") or 0)

    picked = candidates[:n]
    rows = []
    for it in picked:
        rows.append({
            "n": it.get("n"),
            "title": it.get("title") or it.get("label") or "",
        })

    out = {
        "updatedAt": q.get("updatedAt"),
        "note": "1433番：優先度が未定(3)のまま止まっている案件を、古い順にn件まとめて出す候補リスト。"
                "「次はこれ」を1件ずつではなく、まとめて見て決めるためのもの。",
        "totalMitei": len(candidates),
        "totalWaiting": len(waiting),
        "shown": len(rows),
        "items": rows,
        "howToDecide": "進捗表(https://tamago2022.github.io/tamago-shinchoku/)の「🚏 次に発車」で、"
                        "この番号(n)の行にあるPボタンをタップして優先度(A〜F)を付ける。",
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = "%s.tmp.%d" % (out_path, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)
    return out


if __name__ == "__main__":
    n = 20
    for a in sys.argv[1:]:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
        elif a == "--n" and len(sys.argv) > sys.argv.index(a) + 1:
            n = int(sys.argv[sys.argv.index(a) + 1])
    result = build(n=n)
    print("候補 %d件（未定 %d件中／待機 %d件中）を書きました: %s" % (
        result["shown"], result["totalMitei"], result["totalWaiting"], OUT))
    for row in result["items"]:
        print(" -", row["n"], row["title"][:60])
