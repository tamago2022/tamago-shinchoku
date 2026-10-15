#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1042番【口のズレをミリ秒で測る】
avatar431.js の中の数字（0.40 / 0.16 / 0.30 / 260ms）をそのまま入れて、
「母音が切り替わってから、口がその形になるまで何ミリ秒か」を出す。
AIは呼ばない。ただの足し算。毎回同じ答えが出る。
    python3 tools/_1042_zure.py
"""
import json, os, sys, math

FPS = 60.0
MS = 1000.0 / FPS

def rise(k, pct):
    """1極フィルタ x += (1-x)*k が pct に達するまでのフレーム数→ミリ秒"""
    x, n = 0.0, 0
    while x < pct and n < 10000:
        x += (1.0 - x) * k
        n += 1
    return n, n * MS

def main():
    out = {"hakatta": "工場(python3)でavatar431.jsの定数をそのまま計算", "fps": FPS}
    for name, k in (("開く attack k=0.50", 0.50),
                    ("閉じる release k=0.16", 0.16),
                    ("よこはば k=0.30", 0.30)):
        f50, m50 = rise(k, 0.5)
        f90, m90 = rise(k, 0.9)
        out[name] = {"50%": round(m50, 1), "90%": round(m90, 1),
                     "frames90": f90}
    # 前の式（閉じる k=0.12）との比較
    f90, m90 = rise(0.12, 0.9)
    out["（前の式）閉じる k=0.12"] = {"90%": round(m90, 1)}
    # wawa-lipsync 側の解析窓（fftSize=2048 / 48kHz）
    out["解析窓 fftSize2048@48kHz"] = {"ms": round(2048 / 48000 * 1000, 1)}
    tot90 = out["開く attack k=0.50"]["90%"] + out["解析窓 fftSize2048@48kHz"]["ms"]
    out["合計（音が出てから口が90%開くまで）"] = {"ms": round(tot90, 1),
        "判定": "OK（人が気づく目安100〜120ms以内）" if tot90 <= 120 else "要調整"}
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "status", "1042_kuchi_jissoku.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("→ " + p)

if __name__ == "__main__":
    main()
