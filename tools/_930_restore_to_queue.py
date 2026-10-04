#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""930番(4/7)：done_archive.jsonに埋もれてしまい「完了の門」(1141_kanryo_mon.py)の
再チェック対象からも外れている726/796/802を、queue.jsonへ戻す（安全な差分マージ経由）。
アーカイブ側からは同時に削除する（重複させない）。中身(what/result等)は一切変更しない。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import queue_store as qs

TARGET = {726, 796, 802}
REPO = "/Users/mac/tamago/tamago-shinchoku"
ARCHIVE = os.path.join(REPO, "status", "done_archive.json")

# 1) アーカイブから対象を取り出す
with io.open(ARCHIVE, encoding="utf-8") as f:
    arch = json.load(f)
arch_items = arch.get("items") or []
moving = [it for it in arch_items if it.get("n") in TARGET]
remaining = [it for it in arch_items if it.get("n") not in TARGET]
assert len(moving) == len(TARGET), f"見つかった数が想定と違う: {[it.get('n') for it in moving]}"

# 2) queue.jsonへ追加（差分マージ・既存項目は一切触らない）
q = qs.load_queue()
snap = qs.snapshot_items(q)
q["items"].extend(moving)
ok = qs.save_queue(q, snapshot=snap)
print("queue.jsonへ追加:", ok, [it.get("n") for it in moving])

if not ok:
    print("save_queue失敗。アーカイブ側は変更しません。")
    raise SystemExit(1)

# 3) アーカイブから削除（queue.json追加が成功した後だけ）
arch["items"] = remaining
tmp = ARCHIVE + ".tmp"
with io.open(tmp, "w", encoding="utf-8") as f:
    json.dump(arch, f, ensure_ascii=False, indent=1)
os.replace(tmp, ARCHIVE)
print("done_archive.jsonから削除完了。残り件数:", len(remaining))
