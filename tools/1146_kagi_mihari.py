#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1146 鍵の見張り。

鍵の「値」は一切読まない・一切出さない。
見るのは「そこにファイル／項目があるか」と「あと何日で切れるか」だけ。

使い方:
    python3 tools/1146_kagi_mihari.py              # 人が読む形
    python3 tools/1146_kagi_mihari.py --json       # 機械が読む形
    python3 tools/1146_kagi_mihari.py --warn-days 30

終了コード:
    0 = 全部生きている
    1 = 期限が近い鍵がある（警告）
    2 = 死んでいる／置き場が無い鍵がある（赤）
"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DAICHO = os.path.join(ROOT, "status", "1146", "kagi_daicho.json")
OUT = os.path.join(ROOT, "status", "1146", "kagi_jotai.json")


def expand(path: str) -> str:
    return os.path.expanduser(path.split(":", 1)[0])


def has_key(entry: dict) -> bool:
    """置き場に鍵が『在るか』だけを見る。中身は読まない。"""
    raw = entry.get("path") or ""
    p = expand(raw)
    if not os.path.exists(p):
        return False
    if ":" in raw:  # env ファイルの中の項目名まで指定されている
        name = raw.split(":", 1)[1]
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(name + "="):
                        # 値そのものは絶対に返さない。空でないことだけ。
                        return len(line.split("=", 1)[1].strip()) > 0
        except OSError:
            return False
        return False
    try:
        return os.path.getsize(p) > 0
    except OSError:
        return False


def days_left(entry: dict, today: dt.date):
    life = entry.get("lifetime_days")
    if not life:
        return None  # 期限なし
    issued = entry.get("issued")
    if not issued:
        return None  # 取得日が不明＝計算できない（推測で埋めない）
    got = dt.date.fromisoformat(issued)
    return (got + dt.timedelta(days=life) - today).days


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warn-days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", default=None)
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    with open(DAICHO, "r", encoding="utf-8") as f:
        daicho = json.load(f)

    rows, worst = [], 0
    for e in daicho["keys"]:
        alive = has_key(e)
        left = days_left(e, today)
        if not alive:
            mark, level = "赤", 2
            note = "置き場に鍵が無い"
        elif left is not None and left < 0:
            mark, level = "赤", 2
            note = f"{-left}日前に切れている"
        elif left is not None and left <= args.warn_days:
            mark, level = "黄", 1
            note = f"あと{left}日"
        elif left is None and e.get("lifetime_days"):
            mark, level = "黄", 1
            note = "取得日が台帳に無い＝残り日数が出せない"
        else:
            mark, level = "青", 0
            note = "期限なし" if left is None else f"あと{left}日"
        worst = max(worst, level)
        rows.append({
            "id": e["id"], "name": e["name"], "mark": mark,
            "days_left": left, "note": note,
            "human_per_year": e.get("human_per_year"),
            "renew": e.get("renew"),
        })

    result = {"checked_at": today.isoformat(), "worst": worst, "rows": rows,
              "te_per_year": sum(r["human_per_year"] or 0 for r in rows)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"鍵の見張り {today}　／　たまごさんの手＝年{result['te_per_year']}回")
        print("-" * 64)
        for r in rows:
            print(f"[{r['mark']}] {r['name']}　… {r['note']}")
            if r["mark"] != "青":
                print(f"      直し方: {r['renew']}")
        print("-" * 64)
        print({0: "全部生きている", 1: "期限が近いものがある", 2: "死んでいる鍵がある"}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
