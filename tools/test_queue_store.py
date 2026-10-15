#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件#687：queue.json 777〜804番28件消失の再発防止チェック。

実測した事故：
  auto_launcher.py が queue_lock() を持ったまま長時間（git worktree作成・claude -p起動）
  queue.json を丸ごとメモリに抱え、最後に丸ごと書き戻す実装だった。その間に
  command_ingest.queue_add()（relay_server.py等からの直接呼び出し＝鍵を取らない経路）が
  新しい項目を追加すると、あとから戻ってきた丸ごと書き戻しでその追加分ごと消えていた。

このテストは、修理後の `tools/queue_store.py` が
  ① プロセスAが古いqueueを手元に持ったまま長時間かかる処理をしている間に、
     プロセスBが1件追加して保存しても、Aが最後に保存した時にBの追加が消えないこと
  ② 項目数が減る書き込みは拒否され、status/queue_write_blocked.jsonl に記録されること
の両方を実際に再現して確認する。python3 tools/test_queue_store.py で実行できる。
"""
import copy
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _fresh_env():
    """本物のstatus/queue.jsonに触らない、使い捨ての一時リポジトリを作ってqueue_storeを差し替える。"""
    tmp = tempfile.mkdtemp(prefix="queue_store_test_")
    os.makedirs(os.path.join(tmp, "status"))
    import queue_store
    import importlib
    importlib.reload(queue_store)
    queue_store.REPO = tmp
    queue_store.QUEUE = os.path.join(tmp, "status", "queue.json")
    queue_store.QUEUE_LOCK = os.path.join(tmp, "status", ".queue.lock")
    queue_store.BLOCKED_LOG = os.path.join(tmp, "status", "queue_write_blocked.jsonl")
    queue_store.HISTORY_DIR = os.path.join(tmp, "status", "queue_history")
    return tmp, queue_store


def test_concurrent_add_survives_stale_writeback():
    """① Aが古いqueueを抱えたまま、Bが1件追加→保存。その後Aが（Bの追加を知らないまま）保存しても、
    Bの追加が消えないこと。"""
    tmp, qs = _fresh_env()
    try:
        # 初期状態：3件
        initial = {"items": [{"n": 1, "title": "item1", "status": "waiting"},
                              {"n": 2, "title": "item2", "status": "waiting"},
                              {"n": 3, "title": "item3", "status": "waiting"}]}
        with open(qs.QUEUE, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False)

        # ---- プロセスA：読み込み（この後、長い処理をしている想定）----
        a_q = qs.load_queue()
        a_snapshot = qs.snapshot_items(a_q)

        # ---- プロセスB：（Aが処理している間に）新しい項目を1件追加して即保存----
        b_q = qs.load_queue()
        b_snapshot = qs.snapshot_items(b_q)
        b_q["items"].append({"n": 4, "title": "【dispatchが積んだ新規】item4", "status": "waiting"})
        ok = qs.save_queue(b_q, snapshot=b_snapshot)
        assert ok, "Bの保存が失敗した"

        # ---- プロセスA：自分が実際に触った項目(n=2をrunningに)だけ変更し、古いqを保存----
        for it in a_q["items"]:
            if it["n"] == 2:
                it["status"] = "running"
                it["pid"] = 12345
        ok = qs.save_queue(a_q, snapshot=a_snapshot)
        assert ok, "Aの保存が失敗した"

        # ---- 検証：Bが足した4番が消えていないこと。Aが変えた2番の変更も残っていること----
        disk = qs.load_queue()
        ns = sorted(it["n"] for it in disk["items"])
        assert ns == [1, 2, 3, 4], "4番（Bが積んだ項目）が消えている！ 実際の番号一覧: %s" % ns
        it2 = next(it for it in disk["items"] if it["n"] == 2)
        assert it2["status"] == "running" and it2.get("pid") == 12345, \
            "Aが自分で変更した2番の内容が失われている: %s" % it2
        it4 = next(it for it in disk["items"] if it["n"] == 4)
        assert it4["title"] == "【dispatchが積んだ新規】item4"
        print("PASS: ① 古いqueueを抱えたプロセスが最後に書き戻しても、他プロセスの追加は消えない")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_shrinking_write_is_blocked():
    """② 項目数が減る操作の安全性。

    このsave_queueは「merged はディスクの中身から出発し、deleted_ns に挙げた番号だけを
    間引く」構造にしてあるため、**deleted_nsを渡さない限りitemsが減ることは構造的に起きない**
    （うっかりitemsから漏れても、ディスク側の版がそのまま残る＝自己修復）。
    一方で queue_delete・queue_dedupe のような正当な削除は、deleted_ns で明示すれば
    そのとおりに反映される（削除機能そのものを壊さないことの確認）。
    さらに、queue_delete が2番を消している最中に、他プロセス（relay_server経由の
    queue_add等）が4番を新規に積んでも、両方の変更が正しく両立すること
    （＝787〜804番消失事故と同型の状況で、今回は削除も追加も両方生き残ることの確認）。
    """
    tmp, qs = _fresh_env()
    try:
        initial = {"items": [{"n": 1, "title": "item1", "status": "waiting"},
                              {"n": 2, "title": "item2", "status": "waiting"},
                              {"n": 3, "title": "item3", "status": "waiting"}]}
        with open(qs.QUEUE, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False)

        # ---- ②-a：2番を「うっかり」itemsから落としてしまったが、deleted_nsは渡さない。
        #      → 自分が削除を宣言していない項目なので、ディスク側の版がそのまま残る（自己修復）。----
        q = qs.load_queue()
        snapshot = qs.snapshot_items(q)
        q["items"] = [it for it in q["items"] if it["n"] != 2]
        ok = qs.save_queue(q, snapshot=snapshot)
        assert ok is True
        disk = qs.load_queue()
        ns = sorted(it["n"] for it in disk["items"])
        assert ns == [1, 2, 3], "deleted_nsを渡していないのに2番が消えてしまった: %s" % ns
        print("PASS: ②-a deleted_nsを渡さない限り、itemsから漏れただけでは消えない（自己修復）")

        # ---- ②-b：queue_delete相当（プロセスA）が2番の削除中に、
        #      別プロセスB（relay_server経由のqueue_add相当）が4番を新規追加する。
        #      → 削除(2番)と追加(4番)が両方とも正しく反映されること。----
        a_q = qs.load_queue()
        a_snapshot = qs.snapshot_items(a_q)
        a_q["items"] = [it for it in a_q["items"] if it["n"] != 2]  # Aは2番を消すつもり

        b_q = qs.load_queue()
        b_snapshot = qs.snapshot_items(b_q)
        b_q["items"].append({"n": 4, "title": "item4-added-concurrently", "status": "waiting"})
        assert qs.save_queue(b_q, snapshot=b_snapshot) is True  # Bが先に4番を保存

        ok2 = qs.save_queue(a_q, snapshot=a_snapshot, deleted_ns=[2])  # Aが後から2番の削除を保存
        assert ok2 is True, "正当な削除(deleted_ns=[2])が拒否されてしまった"

        disk2 = qs.load_queue()
        ns2 = sorted(it["n"] for it in disk2["items"])
        assert ns2 == [1, 3, 4], (
            "削除(2番)と並行追加(4番)の両立に失敗した: %s" % ns2)
        print("PASS: ②-b 削除(deleted_ns)と並行追加のどちらも取りこぼさない")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_untouched_item_changed_elsewhere_is_not_clobbered():
    """おまけ：自分が触っていない項目を、他プロセスが自分の読み込み後に変更していた場合は
    そちらの変更を採用する（自分の古い版で上書きしない）こと。"""
    tmp, qs = _fresh_env()
    try:
        initial = {"items": [{"n": 1, "title": "item1", "status": "waiting"}]}
        with open(qs.QUEUE, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False)

        a_q = qs.load_queue()
        a_snapshot = qs.snapshot_items(a_q)

        # 他プロセスがn=1を"done"に変えて保存
        b_q = qs.load_queue()
        b_snapshot = qs.snapshot_items(b_q)
        b_q["items"][0]["status"] = "done"
        assert qs.save_queue(b_q, snapshot=b_snapshot)

        # Aはn=1を一切触らずに（別件のupdatedAtだけ変えて）保存
        a_q["updatedAt"] = "dummy"
        assert qs.save_queue(a_q, snapshot=a_snapshot)

        disk = qs.load_queue()
        assert disk["items"][0]["status"] == "done", \
            "自分が触っていない項目なのに、古い版(waiting)で上書きしてしまった: %s" % disk["items"][0]
        print("PASS: ③ 自分が触っていない項目は、他プロセスの新しい変更を消さない")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_concurrent_add_survives_stale_writeback()
    test_shrinking_write_is_blocked()
    test_untouched_item_changed_elsewhere_is_not_clobbered()
    print("全テストPASS")
