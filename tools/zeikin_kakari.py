#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1036番【税金ライン・常駐】1日1回、拾って裏を取る係。

━━ たまごさん（2026-09-23・原文）━━

  「ひたすら裏取りリサーチ。告発系の発信者いるじゃん。もう、それの自動化。
    それだけやる役目の人がいてもいい。」

━━ 形（新しい常駐を作らない）━━

  launchd を増やさない。**既に動いている心臓（tools/heartbeat.sh・15秒おき）に相乗りし、
  中で1日1回に間引く。**（tools/daily_ingest_scheduler.py と同じ型をそのまま踏襲）

  心臓は Mac の上で動いている ＝ Vault にも外のAPIにも手が届く。
  （サンドボックスからは両方とも届かない。実測：curl → 000）

━━ 1日1回やること ━━

  ① 拾う   tools/zeikin_hiroi.py  … 棚を丸ごと＋#税金タグ。新しいノートが増えたら自動で積む
  ② 裏取る tools/zeikin_uratori.py … 未のものを上から --limit 件
  ③ 数える status/uratori/counts.json に3つの数字だけ書く
             （裏取り待ち／裏が取れた／取れなかった）

━━ 赤の出し方（★黙って飲み込まない）━━

  「走った回数>0 なのに 取れた回数=0」＝赤。status/uratori/akai.txt に書く。
  no_credential・401・403・skip を成功として数えない。

━━ 使い方 ━━

    python3 tools/zeikin_kakari.py            # 1日1回だけ本体が走る（それ以外は即戻る）
    python3 tools/zeikin_kakari.py --now      # 間引きを無視して今すぐ走らせる
    python3 tools/zeikin_kakari.py --sanji    # 3つの数字だけ出す（進捗表用）

終了コード: 0=正常 / 1=赤
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUTDIR = os.path.join(REPO, "status", "uratori")
MARKER = os.path.join(REPO, "status", ".zeikin_kakari_last")
COUNTS = os.path.join(OUTDIR, "counts.json")
AKAI = os.path.join(OUTDIR, "akai.txt")
LOG = os.path.join(OUTDIR, "kakari.log")
JST = timezone(timedelta(hours=9))

HIROI = os.path.join(HERE, "zeikin_hiroi.py")
URA = os.path.join(HERE, "zeikin_uratori.py")


def today() -> str:
    return datetime.now(JST).strftime("%F")


def now() -> str:
    return datetime.now(JST).strftime("%F %T")


def ran_today() -> bool:
    try:
        return open(MARKER, encoding="utf-8").read().strip() == today()
    except Exception:
        return False


def mark():
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    with open(MARKER, "w", encoding="utf-8") as f:
        f.write(today())


def run(cmd, timeout=240):
    try:
        p = subprocess.run([sys.executable] + cmd, capture_output=True,
                           text=True, timeout=timeout, cwd=REPO)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 99, repr(e)


def sanji() -> dict:
    try:
        return json.load(open(COUNTS, encoding="utf-8"))
    except Exception:
        return {"machi": 0, "toreta": 0, "torezu": 0, "at": "―"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--sanji", action="store_true")
    ap.add_argument("--limit", type=int, default=8)
    a = ap.parse_args()

    if a.sanji:
        c = sanji()
        print("裏取り待ち %d ／ 裏が取れた %d ／ 取れなかった %d （%s）"
              % (c.get("machi", 0), c.get("toreta", 0), c.get("torezu", 0),
                 c.get("at", "―")))
        return 0

    if not a.now and ran_today():
        return 0
    mark()
    os.makedirs(OUTDIR, exist_ok=True)

    before = sanji()
    lines = ["== %s 税金ラインの係 ==" % now()]

    rc1, o1 = run([HIROI, "--tana", "--budget", "60"])
    lines.append("① 棚を丸ごと拾う rc=%d\n%s" % (rc1, o1.strip()[:1500]))
    rc2, o2 = run([HIROI, "--budget", "70"])
    lines.append("① タグを拾う rc=%d\n%s" % (rc2, o2.strip()[:1500]))
    rc3, o3 = run([URA, "--limit", str(a.limit)])
    lines.append("② 裏を取る rc=%d\n%s" % (rc3, o3.strip()[:3000]))

    after = sanji()
    hashitta = a.limit
    fueta = after.get("toreta", 0) - before.get("toreta", 0)
    lines.append("③ 裏取り待ち %d ／ 裏が取れた %d ／ 取れなかった %d"
                 % (after.get("machi", 0), after.get("toreta", 0),
                    after.get("torezu", 0)))

    akai = (hashitta > 0 and fueta == 0 and after.get("toreta", 0) == 0)
    if akai:
        msg = ("%s ★赤：走ったのに1件も取れていません（走った%d・増えた%d）。"
               "APIの口か、Vaultへの道が閉じている可能性があります。"
               % (now(), hashitta, fueta))
        lines.append(msg)
        with open(AKAI, "w", encoding="utf-8") as f:
            f.write(msg + "\n")
    elif os.path.exists(AKAI):
        try:
            os.remove(AKAI)
        except Exception:
            pass

    body = "\n".join(lines)
    print(body)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(body + "\n\n")
    except Exception:
        pass
    return 1 if akai else 0


if __name__ == "__main__":
    sys.exit(main())
