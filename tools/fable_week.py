#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fable解禁期間（2026-10-15 たまごさん指示）

たまごさん：「今週はバリバリ回そう。23日に上限のリセットがあるから、木・金・土で使い切っていい。
Fable は普段使えないから、Fable の方が効果的な仕事をやりまくっていい（仕組み作りも含む）」

■ 何をするか
  status/fable_week.json の until までの間だけ、積む側が fixedModel="claude-fable-5-1" を
  明示した仕事を Fable で発車してよい（auto_launcher.pick_model）。自動判定では Fable に上げない。
  期間外・ファイルが無い・週枠が stop のときは従来どおり Sonnet に落とす。
  no_fable.flag（2026-09-03）は消さずに残し、期間中だけ「明示指定のFable」に限り上書きする。

使い方:
  python3 tools/fable_week.py            # 今が解禁中かを表示
  python3 tools/fable_week.py --self-test
"""
import io
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CONF = os.path.join(REPO, "status", "fable_week.json")
QUOTA = os.path.join(REPO, "status", "quota.json")
FABLE = "claude-fable-5-1"
JST = timezone(timedelta(hours=9))


def _load(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def active(now=None, conf_path=CONF, quota_path=QUOTA):
    """(解禁中か, 理由)。"""
    c = _load(conf_path, None)
    if not c or not c.get("until"):
        return False, "fable_week.json なし"
    try:
        until = datetime.fromisoformat(c["until"])
        if until.tzinfo is None:
            until = until.replace(tzinfo=JST)
    except Exception:
        return False, "until が読めない"
    now = now or datetime.now(JST)
    if now >= until:
        return False, "期間切れ（%s まで）" % c["until"]
    q = _load(quota_path, {}) or {}
    if q.get("fableLevel") == "stop":
        return False, "Fable週枠がstop（%s%%）" % q.get("fablePct")
    return True, "Fable解禁中（%s まで・%s）" % (c["until"], c.get("why", ""))


def _self_test():
    import tempfile
    d = tempfile.mkdtemp()
    cp, qp = os.path.join(d, "c.json"), os.path.join(d, "q.json")
    now = datetime(2026, 10, 15, 12, 0, tzinfo=JST)
    assert active(now, cp, qp)[0] is False                      # ファイル無し
    json.dump({"until": "2026-10-23T00:00:00+09:00"}, open(cp, "w"))
    json.dump({"fableLevel": "ok"}, open(qp, "w"))
    assert active(now, cp, qp)[0] is True                       # 期間内
    assert active(datetime(2026, 10, 23, 0, 1, tzinfo=JST), cp, qp)[0] is False  # 期間外
    json.dump({"fableLevel": "stop", "fablePct": 90}, open(qp, "w"))
    assert active(now, cp, qp)[0] is False                      # 週枠stop
    for f in (cp, qp):
        os.remove(f)
    os.rmdir(d)  # 使ったらしまう
    print("self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(active())
