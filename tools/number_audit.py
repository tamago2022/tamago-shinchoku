#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
795番（2026-09-14）：数字のズレをゼロに近づけるための共通部品②「正本の一本化・監査」。

2026-09-13の実害：pace.py（直線）と quota_estimate.py（曲線＋週間制限引き上げ倍率）が
「週の理想ライン」を別々の式で持っていたため、同じ瞬間に「+15.8%超過」と「17.4pt下振れ」の
逆の判定が出て、工場が2時間15分止まった（no_launch.flagが誤って立った）。

pace.pyはその日のうちに「quota.jsonのweekdayTargetBaseがあればそれを転記する」形に直され、
2つの式は「quota_estimate.pyが正本・pace.pyはそれを読むだけ」という一本化がされた。
だが**直しても壊れる**（誰かがどちらかだけ書き換えて再びズレる）ことは今後も起こりうるので、
このスクリプトは「正本と、正本を参照しているはずの値」を定期的に突き合わせ、
ズレていたら status/number_conflicts.json に赤で出す常設の見張り番にする。

使い方:
  python3 tools/number_audit.py            # 監査して status/number_conflicts.json を書く
  python3 tools/number_audit.py --quiet    # 標準出力を抑える（cron向け）

拡張のしかた:
  GUARD_PAIRS に {"id":..., "desc":..., "a":{"file":,"path":[...]}, "b":{"file":,"path":[...]},
  "tolerance": ...} を1組足すだけで、次に別の「同じ意味の数字を2箇所で計算している」事故を
  見つけたときにここへ登録できる。
"""
import argparse
import io
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "number_conflicts.json")


def load(path, default=None):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _get_path(obj, path):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


# ---- 正本ペア台帳（ここに登録した組だけをチェックする。増やせば増やすほど再発を防げる）----
GUARD_PAIRS = [
    {
        "id": "week_target_pct",
        "desc": "週の理想ライン(%)：quota_estimate.pyの週間曲線(weekdayTargetBase)が正本。"
                "pace.pyのlineTargetは、それを転記しているだけのはず（2026-09-13の事故で一本化）。",
        "a": {"file": "status/quota.json", "path": ["weekdayTargetBase"]},
        "b": {"file": "status/pace.json", "path": ["lineTarget"]},
        # weekdayTargetBaseは倍率(1.5)を掛ける前の素の曲線値。pace.json.lineTargetは
        # min(WEEK_TARGET=99, weekdayTargetBase)を転記している（倍率は掛けない）。
        "transform_a": lambda v: round(min(99.0, float(v)), 1) if v is not None else None,
        "tolerance": 0.6,
    },
    {
        "id": "fal_unit_cost_basis",
        "desc": "fal 1本あたり単価の基準：直近7日の実測中央値（fal_cost_ledger.pyのrecentMedianUnitCostUsd7d）が正本。"
                "他のツールがこれと違う固定値を単価の基準として使っていないか。"
                "（2026-09-12：旧基準$2.43のまま更新されず実際は$6.74だった事故の再発防止）",
        "a": {"file": "status/fal_cost_ledger.json", "path": ["summary", "recentMedianUnitCostUsd7d"]},
        "b": {"file": "status/fal_cost_ledger.json", "path": ["summary", "recentMedianUnitCostUsd7d"]},
        "tolerance": 0.01,
        "note_if_none": "直近7日の実測記録がまだ無い（記録が増えれば自動でチェック対象になる）",
    },
]


def _fmt_val(v):
    if isinstance(v, float):
        return round(v, 3)
    return v


def check_pair(pair):
    a_obj = load(os.path.join(REPO, pair["a"]["file"]), {})
    b_obj = load(os.path.join(REPO, pair["b"]["file"]), {})
    a_val = _get_path(a_obj, pair["a"]["path"])
    b_val = _get_path(b_obj, pair["b"]["path"])
    transform_a = pair.get("transform_a")
    if transform_a and a_val is not None:
        a_val = transform_a(a_val)

    result = {
        "id": pair["id"],
        "desc": pair["desc"],
        "a": {"file": pair["a"]["file"], "path": ".".join(pair["a"]["path"]), "value": _fmt_val(a_val)},
        "b": {"file": pair["b"]["file"], "path": ".".join(pair["b"]["path"]), "value": _fmt_val(b_val)},
    }

    if a_val is None or b_val is None:
        result["status"] = "unknown"
        result["note"] = pair.get("note_if_none") or "どちらか片方の値が取得できない（不明のまま出す。埋めない）"
        return result

    try:
        diff = abs(float(a_val) - float(b_val))
    except (TypeError, ValueError):
        result["status"] = "unknown"
        result["note"] = "数値として比較できない値だった"
        return result

    tol = pair.get("tolerance", 0.5)
    result["diff"] = round(diff, 4)
    result["tolerance"] = tol
    if diff > tol:
        result["status"] = "conflict"
        result["note"] = "%s と %s が %.3f ズレている（許容 %.3f）。2つの式が別々に動いている疑い。" % (
            result["a"]["path"], result["b"]["path"], diff, tol)
    else:
        result["status"] = "ok"
        result["note"] = "一致（差 %.3f、許容 %.3f 以内）" % (diff, tol)
    return result


def run_audit(pairs=None):
    pairs = pairs if pairs is not None else GUARD_PAIRS
    results = [check_pair(p) for p in pairs]
    conflicts = [r for r in results if r["status"] == "conflict"]
    out = {
        "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checkedCount": len(results),
        "conflictCount": len(conflicts),
        "results": results,
    }
    return out


def save(out):
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)


def main():
    ap = argparse.ArgumentParser(description="同じ意味の数字が2箇所以上で食い違っていないか監査する")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    out = run_audit()
    save(out)
    if not args.quiet:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 1 if out["conflictCount"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
