#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
424番：どの仕事がいくら使ったか見える化（初回だけの穴埋め用）。

harvest() は「これから終わる仕事」からしかコストを拾えない。この道具を1回動かすと、
queue.json に残っている過去の完了済み項目（awaiting_check/verifying/doneで
sessionIdとfinishedAtが残っているもの）のログを遡って読み、
status/cost_by_task.json へ足りない分だけ足す。

**再実行しても安全**（冪等）。cost_by_task.json に既にある番号(n)は二重に足さない。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import auto_launcher as al  # noqa: E402

REPO = al.REPO
QUEUE = al.QUEUE
COST_LEDGER = al.COST_LEDGER


def main():
    q = al.load(QUEUE, {"items": []})
    existing = al.load(COST_LEDGER, {"tasks": []})
    have_n = {t.get("n") for t in (existing.get("tasks") or [])}

    items = [it for it in q.get("items", [])
             if it.get("finishedAt") and it.get("sessionId") and it.get("n") not in have_n]
    items.sort(key=lambda it: it.get("finishedAt") or "")

    added = 0
    for it in items:
        sid = (it.get("sessionId") or "")[:8]
        logf = os.path.join(REPO, "status", "auto-launch-%s.log" % sid)
        if not os.path.exists(logf):
            continue
        raw = io.open(logf, encoding="utf-8", errors="ignore").read()
        cost_usd, tok_in, tok_out, tok_cache_read, tok_cache_creation, model_name = (
            None, 0, 0, 0, 0, "")
        for line in raw.splitlines():
            line = line.strip()
            if not line or '"total_cost_usd"' not in line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue
            cost_usd = j.get("total_cost_usd")
            u = j.get("usage") or {}
            tok_in = int(u.get("input_tokens") or 0)
            tok_out = int(u.get("output_tokens") or 0)
            tok_cache_read = int(u.get("cache_read_input_tokens") or 0)
            tok_cache_creation = int(u.get("cache_creation_input_tokens") or 0)
            mu = j.get("modelUsage") or {}
            if mu:
                model_name = "+".join(mu.keys())
            break
        if cost_usd is None and not tok_in and not tok_out:
            continue  # このログにusageが無い＝拾えるものが無い
        al._record_cost_by_task(it.get("n"), it.get("title"), cost_usd, tok_in, tok_out,
                                 tok_cache_read, tok_cache_creation, model_name,
                                 it.get("startedAt"), it.get("finishedAt"))
        added += 1
    print("穴埋め完了：%d件を status/cost_by_task.json へ追加" % added)


if __name__ == "__main__":
    main()
