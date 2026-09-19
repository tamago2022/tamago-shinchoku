#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""933番(7/7)：hold 711・745を1回見直し、生きているか/畳んだままにするかを判定してqueue.jsonへ反映する。
   直接queue.jsonを書かず、queue_store.py経由(差分マージ・世代バックアップ付き)で書く。
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(__file__))
import queue_store as qs

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

NOTES = {
    711: (
        "【933番棚卸し・2026-09-17再確認】710番(Måneskin単曲・見本)を確認したところ、"
        "710は今も status=hold のまま（たまごさん本人の指示『工場を発射しないでください。後で見るからね』"
        "が2026-09-10時点から未解除、ai-brain/kettei.jsonにも解除の決定記録なし）。"
        "711は『710のOK後』という明示条件付きのため、710未OKの今は再開(waiting)へ戻さず"
        "hold継続が正しい判断。案件自体は生きている（30曲分の素材台帳は確定済み・破棄しない）。"
        "710がOKになった時点で最優先に再開する。"
    ),
    745: (
        "【933番棚卸し・2026-09-17再確認】2026-09-12にLINEスタンプ制作全体をCodex側へ移管済み、"
        "『たまごさんから「やっぱりお願いします」が来たら再開する』が現行方針のため、本工場側では"
        "引き続き対象外（不要ではないが現在は停止中）。59円のfal生成は未実行のまま・上限枠(costApproved)"
        "も現状維持。再開トリガーが来るまでhold継続。"
    ),
}

q = qs.load_queue()
snap = qs.snapshot_items(q)
items = q["items"]

changed = []
for it in items:
    n = it.get("n")
    if n in NOTES:
        it["status"] = "hold"
        it["blockedNote"] = NOTES[n]
        it["holdReviewedAt"] = now
        changed.append(n)

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok)
for n in changed:
    print("n=", n, "-> hold(理由更新)")
