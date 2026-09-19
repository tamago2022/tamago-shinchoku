#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週の作業配分の実績集計＋ゲート判定。

status/cost_by_task.json（実績コストの正本）から今週分を抽出し、shukan_kubun.classify_item()で
mitai/urakata/yobiへ振り分けて％を出す。auto_launcher.pyはこの集計とゲート関数を使って
裏方タスクの新規発車を止める（店主指示「見たいもの60%／裏方30%／予備10%」）。
"""
import io
import json
import os
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
sys.path.insert(0, HERE)
import shukan_kubun  # noqa: E402

JST = shukan_kubun.JST
OUT_PATH = os.path.join(ST, "shukan_haibun.json")

# 仮の週予算（今週の実績コストが0で直近7日間の実績も無い場合の最終フォールバック）。
_FALLBACK_WEEKLY_BUDGET_USD = 50.0


def _jread(name, default=None):
    try:
        with io.open(os.path.join(ST, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _parse_dt(s):
    if not s:
        return None
    try:
        dt = datetime.datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt


def _find_item(n, queue_items, deleted_items):
    for it in queue_items:
        if it.get("n") == n:
            return it
    for it in deleted_items:
        if it.get("n") == n:
            return it
    return None


def day_rule(now=None):
    """火水木=urakata_ok／金=urakata_finish_only（新規着火はしない）／土日月=mitai_only"""
    now = now or datetime.datetime.now(JST)
    wd = now.weekday()  # 月=0 火=1 水=2 木=3 金=4 土=5 日=6
    if wd in (1, 2, 3):
        return "urakata_ok"
    if wd == 4:
        return "urakata_finish_only"
    return "mitai_only"


def _fallback_weekly_budget(now=None):
    """今週の実績が0の時の代替：直近7日間のcost_by_task.jsonの合計。無ければ$50。"""
    now = now or datetime.datetime.now(JST)
    cost_data = _jread("cost_by_task.json", {"tasks": []})
    tasks = cost_data.get("tasks") or []
    cutoff = now - datetime.timedelta(days=7)
    total = 0.0
    for t in tasks:
        dt = _parse_dt(t.get("finishedAt"))
        if dt is None:
            continue
        if cutoff <= dt <= now:
            total += float(t.get("costUsd") or 0.0)
    return total if total > 0 else _FALLBACK_WEEKLY_BUDGET_USD


def build_haibun(now=None):
    """今週分の集計を作り、status/shukan_haibun.jsonへは main() 側で書き出す。"""
    now = now or datetime.datetime.now(JST)
    ws = shukan_kubun.week_start(now)

    cost_data = _jread("cost_by_task.json", {"tasks": []})
    tasks = cost_data.get("tasks") or []
    queue_data = _jread("queue.json", {"items": []})
    queue_items = queue_data.get("items") or []
    deleted_data = _jread("deleted.json", {"items": []})
    deleted_items = deleted_data.get("items") or []

    mitai_cost = 0.0
    urakata_cost = 0.0
    yobi_cost = 0.0
    for t in tasks:
        dt = _parse_dt(t.get("finishedAt"))
        if dt is None or dt < ws or dt > now:
            continue
        item = _find_item(t.get("n"), queue_items, deleted_items)
        if item is None:
            item = {"title": t.get("title") or ""}
        cls = shukan_kubun.classify_item(item)
        cost = float(t.get("costUsd") or 0.0)
        if cls == "mitai":
            mitai_cost += cost
        elif cls == "urakata":
            urakata_cost += cost
        else:
            yobi_cost += cost

    total = mitai_cost + urakata_cost + yobi_cost

    def _pct(x):
        return round((x / total * 100.0), 1) if total > 0 else 0.0

    mitai_pct = _pct(mitai_cost)
    urakata_pct = _pct(urakata_cost)
    yobi_pct = _pct(yobi_cost)

    dr = day_rule(now)
    # 「試す枠」＝週の予備＋残り。予備は10%割当。今週すでに使った予備コストの割合(yobi_pct)を引いた残り。
    try_budget_pct = round(max(0.0, 10.0 - yobi_pct), 1)
    friday_cutoff = (dr == "urakata_finish_only") and (try_budget_pct < 20.0)

    return {
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "weekStart": ws.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "totalCostUsd": round(total, 4),
        "mitaiCostUsd": round(mitai_cost, 4), "mitaiPct": mitai_pct,
        "urakataCostUsd": round(urakata_cost, 4), "urakataPct": urakata_pct,
        "yobiCostUsd": round(yobi_cost, 4), "yobiPct": yobi_pct,
        "reversed": mitai_pct < urakata_pct,
        "dayRule": dr,
        "fridayCutoff": friday_cutoff,
        "tryBudgetPct": try_budget_pct,
    }


def urakata_blocked(haibun):
    """裏方の新規発車を止めるべきか。裏方が30%以上、または曜日ルールで裏方NGな日。"""
    # 2026-09-15：週が始まった直後は分母が小さすぎて割合が意味を持たない。
    #   実測：リセット直後、その週の支出が $1.52（自動検知の裏方1本）しか無い時点で
    #   urakataPct=100% となり、**週の最初の1本目から裏方が全部止まった。**
    #   → 週の支出が一定額に達するまでは、割合での判定をしない（曜日ルールだけ効かせる）。
    MIN_DENOM_USD = 10.0
    try:
        _total = float(haibun.get("totalCostUsd") or 0.0)
    except Exception:
        _total = 0.0
    if _total >= MIN_DENOM_USD and (haibun.get("urakataPct") or 0.0) >= 30:
        return True
    dr = haibun.get("dayRule")
    if dr in ("mitai_only", "urakata_finish_only"):
        return True
    return False


def single_task_over_limit(cost_estimate_usd, haibun):
    """1本のタスクのcostEstimate（数値・USD）が週予算の3%を超えるか。"""
    if cost_estimate_usd is None:
        return False
    try:
        total = float(haibun.get("totalCostUsd") or 0.0)
    except Exception:
        total = 0.0
    if total <= 0:
        total = _fallback_weekly_budget()
    limit = total * 0.03
    return float(cost_estimate_usd) > limit


def main():
    haibun = build_haibun()
    with io.open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(haibun, f, ensure_ascii=False, indent=1)
    print(json.dumps(haibun, ensure_ascii=False, indent=1))
    return haibun


if __name__ == "__main__":
    main()
