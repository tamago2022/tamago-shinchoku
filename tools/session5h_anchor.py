#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5時間セッション枠（週枠とは別物・ローリング）のアンカー登録。
たまごさんがアプリで見た「今◯%使用・あと◯分でリセット」を1行で登録する。
週枠と違い、この枠は「使い切らないと消える」＝余らせるのが損。quota_estimate.py がこの値を元に
「このままだと何%余る見込みか（もったいない度）」を出し、factory_status.py が本数を上限まで増やす判断に使う。

使い方:
  python3 session5h_anchor.py <今の使用pct> <あと何分でリセットか>
  例: python3 session5h_anchor.py 20 160   # 今20%使用・あと160分(2時間40分)でリセット
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "status", "session5h_anchor.json")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    pct = float(sys.argv[1])
    remain_min = float(sys.argv[2])
    now = time.time()
    d = {
        "t": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "pct": pct,
        "remainMin": remain_min,
        "resetAt": time.strftime("%Y-%m-%d %H:%M", time.localtime(now + remain_min * 60)),
        "setAt": time.strftime("%Y-%m-%d %H:%M"),
        "source": "たまごさんのアプリ実測",
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    print(json.dumps(d, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
