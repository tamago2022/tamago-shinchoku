#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1191番【日本語残りの解消】DB（棚に出ているカード・棚名）の日本語を集めるだけ（読むだけ・課金0）。

工場(Mac)で走る。サンドボックスからは Supabase に回線が出ないため。
鍵は joy-relief-station/.env の公開用(publishable)鍵だけ。値はどこにも書かない。
出力: status/1191_nihongo_nokori/db_ja.json  {"stock":[{id,title,whisper,note}],"shelves":[{title,subtitle}]}
"""
import json, os, re, sys, urllib.request
SH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOY = os.path.expanduser("~/Desktop/joy-relief-station")
OUT = os.path.join(SH, "status", "1191_nihongo_nokori", "db_ja.json")
JA = re.compile(r"[぀-ヿ㐀-鿿]")


def env():
    e = {}
    for name in (".env", ".env.local"):
        p = os.path.join(JOY, name)
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                if "=" in l and not l.startswith("#"):
                    k, v = l.strip().split("=", 1)
                    e[k] = v.strip('"')
    return e


def fetch(url, key, t, sel):
    out, off = [], 0
    while True:
        r = urllib.request.Request(f"{url}/rest/v1/{t}?select={sel}",
                                   headers={"apikey": key, "Authorization": "Bearer " + key,
                                            "Range": f"{off}-{off+999}"})
        rows = json.loads(urllib.request.urlopen(r, timeout=60).read())
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def main():
    e = env()
    url = e.get("VITE_SUPABASE_URL"); key = e.get("VITE_SUPABASE_PUBLISHABLE_KEY")
    if not (url and key):
        print("鍵が見つからない"); return 1
    res = {}
    try:
        stock = [r for r in fetch(url, key, "admin_stock", "id,title,whisper,note,deleted_at") if not r.get("deleted_at")]
        res["stock"] = [{k: r.get(k) for k in ("id", "title", "whisper", "note")} for r in stock
                        if any(JA.search(r.get(k) or "") for k in ("title", "whisper", "note"))]
    except Exception as ex:
        res["stock_err"] = str(ex)[:200]
    try:
        res["shelves"] = fetch(url, key, "admin_shelves", "title,subtitle")
    except Exception as ex:
        res["shelves_err"] = str(ex)[:200]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("stock", len(res.get("stock", [])), "shelves", len(res.get("shelves", [])), res.get("stock_err", ""), res.get("shelves_err", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
