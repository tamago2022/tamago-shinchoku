#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
632番：falの予算管理（モデル別にいくら使ったかを全部記録する）。

たまごさんの言葉（2026-09-07）：
  「ファルの予算管理をしてほしいな。」
  「何のモデルを使ったのかっていうのが気になるよね。何の動画で何を使ったのか。」
  「捨てたものにいくら使ったか」も必ず出す。

status/cost_by_task.json（424番）は Claude Code セッション自体のトークン代を記録するもので、
fal.ai への実費（動画・画像・音声生成）は記録していなかった（今回確認した事実）。
そのため fal 専用の帳簿を新設する。書き方の型（tmpファイル→os.replaceで原子的に置換、
再実行しても安全＝冪等）は 424番の _record_cost_by_task と同じにする。

台帳: status/fal_cost_ledger.json
表示: index.html の「💰 falの予算（モデル別）」セクション（進捗表の「できたもの」棚のすぐ下）

他のタスク（例：636番）からもこのモジュールを import して add_record() を呼べば、
1回投げるごとに1行、この帳簿へ自動で積み上がる仕組みにしてある。

使い方（CLI）:
  python3 tools/fal_cost_ledger.py --add \
    --n 632 --title "アンビエント試作" --model "bytedance/seedance-2.0/mini/image-to-video" \
    --what "8秒微動ループ" --count 1 --unit-cost-usd 0.40 --result adopted \
    --elapsed-min 4.5 --note "花の写真から"

  python3 tools/fal_cost_ledger.py --summary   # 集計をJSONで表示
  python3 tools/fal_cost_ledger.py --check-budget 100   # 100円を使う前に上限を超えないか確認
"""
import argparse
import io
import json
import os
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LEDGER = os.path.join(REPO, "status", "fal_cost_ledger.json")

# 為替換算はledger側の実測記録がある場合そちらを優先し、無い時だけこの概算を使う。
USD_TO_YEN_FALLBACK = 150.0

# 月間の上限（円）。個別タスクの上限（実験150〜300円等）とは別に、月合計の天井として設定。
# 具体額の出典が無いため「工場全体で使いすぎに気づける」を目的にAI側で暫定設定した数値。
# 実績を見ながら調整してよい（このファイルの定数を書き換えるだけで反映される）。
DEFAULT_MONTHLY_CAP_YEN = 3000

RESULT_LABELS = {
    "adopted": "採用",
    "discarded": "捨てた",
    "failed_no_charge": "失敗・無課金",
    "in_progress": "実行中",
}


def load(p, default):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return default


def _atomic_save(data):
    tmp = LEDGER + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LEDGER)


def _record_key(rec):
    """同じ内容の二重記録を防ぐための識別キー（n + model + what + date）。"""
    return (rec.get("n"), rec.get("model"), rec.get("what"), rec.get("date"))


def add_record(n, title, model, what, count=1, unit_cost_usd=None, unit_cost_yen=None,
               total_cost_usd=None, total_cost_yen=None, elapsed_min=None,
               result="adopted", note="", date=None, usd_to_yen=None):
    """1回投げるごとに1行、台帳へ足す。再実行しても同じ内容なら二重に足さない（冪等）。"""
    data = load(LEDGER, {"records": [], "monthlyCapYen": DEFAULT_MONTHLY_CAP_YEN})
    records = data.get("records") or []

    rate = usd_to_yen or USD_TO_YEN_FALLBACK
    if total_cost_usd is None and unit_cost_usd is not None:
        total_cost_usd = round(unit_cost_usd * count, 6)
    if total_cost_yen is None and total_cost_usd is not None:
        total_cost_yen = round(total_cost_usd * rate, 2)
    if total_cost_yen is None and unit_cost_yen is not None:
        total_cost_yen = round(unit_cost_yen * count, 2)
    if unit_cost_yen is None and total_cost_yen is not None and count:
        unit_cost_yen = round(total_cost_yen / count, 2)
    if unit_cost_usd is None and total_cost_usd is not None and count:
        unit_cost_usd = round(total_cost_usd / count, 6)

    rec = {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "n": n,
        "title": title or "",
        "model": model or "",
        "what": what or "",
        "count": count,
        "unitCostUsd": unit_cost_usd,
        "unitCostYen": unit_cost_yen,
        "totalCostUsd": total_cost_usd,
        "totalCostYen": total_cost_yen,
        "elapsedMin": elapsed_min,
        "result": result if result in RESULT_LABELS else "adopted",
        "note": note or "",
        "recordedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    }

    key = _record_key(rec)
    existing_keys = {_record_key(r) for r in records}
    if key in existing_keys:
        return False, rec  # 既に同じ内容がある＝スキップ（冪等）

    records.append(rec)
    data["records"] = records
    if "monthlyCapYen" not in data:
        data["monthlyCapYen"] = DEFAULT_MONTHLY_CAP_YEN
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    data["summary"] = compute_summary(data)
    _atomic_save(data)
    return True, rec


def compute_summary(data=None):
    """モデル別合計・今月合計・最安の1本あたり単価・捨てたものの合計、を計算する。"""
    data = data or load(LEDGER, {"records": [], "monthlyCapYen": DEFAULT_MONTHLY_CAP_YEN})
    records = data.get("records") or []
    cap_yen = data.get("monthlyCapYen", DEFAULT_MONTHLY_CAP_YEN)

    this_month = datetime.now().strftime("%Y-%m")
    month_records = [r for r in records if (r.get("date") or "").startswith(this_month)]
    month_total_yen = round(sum(r.get("totalCostYen") or 0 for r in month_records), 2)
    month_total_usd = round(sum(r.get("totalCostUsd") or 0 for r in month_records), 4)

    all_total_yen = round(sum(r.get("totalCostYen") or 0 for r in records), 2)

    by_model = {}
    for r in records:
        m = r.get("model") or "(不明)"
        b = by_model.setdefault(m, {
            "model": m, "totalYen": 0.0, "totalUsd": 0.0, "count": 0,
            "adoptedCount": 0, "discardedCount": 0, "failedCount": 0,
        })
        b["totalYen"] += r.get("totalCostYen") or 0
        b["totalUsd"] += r.get("totalCostUsd") or 0
        b["count"] += r.get("count") or 1
        if r.get("result") == "adopted":
            b["adoptedCount"] += 1
        elif r.get("result") == "discarded":
            b["discardedCount"] += 1
        elif r.get("result") == "failed_no_charge":
            b["failedCount"] += 1
    by_model_list = sorted(by_model.values(), key=lambda b: b["totalYen"], reverse=True)
    for b in by_model_list:
        b["totalYen"] = round(b["totalYen"], 2)
        b["totalUsd"] = round(b["totalUsd"], 4)

    # 1本あたり単価が一番安かった採用済みの記録
    adopted_with_unit = [r for r in records
                          if r.get("result") == "adopted" and r.get("unitCostYen") not in (None, 0)]
    cheapest = min(adopted_with_unit, key=lambda r: r["unitCostYen"]) if adopted_with_unit else None

    discarded_total_yen = round(sum(
        r.get("totalCostYen") or 0 for r in records if r.get("result") == "discarded"), 2)
    failed_total_yen = round(sum(
        r.get("totalCostYen") or 0 for r in records if r.get("result") == "failed_no_charge"), 2)

    return {
        "thisMonth": this_month,
        "thisMonthTotalYen": month_total_yen,
        "thisMonthTotalUsd": month_total_usd,
        "allTimeTotalYen": all_total_yen,
        "capYen": cap_yen,
        "remainingYen": round(cap_yen - month_total_yen, 2),
        "overCap": month_total_yen > cap_yen,
        "byModel": by_model_list,
        "cheapestPerUnit": ({
            "model": cheapest.get("model"),
            "unitCostYen": cheapest.get("unitCostYen"),
            "what": cheapest.get("what"),
            "n": cheapest.get("n"),
        } if cheapest else None),
        "discardedTotalYen": discarded_total_yen,
        "failedNoChargeTotalYen": failed_total_yen,
        "recordCount": len(records),
    }


def check_budget_before_spend(estimated_yen):
    """投げる前に呼ぶ。上限を超えそうなら ok=False を返し、安い経路を先に試すよう促す。"""
    data = load(LEDGER, {"records": [], "monthlyCapYen": DEFAULT_MONTHLY_CAP_YEN})
    summary = compute_summary(data)
    projected = summary["thisMonthTotalYen"] + estimated_yen
    cap = summary["capYen"]
    ok = projected <= cap
    return {
        "ok": ok,
        "estimatedYen": estimated_yen,
        "currentMonthYen": summary["thisMonthTotalYen"],
        "projectedYen": round(projected, 2),
        "capYen": cap,
        "message": (
            "上限内。実行してよい。" if ok else
            "上限を超える見込み。たまごさんに聞く前に、まず安い経路（低解像度・短尺・別モデル）へ"
            "落とせないか試すこと。それでも必要なら .claude/PENDING_DECISIONS.md 相当の記録先へ1行残す。"
        ),
    }


def _cli():
    ap = argparse.ArgumentParser(description="falの予算管理（モデル別コスト台帳）")
    ap.add_argument("--add", action="store_true", help="1件追加する")
    ap.add_argument("--summary", action="store_true", help="集計をJSONで表示する")
    ap.add_argument("--check-budget", type=float, default=None, metavar="YEN",
                     help="この円数を使う前に上限を超えないか確認する")
    ap.add_argument("--n", type=int)
    ap.add_argument("--title")
    ap.add_argument("--model")
    ap.add_argument("--what")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--unit-cost-usd", type=float, default=None)
    ap.add_argument("--unit-cost-yen", type=float, default=None)
    ap.add_argument("--total-cost-usd", type=float, default=None)
    ap.add_argument("--total-cost-yen", type=float, default=None)
    ap.add_argument("--elapsed-min", type=float, default=None)
    ap.add_argument("--result", default="adopted", choices=list(RESULT_LABELS.keys()))
    ap.add_argument("--note", default="")
    ap.add_argument("--date", default=None)
    args = ap.parse_args()

    if args.check_budget is not None:
        print(json.dumps(check_budget_before_spend(args.check_budget), ensure_ascii=False, indent=2))
        return

    if args.add:
        added, rec = add_record(
            n=args.n, title=args.title, model=args.model, what=args.what, count=args.count,
            unit_cost_usd=args.unit_cost_usd, unit_cost_yen=args.unit_cost_yen,
            total_cost_usd=args.total_cost_usd, total_cost_yen=args.total_cost_yen,
            elapsed_min=args.elapsed_min, result=args.result, note=args.note, date=args.date,
        )
        print(("追加した: " if added else "既に同じ内容が台帳にある（スキップ・冪等）: ")
              + json.dumps(rec, ensure_ascii=False))
        return

    # 既定は集計表示
    print(json.dumps(compute_summary(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
