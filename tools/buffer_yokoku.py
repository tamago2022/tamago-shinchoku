#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【ところてん #642】Bufferの予約を『読むだけ』で見て、これから出る投稿のページが整っているかを一覧にする。

決まり（たまごさん 2026-10-05）:
  ・「今日の9時にこれが出る」を直前に知るのは嫌。投稿の24時間前までに、基準ページ（亜蘭知子 Midnight Pretenders）の水準へ整え終える。
  ・間に合わないものは、前日に Issue #642 でチャッピーに「◯日◯時の◯◯は保留に」と伝える。
  ・出し先は oasisjoyrelief だけ。eggypop2014 は触らない。投稿・編集・削除はしない（読むだけ）。

使い方:  python3 tools/buffer_yokoku.py [--hours 72]
出力:    status/buffer_yokoku.md（人用）と標準出力
"""
import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import buffer_yoyaku as y  # noqa: E402
import buffer_page_kanmon as k  # noqa: E402

JST = datetime.timezone(datetime.timedelta(hours=9))


def yomu():
    tok = y.token()
    orgs = (((y.gql(tok, y.Q_ORGS).get("data") or {}).get("account") or {}).get("organizations") or [])
    chans = []
    for o in orgs:
        got = (y.gql(tok, y.Q_CHANNELS, {"orgId": o["id"]}).get("data") or {}).get("channels") or []
        for c in got:
            c["_org"] = o["id"]
        chans += got
    ch = y.pick_channel(chans, "oasisjoyrelief", ["eggypop2014"])
    if not ch:
        return []
    q = y.gql(tok, y.Q_POSTS, {"orgId": ch["_org"], "channelIds": [ch["id"]]})
    return [(e.get("node") or {}) for e in (((q.get("data") or {}).get("posts") or {}).get("edges") or [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=72)
    a = ap.parse_args()
    now = datetime.datetime.now(JST)
    rows = []
    for p in yomu():
        due = p.get("dueAt") or ""
        try:
            dt = datetime.datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(JST)
        except Exception:
            continue
        if dt < now or dt > now + datetime.timedelta(hours=a.hours):
            continue
        text = p.get("text") or ""
        u = re.findall(r"https://joy-relief-station\.lovable\.app/\S+", text)
        url = u[0].rstrip("）)、。,.") if u else ""
        rows.append((dt, text.split("\n")[0][:60], url))
    rows.sort()
    out = ["# これから%d時間に出る投稿（Bufferの予約・読むだけ）  %s 時点" % (a.hours, now.strftime("%m-%d %H:%M"))]
    ng = 0
    for dt, first, url in rows:
        if not url:
            res = {"tsuuka": False, "riyuu": ["URLが無い"]}
        else:
            res = k.shiraberu(url)
        left = (dt - now).total_seconds() / 3600
        mark = "◯整備済み" if res["tsuuka"] else "✕要整備"
        if not res["tsuuka"]:
            ng += 1
        warn = "  ★24時間を切っている" if (not res["tsuuka"] and left < 24) else ""
        out.append("- %s | %s | %s | %s%s" % (dt.strftime("%m-%d %H:%M"), first, mark,
                                              "、".join(res["riyuu"])[:90], warn))
    out.append("")
    out.append("要整備 %d 本 / 全 %d 本" % (ng, len(rows)))
    txt = "\n".join(out)
    open(os.path.join(os.path.dirname(HERE), "status", "buffer_yokoku.md"), "w", encoding="utf-8").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
