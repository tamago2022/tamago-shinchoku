#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1155番【スマホで開けることを自分で確かめる係】375px幅で本番を開いて、撮って、測る。

たまごさん（2026-09-26）:
  「200が返った、ページが開いた、は確認ではない。自分が客として通しで触って、
    頼まれたことが実際に起きるのを確かめるまで完了と書くな。」

やること（全部0円・外の課金APIは叩かない）:
  ・375×812（iPhone相当・touch有効）で本番URLを開く
  ・横に溢れていないか測る（scrollWidth > clientWidth なら赤）
  ・画面の中身を文字で取り出す（「入った記録」「残り%」が本当に出ているか）
  ・全画面のスクショを status/1155/shot/ に保存する

使い方:
  python3 tools/1155_sumaho.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHOT = os.path.join(REPO, "status", "1155", "shot")
OUT = os.path.join(REPO, "status", "1155", "sumaho.json")

BASE = "https://tamago2022.github.io/tamago-shinchoku"
PAGES = [
    ("shinchoku", BASE + "/",
     ["wUsed", "wRemain", "wHours", "paceNums"]),
    ("nagekomi", BASE + "/share/nagekomi-c5fd9d5791b32e88.html",
     ["daichoSum", "daichoAka", "daichoRows"]),
]


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT, exist_ok=True)
    res = {"width": 375, "height": 812, "pages": [], "red": []}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 375, "height": 812},
                            device_scale_factor=2, is_mobile=True,
                            has_touch=True,
                            user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                                        "Version/17.0 Mobile/15E148 Safari/604.1"))
        for name, url, ids in PAGES:
            p = ctx.new_page()
            r = {"name": name, "url": url, "text": {}}
            try:
                resp = p.goto(url, wait_until="networkidle", timeout=60000)
                r["status"] = resp.status if resp else None
                p.wait_for_timeout(3500)
                over = p.evaluate("() => ({sw:document.documentElement.scrollWidth,"
                                  "cw:document.documentElement.clientWidth})")
                r["yokoAfure"] = over["sw"] > over["cw"] + 1
                r["scrollWidth"] = over["sw"]
                r["clientWidth"] = over["cw"]
                if r["yokoAfure"]:
                    res["red"].append("%s：横に溢れている（%dpx > %dpx）"
                                      % (name, over["sw"], over["cw"]))
                for i in ids:
                    try:
                        r["text"][i] = (p.eval_on_selector(
                            "#" + i, "e => e.innerText") or "").strip()[:700]
                    except Exception as e:
                        r["text"][i] = "★取れない（%s）" % type(e).__name__
                        res["red"].append("%s：#%s が取れない" % (name, i))
                shot = os.path.join(SHOT, name + "-375.png")
                p.screenshot(path=shot, full_page=True)
                r["shot"] = os.path.relpath(shot, REPO)
            except Exception as e:
                r["error"] = "%s: %s" % (type(e).__name__, e)
                res["red"].append("%s：開けなかった（%s）" % (name, type(e).__name__))
            finally:
                p.close()
            res["pages"].append(r)
        b.close()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])
    return 1 if res["red"] else 0


if __name__ == "__main__":
    sys.exit(main())
