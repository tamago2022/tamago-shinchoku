#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1140番【毎日1回、全件を機械で流し直す常駐】

たまごさん（2026-09-25）:
  「毎日1回、全件を機械で流し直す常駐にする。新しく壊れたものが翌日には赤になる形。」

新しい launchd 常駐は作らない。既存の心臓（tools/heartbeat.sh・15秒おき）に相乗りし、
中で1日1回に間引く（daily_ingest_scheduler.py と同じ型をそのまま踏襲）。

やること（積むだけ。実際に走るのは工場側の gaibu_runner）:
  kind="kansei" / payload={"kensa": true}
    → tools/1140_jissoku.py  全動画IDを oEmbed で1件ずつ実測（回線があるのは工場側だけ）
    → tools/1140_kensa.py    全曲検査 → 隠す表 kanseiHidden.generated.ts を作り直す
    → GitHub の main に、変わったファイルだけ1コミットで入れる（Lovableが自動で配信）

二重投入防止: status/.1140_last_queued に最後に積んだ日付(JST)を書く。
"""
from __future__ import annotations
import os, sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
MARKER = os.path.join(ROOT, "status", ".1140_last_queued")
JST = timezone(timedelta(hours=9))


def main():
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if os.path.exists(MARKER):
        try:
            if open(MARKER, encoding="utf-8").read().strip() == today:
                return 0
        except Exception:
            pass
    import shigoto_queue
    jid = shigoto_queue.enqueue_job("kansei", {"kensa": True})
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    open(MARKER, "w", encoding="utf-8").write(today)
    print("1140番の流し直しを積みました: %s" % jid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
