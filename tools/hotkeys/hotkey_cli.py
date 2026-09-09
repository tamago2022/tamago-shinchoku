#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ベッドホットキーから、工場の既存の仕組み（command_ingest.py の関数）を直接呼び出す薄いラッパー。
新しい受信箱は作らない。既にある queue_add / launch_switch をそのまま使う。

使い方:
  hotkey_cli.py ingest "<URL>"   仕入れ箱（発車待ちキュー）へ動画URLを追加
  hotkey_cli.py pause            工場の自動発車を止める
  hotkey_cli.py resume           工場の自動発車を再開する
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)  # tools/hotkeys -> tools
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from command_ingest import queue_add, launch_switch  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("使い方: hotkey_cli.py [ingest <URL>|pause|resume]", file=sys.stderr)
        sys.exit(1)
    action = sys.argv[1]
    if action == "ingest":
        if len(sys.argv) < 3 or not sys.argv[2].strip():
            print("URLが指定されていません", file=sys.stderr)
            sys.exit(1)
        url = sys.argv[2].strip()
        status, msg = queue_add(
            "この動画を仕入れ候補として確認して棚に追加を検討: %s" % url,
            priority=2,
            label="ベッドから仕入れ登録",
            origin="user",
        )
        print("%s: %s" % (status, msg))
        sys.exit(0 if status in ("done", "skipped") else 1)
    elif action == "pause":
        status, msg = launch_switch(False)
        print("%s: %s" % (status, msg))
    elif action == "resume":
        status, msg = launch_switch(True)
        print("%s: %s" % (status, msg))
    else:
        print("不明なアクション: %s" % action, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
