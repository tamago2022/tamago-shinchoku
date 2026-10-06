#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件#687の実際の事故経路そのものを再現する統合テスト。

実測した事故の経路：
  `tools/relay_server.py` は `command_ingest.queue_add()` を**直接**呼ぶ（`process()`の
  `with queue_lock():` を経由しない）。この経路には鍵が無かったため、
  `tools/auto_launcher.py` の `_main_impl()` が queue_lock を持ったまま長時間
  （git worktree作成・claude -p起動）queue.json を手元に抱えている間に
  `queue_add()` が割り込むと、auto_launcher側が最後に書き戻す時にqueue_add側の
  追加分ごと消えていた（777〜804番28件消失）。

このテストは `tools/test_queue_store.py`（内部ロジックの単体テスト）とは別に、
実際の `command_ingest.queue_add()` と `auto_launcher.save_queue()` を
（relay_server.py が呼ぶのと同じ形で）そのまま使って、同じ事故の型が
再発しないことを確認する。python3 tools/test_queue_rollback_regression.py で実行できる。
"""
import importlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _rebind(mod, tmp):
    """モジュールのREPO/QUEUE等のパス定数を、使い捨ての一時リポジトリへ差し替える。"""
    mod.REPO = tmp
    if hasattr(mod, "QUEUE"):
        mod.QUEUE = os.path.join(tmp, "status", "queue.json")
    if hasattr(mod, "QUEUE_LOCK"):
        mod.QUEUE_LOCK = os.path.join(tmp, "status", ".queue.lock")


def test_relay_server_style_direct_queue_add_survives_auto_launcher_stale_writeback():
    tmp = tempfile.mkdtemp(prefix="queue_rollback_regression_")
    try:
        os.makedirs(os.path.join(tmp, "status"))
        initial = {
            "updatedAt": "2026-09-13 10:00",
            "note": "test",
            "repo": "/tmp/does-not-matter",
            "items": [
                {"n": 793, "title": "既存の発車待ち", "status": "waiting",
                 "why": "x", "what": "x", "limitMin": 180, "model": "claude-sonnet-5"},
            ],
        }
        queue_path = os.path.join(tmp, "status", "queue.json")
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False)

        import queue_store
        importlib.reload(queue_store)
        _rebind(queue_store, tmp)

        import auto_launcher
        importlib.reload(auto_launcher)
        auto_launcher.queue_store = queue_store
        _rebind(auto_launcher, tmp)
        auto_launcher.QUEUE_LOCK = queue_store.QUEUE_LOCK
        auto_launcher.queue_lock = queue_store.queue_lock

        import command_ingest
        importlib.reload(command_ingest)
        command_ingest.queue_store = queue_store
        _rebind(command_ingest, tmp)
        command_ingest.QUEUE_LOCK = queue_store.QUEUE_LOCK
        command_ingest.queue_lock = queue_store.queue_lock

        # ---- auto_launcher側：queue_lock()を持ったまま長時間（git worktree作成・
        #      claude -p起動を模した重い処理）queueを手元に抱えているところを再現----
        q = auto_launcher.load(auto_launcher.QUEUE, {})
        snap = queue_store.snapshot_items(q)
        # ここで「重い処理」が起きている間に……

        # ---- relay_server.py が queue_add() を直接呼ぶ（鍵を経由しない実際の経路）----
        status, msg = command_ingest.queue_add(
            "【自動発車】発車待ちの794番です\n\n# やること\n【作り直し】案内所コンシェルジュ",
            priority=2, label="794番テスト", origin="user")
        assert status == "done", "queue_addが失敗した: %s" % msg

        # ---- auto_launcher側が（794番の存在を知らないまま）自分の変更(793番→running)を書き戻す----
        for it in q["items"]:
            if it["n"] == 793:
                it["status"] = "running"
                it["pid"] = 99999
                it["sessionId"] = "dummy-session"
        q["updatedAt"] = "2026-09-13 10:05"
        ok = auto_launcher.save_queue(q, snapshot=snap)
        assert ok, "auto_launcher.save_queueが失敗した"

        # ---- 検証：794番（queue_addで積んだ分）が消えていないこと。793番の変更も残ること。----
        disk = queue_store.load_queue()
        ns = sorted(it["n"] for it in disk["items"])
        assert 794 in ns, ("794番（relay_server経由でqueue_addが積んだ項目）が消えている！"
                            " 実際の番号一覧: %s" % ns)
        it793 = next(it for it in disk["items"] if it["n"] == 793)
        assert it793["status"] == "running" and it793.get("pid") == 99999, (
            "auto_launcher側が着火した793番の状態が失われている: %s" % it793)
        print("PASS: relay_server経由の直接queue_add()呼び出しが、"
              "auto_launcherの長時間保持からの書き戻しに巻き込まれて消えない")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_relay_server_style_direct_queue_add_survives_auto_launcher_stale_writeback()
    print("全テストPASS")
