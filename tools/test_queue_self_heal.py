#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件#687・2026-09-13 18:55事故の再現テスト：271件→0件。

実測：`tools/verify_check_pages.py` が queue_store.py を経由せず、独自の
`with open(QUEUE, "w") as f: json.dump(d, f)` で直接書き込んでいた。この経路は
save_queue()の差分マージ・件数減少ガードを一切通らないため、何らかの理由で
d["items"]が空になった状態がそのまま書き込まれ、271件のqueue.jsonが0件（16バイト）
になった。世代バックアップ（queue_history/）のおかげでDispatchが手で復元できたが、
「件数が減る書き込みを禁止」という要件は、save_queue()を経由しない書き込みには
効いていなかった。

このテストは、queue_store.load_queue() 自身に組み込んだ自己修復
（件数がMIN_HEALTHY_ITEMS未満なら直近の健全な世代バックアップから自動で戻す）が、
save_queue()を一切経由しない直接書き込みからも実際に復旧できることを確認する。
python3 tools/test_queue_self_heal.py で実行できる。
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _fresh_env():
    tmp = tempfile.mkdtemp(prefix="queue_self_heal_test_")
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


def test_direct_unprotected_write_to_empty_self_heals_on_next_load():
    """verify_check_pages.py(修理前)の実際の事故手順そのものを再現する：
    ①正常な271件相当のqueue.jsonがあり、世代バックアップも1つ以上ある状態から、
    ②queue_store.pyを一切経由しない `open(QUEUE,"w")` で {"items": []} を直接書き込み、
    ③次に誰か(auto_launcher等)が queue_store.load_queue() で読みに来た瞬間に
    自動修復されることを確認する。"""
    tmp, qs = _fresh_env()
    try:
        healthy = {"items": [{"n": i, "title": "item%d" % i, "status": "waiting"} for i in range(1, 51)]}
        with open(qs.QUEUE, "w", encoding="utf-8") as f:
            json.dump(healthy, f, ensure_ascii=False)

        # 健全な世代バックアップを1つ作っておく（save_queue()経由の正常な保存を模す）
        snap = qs.snapshot_items(qs.load_queue())
        q = qs.load_queue()
        q["items"][0]["status"] = "running"
        assert qs.save_queue(q, snapshot=snap) is True
        assert len(qs.load_queue()["items"]) == 50

        # ---- 事故の再現：queue_store.pyを経由しない直接の丸ごと上書きで0件にする ----
        # （verify_check_pages.py修理前の `with open(QUEUE,"w") as f: json.dump(d, f)` と同じ形）
        with io.open(qs.QUEUE, "w", encoding="utf-8") as f:
            json.dump({"items": []}, f, ensure_ascii=False)

        # 直接ファイルを見ると、たしかに0件に壊れている（これが事故の瞬間）
        with io.open(qs.QUEUE, encoding="utf-8") as f:
            broken = json.load(f)
        assert broken["items"] == [], "前提が崩れている：事故を再現できていない"

        # ---- 次に誰かがload_queue()で読みに来た瞬間、自己修復が働くこと ----
        healed = qs.load_queue()
        assert len(healed["items"]) == 50, (
            "自己修復が働かず、0件のまま返ってきた: %d件" % len(healed["items"]))

        # ディスク上のqueue.json自体も直っていること（次の読者も0件を踏まない）
        with io.open(qs.QUEUE, encoding="utf-8") as f:
            disk_after = json.load(f)
        assert len(disk_after["items"]) == 50, "ディスク上のqueue.json自体は直っていない"

        # 壊れていた0件の中身は証拠として退避されていること
        empties = [p for p in os.listdir(os.path.join(tmp, "status")) if p.startswith("queue.json.EMPTY-")]
        assert empties, "壊れていた内容の退避（queue.json.EMPTY-*）が残っていない"

        print("PASS: save_queue()を経由しない直接書き込みで0件に壊れても、"
              "次のload_queue()で自動修復される")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_save_queue_refuses_to_go_below_floor_even_with_bad_deleted_ns():
    """呼び出し側のバグでdeleted_nsに大量の番号が誤って入っていても、
    結果がMIN_HEALTHY_ITEMS未満になるならsave_queue自体が書き込みを拒否すること
    （絶対安全弁・件数の説明が付いていても異常に少なければ通さない）。"""
    tmp, qs = _fresh_env()
    try:
        healthy = {"items": [{"n": i, "title": "item%d" % i, "status": "waiting"} for i in range(1, 51)]}
        with open(qs.QUEUE, "w", encoding="utf-8") as f:
            json.dump(healthy, f, ensure_ascii=False)

        q = qs.load_queue()
        snap = qs.snapshot_items(q)
        q["items"] = []  # 全部消したつもり
        all_ns = list(range(1, 51))
        ok = qs.save_queue(q, snapshot=snap, deleted_ns=all_ns)  # 全件をdeleted_nsで「説明」しても
        assert ok is False, "50件全消しがdeleted_nsで説明されただけで通ってしまった"

        disk = qs.load_queue()
        assert len(disk["items"]) == 50, "拒否したはずなのにディスクが変わっている"
        print("PASS: deleted_nsで説明されていても、MIN_HEALTHY_ITEMSを割る書き込みは拒否される")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_direct_unprotected_write_to_empty_self_heals_on_next_load()
    test_save_queue_refuses_to_go_below_floor_even_with_bad_deleted_ns()
    print("全テストPASS")
