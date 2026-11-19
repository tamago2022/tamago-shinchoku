#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
795番（2026-09-14）：数字のズレをゼロに近づけるための共通部品③「予測と実測の突き合わせ」。

たまごさんの言葉：「計算、見立て、見積もり、なんかズレてるよね」。
これまでの事故（例）：
  - fal 771番: 「8.2円」と見積もった → 実費108円（13倍）
  - fal 751番: 「108円」と見積もった → 実費232円（2.1倍）
  - 1本単価: 「$2.43」と見積もった → 実際$6.74（2.8倍）
これらは「予測した時点で記録し、実測が出たら突き合わせる」仕組みが無かったために、
誰も後から「予測がどれだけ外れていたか」を見ておらず、同じ式が直らずに繰り返された。

やること:
  1. 何か（金額・時間・件数）を見積もった時点で record_estimate() を呼び、1行jsonlへ書く（id発行）
  2. 実測が出たら record_actual(id, ...) を呼び、同じidで1行足す（jsonlは追記のみ・書き換えない）
  3. compute_gaps() が id ごとに estimate/actual を突き合わせ、ズレ率の大きい順トップNを出す
  4. ズレ率が2倍を超えた組は "needsFix": true を立てる（「その場で式を直す」対象の目印）

台帳: status/estimate_vs_actual.jsonl（追記専用・行を書き換えない。1id=複数行あってよい）
集計: status/estimate_vs_actual_summary.json（進捗表が読む）

使い方（CLI）:
  python3 tools/estimate_vs_actual.py --estimate --n 771 --kind fal_cost_yen \
      --value 8.2 --formula "0.055秒課金想定 × $0.130/秒 × 150円/$" --note "動画1本"
  python3 tools/estimate_vs_actual.py --actual --id <上のコマンドが返したid> \
      --value 108 --source "fal.aiダッシュボード 2026-09-12 手動確認"
  python3 tools/estimate_vs_actual.py --report          # トップ5を再計算してJSON出力
"""
import argparse
import hashlib
import io
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LEDGER = os.path.join(REPO, "status", "estimate_vs_actual.jsonl")
SUMMARY = os.path.join(REPO, "status", "estimate_vs_actual_summary.json")
NEEDS_FIX_RATIO = 2.0  # このズレ率を超えたら「その場で式を直す」対象


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def make_id(n, kind, ts=None):
    ts = ts or time.strftime("%Y%m%dT%H%M%S")
    raw = "%s-%s-%s" % (n, kind, ts)
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]
    return "%s-%s-%s-%s" % (n if n is not None else "x", kind, ts, h)


def _append(row):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with io.open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def record_estimate(n, kind, value, formula, note="", unit=""):
    """予測した時点で呼ぶ。formula必須（計算式そのまま）。idを返す（あとで record_actual に渡す）。"""
    if not formula:
        raise ValueError("estimateにはformula（計算式）が必須です")
    row_id = make_id(n, kind)
    row = {
        "id": row_id, "n": n, "kind": kind, "type": "estimate",
        "value": value, "unit": unit, "formula": formula, "note": note,
        "t": _now_iso(),
    }
    _append(row)
    return row_id


def record_actual(row_id, value, source, note=""):
    """実測が出た時点で呼ぶ。sourceは必須（取得元）。同じidへ1行足す(書き換えない・追記のみ)。"""
    if not source:
        raise ValueError("actualにはsource（取得元）が必須です")
    row = {
        "id": row_id, "type": "actual",
        "value": value, "source": source, "note": note,
        "t": _now_iso(),
    }
    _append(row)
    return row


def _read_rows():
    rows = []
    try:
        with io.open(LEDGER, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    except Exception:
        pass
    return rows


def compute_gaps(top_n=5):
    """id単位でestimate/actualをまとめ、ズレ率の大きい順トップNを出す。
    ズレ率 = actual/estimate（1.0が完全一致）。0除算・符号ゼロは安全にスキップする。"""
    rows = _read_rows()
    by_id = {}
    for r in rows:
        rid = r.get("id")
        if not rid:
            continue
        by_id.setdefault(rid, {"estimates": [], "actuals": []})
        if r.get("type") == "estimate":
            by_id[rid]["estimates"].append(r)
        elif r.get("type") == "actual":
            by_id[rid]["actuals"].append(r)

    pairs = []
    for rid, g in by_id.items():
        if not g["estimates"] or not g["actuals"]:
            continue
        est = g["estimates"][0]  # 最初の見積もり（後から見積もりを上書きしない）
        act = g["actuals"][-1]   # 最新の実測（更新があれば最新を正とする）
        ev, av = est.get("value"), act.get("value")
        if ev in (None, 0) or av is None:
            continue
        try:
            ev_f, av_f = float(ev), float(av)
            ratio = av_f / ev_f
            # gapScore は「相対誤差＋1」（1.0=完全一致、2.0=見積もりの2倍ズレている）。
            # 符号反転（例：+15.8%超過の見積もりが実は-20ptの下振れだった）や実測ゼロ
            # （例：$55かかると誤検知したが実際は0円）でも Infinity/NaN にならない安全な式。
            gap_score = 1.0 + abs(av_f - ev_f) / abs(ev_f)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if gap_score != gap_score or gap_score in (float("inf"), float("-inf")):  # NaN/Infガード
            continue
        pairs.append({
            "id": rid, "n": est.get("n"), "kind": est.get("kind"), "unit": est.get("unit"),
            "estimateValue": ev, "estimateFormula": est.get("formula"), "estimateAt": est.get("t"),
            "actualValue": av, "actualSource": act.get("source"), "actualAt": act.get("t"),
            "ratio": round(ratio, 3), "gapScore": round(gap_score, 3),
            "needsFix": gap_score >= NEEDS_FIX_RATIO,
        })
    pairs.sort(key=lambda p: p["gapScore"], reverse=True)
    top = pairs[:top_n]
    out = {
        "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pairCount": len(pairs),
        "needsFixCount": sum(1 for p in pairs if p["needsFix"]),
        "top": top,
        "note": ("ズレ率(gapScore)が%.0f倍を超えた式は、その場で直す（たまごさんに毎回謝るのではなく式そのものを直す）"
                  % NEEDS_FIX_RATIO),
    }
    return out


def save_summary(out):
    tmp = SUMMARY + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SUMMARY)


def _cli():
    ap = argparse.ArgumentParser(description="予測と実測の突き合わせ台帳")
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--actual", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--kind")
    ap.add_argument("--id")
    ap.add_argument("--value", type=float)
    ap.add_argument("--formula")
    ap.add_argument("--source")
    ap.add_argument("--unit", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    if args.estimate:
        rid = record_estimate(args.n, args.kind, args.value, args.formula, note=args.note, unit=args.unit)
        print(json.dumps({"id": rid}, ensure_ascii=False))
        return
    if args.actual:
        if not args.id:
            raise SystemExit("--actual には --id が必須（--estimate が返したid）")
        row = record_actual(args.id, args.value, args.source, note=args.note)
        print(json.dumps(row, ensure_ascii=False))
        return
    # 既定：再計算して保存＋表示
    out = compute_gaps(top_n=args.top)
    save_summary(out)
    if not args.report:
        pass
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
