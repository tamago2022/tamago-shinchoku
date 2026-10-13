#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1372番：既存の「判定日赤」形式（優先度1・urgent）の待機項目に、
本文中の【言われた日時】から queuedAt を1回だけ補完するワンショット移行。

背景：1372番自身がpriority=1のまま2026-09-18〜09-27の9日間着火されず、
同種の114件が全件7〜10日待たされていた実測が出た。auto_launcher.pyの
緊急横入り枠（URGENT_WAIT_MIN=90分超過で+1本）はqueuedAtが無いと発動できない
（新規項目にはqueue_add()が付与するようにしたが、既存項目は付いていない）ため、
本当に長く待たされている既存項目にもすぐ効かせるための一度きりの補完。

実行後は消さずに残す（何をいつ移行したかの記録として。再実行しても、
既にqueuedAtがある項目はスキップするので安全＝冪等）。
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import queue_store  # noqa: E402

PAT = re.compile(r"言われた日時[】\]]\s*(\d{4})-(\d{2})-(\d{2}).*?(\d{2}):(\d{2})")


def main():
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        items = q.get("items") or []
        snap = queue_store.snapshot_items(q)
        touched = []
        for it in items:
            if it.get("status") != "waiting":
                continue
            if it.get("queuedAt"):
                continue
            what = it.get("what") or ""
            m = PAT.search(what)
            if not m:
                continue
            y, mo, d, h, mi = m.groups()
            ts = "%s-%s-%sT%s:%s:00+09:00" % (y, mo, d, h, mi)
            it["queuedAt"] = ts
            it["queuedAtSource"] = "1372backfill:言われた日時"
            touched.append((it.get("n"), ts))
        if touched:
            q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
            queue_store.save_queue(q, snapshot=snap)
        print("補完件数: %d" % len(touched))
        for n, ts in touched:
            print("  %s番 -> queuedAt=%s" % (n, ts))
        return len(touched)


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
