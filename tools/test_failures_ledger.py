#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
failures_ledger.py の逆テスト（案件#813）。

「潰した」と自己申告するだけでは信用しない、という今回の本題（3条件の厳格化）を
実際にコードで壊して確認する。わざと不完全な失敗エントリを作り、それが赤(list_open)に
残ることを確認する。逆に3条件を全部揃えたエントリはlist_openから消えることも確認する。
再発検出（同じrootCauseキーワードが2回出てきたらrecurrenceが立つ）も同様に確認する。
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import failures_ledger as fl  # noqa: E402


def with_tmp_jsonl(fn):
    tmp = tempfile.mkdtemp(prefix="failures_ledger_test_")
    orig = fl.JSONL
    fl.JSONL = os.path.join(tmp, "failures.jsonl")
    try:
        fn()
    finally:
        fl.JSONL = orig
        shutil.rmtree(tmp, ignore_errors=True)


def test_incomplete_entry_stays_open():
    entry = {
        "id": "F-TEST-01",
        "date": "2026-09-14",
        "what": "テスト：直しただけでpreventedByが空",
        "howFound": "テスト",
        "rootCause": "テスト用のダミー原因 queue.json",
        "rootCauseEvidence": "実測ログのパス",
        "fixedBy": "コミットXXXX",
        # preventedBy / reverseTest をわざと入れない
    }
    fl.append_entry(entry, bump_recurrence_on_match=False)
    open_list = fl.list_open()
    ids = [e["id"] for e in open_list]
    assert "F-TEST-01" in ids, "preventedByが空なのに赤リストから漏れた（バグ）"
    print("PASS: preventedByが空のエントリは list_open（赤）に残る")


def test_complete_entry_is_not_open():
    entry = {
        "id": "F-TEST-02",
        "date": "2026-09-14",
        "what": "テスト：3条件を全部満たす",
        "howFound": "テスト",
        "rootCause": "テスト用のダミー原因 rendering",
        "rootCauseEvidence": "実測ログのパス",
        "fixedBy": "コミットYYYY",
        "preventedBy": "test_dummy.py",
        "reverseTest": "わざと壊して検出したことを確認済み（本テスト内で実施）",
    }
    fl.append_entry(entry, bump_recurrence_on_match=False)
    open_list = fl.list_open()
    ids = [e["id"] for e in open_list]
    assert "F-TEST-02" not in ids, "3条件揃っているのに赤リストに残った（バグ）"
    print("PASS: 3条件を満たすエントリは list_open（赤）から消える")


def test_recurrence_detected_on_shared_root_cause():
    e1 = {
        "id": "F-TEST-03",
        "date": "2026-09-01",
        "what": "1回目：queue.json wipe",
        "howFound": "テスト",
        "rootCause": "queue_lock 未取得 auto_launcher save_queue",
        "rootCauseEvidence": "根拠1",
    }
    e2 = {
        "id": "F-TEST-04",
        "date": "2026-09-14",
        "what": "2回目：同じ経路でqueue.jsonがまた壊れた",
        "howFound": "テスト",
        "rootCause": "queue_lock 未取得 auto_launcher save_queue（再発）",
        "rootCauseEvidence": "根拠2",
    }
    fl.append_entry(e1, bump_recurrence_on_match=True)
    saved2, sim = fl.append_entry(e2, bump_recurrence_on_match=True)
    assert sim, "同じrootCauseキーワードなのに似た失敗が見つからなかった（再発検出が壊れている）"
    assert saved2["recurrence"] >= 1, "再発なのにrecurrenceが立たなかった"
    print("PASS: 同じrootCauseキーワードの2件目はrecurrenceが立つ（一致語:", sim[0][1], "）")


def test_duplicate_id_rejected():
    entry = {
        "id": "F-TEST-05",
        "date": "2026-09-14",
        "what": "重複id拒否テスト",
        "howFound": "テスト",
        "rootCause": "dummy",
        "rootCauseEvidence": "dummy",
    }
    fl.append_entry(entry, bump_recurrence_on_match=False)
    try:
        fl.append_entry(entry, bump_recurrence_on_match=False)
        raise AssertionError("同じidの2回目追記がエラーにならなかった（台帳の丸ごと書き戻し事故を防げない）")
    except ValueError:
        print("PASS: 同じidの2回目追記はValueErrorで拒否される（差分追記のみ許可）")


def test_missing_required_field_rejected():
    entry = {
        "id": "F-TEST-06",
        "date": "2026-09-14",
        # what が無い
        "howFound": "テスト",
        "rootCause": "dummy",
    }
    try:
        fl.append_entry(entry, bump_recurrence_on_match=False)
        raise AssertionError("必須フィールド欠落なのに追記できてしまった")
    except ValueError:
        print("PASS: 必須フィールドが欠けたエントリは追記時に拒否される")


def run_all():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            with_tmp_jsonl(fn)
    print("全テストPASS")


if __name__ == "__main__":
    run_all()
