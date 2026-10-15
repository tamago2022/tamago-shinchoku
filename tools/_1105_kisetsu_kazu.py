#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1105番【季節の棚の枚数・実測】

Gensparkの「秋の棚0枚／春の棚0枚／冬の棚0枚」は誤り。
その訂正を、推測ではなくDBの実数で置き換えるための道具。

やること:
  admin_shelves から季節の棚を引き、admin_shelf_picks の行数を status 別に数える。
  ★数えた数しか書かない。取れなかったものは「取れず」と書く。

使い方: python3 tools/_1105_kisetsu_kazu.py
"""
import io
import json
import os
import sys
import urllib.error
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import tana  # noqa: E402

KISETSU = ["春の棚", "夏の棚", "夏の終わりに聴きたい棚", "秋の棚", "冬の棚",
           "クリスマスの棚", "クリスマス棚"]
OUT = os.path.join(REPO, "status", "0924_tana_narabi", "kisetsu_kazu.json")


def main():
    diag = []
    url, key, keyname, where = tana.keys(diag)
    if not url:
        print(json.dumps({"ok": False, "diag": diag, "where": where}, ensure_ascii=False))
        return 1

    st, shelves = tana._req(url, key,
                            "/rest/v1/admin_shelves?select=id,title,world&limit=1000")
    diag.append("admin_shelves HTTP %d / %d件" % (st, len(shelves)))

    res = []
    for name in KISETSU:
        hits = [s for s in shelves if (s.get("title") or "").strip() == name]
        if not hits:
            res.append({"棚": name, "DBに在るか": False, "枚数": None, "備考": "DBの棚には無い（作り付けの棚かもしれない）"})
            continue
        row = {"棚": name, "DBに在るか": True, "id": hits[0]["id"], "world": hits[0].get("world")}
        sid = urllib.parse.quote(str(hits[0]["id"]), safe="")
        try:
            st2, picks = tana._req(url, key,
                                   "/rest/v1/admin_shelf_picks?select=id,status&shelf_id=eq.%s&limit=2000" % sid)
            byst = {}
            for p in picks:
                k = p.get("status") or "(status無し)"
                byst[k] = byst.get(k, 0) + 1
            row["枚数"] = len(picks)
            row["status別"] = byst
        except urllib.error.HTTPError as e:
            row["枚数"] = None
            row["備考"] = "admin_shelf_picks HTTP %d（取れず）" % e.code
        res.append(row)

    out = {"at": tana.now(), "kagi": keyname, "diag": diag, "kisetsu": res}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
