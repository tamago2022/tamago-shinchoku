#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1043番【スマホの門】たまごさんのiPhoneのSafariと同じ経路で、箱のボタンを実際に押す門。

たまごさん（2026-09-24・原文）:
  「こういうのを俺で試さないでよ。俺が依頼したものが確実になってるものだけ見せてよ」
  「Macからの投げが通っても意味がない。たまごさんが使う経路で通す」

やること（工場側＝Macで走る。サンドボックスからは中継所へ出られないため）:
  1. tools/sumaho_gate.mjs を呼ぶ（headless Chrome・iPhoneのUA・375x812・タッチあり）
  2. 本番の箱ページを開いて、4パターンを**ボタンを押して**投げる
  3. 画面に出た文字（届いた／届かなかった＋理由）と、consoleのエラー、CORSの遮断を全部拾う
  4. 台帳（status/nagekomi.jsonl）が本当に増えたかを、投げる前後の行数で突き合わせる
     ★画面が「届いた」と言っても台帳が増えていなければ**通っていない**と判定する

★投げるURLには ?kikai=1 が付く＝台帳に「機械の試し投げ」の印が入る。
  たまごさんの一覧には1件も混ざらない（tools/nagekomi_list.py が既定で外す）。

使い方:
  python3 tools/sumaho_gate.py
  python3 tools/sumaho_gate.py --box <箱のURL>
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JST = timezone(timedelta(hours=9))
STATUS = os.path.join(REPO, "status")
LEDGER = os.path.join(STATUS, "nagekomi.jsonl")
OUT_JSON = os.path.join(STATUS, "sumaho_gate.json")
PNG = os.path.join(STATUS, "sumaho_gate_375.png")
BOX = ("https://tamago2022.github.io/tamago-shinchoku/share/"
       "nagekomi-c5fd9d5791b32e88.html")
LIMIT_SEC = 300


def now():
    return datetime.now(JST)


def ledger_ids():
    ids = set()
    try:
        for line in io.open(LEDGER, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line).get("id"))
            except Exception:
                pass
    except OSError:
        pass
    return ids


def run(box=None):
    box = box or BOX
    res = {"ranAt": now().strftime("%Y-%m-%d %H:%M"), "box": box,
           "diag": [], "red": [], "totalYen": 0.0}
    mjs = os.path.join(HERE, "sumaho_gate.mjs")
    if not os.path.exists(mjs):
        res["red"].append("tools/sumaho_gate.mjs が無い")
        res["ok"] = False
        return res

    before = ledger_ids()
    res["diag"].append("投げる前の台帳 %d行" % len(before))
    t0 = time.time()
    try:
        r = subprocess.run(["node", mjs, box, OUT_JSON, PNG],
                           capture_output=True, text=True, timeout=LIMIT_SEC)
    except subprocess.TimeoutExpired:
        res["red"].append("スマホの門が %d秒で終わらなかった" % LIMIT_SEC)
        res["ok"] = False
        return res
    res["seconds"] = round(time.time() - t0, 1)
    try:
        gate = json.load(io.open(OUT_JSON, encoding="utf-8"))
    except Exception:
        gate = {"error": (r.stderr or r.stdout or "")[-600:]}
    res["gamen"] = gate.get("oshita") or []
    res["console"] = (gate.get("console") or [])[-12:]
    res["netFail"] = (gate.get("netFail") or [])[-8:]
    res["pageDiag"] = str(gate.get("diag") or "")[:800]
    if gate.get("corsBlocked"):
        # ★これが1043番で探していたもの。ブラウザが本番のPOSTを送らずに捨てた証拠
        res["red"].append("★ブラウザが止めた（CORS）：%s" % str(gate["corsBlocked"])[:200])
    if gate.get("error"):
        res["red"].append("門が転んだ：%s" % str(gate["error"])[:300])
    if gate.get("png"):
        res["png"] = gate["png"]

    # ★画面の言葉を信じない。台帳が増えたかで判定する
    time.sleep(3)
    after = ledger_ids()
    fueta = [i for i in after - before if i]
    res["fuetaCount"] = len(fueta)
    res["fuetaIds"] = fueta
    res["diag"].append("投げた後の台帳 %d行（増えた %d件）" % (len(after), len(fueta)))
    gamen_ok = sum(1 for x in res["gamen"] if x.get("ok"))
    res["gamenOk"] = gamen_ok
    # ④パターン：URLの分が3本＋ひとことだけの分は nagekomi_shiji（別の置き場）なので台帳は増えない
    res["kitai"] = {"台帳に増える本数": 3, "指示として残る本数": 1}
    if len(fueta) < 3:
        res["red"].append("★台帳が %d件しか増えていない（3件のはず）＝スマホの経路が通っていない"
                          % len(fueta))
    if gamen_ok < 4:
        res["red"].append("★画面が「届いた」と出なかったパターンがある（%d/4）" % gamen_ok)
    res["ok"] = not res["red"]
    return res


def run_job(payload):
    p = payload or {}
    out = run(box=p.get("box"))
    out.setdefault("totalYen", 0.0)
    out.setdefault("ok", not out.get("red"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box")
    a = ap.parse_args()
    print(json.dumps(run(box=a.box), ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
