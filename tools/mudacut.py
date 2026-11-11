#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""無駄カット（2026-11-08 たまごさん・週枠100%超え）。正本は status/mudacut.json。消すと全部解除。

  ① 空カード埋めの自動補充を止める（itsumo_shigoto の kara 積み）
  ② 同じ便の3回目以降の発車は保留(hold)へ（何度やり直しても、発車回数で数える）
  ③ 優先度1の「緊急横入り(+1本)」で上限を上書きしない
"""
import io
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = os.path.join(REPO, "status", "mudacut.json")
KAISUU = os.path.join(REPO, "status", "hassha_kaisuu.json")
HORYU_NOTE = "無駄カット（2026-11-08）：同じ便の3回目以降の走り直しは禁止。保留。解除はたまごさんの指示のみ"


def _flag():
    try:
        return json.load(io.open(FLAG, encoding="utf-8")) or {}
    except Exception:
        return {}


def kara_teishi():
    return bool(_flag().get("karaHojuuTeishi"))


def yokoiri_kaijo():
    return bool(_flag().get("yokoiriKaijo"))


def jougen():
    v = _flag().get("hasshaJougen")
    return v if isinstance(v, int) else None


def _kaisuu_all():
    try:
        return json.load(io.open(KAISUU, encoding="utf-8")) or {}
    except Exception:
        return {}


def kaisuu(item):
    """これまでの発車回数（台帳の hasshaKaisuu と、ログから数えた分の大きい方）。"""
    a = int(item.get("hasshaKaisuu") or 0)
    b = int(_kaisuu_all().get(str(item.get("n")), 0) or 0)
    return max(a, b)


def kinshi(item):
    """True＝もう発車させない（3回目以降）。テスト便は対象外。"""
    j = jougen()
    if j is None or item.get("test"):
        return False
    return kaisuu(item) >= j


def kazoeru(item):
    """発車した直後に1回足す。"""
    k = kaisuu(item) + 1
    item["hasshaKaisuu"] = k
    d = _kaisuu_all()
    d[str(item.get("n"))] = k
    try:
        tmp = KAISUU + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(json.dumps(d))
        os.replace(tmp, KAISUU)
    except Exception:
        pass
    return k


def horyu(item):
    item["statusBefore"] = item.get("status")
    item["status"] = "hold"
    item["holdNote"] = HORYU_NOTE
    item["mudacutAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
