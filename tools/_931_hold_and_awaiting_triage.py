#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""931番(5/7)：hold 9件を1回だけ見直し、生き返らせるものと畳んだままにするものを分ける。
   直接queue.jsonを書かず、queue_store.py経由(差分マージ・世代バックアップ付き)で書く。

   容量条件チェック(2026-09-17実測): df -h / → 空き21GiB。
   「容量が20GBに戻ったら列へ戻す」というholdNoteが付いた6件は条件クリア→再開対象。
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import queue_store as qs

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
NOTE_PREFIX = "【931番棚卸し・2026-09-17】"

# 生きている→再開(waiting)。holdNoteの理由(容量20GB/実装未完了)は解消済みと判断。
REOPEN = {
    6: NOTE_PREFIX + "前回セッションはバックグラウンド待ちで実装未完了のまま終了(resultも空欄)。"
        "生きている案件のため再開。次は同期実行(timeout付き・前で待つ)で最後まで実装すること。",
    42: NOTE_PREFIX + "容量条件(20GB)は空き21GiBで実測クリア。ただし09-06に鬼監督から"
        "「確認ページに実物スクショ(<img>)が無い」で差し戻し済み・未解決のまま。"
        "生きている案件のため再開。次はブラウザ内蔵スクショを確認ページに貼ってから再提出すること。",
    157: NOTE_PREFIX + "容量条件(20GB)は空き21GiBで実測クリア。生きている案件のため再開。",
    469: NOTE_PREFIX + "容量条件(20GB)は空き21GiBで実測クリア。生きている案件のため再開。",
    470: NOTE_PREFIX + "容量条件(20GB)は空き21GiBで実測クリア。生きている案件のため再開。",
    486: NOTE_PREFIX + "容量条件(20GB)は空き21GiBで実測クリア。生きている案件のため再開。",
    487: NOTE_PREFIX + "容量条件(20GB)は空き21GiBで実測クリア。生きている案件のため再開。",
}

# もう要らない/トリガー未発生→hold継続。holdNote自体は変えず、確認済みログだけ追記。
HOLD_KEEP_LOG = {
    1: NOTE_PREFIX + "棚卸し確認済み。再開条件(画像が出ないページの実例URL)がまだ発生していないため"
        "hold継続が妥当。既存のholdNote「出ないページに出くわしたときに確認する」は変更しない。",
    30: NOTE_PREFIX + "棚卸し確認済み。たまごさん本人が2026-09-04に見回り継続を明言し依頼自体が"
        "撤回済み(既にholdNoteが「取り消し」)。運用は変更なく継続稼働中のためhold継続が妥当。",
}

q = qs.load_queue()
snap = qs.snapshot_items(q)
items = q["items"]

changed = []
for it in items:
    n = it.get("n")
    if n in REOPEN:
        it["status"] = "waiting"
        prev_note = it.get("holdNote") or ""
        it["holdNote"] = None
        it["reopenNote"] = REOPEN[n]
        it["reopenedAt"] = now
        changed.append((n, "waiting"))
    elif n in HOLD_KEEP_LOG:
        prev = it.get("holdReviewLog") or ""
        it["holdReviewLog"] = (prev + "\n\n" if prev else "") + HOLD_KEEP_LOG[n]
        changed.append((n, "hold(継続)"))

ok = qs.save_queue(q, snapshot=snap)
print("save_queue ok:", ok)
for n, st in changed:
    print(f"n={n} -> {st}")
