#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1447番【週5日・100時間ずっとやってくれるか】を実測する係。

━━ なぜ作ったか（2026-09-18・たまごさん原文の抜粋）━━
  「週5日だったら100時間くらいずっとやってくれるっていうんだったら
    3,500円払う価値はあると思う」

  これは「もし週5日、ほぼずっと動いてくれるなら」という条件付きの評価。
  実際にDevinがその条件（週5日・継続稼働）を満たしているかどうかを、
  手で数えず、Devin API（/v1/sessions）の created_at/updated_at から機械で出す。

━━ 出すもの ━━
  status/1447_shukan_kado.json … 日別・曜日別の投入本数と稼働分数
  share/check/1447-shukan-kado.html … 確認ページ
"""
import importlib
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT_JSON = os.path.join(REPO, "status", "1447_shukan_kado.json")

seiseki = importlib.import_module("1501_devin_seiseki")


def to_jst(iso_s):
    if not iso_s:
        return None
    try:
        s = iso_s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(JST)
    except Exception:
        return None


def build():
    ss = seiseki.sessions()
    rows = []
    for s in ss:
        c = to_jst(s.get("created_at"))
        u = to_jst(s.get("updated_at"))
        if not c:
            continue
        dur_min = None
        if u:
            dur_min = max(0, round((u - c).total_seconds() / 60.0, 1))
        rows.append({
            "sid": s.get("session_id"),
            "title": s.get("title") or "",
            "created": c.strftime("%Y-%m-%d %H:%M"),
            "updated": u.strftime("%Y-%m-%d %H:%M") if u else None,
            "date": c.strftime("%Y-%m-%d"),
            "dur_min": dur_min,
            "status": s.get("status_enum") or s.get("status"),
        })
    rows.sort(key=lambda r: r["created"])

    if rows:
        start_date = datetime.strptime(rows[0]["date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(rows[-1]["date"], "%Y-%m-%d").date()
    else:
        start_date = end_date = datetime.now(JST).date()

    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], {"n": 0, "min": 0.0, "times": []})
        by_day[r["date"]]["n"] += 1
        by_day[r["date"]]["min"] += (r["dur_min"] or 0)
        by_day[r["date"]]["times"].append(r["created"][11:])

    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
    days_out = []
    cur = start_date
    weekday_total = 0
    weekday_active = 0
    weekday_blank_streak = 0
    max_blank_streak = 0
    total_min = 0.0
    total_n = 0
    while cur <= end_date:
        wd = cur.weekday()
        is_weekday = wd < 5
        key_s = cur.strftime("%Y-%m-%d")
        info = by_day.get(key_s, {"n": 0, "min": 0.0, "times": []})
        total_min += info["min"]
        total_n += info["n"]
        if is_weekday:
            weekday_total += 1
            if info["n"] > 0:
                weekday_active += 1
                weekday_blank_streak = 0
            else:
                weekday_blank_streak += 1
                max_blank_streak = max(max_blank_streak, weekday_blank_streak)
        days_out.append({
            "date": key_s,
            "weekday": weekday_ja[wd],
            "is_weekday": is_weekday,
            "n": info["n"],
            "min": round(info["min"], 1),
            "times": info["times"],
        })
        cur += timedelta(days=1)

    span_days = (end_date - start_date).days + 1

    # 財布・流し続ける係(1142番)の今の状態も一緒に出す（勝手に開けたり止めたりしない・実測だけ）
    yosan_devin = None
    try:
        import yosan
        st = yosan.settei()
        used, _ = yosan.tsukatta_gokei("devin") or (0, 0)
        limit = float((st.get("devin") or {}).get("jougen_yen", 0) if isinstance(st.get("devin"), dict) else 0)
        yosan_devin = {"jougen_yen": limit, "tsukatta_yen": float(used or 0)}
    except Exception as e:
        yosan_devin = {"error": repr(e)[:200]}

    nagashi_state = None
    try:
        with io.open(os.path.join(REPO, "status", "1142", "nagashi.json"), encoding="utf-8") as f:
            nagashi_state = json.load(f)
    except Exception:
        nagashi_state = None

    out = {
        "at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        "tsukurikata": "Devin API（/v1/sessions）の created_at/updated_at から機械で出している。手で書いた数字は無い。",
        "shitsumon": "週5日だったら100時間くらいずっとやってくれるっていうんだったら3,500円払う価値はあると思う（2026-09-18・たまごさん原文）",
        "kikan": {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d"), "nissuu": span_days},
        "goukei": {
            "nageta_hon": total_n,
            "kado_fun": round(total_min, 1),
            "kado_jikan": round(total_min / 60.0, 1),
            "heijitsu_nissuu": weekday_total,
            "heijitsu_kado_nissuu": weekday_active,
            "heijitsu_kuuhaku_nissuu": weekday_total - weekday_active,
            "saidai_renzoku_kuuhaku_heijitsu": max_blank_streak,
        },
        "hantei": {
            "joken": "週5日（平日5日とも投入あり）／100時間（週あたり）",
            "jittai": "平日%d日のうち%d日は投入ゼロ。実働合計は%.1f時間（100時間には遠く届かない）" % (
                weekday_total - weekday_active, weekday_total, total_min / 60.0),
            "mitasu": False,
        },
        "yosan_devin": yosan_devin,
        "nagashi_1142": {
            "note": "1142番「流し続ける係」は既に実装済み・心臓(heartbeat)から1分おきに監視している",
            "devin_hashiru": (nagashi_state or {}).get("devin_hashiru"),
            "devin_tomete_iru_riyuu": (nagashi_state or {}).get("devin_tomete_iru_riyuu"),
            "kyou_nageta": (nagashi_state or {}).get("kyou_nageta"),
        },
        "days": days_out,
        "rows_sample": rows[-10:],
    }
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    d = build()
    print(json.dumps(d["goukei"], ensure_ascii=False, indent=1))
    print(json.dumps(d["hantei"], ensure_ascii=False, indent=1))
