#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
利用枠（週枠）の推定（2026-09-03）— 「土曜に天井に着いて火曜まで止まる」を機械で防ぐ。

枠を読める API は無い（確認できていない）ので **推定** する。方法:
  1. ~/.claude/projects/**/*.jsonl の assistant メッセージの usage（モデル別トークン）を、週枠リセット（火曜 17:59 JST）以降で集計
     重み: input 1.0 / cache_creation 1.25 / cache_read 0.1 / output 5.0（費用の比率に近い概算）
  2. たまごさんがスマホで見た実測値（アンカー）で目盛りを合わせる: status/quota_anchor.json {"t":..., "fablePct":63, "allPct":44}
     → 現在% ≒ アンカー% × (今の累計 ÷ アンカー時点の累計)
  3. 直近6時間の消費ペースから「このまま行くと何時間で天井（100%）か」「リセットまでに何%に達するか」を出す
出力: status/quota.json（factory_status/watchdog が machine.json の quota 節に載せる。PWAが読む）。すべて「推定」と明記。
状態: status/quota-state.json（ファイルごとの読み終えたバイト位置と15分バケツ別の累計。毎回全部読み直さない）

使い方:
  python3 quota_estimate.py            # 更新して要約を表示
  python3 quota_estimate.py --quiet
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATE = os.path.join(REPO, "status", "quota-state.json")
ANCHOR = os.path.join(REPO, "status", "quota_anchor.json")
SESSION5H_ANCHOR = os.path.join(REPO, "status", "session5h_anchor.json")
OUT = os.path.join(REPO, "status", "quota.json")
SESSION5H_HOURS = 5
W = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1, "output_tokens": 5.0}
BUCKET = 900  # 15分
RESET_WDAY, RESET_H, RESET_M = 1, 17, 59  # 火曜 17:59（ローカル＝JST）
WARN_PCT, STOP_PCT = 75, 85
# 曜日ごとの目標上限（たまごさん指定・2026-09-03）。tm_wday: 月0/火1/水2/木3/金4/土5/日6
WEEKDAY_TARGET = {2: 30, 3: 45, 4: 55, 5: 70, 6: 80, 0: 90, 1: 100}
WEEKDAY_TARGET_TABLE = "水30/木45/金55/土70/日80/月90/火100(17:59まで)"


def last_reset(now=None):
    now = now or time.time()
    lt = time.localtime(now)
    # 今週の火曜 17:59
    days_since_tue = (lt.tm_wday - RESET_WDAY) % 7
    t = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - days_since_tue, RESET_H, RESET_M, 0, 0, 0, -1))
    if t > now:
        t -= 7 * 86400
    return t


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)


def avg_alive(now, hours):
    """直近◯時間の history.jsonl から、5分刻みの各スナップショットで生きていたセッション数の平均を出す。
    「Sonnet1本を1時間回すと何%」を出すための分母（自動制御の心臓部・2026-09-03）。"""
    path = os.path.join(REPO, "status", "history.jsonl")
    since_h = now - hours * 3600
    counts = {}
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                t = ts_epoch(r.get("t") or "")
                if not t or t < since_h:
                    continue
                counts[r.get("t")] = counts.get(r.get("t"), 0) + 1
    except Exception:
        return None
    return (sum(counts.values()) / len(counts)) if counts else None


def ts_epoch(ts):
    try:
        t = time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
        return time.mktime(t) - time.timezone if ts.endswith("Z") else time.mktime(t)
    except Exception:
        return None


def scan(state, since):
    files = state.setdefault("files", {})
    buckets = state.setdefault("buckets", {})  # {"<bucket_epoch>": {"fable": w, "other": w, "fableMsgs": n, "otherMsgs": n}}
    for p in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
        try:
            st = os.stat(p)
        except Exception:
            continue
        if st.st_mtime < since:
            continue
        rec = files.get(p, {"off": 0})
        if st.st_size < rec["off"]:
            rec["off"] = 0
        if st.st_size == rec["off"]:
            continue
        try:
            with open(p, "rb") as f:
                f.seek(rec["off"])
                data = f.read()
            # 最後の行が書きかけなら次回に回す
            nl = data.rfind(b"\n")
            if nl < 0:
                continue
            chunk = data[:nl + 1]
            rec["off"] += len(chunk)
            for ln in chunk.decode("utf-8", "ignore").splitlines():
                if '"usage"' not in ln or '"type":"assistant"' not in ln:
                    continue
                try:
                    e = json.loads(ln)
                except Exception:
                    continue
                m = e.get("message") or {}
                u = m.get("usage") or {}
                t = ts_epoch(e.get("timestamp") or "")
                if not t or t < since:
                    continue
                w = sum(float(u.get(k) or 0) * v for k, v in W.items())
                if w <= 0:
                    continue
                b = str(int(t // BUCKET * BUCKET))
                bb = buckets.setdefault(b, {"fable": 0.0, "other": 0.0, "fableMsgs": 0, "otherMsgs": 0})
                if "fable" in str(m.get("model") or ""):
                    bb["fable"] += w; bb["fableMsgs"] += 1
                else:
                    bb["other"] += w; bb["otherMsgs"] += 1
        except Exception:
            pass
        files[p] = rec
    # リセット前のバケツは捨てる
    for k in list(buckets):
        if int(k) < since:
            del buckets[k]
    return state


def main():
    now = time.time()
    since = last_reset(now)
    next_reset = since + 7 * 86400
    state = load(STATE, {})
    if state.get("since") != since:
        state = {"since": since, "files": {}, "buckets": {}}  # 週が変わったら作り直し
    scan(state, since)
    save(STATE, state)
    buckets = state["buckets"]
    cum = lambda upto, key: sum(v[key] for k, v in buckets.items() if int(k) <= upto)
    total_between = lambda lo, hi: sum(v["fable"] + v["other"] for k, v in buckets.items() if lo <= int(k) <= hi)
    fable_now, all_now = cum(now, "fable"), cum(now, "fable") + cum(now, "other")
    anchor = load(ANCHOR, {})
    est = {"method": "推定（会話ログのトークン量×アンカー実測で目盛り合わせ）", "anchor": anchor}
    a_t = ts_epoch(anchor.get("t", "")) if anchor else None
    if a_t and a_t >= since:
        fa, aa = cum(a_t, "fable"), cum(a_t, "fable") + cum(a_t, "other")
        fable_pct = anchor["fablePct"] * (fable_now / fa) if fa > 0 else None
        all_pct = anchor["allPct"] * (all_now / aa) if aa > 0 else None
    else:
        fable_pct = all_pct = None
        est["method"] = "推定不可（アンカー未設定。python3 tools/quota_anchor.py <Fable%> <全モデル%> で設定）"
    # ペース：直近6時間
    six = now - 6 * 3600
    f6 = sum(v["fable"] for k, v in buckets.items() if int(k) >= six)
    a6 = f6 + sum(v["other"] for k, v in buckets.items() if int(k) >= six)
    hours_left = (next_reset - now) / 3600
    proj = {}
    if fable_pct is not None and fable_now > 0:
        pct_per_hour = fable_pct / max(1e-9, (now - since) / 3600)  # 平均ペース
        pace6 = (fable_pct * (f6 / fable_now)) / 6 if fable_now else 0  # 直近6hのペース（%/h）
        rate = max(pace6, 0)
        proj = {"fablePctAtReset_avgPace": round(min(999, fable_pct + pct_per_hour * hours_left), 1),
                "fablePctAtReset_recentPace": round(min(999, fable_pct + rate * hours_left), 1),
                "hoursToCeiling_recentPace": round((100 - fable_pct) / rate, 1) if rate > 0 and fable_pct < 100 else None,
                "recentPacePctPerHour": round(rate, 2)}
    fable_level = "stop" if (fable_pct or 0) >= STOP_PCT else "warn" if (fable_pct or 0) >= WARN_PCT else "ok"
    if proj.get("fablePctAtReset_recentPace") is not None and proj["fablePctAtReset_recentPace"] >= 100 and fable_level == "ok":
        fable_level = "warn"  # このペースだとリセット前に天井
    # 2026-09-03 曜日ごとの目標カーブ（たまごさん指定：水30/木45/金55/土70/日80/月90/火100）で日次予算を超えていれば
    # 75/85%の絶対閾値に届いていなくても「今日はもう使わない」として stop にする（例：今週は木金ゼロ・土日月10%ずつの計画）
    weekday_target = WEEKDAY_TARGET[time.localtime(now).tm_wday]
    over_pct = round(fable_pct - weekday_target, 1) if fable_pct is not None else None
    if over_pct is not None and over_pct > 0:
        fable_level = "stop"
    elif over_pct is not None and over_pct > -10 and fable_level == "ok":
        fable_level = "warn"
    # 2026-09-03 訂正（たまごさん本人）：週枠は「余らせるのが正解」ではなく「火曜17:59直前に99%で走り切る」のが正解。
    # 曲線から**大きく下振れ**（使わなさすぎ）も**上振れ**（使いすぎ）も同じく失点。判定は両側にする。
    CURVE_BAND = 10  # このポイント差までは「曲線内」とみなす
    fable_curve_state = ("over" if over_pct is not None and over_pct > CURVE_BAND else
                          "under" if over_pct is not None and over_pct < -CURVE_BAND else
                          "on_track" if over_pct is not None else "unknown")
    fable_headroom_pct = round(-over_pct, 1) if (over_pct is not None and over_pct < 0) else 0.0
    # 1日あたりの許容量（残り%÷残り日数）と今日（直近24h）の実消費。今日の消費が許容量を超えていれば絞る
    day = {}
    if fable_pct is not None:
        f24 = sum(v["fable"] for k, v in buckets.items() if int(k) >= now - 86400)
        a24 = f24 + sum(v["other"] for k, v in buckets.items() if int(k) >= now - 86400)
        f_today = fable_pct * (f24 / fable_now) if fable_now else 0
        a_today = (all_pct or 0) * (a24 / all_now) if all_now else 0
        days_left = max(hours_left / 24, 0.25)
        day = {"fableAllowancePerDay": round((100 - fable_pct) / days_left, 1), "fableUsedLast24h": round(f_today, 1),
               "allAllowancePerDay": round((100 - (all_pct or 0)) / days_left, 1), "allUsedLast24h": round(a_today, 1),
               "weeklyEvenPacePerDay": round(100 / 7, 1)}
        if f_today > day["fableAllowancePerDay"] and fable_level == "ok":
            fable_level = "warn"  # 今日のFable消費が「残りを日割りした許容量」を超えた
    all_level = "stop" if (all_pct or 0) >= STOP_PCT else "warn" if (all_pct or 0) >= WARN_PCT else "ok"
    days_elapsed = round((now - since) / 86400, 1)
    ceiling_days = None
    if proj.get("hoursToCeiling_recentPace"):
        ceiling_days = round(proj["hoursToCeiling_recentPace"] / 24, 1)
    # 2026-09-03 全モデル週枠は Fable と別計算・別判定（混ぜない）。曲線は「経過日数÷7日」の直線（火曜17:59直前に99%）。
    # Fable専用の曲線（水30/木45/…）は本人の個人的なFableの使い方の感覚値なので、全モデルには流用しない。
    all_linear_target = round(min(99.0, (days_elapsed / 7.0) * 100.0), 1)
    all_over_pct = round(all_pct - all_linear_target, 1) if all_pct is not None else None
    all_curve_state = ("over" if all_over_pct is not None and all_over_pct > CURVE_BAND else
                        "under" if all_over_pct is not None and all_over_pct < -CURVE_BAND else
                        "on_track" if all_over_pct is not None else "unknown")

    # ---- 5時間セッション枠（週枠とは別物・ローリング）2026-09-03 ----
    # 週枠＝余らせるのが正解。5時間枠＝使い切らないと消える（たまごさん指摘）。
    # なのでこちらは「このままだと何%余る見込みか（もったいない度）」を出す。本数を増やす判断は factory_status.py が使う。
    session5h = None
    sa = load(SESSION5H_ANCHOR, {})
    if sa.get("t") is not None and sa.get("remainMin") is not None:
        anchor_t5 = ts_epoch(sa["t"])
        if anchor_t5:
            elapsed_at_anchor_h = SESSION5H_HOURS - sa["remainMin"] / 60
            window_start = anchor_t5 - elapsed_at_anchor_h * 3600
            reset_at5 = window_start + SESSION5H_HOURS * 3600
            tok_at_anchor = total_between(window_start, anchor_t5)
            tok_now = total_between(window_start, now)
            pct5 = sa["pct"] * (tok_now / tok_at_anchor) if tok_at_anchor > 0 else sa["pct"]
            hours_left5 = max(0.0, (reset_at5 - now) / 3600)
            elapsed_since_anchor_h = (now - anchor_t5) / 3600
            elapsed_in_window_h = max(1e-9, (now - window_start) / 3600)
            avg_pace_in_window = pct5 / elapsed_in_window_h
            rate5 = ((pct5 - sa["pct"]) / elapsed_since_anchor_h) if elapsed_since_anchor_h >= 0.1 else avg_pace_in_window
            rate5 = max(0.0, rate5)
            projected5 = min(999.0, pct5 + rate5 * hours_left5)
            waste_pct = max(0.0, 100.0 - projected5) if hours_left5 > 0 else 0.0
            mottainai = hours_left5 > 0 and waste_pct >= 20
            session5h = {
                "pct": round(pct5, 1), "resetAt": time.strftime("%Y-%m-%d %H:%M", time.localtime(reset_at5)),
                "hoursLeft": round(hours_left5, 2), "recentPacePctPerHour": round(rate5, 2),
                "projectedPctAtReset": round(projected5, 1), "wasteRiskPct": round(waste_pct, 1),
                "mottainai": mottainai, "anchor": sa,
                "note": "5時間枠は使い切らないと消える。余る見込みが大きいときは本数を安全上限まで増やす（factory_status.pyが判定）",
            }

    # ---- 自動制御の心臓部（2026-09-03）：「セッション1本を1時間動かすと全モデル週枠が何%進むか」 ----
    # 直近6時間の全モデル消費ペース(%/h) ÷ 直近6時間の平均生存本数 = 1本1時間あたりの消費%。
    # これが出れば「5時間枠を埋めるのに何本要るか」「週枠の曲線に対して何本が適正か」を逆算できる。
    benchmark = None
    if all_pct is not None and all_now > 0:
        all_pace6 = (all_pct * (a6 / all_now)) / 6  # %/hour（直近6h実績）
        alive6 = avg_alive(now, 6)
        pct_per_session_hour = round(all_pace6 / alive6, 4) if alive6 and alive6 > 0 else None
        benchmark = {"allPacePctPerHour6h": round(all_pace6, 3), "aliveAvgLast6h": round(alive6, 1) if alive6 else None,
                     "pctPerSessionHour": pct_per_session_hour,
                     "note": "標本6h未満だと不安定。走らせ続けるほど精度が上がる"}
        if pct_per_session_hour and session5h:
            target5h = 90.0  # 使い切りすぎて途中で天井に当たらないよう90%止まりを狙う
            need5h = (target5h - session5h["pct"]) / (pct_per_session_hour * session5h["hoursLeft"]) if session5h["hoursLeft"] > 0 else None
            benchmark["sonnetSessionsFor5hWindow"] = round(need5h, 1) if need5h and need5h > 0 else None
        if pct_per_session_hour:
            days_left_w = max(hours_left / 24, 0.1)
            target_all_reset = 99.0
            need_weekly = (target_all_reset - (all_pct or 0)) / (pct_per_session_hour * days_left_w * 24) if days_left_w > 0 else None
            benchmark["sonnetSessionsForWeeklyCurve"] = round(need_weekly, 1) if need_weekly and need_weekly > 0 else None

    out = {"updatedAt": time.strftime("%Y-%m-%d %H:%M"), "estimated": True,
           "fablePct": round(fable_pct, 1) if fable_pct is not None else None,
           "allPct": round(all_pct, 1) if all_pct is not None else None,
           "resetAt": time.strftime("%Y-%m-%d %H:%M", time.localtime(next_reset)),
           "daysLeft": round(hours_left / 24, 1), "hoursLeft": round(hours_left, 1),
           "fableLevel": fable_level, "allLevel": all_level, "warnPct": WARN_PCT, "stopPct": STOP_PCT, "daily": day,
           "policy": ("Fable＝マガジン記事執筆のみ。他は全部Sonnet。週枠は「余らせる」のではなく火曜17:59直前に99%で走り切るのが正解＝"
                      "曲線(" + WEEKDAY_TARGET_TABLE + ")から" + str(CURVE_BAND) + "pt以上の上振れでFableゼロ(新規停止・走行中もSonnetへ交代)、下振れならFable投入・本数増加の余地あり。"
                      "全モデル週枠も同じ考え方だが曲線は別計算（経過日数÷7日の直線）で混ぜない。5時間枠は別物でこちらは常に使い切る。"
                      "本数は減らさない・増やす方向のみ"),
           "costNote": ("2026-09-02公式検証：入力$10/出力$50は据え置き、安くなったのはキャッシュ読み込みのみ($1→$0.25)。"
                        "1回投げるだけの短いタスクはむしろ約20%割高。短いタスクをFableで大量に投げるのが最悪の使い方"
                        "（09-02に26本中21本をFableで立てて63%到達した原因）。方針：普段はOpus/Sonnet、一晩任せる重い仕事だけFable、大量処理はSonnet。"
                        "effortは普段high・詰まったら自動再開時のみxhigh・maxの常用はしない"),
           "fableWeightedTokensSinceReset": int(fable_now), "allWeightedTokensSinceReset": int(all_now),
           "last6h": {"fable": int(f6), "all": int(a6)},
           "projection": proj, **est,
           "weekdayTarget": weekday_target, "weekdayTargetTable": WEEKDAY_TARGET_TABLE,
           "overPct": over_pct, "daysElapsedSinceReset": days_elapsed, "ceilingDaysAtRecentPace": ceiling_days,
           "fableCurve": {"target": weekday_target, "overPct": over_pct, "state": fable_curve_state,
                          "headroomPct": fable_headroom_pct, "band": CURVE_BAND,
                          "note": "state=over→Fableゼロで絞る／under→Fable投入・本数増加の余地あり／on_track→曲線どおり"},
           "allCurve": {"target": all_linear_target, "overPct": all_over_pct, "state": all_curve_state, "band": CURVE_BAND,
                        "note": "Fableとは別計算（経過日数÷7日の直線）。under→本数を増やす余地あり（factory_status.pyが判定）"},
           "session5h": session5h,
           "benchmark": benchmark,
           "line": ("Fable週枠 %s%%（今日の目標%s%%・%s） ／ 全モデル %s%%（曲線目標%s%%・%s） ／ リセットまで %.1f日%s ／ 5時間枠 %s" % (
               "?" if fable_pct is None else round(fable_pct), weekday_target,
               {"over": "%.1fpt上振れ→絞る" % over_pct if over_pct else "", "under": "%.1fpt下振れ→投入余地あり" % (-over_pct) if over_pct else "",
                "on_track": "曲線どおり", "unknown": "?"}.get(fable_curve_state, "?"),
               "?" if all_pct is None else round(all_pct), all_linear_target,
               {"over": "%.1fpt上振れ" % all_over_pct if all_over_pct else "", "under": "%.1fpt下振れ→本数増やす余地" % (-all_over_pct) if all_over_pct else "",
                "on_track": "曲線どおり", "unknown": "?"}.get(all_curve_state, "?"),
               hours_left / 24,
               ("（このペースだと%.0f時間で天井）" % proj["hoursToCeiling_recentPace"]) if proj.get("hoursToCeiling_recentPace") else "",
               ("%s%%・残%.1fh%s" % (session5h["pct"], session5h["hoursLeft"],
                                      "・もったいない（%.0f%%余る見込み→本数増やす）" % session5h["wasteRiskPct"] if session5h["mottainai"] else "")
                ) if session5h else "未計測（session5h_anchor.py未設定）"))}
    save(OUT, out)
    if "--quiet" not in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(0)
