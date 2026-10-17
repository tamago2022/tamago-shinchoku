#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ごきげん補給所のDB（Supabase REST）へ、決めた要求だけを順に送る（mac_jobs から走らせる）。
鍵は tana.py と同じ口（gaibu_copy_naoshi.find_write_key）。鍵の値は出力に書かない。
使い方: python3 tools/houou_rest.py <in.json> <out.json>
  in.json = [{"method":"GET","path":"/rest/v1/admin_shelves?select=*"}, {"method":"PATCH","path":"...","body":{...},"prefer":"return=representation"}]
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gaibu_copy_naoshi as naoshi  # noqa: E402


def main():
    reqs = json.load(open(sys.argv[1], encoding="utf-8"))
    diag = []
    url, key, keyname, where = naoshi.find_write_key(diag)
    out = {"keyName": keyname, "diag": [str(d)[:200] for d in diag], "res": []}
    if not url:
        out["error"] = where
    else:
        for r in reqs:
            body = r.get("body")
            data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
            h = {"apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"}
            if data is not None:
                h["Content-Type"] = "application/json"
            if r.get("prefer"):
                h["Prefer"] = r["prefer"]
            try:
                q = urllib.request.Request(url + r["path"], data=data, method=r.get("method", "GET"), headers=h)
                with urllib.request.urlopen(q, timeout=60) as resp:
                    raw = resp.read().decode("utf-8", "replace")
                    out["res"].append({"status": resp.status, "path": r["path"][:200],
                                       "rows": json.loads(raw) if raw.strip() else []})
            except urllib.error.HTTPError as e:
                out["res"].append({"status": e.code, "path": r["path"][:200],
                                   "error": e.read().decode("utf-8", "replace")[:600]})
            except Exception as e:  # noqa: BLE001
                out["res"].append({"path": r["path"][:200], "error": "%s: %s" % (type(e).__name__, e)})
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done", len(out["res"]), out.get("keyName"))


if __name__ == "__main__":
    main()
