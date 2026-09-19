#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
795番：estimate_vs_actual.py の動作テスト。
一時ディレクトリで台帳を作り、estimate→actualを積んでcompute_gaps()が
ズレ率の大きい順に正しく並ぶか、needsFix判定が閾値どおりかを確認する。
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import estimate_vs_actual as eva  # noqa: E402


def run():
    orig_ledger, orig_summary = eva.LEDGER, eva.SUMMARY
    tmp = tempfile.mkdtemp(prefix="eva_test_")
    try:
        eva.LEDGER = os.path.join(tmp, "estimate_vs_actual.jsonl")
        eva.SUMMARY = os.path.join(tmp, "estimate_vs_actual_summary.json")

        # 実例1：fal 771番 8.2円 → 実費108円（13倍）
        id1 = eva.record_estimate(771, "fal_cost_yen", 8.2, formula="0.055秒×$0.130/秒×150円/$", unit="円")
        eva.record_actual(id1, 108, source="fal.aiダッシュボード 2026-09-12 手動確認")

        # 実例2：fal 751番 108円 → 実費232円（2.1倍）
        id2 = eva.record_estimate(751, "fal_cost_yen", 108, formula="旧単価×1本", unit="円")
        eva.record_actual(id2, 232, source="fal.aiダッシュボード 2026-09-12 手動確認")

        # 実例3：1本単価 $2.43 → 実際$6.74（2.8倍）
        id3 = eva.record_estimate(None, "fal_unit_cost_usd", 2.43, formula="旧基準（更新なし）", unit="$")
        eva.record_actual(id3, 6.74, source="fal.aiダッシュボード 直近7日実測中央値")

        # 実例4：ほぼ一致するケース（needsFixにならないはず）
        id4 = eva.record_estimate(900, "time_min", 30, formula="想定30分", unit="分")
        eva.record_actual(id4, 32, source="実測ログ")

        out = eva.compute_gaps(top_n=5)
        assert out["pairCount"] == 4, "ペア数が想定と違う: %r" % out
        top_ids = [p["id"] for p in out["top"]]
        assert top_ids[0] == id1, "1番ズレが大きいはずのid1が先頭に来ていない: %r" % top_ids
        assert out["top"][0]["ratio"] == round(108 / 8.2, 3)
        assert out["top"][0]["needsFix"] is True
        # id4（32/30=1.067倍）はneedsFixにならない
        id4_entry = [p for p in out["top"] if p["id"] == id4][0]
        assert id4_entry["needsFix"] is False, "ほぼ一致なのにneedsFixになった: %r" % id4_entry
        assert out["needsFixCount"] == 3, "needsFixCountが想定と違う: %r" % out

        print("PASS: 4件を投入 → gapScore降順で並び、ズレ率2倍超の3件がneedsFix=Trueになった")
        print("先頭: id=%s ratio=%sx" % (out["top"][0]["id"], out["top"][0]["ratio"]))
        print("ALL PASS")
        return 0
    finally:
        eva.LEDGER, eva.SUMMARY = orig_ledger, orig_summary
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(run())
