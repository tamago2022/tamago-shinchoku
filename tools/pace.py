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


# ---- 燃料の配分を自動でやる（2026-09-05・たまごさん指示）----
# たまごさんの言葉：
#   「**5時間枠は、リセットがかかるとき90〜99%で着地するのが理想。そのギリギリをついてほしい。**
#    まだ3%しかないのに5時間経って0%に戻る、それは全然使えてない、元が取れてない。
#    **週間は、土日月＋火18時まで。1日30%。30%を超えたらもう今日はストップ。**
#    Fableは今のところ使う予定ない。**そこまでマネジメントしてくれたら非常に助かります。**」
DAILY_CAP = 30.0        # 1日に使ってよい週枠の割合（超えたら今日は打ち止め）
# ---- 2026-09-05 18:50 たまごさんの言葉（そのまま）----
#   「5時間かけて99%、100%使うのが理想だけど、**コンピューターの作業が止まるのはマイナス**だから、
#    例えば80%とか75%でも、**ずっと毎回5時間ごとに75%使えてれば無駄は無い**ねみたいな。
#    1ヵ月ずっと70%、80%、毎回の5時間で回ってれば俺は満足。
#    **コンピューターも止まらず、タスクも進み続ける。その状態が理想。**」
#   → 天井ぎりぎり（95%）を狙うのをやめる。**78%で安定して着地させる。**
#     100%を1回取って翌日フリーズするより、78%を毎回取り続ける方が総量で勝つ。
S5_TARGET = 88.0        # 5時間枠の着地目標（2026-09-05 18:55 たまごさん「78に下げちゃったら…目一杯使いたい。85でも90でもいい」）
S5_FLOOR = 82.0         # これを下回る見込みなら、まだ余っている＝本数を増やしてよい
# 実測（たまごさんの体感 2026-09-05）：**6本だと重くなる。4本なら平気。5本を試す。**
CAP_MIN, CAP_MAX = 3, 5  # 同時に走らせる本数の下限・上限（6本は行き過ぎ）


# ---- 2026-09-09 20:00 実測バグ（702番）----
#   進捗表は「今日30%使用・目安11.7%に対して+18.3%超過」と赤で出ているのに、
#   launch_cap.json は cap=5 のまま11時間動いていなかった。
#   原因1：下の cap 書き換え条件に `used < DAILY_CAP` が入っていて、
#          usedToday が DAILY_CAP(30) に達した瞬間に「capを書き換えない」に化けていた
#          （＝一番下げたい瞬間にフリーズする。凍結バグ）。
#   原因2：cap の計算が「5時間枠の着地見込み」だけを見ていて、週の予算（pace.jsonのoverLine/state）を
#          一度も見ていなかった。だから週が大幅超過でも本数が減らなかった。
# 直し方：
#   ・下げる方向の書き込みは DAILY_CAP に関係なく必ず行う（②のガードは「増やす」時だけに掛ける）。
#   ・週の予算超過（overLine）を段階で見る：+5%→cap-1／+10%→cap-2／+15%→新規発車そのものを止める
#     （no_launch.flag。走行中は止めない＝0本にはしない）。今日のstateが"over"のときも1本減らす。
#   ・逆に週の予算が10pt以上余っていれば1本増やす（「余ってるのに1本しか回ってない」対策）。
#   ・5時間枠の判定と週の判定、両方が同時に「下げたい」と言ったら、より安全な（小さい）方を採用。
#     どちらかが下げたいと言っているときは増やさない。
WEEK_OVER_STOP = 15.0    # これを超えたら新規発車そのものを止める（走行中は継続）
WEEK_OVER_2 = 10.0       # これを超えたら cap-2
WEEK_OVER_1 = 5.0        # これを超えたら cap-1
WEEK_UNDER_UP = -10.0    # これより下（＝週の予算が大きく余っている）なら cap+1
DAILY_FLAG_MARK = "1日の上限"
WEEK_FLAG_MARK = "週の予算"


def manage_fuel(d, q):
    """今日の使いすぎ・週の予算超過を止め、5時間枠を余らせないように本数を上下させる。"""
    repo_status = lambda n: os.path.join(REPO, "status", n)
    flag = repo_status("no_launch.flag")
    cap_path = repo_status("launch_cap.json")
    notes = []

    used = d.get("usedToday")
    over_line = d.get("overLine")     # 週の理想ラインとの差。+なら使いすぎ、-なら余っている
    day_state = d.get("state")        # 今日の使用が今日の予算に対して ok/warn/over/unknown

    daily_stop = isinstance(used, (int, float)) and used >= DAILY_CAP
    week_stop = isinstance(over_line, (int, float)) and over_line > WEEK_OVER_STOP

    # ① 上限（1日 or 週）に触れたら新規発車だけ止める（走行中はそのまま・0本にはしない）
    if daily_stop or week_stop:
        try:
            cur = io.open(flag, encoding="utf-8").read() if os.path.exists(flag) else ""
        except Exception:
            cur = ""
        add = []
        if daily_stop and DAILY_FLAG_MARK not in cur:
            add.append("今日はもう%.1f%%使ったので自動で止めました（1日の上限%.0f%%）" % (used, DAILY_CAP))
            notes.append("今日の上限%.0f%%に達したので発車を止めました" % DAILY_CAP)
        if week_stop and WEEK_FLAG_MARK not in cur:
            add.append("週の予算を+%.1f%%超えたので新規発車を止めました（走行中は継続）" % over_line)
            notes.append("週の予算を+%.1f%%超えたので新規発車を止めました" % over_line)
        if add:
            io.open(flag, "w", encoding="utf-8").write(
                (cur.strip() + "; " if cur.strip() else "") + "; ".join(add)
                + "（%s）\n" % time.strftime("%Y-%m-%d %H:%M"))
    else:
        # 両方の条件が外れたときだけ、自動で立てたフラグを自動で解除する（手動フラグは触らない）
        try:
            if os.path.exists(flag):
                cur = io.open(flag, encoding="utf-8").read()
                if (DAILY_FLAG_MARK in cur or WEEK_FLAG_MARK in cur) and "ログインが切れています" not in cur:
                    os.remove(flag)
                    notes.append("使用が落ち着いたので発車を再開しました")
        except Exception:
            pass

    # ② 同時本数（cap）を上下させる。5時間枠のシグナルと週の予算シグナルを両方見て、
    #    下げ提案があれば一番安全な（小さい）方を採る。上げるのは両方が問題ないときだけ。
    cap_now = (load(cap_path, {}) or {}).get("cap")
    if not isinstance(cap_now, int):
        cap_now = CAP_MAX
    proposals = []   # (提案cap, 理由, +1/-1/-2/-3の向き)

    s5 = (q.get("session5h") or {})
    pct = s5.get("pct")
    hours_left = s5.get("hoursLeft")
    rate = s5.get("recentPacePctPerHour")
    if isinstance(pct, (int, float)) and isinstance(hours_left, (int, float)) and hours_left > 0.2:
        r = rate if isinstance(rate, (int, float)) and rate > 0 else None
        projected = pct + (r * hours_left) if r else None
        d["s5Projected"] = round(projected, 1) if projected is not None else None
        if projected is not None:
            if projected < S5_FLOOR:
                proposals.append((min(CAP_MAX, cap_now + 1),
                                   "5時間枠の着地見込み%.0f%%で余っている" % projected, 1))
            elif projected > S5_TARGET + 7:
                proposals.append((max(CAP_MIN, cap_now - 1),
                                   "5時間枠の着地見込み%.0f%%で行き過ぎ" % projected, -1))

    if isinstance(over_line, (int, float)):
        if over_line > WEEK_OVER_STOP:
            proposals.append((CAP_MIN, "週の予算を+%.1f%%超過（新規発車は停止中）" % over_line, -3))
        elif over_line > WEEK_OVER_2:
            proposals.append((max(CAP_MIN, cap_now - 2), "週の予算を+%.1f%%超過" % over_line, -2))
        elif over_line > WEEK_OVER_1:
            proposals.append((max(CAP_MIN, cap_now - 1), "週の予算を+%.1f%%超過" % over_line, -1))
        elif day_state == "over":
            proposals.append((max(CAP_MIN, cap_now - 1), "今日の使用が今日の予算を超過(state=over)", -1))
        elif over_line < WEEK_UNDER_UP:
            proposals.append((min(CAP_MAX, cap_now + 1), "週の予算が余っている(overLine=%.1f)" % over_line, 1))

    downs = [p for p in proposals if p[2] < 0]
    ups = [p for p in proposals if p[2] > 0]
    new_cap, why = cap_now, None
    if downs:
        new_cap, why, _ = min(downs, key=lambda p: p[0])
    elif ups:
        new_cap, why, _ = ups[0]
        # 増やすのは、今日すでに1日の上限を使い切っていないときだけ
        if isinstance(used, (int, float)) and used >= DAILY_CAP:
            new_cap, why = cap_now, None

    # 下げる方向は DAILY_CAP に関係なく必ず書く（凍結バグの直し）。増やす方向だけ↑で既にガード済み。
    if why and new_cap != cap_now:
        json.dump({"cap": new_cap, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "why": why},
                  io.open(cap_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        notes.append("同時本数を%d→%d本にしました（%s）" % (cap_now, new_cap, why))
    elif not os.path.exists(cap_path):
        json.dump({"cap": cap_now, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "why": "初期値"},
                  io.open(cap_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    d["dailyCap"] = DAILY_CAP
    d["s5Target"] = S5_TARGET
    d["cap"] = (load(cap_path, {}) or {}).get("cap")
    d["capWhy"] = (load(cap_path, {}) or {}).get("why")
    d["fuelNotes"] = notes
    return d


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
    # 2026-09-05 週がリセットされると使用率が 86% → 0% のように落ちる。
    #   その前の記録を基準にすると「今日 -86% 使った」というおかしな数字になるので、
    #   **落ちた地点を新しい起点にする。**
    todays = []
    for r in rows:
        try:
            t = datetime.strptime(r["t"], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            continue
        if t >= today0:
            todays.append(r)
    base = None
    for r in todays:
        v = r.get("allPct")
        if v is None:
            continue
        if base is None or v < base - 20:     # 20pt以上の急落＝リセット
            base = v
    first_today = {"allPct": base} if base is not None else None
    used_today = None
    if base is not None:
        used_today = max(0.0, round(all_pct - base, 1))

    per_day_even = round(WEEK_TARGET / DAYS, 1)                       # 14.1
    remain = max(0.0, WEEK_TARGET - all_pct)
    budget_today = round(min(DAILY_CAP, remain / max(1.0, days_left)), 1)   # 今日あと使える目安（上限30%）
    # 2026-09-13（工場が2時間15分止まっていた原因）：
    #   ここは「経過日数÷7」の直線だけで理想ラインを出していたが、quota.py 側は
    #   曲線（水30/木45/金55/土70/日80/月90/火100）＋週間制限の引き上げ倍率を掛けた
    #   weekdayTarget を既に計算している。**2つの基準がズレていた。**
    #   実害：2026-09-13 03:00、quota.json は「79% / 目標96.4% → 17.4pt下振れ・本数を増やす余地」と
    #         言っているのに、pace.py の直線（63.2%）では「+15.8%超過」となり
    #         no_launch.flag を立てて工場を止めた。たまごさんの「すぐ見たい」6件が発車できなかった。
    #   → quota.py が出している weekdayTarget があればそれを使う（同じ物差しで測る）。
    #     取れないときだけ、従来の直線に戻す（壊れない）。
    line_target = round(WEEK_TARGET * min(1.0, days_used / DAYS), 1)  # 従来の直線（予備）
    _wt = q.get("weekdayTarget")
    try:
        if _wt is not None and float(_wt) > 0:
            line_target = round(min(float(_wt), WEEK_TARGET), 1)
    except (TypeError, ValueError):
        pass
    over = round(all_pct - line_target, 1)

    if used_today is None:
        state = "unknown"
    elif used_today >= budget_today:
        state = "over"
    elif used_today >= budget_today * 0.8:
        state = "warn"
    else:
        state = "ok"

    # 2026-09-09（689番）「クレジットが超余ってるのに1本しか回ってない」「丸1日以上動いて週0%はおかしい」
    #   → allPct=0 をそのまま信じない。quota.json の estimated（実測が読めたか）と
    #     allPctAgeMin（本物のサンプルが何分前か）を pace.json 側にも渡し、
    #     PWA が「0%」を鵜呑みにせず「取れていない」灰色表示へ切り替えられるようにする。
    #   suspectZero：週が始まって6時間以上経っているのに0%＝取得が壊れている疑いが濃厚
    days_used_h = days_used * 24
    suspect_zero = bool(all_pct == 0 and days_used_h > 6)
    data_ok = (q.get("estimated") is False) and (
        q.get("allPctAgeMin") is None or q.get("allPctAgeMin") <= 90)

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
        "estimated": q.get("estimated"),
        "allPctAgeMin": q.get("allPctAgeMin"),
        "allPctAsOf": q.get("allPctAsOf"),
        "dataOk": data_ok,
        "suspectZero": suspect_zero,
        "note": "火曜18:00リセット。7日で99%に着地するのが理想＝1日目安13〜14%。今日の予算＝残り÷残り日数（遅れも使いすぎも引きずらない）。超えたら赤。",
    }
    try:
        d = manage_fuel(d, q)
    except Exception as e:
        d["fuelNotes"] = ["配分の自動調整でつまずきました: %s" % e]
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
