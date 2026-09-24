#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1075番【Gensparkの口】gsk を工場（Mac）側で叩くための、白名簿つきの1本。

たまごさん（2026-09-24・原文）:
  「Gensparkが読める形で置く。実際にGensparkに1回読ませて『読めた』ことを確かめる。」
  「たまごさんにコピペさせない。」

★実測で分かっていること（1075-genspark-notion.html・2026-09-24）
  ・Genspark に Notion は**つながっていない**（`gsk sb-brain ls -s notion` → No mounted source）
  ・見える書庫は project_history と memo の2つだけ
  ・`gsk me` は**クレジットを消費しない**（実測：前後で不変）

━━ 決まり ━━
  ① ★白名簿の外のサブコマンドは走らせない。
  ② ★金が出る問い（search / task create）は、tools/yosan.py の栓を通してからでないと走らない。
  ③ ★叩く前と後の残クレジットを必ず記録する（status/gsk_daicho.jsonl）。
  ④ ★契約・課金のボタンを押さない。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT_DIR = os.path.join(REPO, "status", "1075_spotify")

# ★0円で通ることが実測できているもの＋中を見るだけのもの
TADA = {
    ("me",), ("--help",), ("help",),
    ("sb-brain", "--help"), ("sb-brain", "list-repos"),
    ("sb-brain", "ls"), ("sb-brain", "grep"), ("sb-brain", "read"),
    ("sb-brain", "add", "--help"), ("sb-brain", "write", "--help"),
    ("sb-brain", "upload", "--help"), ("sb-brain", "mount", "--help"),
    # ★2026-09-24 実測：gsk に **notion の口がある**（search / read / create）。
    #   「Gensparkは Notion につながっていない」は sb-brain の話で、こちらは別の口。
    ("notion", "--help"), ("notion", "search"), ("notion", "read"),
    ("notion", "create"),   # ★--help を見るため。実際に作るときは下のKAKUの栓を通す
    ("hub", "--help"), ("hub", "list_hubs"),
}

# ★書き込む口。走らせる前に必ず tools/yosan.py の栓を通す。
KAKU = {("notion", "create")}


def _gsk():
    import genspark_nagashi as gn
    return gn.gsk_path()


def _run(args, timeout=120):
    exe = _gsk()
    if not exe:
        return {"ok": False, "error": "gsk が見つかりませんでした"}
    try:
        r = subprocess.run([exe] + list(args), capture_output=True, text=True,
                           timeout=timeout)
        return {"ok": r.returncode == 0, "rc": r.returncode,
                "stdout": (r.stdout or "")[-6000:], "stderr": (r.stderr or "")[-2000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "%d秒で返りませんでした" % timeout}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _yurusu(args):
    for n in (2, 1):
        if tuple(args[:n]) in TADA:
            return True
    return False


def run_job(payload):
    payload = payload or {}
    op = (payload.get("op") or "tameshi")

    if op == "tameshi":
        # ★白名簿の中だけを順に叩いて、「何ができる口があるか」を実測で並べる。課金0。
        shirabe = [["--help"], ["sb-brain", "--help"], ["sb-brain", "list-repos"],
                   ["sb-brain", "add", "--help"], ["sb-brain", "upload", "--help"]]
        out = []
        for a in shirabe:
            r = _run(a, timeout=60)
            out.append({"cmd": "gsk " + " ".join(a), "ok": r.get("ok"),
                        "stdout": (r.get("stdout") or "")[:2500],
                        "stderr": (r.get("stderr") or "")[:500],
                        "error": r.get("error", "")})
        os.makedirs(OUT_DIR, exist_ok=True)
        json.dump({"at": time.strftime("%F %T"), "kekka": out},
                  io.open(os.path.join(OUT_DIR, "gsk_dekirukoto.json"), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
        return {"ok": True, "op": op, "kekka": out, "totalYen": 0.0}

    if op == "tataku":
        args = payload.get("args") or []
        if not _yurusu(args):
            return {"ok": False, "error": "白名簿の外なので走らせません: %s" % " ".join(args[:3]),
                    "totalYen": 0.0}
        r = _run(args, timeout=int(payload.get("timeoutSec") or 120))
        r["totalYen"] = 0.0
        return r

    return {"ok": False, "error": "知らない op です: %s" % op, "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"op": sys.argv[1] if len(sys.argv) > 1 else "tameshi"}),
                     ensure_ascii=False, indent=1))
