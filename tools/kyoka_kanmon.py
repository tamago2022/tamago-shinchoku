#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""許可ポップアップの関所（2026-10-09）

たまごさんの画面に出た許可ポップアップを、アプリのログ（~/Library/Logs/Claude/main*.log・読むだけ）から
1時間ごと・道具ごとに数えて status/kyoka_kanmon.json に書く。心臓から1時間おき。0円。

なぜ：10/8夜、Dispatchの子セッションが web_fetch・Gmail・Lovable・定期タスクの許可待ちで固まり、
      そのまま見回りに畳まれて「failed」になった。許可ゼロ設定（tools/kyoka_zero.py）は
      ~/.claude/settings.json 用で、Cowork の許可（webfetch:<ドメイン>・コネクタの道具）には効かなかった（実測）。
      → 「何回出たか」を毎日機械で数え、0でなければ道具名つきで赤にする。
        置き換え先：web_fetch → tools/mac_fetch.py ／ Gmail下書き → status/shitagaki/ にファイル ／
                    Lovable → git push ／ 定期タスク → 心臓 ／ 子が固まったら → tools/okoshi.py が起こす
"""
import collections
import glob
import io
import json
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "status", "kyoka_kanmon.json")
LOGS = os.path.expanduser("~/Library/Logs/Claude")
PAT = re.compile(r"^(\d{4}-\d\d-\d\d) (\d\d):\d\d:\d\d .*Emitted tool permission request \S+ for (\S+)")
OKIKAE = {
    "webfetch:": "tools/mac_fetch.py",
    "create_draft": "status/shitagaki/ にファイル",
    "1eb9c4c0": "git push（Lovable は GitHub 連携）",
    "scheduled-tasks": "心臓 tools/heartbeat.sh に1行",
    "request_cowork_directory": "使わない（接続済みフォルダだけで作業）",
    "Bash": "Cowork なら mcp__workspace__bash（許可不要）",
}


def count(lines, days=2):
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - days * 86400))
    c = collections.Counter()
    for ln in lines:
        m = PAT.match(ln)
        if m and m.group(1) >= since:
            tool = m.group(3)
            if tool.startswith("webfetch:"):
                tool = "webfetch:*"
            c[(m.group(1), tool)] += 1
    return c


def main():
    if "--self-test" in sys.argv:
        demo = ["2026-10-09 08:22:21 [info] Emitted tool permission request 3797 for mcp__x__create_draft in session a",
                "2026-10-09 08:22:22 [info] Emitted tool permission request 3798 for webfetch:www.youtube.com in session a",
                "2026-10-09 08:22:23 [info] something else"]
        c = count(demo, days=99999)
        ok = c[("2026-10-09", "mcp__x__create_draft")] == 1 and c[("2026-10-09", "webfetch:*")] == 1 and len(c) == 2
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    lines = []
    for f in sorted(glob.glob(os.path.join(LOGS, "main*.log"))):
        try:
            lines += io.open(f, encoding="utf-8", errors="ignore").read().splitlines()
        except Exception:
            pass
    c = count(lines)
    today = time.strftime("%Y-%m-%d")
    rows = [{"day": d, "tool": t, "n": n,
             "okikae": next((v for k, v in OKIKAE.items() if k in t), "別の道を探す")}
            for (d, t), n in sorted(c.items())]
    tn = sum(r["n"] for r in rows if r["day"] == today)
    res = {"label": "許可ポップアップの回数", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "today": tn, "aka": tn > 0, "rows": rows}
    tmp = OUT + ".tmp"
    json.dump(res, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print("許可ポップアップ 今日 %d回" % tn)


if __name__ == "__main__":
    sys.exit(main() or 0)
