#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
済み照合の関所（2026-10-01 たまごさん）。

  「同じ作業を2回も3回も繰り返してクレジットを溶かすのは論外。
    終わっている作業を再度やらないこと。判断がつかなければ都度確認」

auto_launcher が**発車させる直前**に、その票と同じ題名・同じ目的の「済み票」
（queue.json の done ＋ status/deleted.json の done）が無いかを照合する。
当たったら発車させず hold にして「◯番で済み・もう一度やるか確認」と書く（票は消さない）。

通す（照合しない）もの：
  ・差し戻し／やり直し（title が「差し戻し」で始まる、checkedAt・reopenedAt・redoCount・resumeFrom がある）
    ＝たまごさんか鬼監督が「まだ終わっていない」と判断して戻した正当な再作業
  ・題名や label に「重複OK」がある票
  ・テストの空回し（test）
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DELETED = os.path.join(REPO, "status", "deleted.json")

_PREFIX = re.compile(r"^(判定日赤｜|差し戻し｜|GH\d+\s*(コメント:)?\s*|【[^】]{0,20}】\s*)+")


def _norm(s):
    s = str(s or "").strip()
    s = _PREFIX.sub("", s)
    s = re.sub(r"[\s　「」『』（）()…・、。！!？?]", "", s)
    return s


def _conflict(a, b):
    a, b = _norm(a), _norm(b)
    if len(a) < 8 or len(b) < 8:
        return a == b and bool(a)
    if a == b or a in b or b in a:
        return True
    return len(a) >= 30 and len(b) >= 30 and a[:30] == b[:30]


def is_exempt(it):
    t = str(it.get("title") or "")
    if it.get("test") or it.get("keepalive"):
        return True
    if t.startswith("差し戻し") or "重複OK" in t or "重複OK" in str(it.get("label") or ""):
        return True
    if "【差し戻し（鬼監督＝Codex）】" in str(it.get("what") or ""):
        return True
    for k in ("checkedAt", "reopenedAt", "redoCount", "resumeFrom", "zumiOk"):
        if it.get(k):
            return True
    return False


def done_items(q):
    out = [x for x in (q.get("items") or []) if x.get("status") == "done"]
    try:
        with io.open(DELETED, encoding="utf-8") as f:
            d = json.load(f)
        out += [x for x in (d.get("items") or []) if x.get("status") == "done"]
    except Exception:
        pass
    return out


def find_done_twin(it, dones):
    """同じ題名・同じ目的の済み票を1枚返す。無ければ None。"""
    if is_exempt(it):
        return None
    t = it.get("title")
    h = it.get("hyoudai")
    for d in dones:
        if d.get("n") is not None and d.get("n") == it.get("n"):
            continue
        if _conflict(t, d.get("title")):
            return d
        dh = d.get("hyoudai")
        if h and dh and _conflict(h, dh):
            return d
    return None


def hold_note(twin):
    urls = twin.get("urls") or []
    return ("【済み照合の関所・2026-10-01】%s番「%s」で同じ題名・同じ目的の作業が済んでいます。"
            "同じ作業を繰り返さないため発車を止めました。もう一度やる必要があるなら、"
            "たまごさんの確認後に zumiOk を立てて戻してください。%s"
            % (twin.get("n"), str(twin.get("title") or "")[:40],
               ("済みのURL：" + " / ".join(urls[:3])) if urls else ""))
