#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直近24時間で週枠を食っている仕事（2026-10-22 たまごさん指示「今どの仕事が枠を食っているか」）。

~/.claude/projects/*/*.jsonl（Claude Code の会話ログ）の assistant の usage を、直近24時間だけ足す。
重み＝quota_estimate.py と同じトークン重み × モデル単価比（Fable/Opus 5・Sonnet 3・Haiku 1）。
作業場 q<番号> のフォルダは queue.json の番号に結びつける。Cowork の子は会話ログがここに無いので数えられない（正直に書く）。
読むだけ。書くのは status/public/waku_kuu24.json だけ。

  python3 tools/waku_kuu24.py [--hours 24]
  python3 tools/waku_kuu24.py --self-test
"""
import glob
import io
import json
import os
import re
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "public", "waku_kuu24.json")
QUEUE = os.path.join(REPO, "status", "queue.json")
W = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1, "output_tokens": 5.0}


def model_kake(m):
    m = str(m or "")
    if "fable" in m or "opus" in m:
        return 5.0
    if "haiku" in m:
        return 1.0
    return 3.0


def ts(s):
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").timestamp() + 9 * 3600 if str(s).endswith("Z") else \
            datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
    except Exception:
        return None


def scan(hours=24.0, root=None):
    root = root or os.path.expanduser("~/.claude/projects")
    since = time.time() - hours * 3600
    rows = []
    for p in glob.glob(os.path.join(root, "*", "*.jsonl")):
        try:
            if os.path.getmtime(p) < since:
                continue
        except Exception:
            continue
        w, msgs, models, first, t0, t1 = 0.0, 0, {}, None, None, None
        try:
            for ln in io.open(p, encoding="utf-8", errors="ignore"):
                if first is None and '"type":"user"' in ln:
                    try:
                        e = json.loads(ln)
                        c = (e.get("message") or {}).get("content")
                        if isinstance(c, list):
                            c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        first = re.sub(r"\s+", " ", str(c or ""))[:90]
                    except Exception:
                        pass
                if '"usage"' not in ln or '"type":"assistant"' not in ln:
                    continue
                try:
                    e = json.loads(ln)
                except Exception:
                    continue
                t = ts(e.get("timestamp"))
                if t is None or t < since:
                    continue
                m = e.get("message") or {}
                u = m.get("usage") or {}
                k = model_kake(m.get("model"))
                ww = sum(float(u.get(x) or 0) * v for x, v in W.items()) * k
                w += ww
                msgs += 1
                models[str(m.get("model"))] = models.get(str(m.get("model")), 0) + 1
                t0 = t if t0 is None else min(t0, t)
                t1 = t if t1 is None else max(t1, t)
        except Exception:
            continue
        if msgs:
            d = os.path.basename(os.path.dirname(p))
            mm = re.search(r"worktrees-q(\d+)", d)
            rows.append({"dir": d, "n": mm.group(1) if mm else None, "w": round(w), "msgs": msgs,
                         "model": max(models, key=models.get), "first": first,
                         "from": time.strftime("%m-%d %H:%M", time.localtime(t0)),
                         "to": time.strftime("%m-%d %H:%M", time.localtime(t1))})
    return rows


def matome(rows, items=None):
    items = items or {}
    tot = sum(r["w"] for r in rows) or 1
    by = {}
    for r in rows:
        key = ("n" + r["n"]) if r["n"] else r["dir"]
        b = by.setdefault(key, {"key": key, "n": r["n"], "w": 0, "msgs": 0, "sessions": 0,
                                "model": r["model"], "first": r["first"], "dir": r["dir"]})
        b["w"] += r["w"]; b["msgs"] += r["msgs"]; b["sessions"] += 1
    out = sorted(by.values(), key=lambda b: -b["w"])
    for b in out:
        b["share"] = round(100.0 * b["w"] / tot, 1)
        if b["n"] and b["n"] in items:
            b["title"] = (items[b["n"]].get("title") or "")[:80]
    return {"sessions": len(rows), "total_w": tot, "top": out[:15]}


def self_test():
    rows = [{"dir": "-x-worktrees-q1", "n": "1", "w": 300, "msgs": 3, "model": "claude-sonnet-5", "first": "a"},
            {"dir": "-x-worktrees-q1", "n": "1", "w": 100, "msgs": 1, "model": "claude-sonnet-5", "first": "a"},
            {"dir": "-vault", "n": None, "w": 100, "msgs": 1, "model": "claude-opus-5-5", "first": "b"}]
    m = matome(rows, {"1": {"title": "t"}})
    ok = m["top"][0]["key"] == "n1" and m["top"][0]["share"] == 80.0 and m["top"][0]["sessions"] == 2 \
        and model_kake("claude-opus-5-5") == 5.0 and model_kake("claude-haiku-4-5") == 1.0
    print("SELF-TEST OK" if ok else "SELF-TEST NG %r" % m)
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    hours = float(a[a.index("--hours") + 1]) if "--hours" in a else 24.0
    try:
        items = {str(i.get("n")): i for i in (json.load(io.open(QUEUE, encoding="utf-8")).get("items") or [])}
    except Exception:
        items = {}
    m = matome(scan(hours), items)
    m["at"] = time.strftime("%Y-%m-%d %H:%M")
    m["hours"] = hours
    m["note"] = "Claude Code の会話ログだけ。Cowork/Dispatch の子は数えられない。重み＝トークン重み×モデル単価比"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(m, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for b in m["top"][:8]:
        print("%5.1f%%  %s  %d本  %s  %s" % (b["share"], b["key"], b["sessions"], b["model"], (b.get("title") or b["first"] or "")[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
