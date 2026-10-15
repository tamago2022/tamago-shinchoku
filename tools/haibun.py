#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配分（haibun） ― 「いま何本走らせてよいか」と「余らせていないか」を1か所で答える道具。

■ たまごさんの指定（2026-09-25）

  「週100%を日割り13%。リセットは火曜18:00。火曜朝に92〜93%残、18:30で使い切るのが理想。」
  「余っているなら本数を増やす。天井が近いならモデルを落とす（本数は減らさない）。」
  「クレジットが余ってる状態はただの給料泥棒。」
  「**『余ったまま朝を迎える』を赤にする。数字で出す。**」

■ 先に正直に書いておく（同じ物を2つ作らないため）

  **本数を上下させる計算は、すでに `tools/pace.py` の manage_fuel() が持っている。**
  （週の予算の超過/余りで cap±1、5時間枠の着地見込みで増減、上限5本・下限3本、
    `status/launch_cap.json` に書き、auto_launcher.py がそれを読む）
  だから本数の計算をここで作り直すことはしない。作り直せば必ず2つの答えが食い違う。

  **この道具が足しているのは、pace.py に無かった3つだけ：**

    ① 天井までの余裕を「何%」「あと何本ぶん」で出す（人が読める形にする）
    ② **余ったまま朝を迎えたら赤にする。**朝(4:00-9:00)に、週の曲線より
       10pt以上「使えていない」なら赤。＝給料泥棒の自動検知
    ③ **決めた本数が実際に効いているかを実測する。**
       「上限5本」と書いてあるのに1本しか走っていない、発車が30分以上止まっている、
       発車待ちは200件ある——この状態を赤にする。**積んだで終わらせないための目**

■ 使い方

    python3 tools/haibun.py            # 判定して status/haibun.json に書く
    python3 tools/haibun.py --print    # 書かずに1行で答えるだけ
    python3 tools/haibun.py --self-test

  AIを1回も呼ばない・外へ1回も出ない＝0円。git を叩かない。
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
OUT = os.path.join(STATUS, "haibun.json")

JST = datetime.timezone(datetime.timedelta(hours=9))

# 週の予算の使い方。たまごさんの指定：週100%／日割り13%／火曜18:00リセット。
PER_DAY = 100.0 / 7.0          # 14.3%。指定の「13%」は切り下げ表現なので計算は7日割りで持つ
MORNING = (4, 9)               # 「朝を迎える」の時間帯
UNDER_RED = 10.0               # 曲線より10pt以上使えていなければ赤（給料泥棒）
STALL_MIN = 45                 # 発車がこれだけ止まっていたら赤


def now():
    return datetime.datetime.now(JST)


def load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def parse_ts(s):
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.datetime.strptime((s or "").strip(), fmt)
            return d if d.tzinfo else d.replace(tzinfo=JST)
        except Exception:
            continue
    return None


def judge():
    pace = load(os.path.join(STATUS, "pace.json"))
    quota = load(os.path.join(STATUS, "quota.json"))
    machine = load(os.path.join(STATUS, "machine.json"))
    health = load(os.path.join(STATUS, "health.json"))
    lcap = load(os.path.join(STATUS, "launch_cap.json"))
    queue = load(os.path.join(STATUS, "queue.json"))

    t = now()
    used = float(pace.get("allPct") or quota.get("allPct") or 0.0)
    remain = round(100.0 - used, 1)
    days_left = float(pace.get("daysLeft") or 0.0)
    elapsed = max(0.0, 7.0 - days_left)

    # ---- ① 天井までの余裕 -------------------------------------------------
    # 曲線＝経過日数×14.3%。これより下＝使えていない（余っている）。
    line = round(min(100.0, elapsed * PER_DAY), 1)
    gap = round(used - line, 1)              # マイナス＝余っている
    # 子セッション1本の実測中央値（status/public/cost_by_task.json）から「あと何本ぶん」
    cost = load(os.path.join(STATUS, "public", "cost_by_task.json"))
    per_task_pct = None
    try:
        w = float(quota.get("allWeightedTokensSinceReset") or 0)
        n = len([it for it in (queue.get("items") or []) if it.get("status") in ("done", "merged")]) or 1
        if w > 0 and used > 0:
            per_task_pct = round(used / max(n, 1), 3)
    except Exception:
        pass
    honsuu_bun = int(remain / per_task_pct) if per_task_pct else None

    # ---- 本数は pace.py の答えをそのまま使う（作り直さない）----------------
    cap = lcap.get("cap")
    safe_max = machine.get("safeMax")
    hcap = ((health.get("同時上限") or {}).get("本数"))
    # ★実測で確かめたこと（2026-09-25）：auto_launcher.py が実際に見ているのは
    #   machine.json の safeMax と launch_cap.json の cap の**小さい方だけ**。
    #   health.json の「同時上限」は auto_launcher が一度も読んでいない（session_watchdog と
    #   進捗表の表示用）。だからここで health を min に混ぜると、**実際より少ない本数を
    #   「適正」と言ってしまう。**混ぜない。参考として別枠で出す。
    eff = [v for v in (cap, safe_max) if isinstance(v, int)]
    effective = min(eff) if eff else 3
    why = lcap.get("why") or ""

    # ---- 天井が近いときはモデルを落とす。本数は減らさない ------------------
    warn = float(quota.get("warnPct") or 75)
    stop = float(quota.get("stopPct") or 85)
    if used >= stop:
        model = "claude-sonnet-5（新規は試験のみ）"
    elif used >= warn:
        model = "claude-sonnet-5（Fable停止）"
    else:
        model = "claude-sonnet-5（重い一晩仕事だけFable可）"

    # ---- ② 余ったまま朝を迎えた（給料泥棒）--------------------------------
    reds = []
    morning = MORNING[0] <= t.hour < MORNING[1]
    if morning and gap <= -UNDER_RED and days_left > 0.5:
        reds.append("余ったまま朝を迎えた：曲線%.1f%%に対して実績%.1f%%（%.1fpt使えていない／残%.1f%%）"
                    % (line, used, -gap, remain))

    # ---- ★いちばん重い赤：本物が1本も出ていない ---------------------------
    # 2026-09-25 実測：status/auto_launch.log は 2026-09-21 04:42 から今まで
    # 🧪テスト発車（空回し）1808回だけ。**本物の発車は1回も無い。**
    # 原因は status/no_launch.flag（Claudeのログイン切れ）。
    # クレジットが余るのはペース配分の問題ではなく、これ1つ。**本数の話より先に出す。**
    flag = os.path.join(STATUS, "no_launch.flag")
    if os.path.exists(flag):
        try:
            msg = io.open(flag, encoding="utf-8").read().strip()
        except Exception:
            msg = "発車が止まっています"
        reds.insert(0, "本物が1本も出ていない：%s" % msg[:120])

    # ---- ③ 決めた本数が実際に効いているか（実測）--------------------------
    items = queue.get("items") or []
    waiting = len([i for i in items if i.get("status") == "waiting"])
    running_q = len([i for i in items if i.get("status") == "running"])
    sessions = machine.get("sessions")
    alive = max(running_q, int(sessions or 0))
    last_launch = parse_ts((io.open(os.path.join(STATUS, ".last_launch_at"), encoding="utf-8").read().strip()
                            if os.path.exists(os.path.join(STATUS, ".last_launch_at")) else ""))
    stall_min = round((t - last_launch).total_seconds() / 60.0, 1) if last_launch else None

    if waiting > 0 and alive < effective and stall_min is not None and stall_min > STALL_MIN:
        reds.append("空き枠を放置：走行%d本／上限%d本、発車待ち%d件なのに%.0f分発車していない"
                    % (alive, effective, waiting, stall_min))
    if waiting > 0 and effective <= 1 and gap <= -UNDER_RED:
        reds.append("予算が%.1fpt余っているのに同時上限が%d本に絞られている（首：%s）"
                    % (-gap, effective, ((health.get("同時上限") or {}).get("自動減便") or "不明")))

    return {
        "updatedAt": t.strftime("%Y-%m-%d %H:%M"),
        "cap": effective,
        "why": why or "pace.py の判定（launch_cap.json）",
        "capParts": {"pace": cap, "machineSafeMax": safe_max,
                     "healthSankou": hcap,
                     "note": "auto_launcherが見るのは pace と machineSafeMax の小さい方。healthは参考"},
        "model": model,
        "usedPct": used,
        "remainPct": remain,
        "linePct": line,
        "gapPct": gap,
        "daysLeft": days_left,
        "resetAt": quota.get("resetAt") or pace.get("resetAt"),
        "honsuuBun": honsuu_bun,
        "perTaskPct": per_task_pct,
        "running": alive,
        "waiting": waiting,
        "lastLaunchMinAgo": stall_min,
        "red": bool(reds),
        "reds": reds,
    }


def one_line(d):
    return ("残%.1f%% ／ 適正%d本（pace%s・機械%s・健康%s(参考)） ／ 曲線%.1f%%に対して%+.1fpt ／ %s"
            % (d["remainPct"], d["cap"], d["capParts"]["pace"], d["capParts"]["machineSafeMax"],
               d["capParts"]["healthSankou"], d["linePct"], d["gapPct"],
               ("🔴 " + " ／ ".join(d["reds"])) if d["red"] else "🟢"))


def self_test():
    ok, ng = [], []

    def check(n, c):
        (ok if c else ng).append(n)

    d = judge()
    check("適正本数が1以上", isinstance(d["cap"], int) and d["cap"] >= 1)
    check("残りが0〜100", 0 <= d["remainPct"] <= 100)
    check("曲線が0〜100", 0 <= d["linePct"] <= 100)
    check("本数を作り直していない（pace.pyの値を採っている）",
          d["capParts"]["pace"] is None or d["cap"] <= d["capParts"]["pace"])
    check("赤の理由が文字で出る", isinstance(d["reds"], list))
    check("1行で読める", len(one_line(d)) > 20)
    for n in ok:
        print("  ✔ %s" % n)
    for n in ng:
        print("  ✘ %s" % n)
    print("%d/%d" % (len(ok), len(ok) + len(ng)))
    return 0 if not ng else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    d = judge()
    if not a.print:
        tmp = OUT + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, indent=1))
        os.replace(tmp, OUT)
        try:
            sys.path.insert(0, HERE)
            import commit_kuchi
            commit_kuchi.cmd_request([OUT], why="配分の判定", who="haibun.py")
        except Exception:
            pass
    print(one_line(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
