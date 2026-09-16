#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
894番（2026-09-16）：発車沈黙（10分ルール）の検知＋自己修復を、heartbeat.sh本体の
15秒ループへ直接組み込むための軽量ラッパー。

背景（なぜ必要か）：
  発車0本が10分続いていないかの検知＋自己修復（status/.last_launch_at のmtime判定・
  心臓/5分便の蹴り直し・failures.md/dispatch_outboxへの記録）は既に
  tools/genzaichi.py の check_launch_silence() として797/798番で実装済みだった。
  しかし genzaichi.py 全体は「いまの現在地」7項目をまとめて作る重めの処理で、
  heartbeat.sh からは「実質30分おき」に間引いて呼ばれている（787/882番のコメント参照）。
  そのため、発車が10分止まっても、次にgenzaichi.pyが回ってくるまで
  最大約30分、検知・自己修復が発動しない穴があった。

  今回の894番「止まった瞬間に自分で立て直す」の合格条件（24時間で発車ゼロが10分を
  超えない）を満たすには、この判定自体を高頻度（15秒おきの心臓ループ）で回す必要がある。
  判定ロジックは車輪の再発明をせず genzaichi.py の関数をそのまま import して使う
  （二重実装・二重の状態ファイルを避ける。真実の源は status/.last_launch_at のまま）。

  check_launch_silence() 自身に「連続して赤の間は1回だけ記録する」抑制が入っているため、
  15秒おきに呼んでも failures.md・dispatch_outbox が連打されることはない。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import genzaichi  # noqa: E402


def main():
    try:
        genzaichi.check_launch_silence()
    except Exception:
        # ここが例外で落ちてheartbeat.shの15秒ループ自体を乱すのが一番損（894番の教訓：
        # 「測れないから止まる」が最悪）。何もせず静かに終わる。
        pass


if __name__ == "__main__":
    main()
