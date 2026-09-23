#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1149番【同時本数を機械が決める】取り合いを起こさない。

たまごさん（2026-09-26）:
  「同時本数を機械が決める（残クレジット・Macの余力・落ちた率から）。取り合いを起こさない。」

■ なぜ機械が決めるのか（今日の実害）
  Claudeを同時に起動して refreshToken を取り合い、負けた側が空を書き戻して鍵ごと消えた。
  → 便が1〜3秒で何本も死んだ。**同時本数の上限が無かったことが原因。**
  さらに status/machine_health.jsonl の実測では loadPct が 310%・swap 20.4GB。
  この状態で本数を増やすのは、渋滞の道に車を足すのと同じで**全体が遅くなるだけ**。

■ 決め方（AIMD ＝ TCPの輻輳制御と同じ。増やすときはゆっくり、減らすときは一気に）
  基準 3本 から始め、
    Macの負荷 loadPct が 200%超 → 半分
    swap が 8GB超            → さらに 1本
    直近1時間の落ちた率が 20%超 → 半分（取り合いが起きている合図）
    鍵が切れている（.hassha_stop あり）→ **0本**（止める）
  下限1本・上限5本。
  ★ 1本に絞るのは負けではない。**取り合いで全部死ぬより、1本ずつ確実に通るほうが速い。**

■ 使い方
  python3 tools/1149_dojisu.py          … 決めて status/dojisu_jougen.json に書く
  python3 tools/1149_dojisu.py --miru   … 決めるだけ（書かない）

戻し方（1行）:
  git checkout -- status/dojisu_jougen.json
"""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
JST = timezone(timedelta(hours=9))
SOKO, TENJO, KIJUN = 1, 5, 3


def jsonl(p):
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main():
    now = datetime.now(JST)
    kiri = now - timedelta(hours=1)
    riyuu = []

    # Macの余力（実測）
    mh = jsonl(os.path.join(ST, "machine_health.jsonl"))[-20:]
    load = max([float(r.get("loadPct") or 0) for r in mh] or [0])
    swap = max([float(r.get("swapGB") or 0) for r in mh] or [0])

    # 落ちた率（直近1時間）
    och = jsonl(os.path.join(ST, "ochita.jsonl"))
    ochi = 0
    for r in och:
        t = str(r.get("t") or "")
        try:
            dt = datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
        except Exception:
            continue
        if dt >= kiri:
            ochi += int(r.get("kietaN") or 1)
    ikiteru = sum(int(r.get("ikiteruN") or 0) for r in och[-5:]) or 1
    ochi_ritsu = ochi / max(ochi + ikiteru, 1)

    n = KIJUN
    if load > 200:
        n = max(SOKO, n // 2); riyuu.append(f"Macの負荷が{load:.0f}%（200%超）→ 半分")
    if swap > 8:
        n = max(SOKO, n - 1); riyuu.append(f"swapが{swap:.1f}GB（8GB超）→ 1本減らす")
    if ochi_ritsu > 0.2:
        n = max(SOKO, n // 2); riyuu.append(f"直近1時間の落ちた率が{ochi_ritsu*100:.0f}%（20%超）→ 半分")
    stop = os.path.join(ST, ".hassha_stop")
    tomeru = os.path.exists(stop) and os.path.getsize(stop) > 0
    if tomeru:
        n = 0; riyuu.append("鍵が切れている（.hassha_stop あり）→ 0本。止める")
    n = min(n, TENJO)
    if not riyuu:
        riyuu.append(f"余力あり（負荷{load:.0f}% / swap{swap:.1f}GB / 落ちた率{ochi_ritsu*100:.0f}%）→ 基準どおり")

    res = {"at": now.isoformat(), "jougen": n, "kijun": KIJUN,
           "loadPct": load, "swapGB": swap, "ochiRitsu": round(ochi_ritsu, 3),
           "riyuu": riyuu,
           "note": "1149番が機械で決めた同時本数の上限。取り合いを起こさないための上限。"}
    print(f"同時本数の上限: {n}本")
    for r in riyuu:
        print("  ・" + r)
    if "--miru" not in sys.argv:
        p = os.path.join(ST, "dojisu_jougen.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        with open(os.path.join(ST, "1149", "dojisu_rireki.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
        print(f"書いた: status/dojisu_jougen.json")


if __name__ == "__main__":
    main()
