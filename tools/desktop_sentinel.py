#!/usr/bin/env python3
"""見張り番：デスクトップに joy-relief-station 以外が出現したら記録する（消さない・動かさない）。
憲法 2026-10-04「許可なくデスクトップにファイルを作らない」。bash/node など Python 以外の取りこぼしを拾う。"""
import os, json, time
D = "/Users/mac/Desktop"; OK = {"joy-relief-station", ".DS_Store", ".localized", ".claude", ".Trash"}
extra = sorted(n for n in os.listdir(D) if n not in OK)
out = "/Users/mac/tamago/tamago-shinchoku/status/desktop_sentinel.json"
json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "extra": extra, "ok": not extra}, open(out, "w"), ensure_ascii=False)
if extra:
    with open("/Users/mac/tamago/tamago-shinchoku/status/desktop_sentinel.log", "a") as f:
        f.write("%s 不審: %s\n" % (time.strftime("%F %T"), extra))
