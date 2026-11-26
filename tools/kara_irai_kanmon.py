#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""空票の関所（2026-11-26・40147番／同日40340番で2件目を追加）。

事故：40147番はスマホから追加された票（why="スマホから追加"）で、
タイトルが入力テンプレートの文字列「対応してほしいこと:」のまま、本文を
書く前に送信されてしまった。本文（what）の【タスク】欄も同じプレース
ホルダーのままなので、実行できる依頼が1件も存在しない。
それでも queuedAt 2026-10-02 から2026-11-26まで約2ヶ月、7回以上自動発車
され続けた（依頼内容が無いので何回発車しても実装できる仕事が無い＝
枠の無駄カット対象だが、mudacut.py の「3回目以降hold」はこの票を
捉えられていなかった＝タイトルが空だと判定する専用ロジックが無かった）。

40340番（同日2026-11-26に発見）は同じ構造の別バリエーション：
タイトル・what欄とも「この形式を厳守してください。」というプレース
ホルダー文言のまま（同じ2026-10-02にスマホから追加、queue.json記録と
share/done/index.htmlの「判定日赤」ログを確認すると #2311〜#33683まで
70件以上も同じ文言で繰り返し生成されており、スマホ入力フォームの
ヒント文がそのまま未編集で送信される構造的バグが複数のテンプレ文言で
起きていると判明）。KARA_TITLESを1件追加するだけで、発車前に即hold
される（is_kara()が文字列完全一致で見るだけなので、新しいテンプレ文言
が見つかるたびにここへ追記する）。

対応：発車前にタイトルが既知の未入力テンプレのままかを見て、そうなら
即hold（3回待たず1回目で止める）。解除はたまごさんが本文を書き直して
タイトルが変わった時だけ（自動的にこの関所を通らなくなる）。

実装は既存の tools/mudacut.py の horyu()・tools/fable_week.py の
horyu()/is_fable_item() と同じ「判定関数＋hold化関数＋jsonlログ」の
3点セットをそのまま流用した（1184号の関所：hyo-1795665898で通過済み）。
"""
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(REPO, "status", "kara_irai_kanmon.jsonl")

# 既知の「本文を書く前に送信されたテンプレート」のタイトル文字列。
KARA_TITLES = {
    "対応してほしいこと:",
    "対応してほしいこと",
    "この形式を厳守してください。",
    "この形式を厳守してください",
}

HORYU_NOTE = (
    "空票の関所（2026-11-26・40147番）：タイトルが入力テンプレートのまま"
    "（本文が一度も書かれていない）。たまごさんが本文を書き直して再送する"
    "まで保留。解除は自動（タイトルが変われば次回から通る）。"
)


def is_kara(item):
    """True＝本文が一度も書かれていない空票（タイトルがテンプレのまま）。

    テスト便は対象外（item.get("test")）。空票であること自体はmodelや
    優先度と無関係なので、他の除外条件は設けない。
    """
    if item.get("test"):
        return False
    title = str(item.get("title") or "").strip()
    return title in KARA_TITLES


def horyu(item):
    item["statusBefore"] = item.get("status")
    item["status"] = "hold"
    item["holdNote"] = HORYU_NOTE
    item["karaIraiHoryuAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"n": item.get("n"), "at": item["karaIraiHoryuAt"], "title": item.get("title")},
                ensure_ascii=False,
            ) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    # 逆テスト（憲法「見張りは必ず逆テストする」）：
    # 緑（Falseのまま）は無実の証明にならないので、わざと違反を仕込んで赤になるか確認する。
    ok_true = is_kara({"n": 1, "title": "対応してほしいこと:"})
    ok_true2 = is_kara({"n": 2, "title": "対応してほしいこと"})
    ok_false_test = is_kara({"n": 3, "title": "対応してほしいこと:", "test": True})
    ok_false_real = is_kara({"n": 4, "title": "棚のバッジの位置を直す"})
    ok_true3 = is_kara({"n": 5, "title": "この形式を厳守してください。"})
    ok_true4 = is_kara({"n": 6, "title": "この形式を厳守してください"})
    print("kara(title完全一致, test無し) ->", ok_true, "(期待 True)")
    print("kara(末尾コロン無し)        ->", ok_true2, "(期待 True)")
    print("kara(testフラグ付き)        ->", ok_false_test, "(期待 False)")
    print("kara(実在する依頼文)        ->", ok_false_real, "(期待 False)")
    print("kara(40340番と同じ句点あり) ->", ok_true3, "(期待 True)")
    print("kara(40340番と同じ句点なし) ->", ok_true4, "(期待 True)")
    assert ok_true is True
    assert ok_true2 is True
    assert ok_false_test is False
    assert ok_false_real is False
    assert ok_true3 is True
    assert ok_true4 is True
    print("KARA_IRAI_KANMON_SELFTEST: PASS")
