#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""930番(4/7)：726/796/802をdone_archive.jsonから読み、queue.jsonへ複製する（追加のみ・削除しない）。
   verify_check_pages.pyがqueue.json側しか見ないための一時的な措置。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import queue_store as qs

TARGET = {726, 796, 802}
REPO = "/Users/mac/Desktop/tamago-shinchoku"
ARCHIVE = os.path.join(REPO, "status", "done_archive.json")

with io.open(ARCHIVE, encoding="utf-8") as f:
    arch = json.load(f)
moving = [it for it in (arch.get("items") or []) if it.get("n") in TARGET]
print("found in archive:", [it.get("n") for it in moving])

q = qs.load_queue()
existing_ns = {it.get("n") for it in q["items"]}
snap = qs.snapshot_items(q)
added = []
for it in moving:
    if it.get("n") not in existing_ns:
        q["items"].append(it)
        added.append(it.get("n"))

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok, "added:", added)
