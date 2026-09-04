#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週の配分（天井に行かないためのペース管理）。

2026-09-05 たまごさんの言葉：
  「火曜18時にリセットされるわけだから、とりあえずそれを7で割ってよ。**1日あたり13〜14%前後**なんだよ。
   だから『**今日は20%使ってます**』とか、それで**赤印**になるとか、『**13%までだったらまだ使える**』とか、
   そういうのを作ってほしい。1週間でちょうど99%に行くくらいに配分して。
   いつも間違えて2日くらいでいっぱいになる。**天井に行かないための配分**だよね。」

やること:
  1. いまの使用率(quota.json の allPct)を1行ずつ記録する（status/pace_history.jsonl）
  2. そこから「今日いくつ使ったか」「今日はあといくつ使えるか」「早すぎるか」を計算する
  3. status/pace.json に書く（進捗表が読む）

考え方:
  - 週枠は火曜18:00にリセット。**7日で99%**に着地するのが理想（余らせるのも無駄）
  - 1日の目安 = 99 ÷ 7 ≒ 14.1%
  - ただし「今日あと何%使えるか」は**残りを残り日数で割り直す**（遅れた日・使いすぎた日を引きずらない）
      今日の予算 = (99 - 今の使用率) ÷ 残り日数
  - 今日の使用が今日の予算を超えていたら赤、8割超えたら黄、それ以下は緑
"""
import io
import json
import os
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUOTA = os.path.join(REPO, "status", "quota.json")
HIST = os.path.join(REPO, "status", "pace_history.jsonl")
OUT = os.path.join(REPO, "status", "pace.json")
WEEK_TARGET = 99.0          # 使い切る目標（余らせない）
DAYS = 7.0


def load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def parse_reset(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(s), f).replace(tzinfo=None)
        except Exception:
            pass
    return None


def main():
    q = load(QUOTA, {})
    all_pct = q.get("allPct")
    if all_pct is None:
        return 0
    now = datetime.now()
    # 記録を1行足す
    try:
        with io.open(HIST, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": now.strftime("%Y-%m-%dT%H:%M:%S"), "allPct": all_pct,
                                "fablePct": q.get("fablePct")}, ensure_ascii=False) + "\n")
    except Exception:
        pass

    reset = parse_reset(q.get("resetAt")) or (now + timedelta(days=3))
    start = reset - timedelta(days=DAYS)          # 前回リセット＝週の始まり
    days_left = max(0.05, (reset - now).total_seconds() / 86400.0)
    days_used = max(0.0, (now - start).total_seconds() / 86400.0)

    # 今日（0時以降）の最初の記録を探して「今日いくつ使ったか」を出す
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    first_today = None
    rows = []
    try:
        for ln in io.open(HIST, encoding="utf-8"):
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    except Exception:
        pass
    for r in rows:
        try:
            t = datetime.strptime(r["t"], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            continue
        if t >= today0:
            first_today = r
            break
    used_today = None
    if first_today is not None and first_today.get("allPct") is not None:
        used_today = round(all_pct - first_today["allPct"], 1)

    per_day_even = round(WEEK_TARGET / DAYS, 1)                       # 14.1
    remain = max(0.0, WEEK_TARGET - all_pct)
    budget_today = round(remain / max(1.0, days_left), 1)             # 今日あと使える目安
    line_target = round(WEEK_TARGET * min(1.0, days_used / DAYS), 1)  # 今この時点の理想ライン
    over = round(all_pct - line_target, 1)

    if used_today is None:
        state = "unknown"
    elif used_today >= budget_today:
        state = "over"
    elif used_today >= budget_today * 0.8:
        state = "warn"
    else:
        state = "ok"

    d = {
        "updatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "allPct": all_pct,
        "resetAt": q.get("resetAt"),
        "daysLeft": round(days_left, 2),
        "perDayEven": per_day_even,
        "usedToday": used_today,
        "budgetToday": budget_today,
        "remainWeek": round(remain, 1),
        "lineTarget": line_target,
        "overLine": over,
        "state": state,
        "note": "火曜18:00リセット。7日で99%に着地するのが理想。今日の予算＝残り÷残り日数（遅れも使いすぎも引きずらない）",
    }
    tmp = OUT + ".tmp"
    json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    # 履歴が太らないように、直近2000行だけ残す
    if len(rows) > 2200:
        try:
            with io.open(HIST, "w", encoding="utf-8") as f:
                for r in rows[-2000:]:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
