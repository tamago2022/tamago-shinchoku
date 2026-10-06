#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1401号【上流の関所の宣言口】2026-09-28

tools/stop_kanmon/1401_iru_ka.mjs（PreToolUse）が、タブを開く前にこれを要求する。

  python3 tools/1401_kanmon.py declare --why "ログインが要るので" --url "https://..."
  python3 tools/1401_kanmon.py list
  python3 tools/1401_kanmon.py clear

★宣言するとき、同時に 978番の予約閉栓の票（status/chrome_reserve/）を置く。
  ＝**開く前に、閉じる約束をさせる。**セッションが途中で死んでも外の掃除機が閉じられる。
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DECL = os.path.join(REPO, "status", "1401_sengen")
TTL = 3600

sys.path.insert(0, HERE)
try:
    import chrome_reserve
except Exception:
    chrome_reserve = None


def declare(why, url, ttl):
    os.makedirs(DECL, exist_ok=True)
    tid = "sengen-%d" % int(time.time())
    p = os.path.join(DECL, tid + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"at": time.time(), "why": why, "url": url, "id": tid}, f, ensure_ascii=False)
    note = ""
    if chrome_reserve is not None and url:
        try:
            chrome_reserve.take(tid, [url], ttl=ttl, note=why)
            note = "／予約閉栓の票も置きました（心拍が%d秒止まったら外の掃除機が閉じます）" % ttl
        except Exception as e:
            note = "／★予約閉栓の票が置けませんでした: %s" % e
    print("宣言しました: %s%s" % (why, note))
    print("  この宣言は%d秒間だけ有効です（%s）" % (TTL, p))
    return 0


def listing():
    if not os.path.isdir(DECL):
        print("宣言はありません")
        return 0
    now = time.time()
    n = 0
    for name in sorted(os.listdir(DECL)):
        if not name.endswith(".json"):
            continue
        try:
            o = json.load(open(os.path.join(DECL, name), encoding="utf-8"))
        except Exception:
            continue
        age = now - float(o.get("at", 0))
        print("%s  %s  %s  (%.0f秒前 %s)" % (
            name, o.get("why", ""), o.get("url", ""), age,
            "有効" if age < TTL else "期限切れ"))
        n += 1
    if not n:
        print("宣言はありません")
    return 0


def clear():
    if not os.path.isdir(DECL):
        return 0
    for name in os.listdir(DECL):
        if name.endswith(".json"):
            try:
                os.remove(os.path.join(DECL, name))
            except Exception:
                pass
    print("宣言を消しました")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("declare")
    d.add_argument("--why", required=True)
    d.add_argument("--url", default="")
    d.add_argument("--ttl", type=int, default=300,
                   help="予約閉栓の心拍の猶予（秒）。これだけ心拍が止まったら閉じてよい")
    sub.add_parser("list")
    sub.add_parser("clear")
    a = ap.parse_args()
    if a.cmd == "declare":
        return declare(a.why, a.url, a.ttl)
    if a.cmd == "clear":
        return clear()
    return listing()


if __name__ == "__main__":
    sys.exit(main())
