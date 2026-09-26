#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1163番【工場の体温】(2026-09-26)

たまごさん（Macが重さで固まって再起動した日）:
  「進捗表に『心臓：生／死』『最後に発車した時刻』『今の負荷』を出す。」

■ なぜ専用の紙を1枚作るのか（既存を使い回さない理由・実測）
  進捗表がすでに読んでいる2枚は、この用途には**古すぎた**。
    status/public/genzaichi.json … 22:06時点で generatedAt 19:46（2時間20分前）
    status/public/health.json    … 22:06時点で measuredAt  16:22（5時間44分前）
  古い紙で「心臓：生」と出すのは、**動いていないものを生きていると書く嘘**になる。
  ここは心臓が毎周まわすので、常に数十秒以内の数字しか載らない。

■ 中身（3つだけ。増やさない）
  心臓      … status/.heartbeat_alive の更新からの秒数。
               120秒以内＝生／600秒以内＝あやしい／それ超＝死
               （watchdogの死亡判定は60秒。ここはそれより甘く見て、
                 1周ぶんの揺れで「死」と出さない）
  最後の発車 … status/.last_launch_at（auto_launcher が本物を出した時刻）
  今の負荷   … status/machine_health.json の loadPct と oneline、
               ＋ status/launch_cap.json の同時上限

■ 取れないときは書かない
  値が取れなければ null を入れる。0や「生」で埋めない。
  進捗表側（index.html の「工場の体温」）は null を赤で「取れていません」と出す。

出力: status/public/taion.json
呼び出し: tools/heartbeat.sh（毎周）
"""
import io
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "public", "taion.json")

IKI_SEC = 120     # ここまでは「生」
AYASHII_SEC = 600  # ここまでは「あやしい」。超えたら「死」


def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _age(p):
    try:
        return time.time() - os.path.getmtime(p)
    except Exception:
        return None


def build():
    now = time.time()

    # ---- 心臓 ----
    a = _age(os.path.join(ST, ".heartbeat_alive"))
    if a is None:
        shinzou, shinzou_sec = None, None
    else:
        shinzou_sec = int(a)
        shinzou = "生" if a <= IKI_SEC else ("あやしい" if a <= AYASHII_SEC else "死")

    # ---- 最後の発車 ----
    hassha, hassha_min = None, None
    try:
        hassha = io.open(os.path.join(ST, ".last_launch_at"), encoding="utf-8").read().strip()
        # 2026-09-26T19:25:54+09:00 の形。時刻だけ使う（表示はページ側）
        t = time.mktime(time.strptime(hassha[:19], "%Y-%m-%dT%H:%M:%S"))
        hassha_min = round((now - t) / 60.0, 1)
    except Exception:
        pass

    # ---- 今の負荷 ----
    mh = _load(os.path.join(ST, "machine_health.json"), {}) or {}
    cap = (_load(os.path.join(ST, "launch_cap.json"), {}) or {}).get("cap")
    jougen = _load(os.path.join(ST, "dojisu_jougen.json"), {}) or {}

    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S+0900"),
        "心臓": shinzou,
        "心臓のだまり秒": shinzou_sec,
        "最後の発車": hassha,
        "最後の発車から分": hassha_min,
        "負荷Pct": mh.get("loadPct"),
        "負荷1行": mh.get("oneline"),
        "負荷を測った時刻": mh.get("measuredAt"),
        "同時上限": cap,
        "同時上限の根拠": jougen.get("根拠"),
        "スワップ残りGB": ((jougen.get("実測") or {}).get("swapFreeGB")),
        "出どころ": ("status/.heartbeat_alive ／ status/.last_launch_at ／ "
                     "status/machine_health.json ／ status/launch_cap.json"),
    }


def main():
    o = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)
    print("心臓 %s（%s秒）／最後の発車 %s／負荷 %s%%"
          % (o["心臓"], o["心臓のだまり秒"], o["最後の発車"], o["負荷Pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
