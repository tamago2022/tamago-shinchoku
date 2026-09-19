#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""今週見たいもの3つ（店主に聞く／記録する）。

店主が今週見たいものを言葉にしていないと、裏方（仕組み・点検・整理）が枠を埋めて
「見たかったものが1件も上がらない」事故が再発する。Dispatchが会話開始時に
`--need-ask` を見て、まだ今週分を聞いていなければ1回だけ聞く運用に使う
（聞く動作そのものはこのスクリプトの外・Dispatch側の役目）。
"""
import argparse
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
sys.path.insert(0, HERE)
import shukan_kubun  # noqa: E402

JST = shukan_kubun.JST
PATH = os.path.join(ST, "konshu_mitai.json")

_EMPTY = {"weekStart": None, "items": [], "askedAt": None, "updatedAt": None}


def _load():
    try:
        with io.open(PATH, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return dict(_EMPTY)


def _save(data):
    with io.open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _week_start_str(now=None):
    return shukan_kubun.week_start(now).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _now_str():
    return datetime.datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def set_items(items, now=None):
    """今週分をセットする。今の週と週が違えば新しい週として上書き、同じ週ならitemsを置き換える。"""
    data = _load()
    ws = _week_start_str(now)
    if data.get("weekStart") != ws:
        data = {"weekStart": ws, "items": list(items), "askedAt": None, "updatedAt": None}
    else:
        data["items"] = list(items)
    data["updatedAt"] = _now_str()
    _save(data)
    return data


def need_ask(now=None):
    """今週分(items)が空 かつ 今週まだ聞いていない(askedAt無し)場合にTrue。"""
    data = _load()
    ws = _week_start_str(now)
    if data.get("weekStart") != ws:
        # 週が変わっていれば今週分はまだ無い・まだ聞いていない扱い
        return True
    items_empty = not data.get("items")
    already_asked = bool(data.get("askedAt"))
    return items_empty and not already_asked


def mark_asked(now=None):
    data = _load()
    ws = _week_start_str(now)
    if data.get("weekStart") != ws:
        data = {"weekStart": ws, "items": [], "askedAt": None, "updatedAt": None}
    data["askedAt"] = _now_str()
    data["updatedAt"] = _now_str()
    _save(data)
    return data


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="今週見たいもの3つの記録")
    ap.add_argument("--set", nargs="+", metavar="ITEM", default=None,
                     help="今週見たいものを1〜3個渡す")
    ap.add_argument("--need-ask", action="store_true", help="今聞くべきかをASK/SKIPで出す")
    ap.add_argument("--mark-asked", action="store_true", help="今週分を聞いたことを記録する")
    args = ap.parse_args(argv)

    if args.set is not None:
        data = set_items(args.set)
        print("ok: %s" % json.dumps(data, ensure_ascii=False))
        return 0
    if args.need_ask:
        print("ASK" if need_ask() else "SKIP")
        return 0
    if args.mark_asked:
        mark_asked()
        print("ok")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
