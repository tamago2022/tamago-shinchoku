#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""930番(4/7)棚卸し・2回目。

判明した事実：726/796/802/884はいずれも2026-09-17 16:37:47に
_930_oni_kantoku_batch4.pyでstatus=doneへ正しく確定させたが、後日
（7日以上経過）archive_done.pyがdone_archive.jsonへ移動した。
884だけは別セッションが再修正しstatus=doneを保っていたが、
726/796/802は移動後に何らかの経路でstatusがawaiting_checkへ巻き戻っており、
「生きているqueue.json」からも「アーカイブの一覧」からも実質見えない
確認待ちのゴーストになっていた（原因プロセスは特定できず、oni_modoshi.py/
verify_done.py/archive_done.py本体はいずれもdone_archive.jsonのstatusを
書き換えるコードを持たないことを確認済み）。

対応：930番棚卸し中に本番を再実測（726: queue_light.json 429KB配信を確認、
796/802: 確認ページ200・本文あり）した上で、3件のstatusをdoneへ再確定する。
done_archive.jsonを直接編集する専用の安全な書き込みが無いため、ここに限定して
1回だけ直接書く（対象は3件のstatus/finishedAtのみ・他は一切変更しない）。
"""
import fcntl
import io
import json
import os
import time
from contextlib import contextmanager

REPO = "/Users/mac/tamago/tamago-shinchoku"
ARCHIVE = os.path.join(REPO, "status", "done_archive.json")
LOCK = os.path.join(REPO, "status", ".queue.lock")
TARGET = {726, 796, 802}
NOW = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


@contextmanager
def queue_lock(timeout=30.0):
    f = io.open(LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                break
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


with queue_lock():
    with io.open(ARCHIVE, encoding="utf-8") as f:
        d = json.load(f)

    items = d.get("items") or []
    before_count = len(items)
    changed = []
    for it in items:
        n = it.get("n")
        if n in TARGET and it.get("status") != "done":
            it["status"] = "done"
            it["finishedAt"] = NOW
            it["result"] = (it.get("result") or "") + (
                "\n\n【930番棚卸し・2026-09-27再確定】done_archive.json内でstatusが"
                "awaiting_checkへ巻き戻っていたのを実測(726:queue_light.json 429KB配信"
                "/796・802:確認ページ200・本文あり)の上でdoneへ再確定。"
            )
            changed.append(n)

    after_count = len(items)
    assert before_count == after_count, "件数が変わってはいけない"

    tmp = ARCHIVE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ARCHIVE)

print("changed:", changed)
print("total items (unchanged count):", after_count)
