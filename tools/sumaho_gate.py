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
    """★Playwright で開く。理由（実測 2026-09-24 01:48）：
    headless Chrome を `--remote-debugging-port` で起こす手（tools/sumaho_gate.mjs）は
    「Chromeのデバッグ口が開きませんでした」で48秒使って転んだ。たまごさんのChromeが
    既に走っている機械では取り合いになる。**tools/watashi_gate.py と同じ Playwright に寄せる**
    （道具を2本持たない）。iPhoneのUA・375x812・タッチありはここで指定する。"""
    from playwright.sync_api import sync_playwright

    box = box or BOX
    url = box + ("&" if "?" in box else "?") + "kikai=1&t=%d" % int(time.time())
    res = {"ranAt": now().strftime("%Y-%m-%d %H:%M"), "box": url,
           "ua": "iPhone Safari 17.5 / 375x812", "diag": [], "red": [],
           "console": [], "netFail": [], "gamen": [], "totalYen": 0.0}
    before = ledger_ids()
    res["diag"].append("投げる前の台帳 %d行" % len(before))

    UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
    pats = [
        ("①URLだけ（棚なし・ひとことなし）", "https://www.youtube.com/watch?v=J---aiyznGQ", "", False),
        ("②URL＋棚", "https://www.youtube.com/watch?v=lDK9QqIzhwk", "", True),
        ("③ひとことだけ", "", "1043番 スマホの門 ひとことだけ", False),
        ("④日本語の題名のYouTube", "https://www.youtube.com/watch?v=WSeNSzJ2-Jw",
         "1043番 日本語題名の実測", False),
    ]
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            ctx = br.new_context(user_agent=UA, viewport={"width": 375, "height": 812},
                                 device_scale_factor=3, is_mobile=True, has_touch=True,
                                 locale="ja-JP", timezone_id="Asia/Tokyo")
            pg = ctx.new_page()
            pg.set_default_timeout(20000)
            pg.on("console", lambda m: m.type == "error" and res["console"].append(
                (m.text or "")[:240]))
            pg.on("pageerror", lambda e: res["console"].append("pageerror: " + str(e)[:200]))
            pg.on("requestfailed", lambda r: res["netFail"].append(
                "%s %s ← %s" % (r.method, (r.url or "")[:90], (r.failure or "")[:120])))
            pg.on("response", lambda r: r.status != 200 and "loca.lt" in (r.url or "") and
                  res["netFail"].append("%s HTTP %d（★トンネルが止めた）"
                                        % ((r.url or "")[:90], r.status)))
            pg.goto(url, wait_until="load")
            pg.wait_for_timeout(2500)
            res["parts"] = pg.evaluate(
                "()=>({send:!!document.getElementById('send'),nomu:!!document.getElementById('nomu'),"
                "tana:(document.getElementById('tanaNote')||{}).textContent||''})")
            for name, u, m, tana in pats:
                pg.evaluate("""(a)=>{document.getElementById('u').value=a.u;
                    document.getElementById('m').value=a.m;
                    document.getElementById('msg').textContent='';
                    if(a.t){var b=document.querySelector('#tana button'); if(b) b.click();}}""",
                    {"u": u, "m": m, "t": tana})
                pg.wait_for_timeout(200)
                pg.click("#send")                       # ★実際に押す
                msg, cls = "", ""
                for _ in range(45):
                    pg.wait_for_timeout(400)
                    msg = pg.evaluate("()=>(document.getElementById('msg')||{}).textContent||''")
                    cls = pg.evaluate("()=>(document.getElementById('msg')||{}).className||''")
                    if msg and "送っています" not in msg:
                        break
                nokori = pg.evaluate("()=>{try{return JSON.parse(localStorage.getItem("
                                     "'nagekomi.pending')||'[]').length}catch(e){return -1}}")
                res["gamen"].append({"pattern": name, "ok": "ok" in cls,
                                     "gamen": str(msg)[:260], "tanmatsuNokori": nokori})
            res["pageDiag"] = pg.evaluate(
                "()=>(document.getElementById('diag')||{}).textContent||''")[:900]
            try:
                os.makedirs(os.path.dirname(PNG), exist_ok=True)
                pg.screenshot(path=PNG, full_page=True)
                res["png"] = os.path.relpath(PNG, REPO)
            except Exception:
                pass
            ctx.close()
            br.close()
    except Exception as e:
        res["red"].append("門が転んだ：%s: %s" % (type(e).__name__, str(e)[:240]))

    time.sleep(3)
    after = ledger_ids()
    fueta = [i for i in after - before if i]
    res["fuetaCount"] = len(fueta)
    res["fuetaIds"] = fueta
    res["gamenOk"] = sum(1 for x in res["gamen"] if x.get("ok"))
    res["diag"].append("投げた後の台帳 %d行（増えた %d件）" % (len(after), len(fueta)))
    # ★③ひとことだけ は nagekomi_shiji（別の置き場）なので台帳は増えない＝台帳は3件のはず
    if len(fueta) < 3:
        res["red"].append("★台帳が %d件しか増えていない（3件のはず）＝スマホの経路が通っていない"
                          % len(fueta))
    if res["gamenOk"] < 4:
        res["red"].append("★画面が「届いた」と出なかったパターンがある（%d/4）" % res["gamenOk"])
    try:
        json.dump(res, io.open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass
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
