#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLファイルを Lovable 公式MCP query_database で流し、結果を JSON に書く（mac_jobs から走らせる）。
使い方: python3 tools/houou_sql.py <in.sql> <out.json>
  in.sql は「-- @@」行で区切れば複数本を順に流す。結果は配列で out.json へ。
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("tanaire", os.path.join(HERE, "2210_tanaire.py"))
tanaire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tanaire)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    parts = [p.strip() for p in open(src, encoding="utf-8").read().split("-- @@") if p.strip()]
    db = tanaire.DB()
    out = []
    for p in parts:
        try:
            out.append({"ok": True, "rows": db.q(p)})
        except Exception as e:  # noqa: BLE001
            out.append({"ok": False, "error": str(e)[:500]})
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("done", len(out))


if __name__ == "__main__":
    main()
