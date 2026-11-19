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


KINSHI = os.path.join(REPO, "status", "fable_kinshi.json")


def kinshi(kinshi_path=KINSHI):
    """Fable全面停止（2026-11-08 たまごさんがプランを下げた）。ファイルがある間は解禁期間より優先して禁止。
    解除はたまごさんの指示があった時だけ（ファイルを消す）。"""
    return os.path.exists(kinshi_path)


def is_fable_item(item):
    """Fable指定の便か（fixedModel・model・題名『Fable｜』のどれか）。"""
    item = item or {}
    return (FABLE in str(item.get("fixedModel") or "") or FABLE in str(item.get("model") or "")
            or str(item.get("title") or "").startswith("Fable｜"))


HORYU_NOTE = "Fable全面停止（2026-11-08 プラン変更）。Sonnetに落とさず保留。解除はたまごさんの指示のみ"


def horyu(ns=None):
    """Fable指定の待ち便（waiting/stuck）を鍵を取って保留(hold)にする。消さない。ns=None なら全部。保留にした番号を返す。"""
    sys.path.insert(0, HERE)
    import queue_store
    done = []
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        for it in q.get("items") or []:
            if it.get("status") in ("waiting", "stuck") and is_fable_item(it) and (ns is None or it.get("n") in ns):
                it["fableMaeStatus"] = it.get("status")
                it["status"] = "hold"
                it["holdNote"] = HORYU_NOTE
                it["fableHoryuAt"] = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
                done.append(it.get("n"))
        if done:
            queue_store.save_queue(q, snapshot=snap)
    return done


def active(now=None, conf_path=CONF, quota_path=QUOTA, kinshi_path=KINSHI):
    """(解禁中か, 理由)。"""
    if kinshi(kinshi_path):
        return False, "Fable全面停止中（status/fable_kinshi.json・解除はたまごさんの指示のみ）"
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
    nk = os.path.join(d, "no_kinshi.json")
    now = datetime(2026, 10, 15, 12, 0, tzinfo=JST)
    assert active(now, cp, qp, nk)[0] is False                      # ファイル無し
    json.dump({"until": "2026-10-23T00:00:00+09:00"}, open(cp, "w"))
    json.dump({"fableLevel": "ok"}, open(qp, "w"))
    assert active(now, cp, qp, nk)[0] is True                       # 期間内
    assert active(datetime(2026, 10, 23, 0, 1, tzinfo=JST), cp, qp, nk)[0] is False  # 期間外
    json.dump({"fableLevel": "stop", "fablePct": 90}, open(qp, "w"))
    assert active(now, cp, qp, nk)[0] is False                      # 週枠stop
    json.dump({"fableLevel": "ok"}, open(qp, "w"))
    kp = os.path.join(d, "k.json")
    json.dump({"kinshi": True}, open(kp, "w"))
    assert active(now, cp, qp, kp)[0] is False                  # 全面停止は解禁期間より優先
    assert active(now, cp, qp, os.path.join(d, "none.json"))[0] is True
    assert is_fable_item({"fixedModel": FABLE}) and is_fable_item({"title": "Fable｜x"})
    assert not is_fable_item({"model": "claude-sonnet-5", "title": "空カード埋め"})
    os.remove(kp)
    for f in (cp, qp):
        os.remove(f)
    os.rmdir(d)  # 使ったらしまう
    print("self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(active())
