#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1403番（2026-09-28）残量の数字が止まっていないかの見張り＋取り直し。

■ なにが起きたか（実測）
  2026-09-28 07:35 時点で status/pace.json は 05:17:59 のまま（2時間18分前）。
  たまごさん「今日これだけ動かしているのにクレジットが変わってないね」の正体。
  取得元（Claudeアプリの plan-usage-history.json）も status/quota.json も新しかった
  （07:31／07:34）ので、止まっていたのは pace.py を呼ぶ側だった。
  pace.py は tools/machine_status_push.sh の **747行目** に相乗りしている。
  この便は1回の起動で約260秒ループするため、Macが重い日は747行目まで到達せず、
  ロック入れ替えで殺されて次の便へ回る＝pace.json だけが何時間も古いまま残る。

■ この係がやること（新しい常駐は増やさない。心臓が毎周回で読む top_status.py に1行）
  1. pace.json が STALE_SEC より古ければ pace.py を叩いて取り直す。
  2. 結果を status/zanryo_mihari.json に書く（画面が赤にするための材料）。
     level: ok / warn / red（RED_MIN 分以上更新されていなければ red）
"""
import io
import json
import os
import subprocess
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
PACE = os.path.join(ST, "pace.json")
QUOTA = os.path.join(ST, "quota.json")
OUT = os.path.join(ST, "zanryo_mihari.json")

STALE_SEC = 300      # 5分以上古ければ取り直す（pace.pyは5分おきが本来のカデンス）
WARN_MIN = 20        # 20分以上古い＝黄
RED_MIN = 60         # 60分以上古い＝赤（★たまごさん指示「◯時間以上更新されていなければ赤」）


def age_min(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 60.0
    except Exception:
        return None


def main():
    a = age_min(PACE)
    refreshed = False
    if a is None or a * 60 >= STALE_SEC:
        try:
            subprocess.run(["python3", os.path.join(HERE, "pace.py")],
                           cwd=REPO, capture_output=True, timeout=40)
            refreshed = True
        except Exception:
            pass
        a = age_min(PACE)

    q = age_min(QUOTA)
    level = "ok"
    if a is None or a >= RED_MIN:
        level = "red"
    elif a >= WARN_MIN:
        level = "warn"

    pace = {}
    try:
        pace = json.load(io.open(PACE, encoding="utf-8"))
    except Exception:
        pass

    data = {
        "checkedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "paceAgeMin": None if a is None else round(a, 1),
        "quotaAgeMin": None if q is None else round(q, 1),
        "warnMin": WARN_MIN,
        "redMin": RED_MIN,
        "level": level,
        "refreshed": refreshed,
        "allPct": pace.get("allPct"),
        "allPctAsOf": pace.get("allPctAsOf"),
        "updatedAt": pace.get("updatedAt"),
        "note": "残量の数字が止まっていないかの見張り。%d分以上古ければ赤。"
                "pace.pyはmachine_status_push.shの747行目に相乗りしていて重い日は到達しない"
                "ので、ここで取り直す（1403番）。" % RED_MIN,
    }
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)

    # 画面が実際に読むのは status/public/ の方。その cp は
    # machine_status_push.sh の936行目＝pace.pyの747行目よりさらに後ろにあるため、
    # 取り直しただけでは画面に出ない（実測：public/pace.json が24分遅れていた）。ここで一緒に配る。
    pub = os.path.join(ST, "public")
    try:
        os.makedirs(pub, exist_ok=True)
        for n in ("pace.json", "quota.json", "now.json", "rev.txt", "zanryo_mihari.json"):
            src = os.path.join(ST, n)
            if os.path.exists(src):
                with io.open(src, "rb") as r, io.open(os.path.join(pub, n), "wb") as w:
                    w.write(r.read())
    except Exception:
        pass

    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
