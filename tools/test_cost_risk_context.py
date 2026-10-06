#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
795番：cost_risk.py の文脈判定の再現テスト。

793番「【最優先】『すぐ見たい』の別枠を作る」は、本文中に「777番の教訓：二重課金で$55捨てた」
という**過去の損失額**の言及しか無いのに、旧ロジックでは costEstimate が
「ドル額の言及: $55.0」を拾って costsMoney=True と誤判定されていた（実際に status/queue.json の
793番に costsMoneyClearedBy として人力クリアの跡が残っている＝実害の証拠）。

このテストは：
  1. 793番の実際の本文（過去形の$55だけ）を入れて is_cost_risk() が False になること
  2. これから金がかかる言い方（未来形の$）を入れたケースは True のままであること（見逃し防止の維持）
  3. 文脈が不明なケース（$だけ書いてあり前後に過去/未来の手がかりが無い）は
     is_cost_risk() は False（無条件Trueにしない）だが、estimate_note() には
     「要確認」として出て金額が消えていないこと（拾えないときは空欄にする。無視して消すのとは違う）
を確認する。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cost_risk  # noqa: E402


def run():
    # 1. 793番の実際の本文（過去の言及のみ）
    item_793 = {
        "n": 793,
        "title": "【最優先】「すぐ見たい」の別枠を作る＋優先順位の自動入れ替え",
        "why": "スマホから追加",
        "what": ("【3】★発車の順番を urgent 優先にする（tools/auto_launcher.py）\n"
                 "  - **走行中のものは絶対に列へ戻さない**（777番の教訓。二重課金で$55捨てた）。"),
    }
    assert cost_risk.is_cost_risk(item_793) is False, (
        "793番の過去の損失額($55)を将来費用と誤検知した: note=%s" % cost_risk.estimate_note(item_793))
    note = cost_risk.estimate_note(item_793)
    assert "$55" not in note.replace("$55.0", "") or "過去の言及として除外" in note, (
        "$55が除外扱いになっていない: %s" % note)
    print("PASS: 793番の過去の損失額($55)は costsMoney=False になった")
    print("  estimate_note: %s" % note)

    # 2. これから金がかかる（未来形）→ Trueのまま（見逃し防止の維持）
    item_future = {
        "n": 999, "title": "動画をfalで作る",
        "why": "", "what": "これからfalで動画を10本生成します。1本$3、合計$30かかる予定です。"
    }
    assert cost_risk.is_cost_risk(item_future) is True, "未来形の費用言及を見逃した"
    print("PASS: 未来形（これから$30かかる予定）は costsMoney=True のまま")

    # 3. fal言及も過去/未来の手がかりも無い、ただの$記載（文脈不明）
    item_unknown = {
        "n": 1000, "title": "海外の相場調査", "why": "",
        "what": "他所のサービスは$50くらいらしい。参考までにメモ。"
    }
    risk_unknown = cost_risk.is_cost_risk(item_unknown)
    note_unknown = cost_risk.estimate_note(item_unknown)
    assert risk_unknown is False, "文脈不明の$を無条件でTrueにしてしまった: %r" % risk_unknown
    assert "要確認" in note_unknown, "文脈不明な金額が要確認として出ていない（消してしまっている）: %s" % note_unknown
    print("PASS: 文脈不明の$50は costsMoney=False だが note には「要確認」として残る（消さない）")
    print("  estimate_note: %s" % note_unknown)

    # 4. 明示キーワード(fal.ai)があれば金額が無くても引き続きTrue（既存動作の維持）
    item_fal_only = {"n": 1001, "title": "fal.aiで画像生成", "why": "", "what": "fal.aiを使う"}
    assert cost_risk.is_cost_risk(item_fal_only) is True, "明示的なfalキーワードの無条件Trueが壊れた"
    print("PASS: 明示的なfal.aiキーワードは金額が無くても costsMoney=True のまま（既存動作を維持）")

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
