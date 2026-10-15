#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【Bufferの枠の門番】1日250回の枠を使い切ったら、全員そこで退く。

2026-09-27 に実際に起きたこと:
  tools/1166_yotei.py を心臓の毎周回から呼んでいた（間引き無し）。
  1周回で4回叩くので、数分で 15分100回 の枠を超え、
  さらに **24時間250回** の枠まで使い切った。
    x-ratelimit-limit: 250 ／ x-ratelimit-remaining: 0
    Retry-After: 73274（＝約20時間）
  そのあと何を呼んでも429で、予約の取り直しも投入も一切できなくなった。

だからBufferを叩く道具は **叩く前に必ず ake() を通る**。
枠が戻る時刻を過ぎるまでは、叩かずに False を返す＝APIを1回も使わない。

使い方:
    import buffer_waku
    if not buffer_waku.ake():
        print(buffer_waku.riyuu()); return
    ...叩く...
    except HTTPError as e:
        buffer_waku.tometa(e.headers)   # ★429を受けたらここに渡す
"""
import io
import json
import os
import time
import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(REPO, "status", "buffer_queue", ".waku.json")
JST = datetime.timezone(datetime.timedelta(hours=9))


def _yomu():
    try:
        return json.load(io.open(GATE, encoding="utf-8"))
    except Exception:
        return {}


def modoru():
    """枠が戻るunix時刻（分からなければ0）。"""
    return float(_yomu().get("reset") or 0)


def ake():
    """叩いてよければ True。"""
    return time.time() >= modoru()


def riyuu():
    r = modoru()
    if time.time() >= r:
        return "枠は空いている"
    t = datetime.datetime.fromtimestamp(r, JST)
    return ("★Bufferの枠を使い切っている（1日250回）。%s まで叩かない（あと %.1f 時間）"
            % (t.strftime("%F %H:%M JST"), (r - time.time()) / 3600.0))


def tometa(headers, naze=""):
    """429を受け取ったときに呼ぶ。ヘッダから戻る時刻を読んで門を閉める。"""
    h = {}
    try:
        h = {k.lower(): v for k, v in dict(headers).items()}
    except Exception:
        pass
    reset = 0.0
    try:
        reset = float(h.get("x-ratelimit-reset") or 0)
    except Exception:
        reset = 0.0
    if not reset:
        try:
            reset = time.time() + float(h.get("retry-after") or 900)
        except Exception:
            reset = time.time() + 900
    d = {"reset": reset,
         "tometa_at": datetime.datetime.now(JST).strftime("%F %T"),
         "modoru": datetime.datetime.fromtimestamp(reset, JST).strftime("%F %H:%M"),
         "limit": h.get("x-ratelimit-limit"),
         "remaining": h.get("x-ratelimit-remaining"),
         "naze": naze}
    try:
        os.makedirs(os.path.dirname(GATE), exist_ok=True)
        json.dump(d, io.open(GATE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass
    return d


if __name__ == "__main__":
    print(riyuu())
    print(json.dumps(_yomu(), ensure_ascii=False, indent=1))
