#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""サブスクの引き落とし3日前をGoogleカレンダーで知らせる（2026-10-14）

━━ なぜ作ったか（たまごさん依頼・2026-10-14）━━
  家計簿にあるサブスク全部に、引き落とし日9:00の繰り返し予定を作り、3日前にポップアップとメールで知らせる。
  家計簿にサブスクが増えたら、同じ予定も作られるようにする。

━━ 決めたこと ━━
  ① 正本は status/okane/kakin.json の services（家計簿・お金の紙と同じ）。ここに書き写さない。
  ② 予定の形：題「【サブスク】名前 金額 引き落とし」／引き落とし日 9:00–9:15／毎月（年額は毎年）／
     通知 3日前（4320分前）にポップアップとメール／空き時間扱い。
  ③ 作った予定は status/subsc_calendar/touroku.json に1件ずつ控える（id → eventId）。
  ④ 控えに無いサブスク＝「作り待ち」。心臓（4時間おき）がこれを数え、作り待ちがあれば
     status/dispatch_outbox.jsonl に1日1行だけ積む → Dispatch（Googleカレンダーのコネクタを持つ側）が
     `--machi` の中身どおりに予定を作り、`--done ID イベントID` で控える。
     ★シェルからはカレンダーを叩けない（鍵を工場に置かない）。だから「作る役」はコネクタ、「気づく役」は心臓。
  ⑤ 引き落とし日が分からないサブスクは予定を作らず「日付不明」として一覧に出す。
  ⑥ 課金・解約はしない。AIを呼ばない。外へ出ない＝0円。

━━ 使い方 ━━
  python3 tools/subsc_calendar.py              # 一覧を作る（status/public/subsc_calendar.json）＋作り待ちがあれば outbox に1行
  python3 tools/subsc_calendar.py --machi      # 作り待ちを JSON で（create_event にそのまま渡せる形）
  python3 tools/subsc_calendar.py --done ID EVENT_ID   # 作ったら控える
  python3 tools/subsc_calendar.py --self-test
"""
from __future__ import annotations

import argparse
import calendar
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
KAKIN = os.path.join(STATUS, "okane", "kakin.json")
KAWASE = os.path.join(STATUS, "okane", "kawase.json")
TOUROKU = os.path.join(STATUS, "subsc_calendar", "touroku.json")
OUT = os.path.join(STATUS, "public", "subsc_calendar.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
SENT = os.path.join(STATUS, "subsc_calendar", "outbox_sent.json")
JST = timezone(timedelta(hours=9))
JIKOKU = "09:00"
TSUCHI = [{"method": "popup", "minutes": 4320}, {"method": "email", "minutes": 4320}]
SUBSC_IGAI = ("従量", "無料")


def _load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = "%s.%d.tmp" % (p, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _yen(n):
    return "{:,}円".format(int(round(n)))


def _rate():
    k = _load(KAWASE, {}) or {}
    return float(k["jpy"]) if k.get("jpy") else None


def _nenngaku(s):
    return "年額" in (s.get("name") or "") or "年払い" in (s.get("tsugi_moto") or "") or s.get("shuuki") == "年"


def _kingaku(s, harai, rate):
    if s.get("tsugi_yen"):
        return _yen(s["tsugi_yen"])
    if s.get("tsugi_usd"):
        return ("約%s（$%.2f）" % (_yen(s["tsugi_usd"] * rate), s["tsugi_usd"])) if rate else "$%.2f" % s["tsugi_usd"]
    prev = sorted([h for h in harai if h.get("svc") == s["id"]], key=lambda h: h["d"])
    if prev:
        return _yen(prev[-1]["yen"])
    return "金額不明"


def _tsugi(day, month=None, today=None):
    """day日（年額なら month月day日）の、今日以降で最初の日。月末を超える日は月末に寄せる。"""
    today = today or datetime.now(JST).date()
    y, m = today.year, today.month
    for _ in range(30):
        mm = month or m
        yy = y
        d = min(day, calendar.monthrange(yy, mm)[1])
        c = date(yy, mm, d)
        if c >= today:
            return c
        if month:
            y += 1
        else:
            m += 1
            if m > 12:
                m, y = 1, y + 1
    return None


def _rrule(day, nen, month):
    if nen:
        return "RRULE:FREQ=YEARLY;BYMONTH=%d;BYMONTHDAY=%d" % (month, day)
    if day > 28:  # 30日など：無い月は月末に寄せる
        return "RRULE:FREQ=MONTHLY;BYMONTHDAY=%s;BYSETPOS=-1" % ",".join(str(x) for x in range(28, day + 1))
    return "RRULE:FREQ=MONTHLY;BYMONTHDAY=%d" % day


def build(kakin=None, touroku=None, today=None):
    kakin = kakin if kakin is not None else _load(KAKIN, {})
    touroku = touroku if touroku is not None else _load(TOUROKU, {})
    harai = kakin.get("harai") or []
    rate = _rate()
    machi, sumi, fumei, owari = [], [], [], []
    for s in kakin.get("services") or []:
        if s.get("shurui") in SUBSC_IGAI or s.get("muryo"):
            continue
        if s.get("owari"):
            owari.append({"id": s["id"], "name": s["name"], "tsugi": s.get("tsugi")})
            continue
        t = str(s.get("tsugi") or "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}", t):
            fumei.append({"id": s["id"], "name": s["name"], "naze": s.get("tsugi_moto") or "引き落とし日が分からない"})
            continue
        day, month = int(t[8:10]), int(t[5:7])
        nen = _nenngaku(s)
        start = _tsugi(day, month if nen else None, today)
        kin = _kingaku(s, harai, rate)
        ev = {"id": s["id"], "name": s["name"], "kingaku": kin, "hi": ("毎年%d月%d日" % (month, day)) if nen else ("毎月%d日" % day),
              "summary": "【サブスク】%s %s 引き落とし" % (s["name"], kin),
              "startTime": "%sT%s:00" % (start.isoformat(), JIKOKU),
              "endTime": "%sT09:15:00" % start.isoformat(),
              "recurrenceData": [_rrule(day, nen, month)],
              "overrideReminders": TSUCHI, "availability": "AVAILABILITY_FREE",
              "description": "家計簿（status/okane/kakin.json）から自動。根拠：%s。解約・プラン変更はAIからは押さない。" % (s.get("tsugi_moto") or "不明")}
        if s["id"] in touroku:
            sumi.append(dict(ev, eventId=touroku[s["id"]].get("eventId")))
        else:
            machi.append(ev)
    return {"generatedAt": datetime.now(JST).strftime("%Y-%m-%d %H:%M"), "machi": machi, "sumi": sumi,
            "fumei": fumei, "owari": owari}


def done(sid, event_id):
    t = _load(TOUROKU, {})
    t[sid] = {"eventId": event_id, "at": datetime.now(JST).isoformat(timespec="seconds")}
    _save(TOUROKU, t)


def run():
    d = build()
    _save(OUT, {k: v for k, v in d.items()})
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if d["machi"]:
        sent = _load(SENT, {})
        key = ",".join(sorted(x["id"] for x in d["machi"]))
        if sent.get(today) != key:
            line = {"at": datetime.now(JST).isoformat(), "from": "subsc_calendar",
                    "text": "【サブスクのカレンダー】家計簿に予定の無いサブスクが %d 件（%s）。Googleカレンダーのコネクタで作ってください：\n"
                            "python3 tools/subsc_calendar.py --machi の各行を create_event に渡す → 作ったら --done ID イベントID"
                            % (len(d["machi"]), "・".join(x["name"] for x in d["machi"]))}
            with io.open(OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
            sent[today] = key
            _save(SENT, sent)
    print("サブスクのカレンダー：作り待ち %d・作成済み %d・日付不明 %d（%s）"
          % (len(d["machi"]), len(d["sumi"]), len(d["fumei"]), "・".join(x["name"] for x in d["fumei"]) or "なし"))
    return 0


def self_test():
    k = {"harai": [{"svc": "b", "d": "2026-09-24", "yen": 5321}],
         "services": [
             {"id": "a", "name": "A", "shurui": "サブスク", "tsugi": "2026-11-12", "tsugi_yen": 1500},
             {"id": "b", "name": "B", "shurui": "サブスク", "tsugi": "2026-10-24"},
             {"id": "c", "name": "C", "shurui": "不明", "tsugi": "不明"},
             {"id": "d", "name": "D", "shurui": "従量", "tsugi": "使った分だけ"},
             {"id": "e", "name": "E 年額", "shurui": "サブスク", "tsugi": "2027-09-24", "tsugi_yen": 100},
             {"id": "f", "name": "F", "shurui": "サブスク", "tsugi": "2026-10-30", "tsugi_yen": 1},
             {"id": "g", "name": "G", "shurui": "サブスク", "tsugi": "2026-10-16", "owari": True}]}
    d = build(k, {"a": {"eventId": "x"}}, today=date(2026, 10, 14))
    m = {x["id"]: x for x in d["machi"]}
    res = [
        ("① 控え済みは作り待ちに出ない", "a" not in m and d["sumi"][0]["id"] == "a"),
        ("② 前回の額で題を作る", m["b"]["summary"] == "【サブスク】B 5,321円 引き落とし"),
        ("③ 日付不明は予定を作らず一覧へ", [x["id"] for x in d["fumei"]] == ["c"]),
        ("④ 従量は対象外", "d" not in m),
        ("⑤ 年額は毎年", m["e"]["recurrenceData"][0].startswith("RRULE:FREQ=YEARLY")),
        ("⑥ 30日は月末に寄せる", "BYSETPOS=-1" in m["f"]["recurrenceData"][0]),
        ("⑦ 終了予定は作らない", "g" not in m and d["owari"][0]["id"] == "g"),
        ("⑧ 9:00・3日前ポップアップ＋メール・空き時間", m["b"]["startTime"] == "2026-10-24T09:00:00"
         and m["b"]["overrideReminders"] == TSUCHI and m["b"]["availability"] == "AVAILABILITY_FREE"),
        ("⑨ 過ぎた日は来月から", _tsugi(13, today=date(2026, 10, 14)) == date(2026, 11, 13)),
    ]
    ng = [x for x in res if not x[1]]
    print("サブスクのカレンダー 見本試験: %d件中 %d件 想定どおり" % (len(res), len(res) - len(ng)))
    for n, ok in res:
        print("  %s %s" % ("◯" if ok else "✕", n))
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machi", action="store_true")
    ap.add_argument("--done", nargs=2, metavar=("ID", "EVENT_ID"))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.done:
        done(*a.done)
        print("控えた：%s → %s" % tuple(a.done))
        return 0
    if a.machi:
        print(json.dumps(build()["machi"], ensure_ascii=False, indent=1))
        return 0
    return run()


if __name__ == "__main__":
    sys.exit(main())
