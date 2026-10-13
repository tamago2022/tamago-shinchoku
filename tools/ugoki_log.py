#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""止まっていた時間を記録する（2026-10-04・優先A「工場が止まらない」）。

心臓の見張りループ（heartbeat_watchdog_loop.sh）から10秒おきに呼ばれる。1回は軽い。
見る3つ：
  心臓   status/.heartbeat_alive の更新が60秒超なし
  中継所 status/relay_red.json が🔴（届かない）
  計測   status/machine.json の measuredAt が45分超古い（15分おきの計測が止まった）
前回の呼び出しから経過した秒数を、止まっていた側に足す。見張り自身が止まっていた間も
「前回から間が空いた分」は止まっていた扱いにする（間が10分超なら見張り停止として心臓に計上）。
出力：status/public/downtime.json（今日の分数が1つの数字：minToday）／status/downtime_log.jsonl（日ごと）
"""
import io, json, os, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(REPO, "status")
STATE = os.path.join(S, ".ugoki_state.json")
OUT = os.path.join(S, "public", "downtime.json")
LOGF = os.path.join(S, "downtime_log.jsonl")


def age(p):
    try:
        return time.time() - os.path.getmtime(p)
    except Exception:
        return 1e9


def down_now():
    d = []
    if age(os.path.join(S, ".heartbeat_alive")) > 60:
        d.append("heartbeat")
    try:
        r = json.load(io.open(os.path.join(S, "relay_red.json"), encoding="utf-8"))
        if r.get("han") == "\U0001F534" and age(os.path.join(S, "relay_red.json")) < 900:
            d.append("relay")
    except Exception:
        pass
    try:
        m = json.load(io.open(os.path.join(S, "machine.json"), encoding="utf-8"))
        t = time.mktime(time.strptime(m["measuredAt"][:19], "%Y-%m-%dT%H:%M:%S"))
        if time.time() - t > 2700:
            d.append("keisoku")
    except Exception:
        d.append("keisoku")
    return d


def main():
    now = time.time()
    today = time.strftime("%F")
    try:
        st = json.load(io.open(STATE, encoding="utf-8"))
    except Exception:
        st = {}
    if st.get("date") != today:
        if st.get("date"):
            try:
                with io.open(LOGF, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"date": st["date"], "sec": st.get("sec", {}),
                                        "anyDownSec": st.get("any", 0)}, ensure_ascii=False) + "\n")
            except Exception:
                pass
        st = {"date": today, "sec": {}, "any": 0, "last": now, "down": []}
    gap = max(0.0, now - st.get("last", now))
    prev = st.get("down", [])
    if gap > 600:
        # 見張り自身が10分超止まっていた。その間は心臓側も見張られていない＝止まっていた扱い
        prev = sorted(set(prev) | {"heartbeat"})
    for k in prev:
        st["sec"][k] = st["sec"].get(k, 0) + gap
    if prev:
        st["any"] = st.get("any", 0) + gap
    cur = down_now()
    st["down"] = cur
    st["last"] = now
    io.open(STATE, "w", encoding="utf-8").write(json.dumps(st))
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        io.open(OUT, "w", encoding="utf-8").write(json.dumps({
            "date": today, "minToday": int(st["any"] // 60),
            "byKind": {k: int(v // 60) for k, v in st["sec"].items()},
            "downNow": cur, "at": time.strftime("%FT%T%z")}, ensure_ascii=False))
    except Exception:
        pass


if __name__ == "__main__":
    main()
