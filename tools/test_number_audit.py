#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
795番：number_audit.py の逆テスト（緑は無実の証明ではない。わざと矛盾を仕込んで赤を確認する）。

一時ディレクトリに status/quota.json と status/pace.json を作り、
weekdayTargetBase と lineTarget をわざと大きくズラして conflict が検出されることを確認する。
続けて、一致させたケースでは conflict にならないことも確認する（両側テスト）。

使い方: python3 tools/test_number_audit.py
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import number_audit  # noqa: E402


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def run():
    orig_repo = number_audit.REPO
    tmp = tempfile.mkdtemp(prefix="number_audit_test_")
    try:
        number_audit.REPO = tmp

        # ケース1：わざとズラす（91 vs 60 → diff 31 > tolerance 0.6 のはず）
        _write(os.path.join(tmp, "status", "quota.json"), {"weekdayTargetBase": 91.0})
        _write(os.path.join(tmp, "status", "pace.json"), {"lineTarget": 60.0})
        out = number_audit.run_audit(pairs=[number_audit.GUARD_PAIRS[0]])
        week = out["results"][0]
        assert week["status"] == "conflict", "矛盾を仕込んだのにconflictが出なかった: %r" % week
        assert out["conflictCount"] == 1, "conflictCount が想定と違う: %r" % out
        print("PASS: わざとズラしたケース → conflict を検出した（%s）" % week["note"])

        # ケース2：一致させる（許容差0.6以内）→ ok になるはず
        _write(os.path.join(tmp, "status", "pace.json"), {"lineTarget": 91.0})
        out2 = number_audit.run_audit(pairs=[number_audit.GUARD_PAIRS[0]])
        week2 = out2["results"][0]
        assert week2["status"] == "ok", "一致させたのにconflictのままだった: %r" % week2
        print("PASS: 一致させたケース → ok のまま（誤検知しない）")

        # ケース3：片方が取れない（不明のまま出す。埋めない）
        _write(os.path.join(tmp, "status", "quota.json"), {})
        out3 = number_audit.run_audit(pairs=[number_audit.GUARD_PAIRS[0]])
        week3 = out3["results"][0]
        assert week3["status"] == "unknown", "値が無いのにunknownにならなかった: %r" % week3
        assert week3["a"]["value"] is None
        print("PASS: 値が取れないケース → unknown（埋めずに不明のまま出す）")

        print("ALL PASS")
        return 0
    finally:
        number_audit.REPO = orig_repo
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(run())
