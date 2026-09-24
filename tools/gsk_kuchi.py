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
    # ★1076番：エージェントの口（gsk task）の使い方を見るだけ。--help は課金0。
    ("task", "--help"), ("task", "help"), ("task", "status"), ("task", "info"),
    ("task", "artifacts"), ("task", "artifact"),
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

    if op == "notionkaku":
        # ★Notionに1枚書く。Gensparkの口から書くので、そのままGensparkが読める。
        #   ★書く前と後の残クレジットを必ず測る（憶測で「無料」と書かない）。
        title = (payload.get("title") or "").strip()
        content = payload.get("content") or ""
        parent = (payload.get("parentId") or "").strip()
        if not title or not content or not parent:
            return {"ok": False, "error": "title / content / parentId が要ります",
                    "totalYen": 0.0}

        zen = _run(["me"], timeout=60)
        args_file = os.path.join(OUT_DIR, "_notion_args.json")
        os.makedirs(OUT_DIR, exist_ok=True)
        json.dump({"title": title, "content": content,
                   "parent_id": parent, "parent_type": "page_id"},
                  io.open(args_file, "w", encoding="utf-8"), ensure_ascii=False)
        r = _run(["notion", "create", "--args-file", args_file],
                 timeout=int(payload.get("timeoutSec") or 180))
        ato = _run(["me"], timeout=60)
        try:
            os.remove(args_file)
        except OSError:
            pass

        url = ""
        try:
            d = json.loads((r.get("stdout") or "").strip().splitlines()[-1])
            dd = d.get("data") or {}
            url = (dd.get("url") if isinstance(dd, dict) else "") or ""
        except Exception:
            pass
        try:
            io.open(os.path.join(REPO, "status", "gsk_daicho.jsonl"), "a",
                    encoding="utf-8").write(json.dumps(
                        {"at": time.strftime("%F %T"), "nani": "notion create",
                         "title": title, "ok": r.get("ok"), "url": url},
                        ensure_ascii=False) + "\n")
        except Exception:
            pass
        return {"ok": bool(r.get("ok")), "op": op, "url": url,
                "stdout": (r.get("stdout") or "")[:1200],
                "stderr": (r.get("stderr") or "")[:500],
                "zanMae": (zen.get("stdout") or "")[-300:],
                "zanAto": (ato.get("stdout") or "")[-300:],
                "totalYen": 0.0}

    if op == "tataku":
        args = payload.get("args") or []
        if not _yurusu(args):
            return {"ok": False, "error": "白名簿の外なので走らせません: %s" % " ".join(args[:3]),
                    "totalYen": 0.0}
        r = _run(args, timeout=int(payload.get("timeoutSec") or 120))
        r["totalYen"] = 0.0
        return r

    if op == "helpzenbu":
        # ★1076番：`gsk --help` の**頭**が要る（_run が末尾6000字しか返さないので見えない）。
        #   課金0。白名簿の中だけ。全文はファイルへ落として、そこから読む。
        args = payload.get("args") or ["--help"]
        if not _yurusu(args):
            return {"ok": False, "error": "白名簿の外", "totalYen": 0.0}
        exe = _gsk()
        r = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=90)
        os.makedirs(OUT_DIR, exist_ok=True)
        fn = os.path.join(OUT_DIR, "gsk_help_zenbu.txt")
        io.open(fn, "w", encoding="utf-8").write((r.stdout or "") + "\n" + (r.stderr or ""))
        return {"ok": r.returncode == 0, "op": op, "file": fn,
                "atama": (r.stdout or "")[:12000], "totalYen": 0.0}

    if op == "shirabe":
        # ★1076番（2026-09-24 追記・足すだけ／既存の op は1文字も変えていない）
        #   `gsk search <長い問い>` を1回だけ投げる。実測1クレジット／1回。
        #   ★心臓の genspark_nagashi の口（tick_every 4）は 06:44 を最後に回っていない
        #     （status/gsk/nagashi.log が06:44で止まっている＝動いている心臓に反映されていない）。
        #     だから同じ配管を**待ち行列の側から**呼ぶ。台帳・残クレジットの記録は
        #     genspark_nagashi.hitotsu_nageru をそのまま使う＝記録の形は1つのまま。
        toi = (payload.get("q") or "").strip()
        if not toi:
            return {"ok": False, "error": "q（問い）が要ります", "totalYen": 0.0}
        import importlib
        import genspark_nagashi as gn
        importlib.reload(gn)
        s = {"bangou": payload.get("bangou") or 20,
             "namae": payload.get("namae") or "1076番 Gensparkに作らせる",
             "gsk": ["search", "{{q}}"]}
        g = gn.hitotsu_nageru(s, toi, meta={"対象": payload.get("namae") or "1076番"})
        honbun = ""
        if g.get("答え"):
            try:
                honbun = io.open(os.path.join(REPO, g["答え"]), encoding="utf-8").read()
            except Exception:
                honbun = ""
        return {"ok": bool(g.get("ok")), "op": op, "kotaeFile": g.get("答え"),
                "zanMae": None, "zan": g.get("残クレジット"),
                "tsukatta": g.get("使ったクレジット"),
                "error": g.get("error"), "honbun": honbun[:400000],
                "totalYen": 0.0}

    return {"ok": False, "error": "知らない op です: %s" % op, "totalYen": 0.0}


if __name__ == "__main__":
    print(json.dumps(run_job({"op": sys.argv[1] if len(sys.argv) > 1 else "tameshi"}),
                     ensure_ascii=False, indent=1))
