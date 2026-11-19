#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件#824：週の作業配分ゲート（見たいもの／裏方／予備）の逆テスト。

店主の原則「緑は無実の証明ではない。違反を仕込んで赤になるまで確認する」に従い、
shukan_haibun.py / shukan_kubun.py のゲート判定に、わざと違反を仕込んで
FAILする（＝正しく検知される）ことを確認する。python3 tools/test_shukan_haibun.py で実行できる。
"""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import shukan_haibun  # noqa: E402
import shukan_kubun  # noqa: E402

JST = shukan_kubun.JST


def test_urakata_blocked_true_when_30_percent_or_more():
    """裏方コストが30%以上なら urakata_blocked() は True（新規発車を止める）。"""
    # 2026-09-15：週の支出が $10 未満だと割合が意味を持たないので判定しない仕様になった。
    #   そのため、この検査では現実的な分母（$50）を与える。
    haibun = {"urakataPct": 30.0, "dayRule": "urakata_ok", "totalCostUsd": 50.0}
    assert shukan_haibun.urakata_blocked(haibun) is True, \
        "裏方30%でブロックされなかった（新規裏方タスクが発車し続けてしまう）"


def test_urakata_not_blocked_when_week_just_started():
    """週が始まった直後（支出が小さい）は、割合でブロックしない。
    2026-09-15の実害：リセット直後に裏方1本($1.52)だけ走った時点で urakataPct=100% になり、
    その週の最初の1本目から裏方が全部止まった。"""
    haibun = {"urakataPct": 100.0, "dayRule": "urakata_ok", "totalCostUsd": 1.52}
    assert shukan_haibun.urakata_blocked(haibun) is False, \
        "週初めの小さい分母でブロックされた（工場が週の頭から止まる）"


def test_urakata_blocked_false_at_29_percent_on_urakata_ok_day():
    """裏方コストが29%（30%未満）・かつ曜日ルールがurakata_okなら urakata_blocked() は False。"""
    haibun = {"urakataPct": 29.0, "dayRule": "urakata_ok"}
    assert shukan_haibun.urakata_blocked(haibun) is False, \
        "裏方29%（境界値未満）なのにブロックされた（過剰にブロックしている）"


def test_single_task_over_limit():
    """1本のcostEstimateが週予算(totalCostUsd)の3%を超えたらTrue、超えなければFalse。"""
    haibun = {"totalCostUsd": 100.0}
    assert shukan_haibun.single_task_over_limit(4, haibun) is True, \
        "$100の週予算に対し$4（4%）は3%を超えているはずなのにFalseだった"
    assert shukan_haibun.single_task_over_limit(2, haibun) is False, \
        "$100の週予算に対し$2（2%）は3%以内のはずなのにTrueだった"


def test_day_rule_friday_is_urakata_finish_only():
    """金曜は urakata_finish_only（新規の裏方着火はしない）。"""
    # 2026-09-11 は金曜(weekday()==4)
    friday = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=JST)
    assert friday.weekday() == 4, "テストの前提が崩れている（2026-09-11は金曜のはず）"
    dr = shukan_haibun.day_rule(friday)
    assert dr == "urakata_finish_only", \
        "金曜のdayRuleが urakata_finish_only ではなく %r だった" % dr

    haibun = {"dayRule": "urakata_finish_only", "urakataPct": 0.0}
    assert shukan_haibun.urakata_blocked(haibun) is True, \
        "金曜(urakata_finish_only)なのに裏方0%を理由にブロックが外れてしまった"


def test_classify_item_user_fix_is_mitai_not_urakata():
    """『扉の欄を3つに直して』（たまごさんの指示で直す）はurakataではなくmitaiに分類される
    （実例の再発防止：裏方キーワードに一致していても、店主の直接指示は見たいもの優先）。"""
    item = {"title": "扉の欄を3つに直して", "origin": "user", "what": "間違っている表示を修正"}
    got = shukan_kubun.classify_item(item)
    assert got == "mitai", "『扉の欄を3つに直して』が urakata に分類された（期待は mitai・実際は %r）" % got


def test_classify_item_factory_automation_is_urakata():
    """『重複発車ガードの仕組み化』（factory起点・仕組み化語）はurakataに分類される（正常系）。"""
    item = {"title": "重複発車ガードの仕組み化", "origin": "factory", "what": "自動化で検品を点検する台帳"}
    got = shukan_kubun.classify_item(item)
    assert got == "urakata", "『重複発車ガードの仕組み化』が mitai に分類された（期待は urakata・実際は %r）" % got


if __name__ == "__main__":
    test_urakata_blocked_true_when_30_percent_or_more()
    test_urakata_blocked_false_at_29_percent_on_urakata_ok_day()
    test_single_task_over_limit()
    test_day_rule_friday_is_urakata_finish_only()
    test_classify_item_user_fix_is_mitai_not_urakata()
    test_classify_item_factory_automation_is_urakata()
    print("全テストPASS")
