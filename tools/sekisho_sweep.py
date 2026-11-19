#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""898番・付け足し：既存の share/check/*.html 全件へ一度まとめて関所(sekisho)をかけ、
落ちる件数・一覧を出す（直すのは別タスク。まず何件落ちるかを数える）。

軽量判定（sekisho.check_number_claims_for_url、ネットワーク越しのHTTP GET＋数字判定のみ）を使う。
495ファイル×毎回headless Chromeの「触る検品」まで回すと時間がかかりすぎるため、ここでは対象外
（触る検品自体は既存のverify_click.mjs・harvest()側で個別に既に走っている）。

使い方:
    python3 tools/sekisho_sweep.py [--limit N] [--out status/sekisho_sweep_YYYY-MM-DD.md]
"""
import argparse
import datetime
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CHECK_DIR = os.path.join(REPO, "share", "check")
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/share/check/"

sys.path.insert(0, HERE)
import sekisho  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="件数を絞ってテストしたい時")
    ap.add_argument("--out", default=None, help="結果を書き出すMarkdownパス（省略時は自動命名）")
    ap.add_argument("--timeout", type=int, default=8)
    args = ap.parse_args()

    files = sorted(
        f for f in os.listdir(CHECK_DIR)
        if f.endswith(".html") and not f.startswith("_")
    )
    if args.limit:
        files = files[: args.limit]

    total = len(files)
    fails = []
    oks = 0
    unreachable = []

    for i, fname in enumerate(files, 1):
        url = PAGES_BASE + fname
        ok, reason = sekisho.check_number_claims_for_url(url, "", timeout=args.timeout)
        if ok:
            oks += 1
        else:
            if "取得できず" in reason:
                unreachable.append((fname, reason))
            else:
                fails.append((fname, reason))
        if i % 50 == 0 or i == total:
            print("[%d/%d] OK=%d FAIL=%d UNREACHABLE=%d" % (i, total, oks, len(fails), len(unreachable)))

    today = datetime.date.today().isoformat()
    # status/はgit管理対象外（1秒おきに書き換わる生きている台帳のため）。
    # この一括点検レポートは一度きりの恒久記録なので docs/ 側（gitで追跡される）に置く。
    out_path = args.out or os.path.join(REPO, "docs", "sekisho_sweep_%s.md" % today)
    lines = []
    lines.append("# 関所(sekisho)一括点検：既存 share/check/ 全%d件（%s）" % (total, today))
    lines.append("")
    lines.append("案件#898・再設計後の付け足し要件「既存の全ページに一度まとめて関所をかけて、")
    lines.append("落ちるものの一覧を出す（直すのは別タスク。まず何件落ちるかを数える）」の結果。")
    lines.append("")
    lines.append("軽量判定（HTTP取得＋px/%の数字主張と実測の食い違いだけ）。触る検品・AI検品は含まない。")
    lines.append("")
    lines.append("## 集計")
    lines.append("")
    lines.append("- 対象：%d件" % total)
    lines.append("- 通過：%d件" % oks)
    lines.append("- 不合格（数字の主張に実測の跡が無い／食い違う）：%d件" % len(fails))
    lines.append("- 取得できず（404等・関所の対象外として別枠）：%d件" % len(unreachable))
    lines.append("")
    if fails:
        lines.append("## 不合格一覧（%d件）" % len(fails))
        lines.append("")
        for fname, reason in fails:
            lines.append("- `%s` — %s" % (fname, reason))
        lines.append("")
    if unreachable:
        lines.append("## 取得できなかった一覧（%d件）" % len(unreachable))
        lines.append("")
        for fname, reason in unreachable:
            lines.append("- `%s` — %s" % (fname, reason))
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("")
    print("書きました: %s" % out_path)
    print("対象=%d 通過=%d 不合格=%d 取得不可=%d" % (total, oks, len(fails), len(unreachable)))


if __name__ == "__main__":
    main()
