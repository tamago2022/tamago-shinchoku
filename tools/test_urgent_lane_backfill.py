#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1372番（2026-09-27）「今走ってるものは3時間縛りだから、次もちゃんと待機していて
自動的に上に繰り上がる仕組みにしてほしい」の回帰テスト。

実測：1372番自身がpriority=1のまま2026-09-18〜09-27の9日間着火されず、同種114件が
全件7〜10日待たされていた（主因はログイン切れの長期化＋優先度1が114件も並んでいたこと）。
ここで固定するのは3つの純粋関数（ファイルI/Oなし＝本物のqueue.jsonに一切触れずに検証できる）：
  ① queued_minutes_ago()   … queuedAtからの経過分数、無ければNone
  ② urgent_wait_list()     … 優先度1/urgentでURGENT_WAIT_MIN分超のものだけを長い順に返す
  ③ urgent_lane_safe_max() … 枠が埋まっていて長期待機のurgentがあれば+1本、
                              measured_safe_maxは絶対に超えない

python3 tools/test_urgent_lane_backfill.py で実行できる。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import auto_launcher as al  # noqa: E402


def _iso(minutes_ago, now):
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00", time.localtime(now - minutes_ago * 60))


def run():
    failures = []
    now = time.time()

    # ① queuedAtが無い／壊れている項目はNone（安全側・対象にしない）
    if al.queued_minutes_ago({"n": 1}, now) is not None:
        failures.append("queuedAtが無いのにNoneを返していません")
    if al.queued_minutes_ago({"n": 2, "queuedAt": "壊れた文字列"}, now) is not None:
        failures.append("壊れたqueuedAtでも例外にならずNoneでないものを返しています")

    # ② 待機が短い（60分）ものは対象外、91分なら対象、優先度1でもurgentでもなければ対象外
    items = [
        {"n": 10, "status": "waiting", "priority": 1, "queuedAt": _iso(91, now)},   # 対象
        {"n": 20, "status": "waiting", "priority": 1, "queuedAt": _iso(60, now)},    # 60分待ち＝まだ対象外
        {"n": 30, "status": "waiting", "priority": 3, "queuedAt": _iso(500, now)},   # 優先度1でもurgentでもない
        {"n": 40, "status": "waiting", "urgent": True, "queuedAt": _iso(200, now)},  # urgentなら対象
        {"n": 50, "status": "running", "priority": 1, "queuedAt": _iso(999, now)},   # waitingでない
        {"n": 60, "status": "waiting", "priority": 1, "queuedAt": _iso(1000, now)},  # 一番長く待っている
    ]
    got = [it["n"] for it in al.urgent_wait_list(items, now)]
    if got != [60, 40, 10]:
        failures.append("urgent_wait_listの対象・順序が期待と違います：期待[60,40,10]、実際%r" % got)

    # ③-a 枠に空きがあれば横入りしない（そもそも待たせていない）
    sm, hit = al.urgent_lane_safe_max(alive=2, safe_max=3, measured_safe_max=4, items=items, now=now)
    if sm != 3 or hit is not None:
        failures.append("空きがあるのに横入り判定が動いています：sm=%r hit=%r" % (sm, hit))

    # ③-b 枠が埋まっていて長期待機のurgentがあり、measured_safe_maxに余裕があれば+1
    sm2, hit2 = al.urgent_lane_safe_max(alive=3, safe_max=3, measured_safe_max=4, items=items, now=now)
    if sm2 != 4 or hit2 is None or hit2.get("n") != 60:
        failures.append("枠が埋まっていて余裕があるのに+1本されていません：sm=%r hit=%r" % (sm2, hit2))

    # ③-c measured_safe_maxに全く余裕が無ければ、待たされていても増やさない（安全弁）
    sm3, hit3 = al.urgent_lane_safe_max(alive=3, safe_max=3, measured_safe_max=3, items=items, now=now)
    if sm3 != 3 or hit3 is not None:
        failures.append("measured_safe_maxに余裕が無いのに枠を超えて増やしています：sm=%r hit=%r" % (sm3, hit3))

    # ③-d 長期待機のurgentが1つも無ければ、枠が埋まっていても増やさない
    items_no_urgent = [{"n": 70, "status": "waiting", "priority": 3, "queuedAt": _iso(1000, now)}]
    sm4, hit4 = al.urgent_lane_safe_max(alive=3, safe_max=3, measured_safe_max=5,
                                         items=items_no_urgent, now=now)
    if sm4 != 3 or hit4 is not None:
        failures.append("長期待機のurgentが無いのに枠を増やしています：sm=%r hit=%r" % (sm4, hit4))

    if failures:
        print("FAIL（%d件）" % len(failures))
        for f in failures:
            print(" - " + f)
        return 1
    print("PASS：1372番の緊急横入り枠（queued_minutes_ago/urgent_wait_list/urgent_lane_safe_max）"
          "は要求どおり動いています")
    return 0


if __name__ == "__main__":
    sys.exit(run())
