#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
874番（2026-09-15）：週次利用上限（weekly limit）の誤stuck化からの一括復旧。

背景：2026-09-14 16:12〜2026-09-15 18:00の約26時間、"claude -p"の起動が
"You've hit your weekly limit"を1〜3秒で返し続けていたが、auto_launcher.py側に
この特別扱いが無かったため、59件の正常な仕事が「URLが1本も無いまま終了」という
通常失敗としてredo_guardに数えられ、そのままstuckへ落ちた（仕事の中身の問題ではない）。
恒久対策はauto_launcher.py本体に実装済み（今後は失敗として数えず列に戻る）。
本スクリプトは、既にstuckへ落ちてしまった「過去分」を安全に waiting へ戻す一回きりの復旧。

安全条件（この2つを両方満たす項目だけを対象にする。1つでも欠ければ何もしない）：
  1. status が "stuck"
  2. result に "weekly limit" を含む
  3. stuckReasonSummary が「URLが1本も無いまま終了」だけで構成されている
     （他の実質的な指摘が混ざっている項目＝例：820番は対象外のまま残す＝
      本当の不具合報告を握りつぶさないため）

冪等：対象が無くなれば毎回0件で終わる。何度実行しても安全。
"""
import io
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import queue_store  # noqa: E402


def _is_pure_weekly_limit_stuck(it):
    if it.get("status") != "stuck":
        return False
    if "weekly limit" not in (it.get("result") or ""):
        return False
    summary = (it.get("stuckReasonSummary") or "").strip()
    parts = [p.strip() for p in summary.split("／") if p.strip()]
    if not parts:
        return False
    return all(p == "URLが1本も無いまま終了" for p in parts)


def main():
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        items = q.get("items") or []
        snap = queue_store.snapshot_items(q)
        recovered = []
        for it in items:
            if not _is_pure_weekly_limit_stuck(it):
                continue
            n = it.get("n")
            recovered.append(n)
            it["status"] = "waiting"
            it["priority"] = it.get("priority") or 2
            it["what"] = (it.get("what") or "") + (
                "\n\n【874番・週次利用上限からの自動復旧・%s】"
                "前回の失敗は仕事の中身ではなく、Claudeの週次利用上限（weekly limit）に"
                "ぶつかっただけでした（auto_launcher.pyに恒久対策済み）。"
                "改めて最初から仕上げてください。"
                % time.strftime("%Y-%m-%d %H:%M")
            )
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt",
                      "redoCount", "failReasons", "stuckAt", "stuckReasonSummary",
                      "stuckRedoTotal"):
                it.pop(k, None)
            it.pop("pid", None)
        if recovered:
            queue_store.save_queue(q, snapshot=snap)
        print(json.dumps({"recovered_ns": recovered, "count": len(recovered)},
                          ensure_ascii=False))


if __name__ == "__main__":
    main()
