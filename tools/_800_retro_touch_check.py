#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件#800：過去に「PASS」で確認待ちを素通りした（=status: done）仕事のうち、
本番URLを持つものを対象に、新しい「触る検品」(tools/verify_click.mjs)を後追いで実行し、
何件が実は不合格だったかを実測する（今までどれだけ素通ししていたかの実数を出す）。

使い方: python3 tools/_800_retro_touch_check.py [--limit N]
出力: status/retro_touch_check_800.json（サンプル・結果・件数）
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import auto_launcher as al  # noqa: E402

QUEUE = os.path.join(REPO, "status", "queue.json")
OUT = os.path.join(REPO, "status", "retro_touch_check_800.json")


def pick_candidates(limit):
    q = json.load(io.open(QUEUE, encoding="utf-8"))
    cands = []
    for it in q.get("items", []):
        if it.get("status") != "done":
            continue
        urls = it.get("urls") or []
        prod = [u for u in urls if u.startswith("http")
                and "/share/check/" not in u
                and "github.com" not in u
                and "lovable.dev" not in u]
        if not prod:
            continue
        # joy-relief-station（実際に触れるUIを持つ本番ページ）を優先する
        pri = [u for u in prod if "joy-relief-station.lovable.app" in u]
        cands.append((it.get("n"), it.get("title") or "", (pri or prod)[0]))
    # 新しい順（nが大きい順）に取り、joy-relief-stationのcover-guide系を優先的に混ぜる
    cands.sort(key=lambda c: c[0], reverse=True)
    prioritized = [c for c in cands if "joy-relief-station" in c[2]]
    others = [c for c in cands if "joy-relief-station" not in c[2]]
    ordered = prioritized[: max(0, limit - 2)] + others[:2]
    # 重複URLは1回だけ
    seen = set()
    out = []
    for c in ordered:
        if c[2] in seen:
            continue
        seen.add(c[2])
        out.append(c)
    return out[:limit]


def run_one(n, title, url, per_item_timeout=200):
    it = {}
    if not al.start_touch_check(it, url):
        return {"n": n, "title": title, "url": url, "ok": None, "reason": "着火失敗"}
    t0 = time.time()
    while True:
        outcome = al.collect_touch_check(it)
        if outcome is not None:
            ok, reason, report = outcome
            return {"n": n, "title": title, "url": url, "ok": ok, "reason": reason,
                    "summary": {
                        "totalClickable": (report or {}).get("totalClickable"),
                        "tested": (report or {}).get("tested"),
                        "noResponseCount": len((report or {}).get("noResponse") or []),
                        "consoleErrorCount": len((report or {}).get("consoleErrors") or []),
                    }}
        if time.time() - t0 > per_item_timeout:
            pid = it.get("touchPid")
            if pid:
                try:
                    os.kill(int(pid), 9)
                except Exception:
                    pass
            return {"n": n, "title": title, "url": url, "ok": None, "reason": "個別タイムアウト"}
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    cands = pick_candidates(args.limit)
    results = []
    for n, title, url in cands:
        print("→ 検品中: %s番 %s" % (n, url), file=sys.stderr, flush=True)
        r = run_one(n, title, url)
        print("  結果:", r.get("ok"), r.get("reason"), file=sys.stderr, flush=True)
        results.append(r)
        # 書きかけでも都度保存（外部状態への冪等な途中保存・止まっても失われない）
        _save(cands, results)

    _save(cands, results)
    fails = [r for r in results if r.get("ok") is False]
    errs = [r for r in results if r.get("ok") is None]
    passes = [r for r in results if r.get("ok") is True]
    print("=== 集計 ===")
    print("検品対象: %d件" % len(results))
    print("不合格（無反応/コンソールエラー）: %d件" % len(fails))
    print("合格: %d件" % len(passes))
    print("技術的エラー（測れず）: %d件" % len(errs))
    for r in fails:
        print("  ✗ %s番「%s」 %s — %s" % (r["n"], (r["title"] or "")[:30], r["url"], r["reason"]))


def _save(cands, results):
    data = {
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "sampleSize": len(cands),
        "done": len(results),
        "results": results,
    }
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)


if __name__ == "__main__":
    main()
