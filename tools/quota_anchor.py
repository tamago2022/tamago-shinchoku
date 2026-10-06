#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
利用枠の目盛り合わせ（アンカー）。たまごさんがスマホの「使用状況」で見た実測値を1行で登録する。
以後の推定（quota_estimate.py）はこの値に合わせて計算する。新しい実測値が出るたびに上書きしてよい。

  python3 quota_anchor.py 63 44                    # いま Fable 63% / 全モデル 44%
  python3 quota_anchor.py 63 44 "2026-09-03T01:28" # 見た時刻を指定（省略時は今）
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ANCHOR = os.path.join(os.path.dirname(HERE), "status", "quota_anchor.json")


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    t = sys.argv[3] if len(sys.argv) > 3 else time.strftime("%Y-%m-%dT%H:%M:%S")
    d = {"t": t, "fablePct": float(sys.argv[1]), "allPct": float(sys.argv[2]), "setAt": time.strftime("%Y-%m-%d %H:%M")}
    with open(ANCHOR, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    print(json.dumps(d, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
