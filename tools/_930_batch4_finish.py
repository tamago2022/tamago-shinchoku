#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""930番(4/7)の未反映分だけを仕上げる。
   726/796/802: 前回セッションが result には鬼監督PASSを書き込み済みだが
   status が awaiting_check のまま反映されていなかった。ここで status=done に確定する。
   884は現状(status=done)を維持するかどうか別途判断するため、ここでは触らない。
   719/731は既にholdNote付きでhold済みのため、ここでも触らない。
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(__file__))
import queue_store as qs

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
TARGET_DONE = {726, 796, 802}

q = qs.load_queue()
snap = qs.snapshot_items(q)
items = q["items"]

changed = []
for it in items:
    n = it.get("n")
    if n in TARGET_DONE and it.get("status") != "done":
        it["status"] = "done"
        it["finishedAt"] = now
        changed.append(n)

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok)
print("changed:", changed)
