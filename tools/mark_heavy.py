#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「重い」事象を記録する（2026-09-03）。固まった／ボタンが押せない／タブが切り替わらない／作業効率が落ちた、を
その瞬間の本数・負荷と一緒に status/heavy_events.jsonl に1行足す。calibrate.py がこれを上限のラインに使う。

  python3 mark_heavy.py "固まった"                 # 人（たまごさん／Dispatch）が記録
  python3 mark_heavy.py "タブが切り替わらない" --auto  # 機械の自動検知（factory_status から）
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MACHINE = os.path.join(REPO, "status", "machine.json")
OUT = os.path.join(REPO, "status", "heavy_events.jsonl")


def main():
    args = sys.argv[1:]
    what = next((a for a in args if not a.startswith("--")), "重い")
    top_cpu = ""
    if "--top-cpu" in args:
        i = args.index("--top-cpu")
        if i + 1 < len(args):
            top_cpu = args[i + 1]
    try:
        m = json.load(open(MACHINE, encoding="utf-8"))
    except Exception:
        m = {}
    row = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "what": what, "by": "auto" if "--auto" in args else "human",
           "n": m.get("sessions"), "working": m.get("working"),
           "loadRatio": round(m.get("load5") / m.get("cores"), 2) if m.get("load5") and m.get("cores") else None,
           "mem": m.get("memPressure"), "swapGB": m.get("swapGB"), "swapUp": m.get("swapIncreasing"), "ioMBs": m.get("ioMBs"),
           "topCpu": top_cpu or m.get("topCpu")}
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
