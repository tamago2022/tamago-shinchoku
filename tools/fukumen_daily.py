#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1029番【覆面調査員の潜伏】毎日ひとりでに1周させる係。

■ たまごさんの言葉（そのまま）
  「潜伏してひたすら触ってくれる人がいれば、どこを直してどうすればもっと体験が良くなるか
    分かるんじゃないの？」「いつも俺に実機テストさせるじゃん。テストも大変なんだから。」

■ この工場の決まりに合わせた作り
  ・**新しいlaunchd常駐・新しい定期タスクは増やさない。**既存の5分便
    （tools/machine_status_push.sh）に1行だけ相乗りする。
  ・中で**1日1回**ゲートする。5分おきに呼ばれても外へ出るのは1日1回。
  ・★ゲートを使い切るのは「最後まで走り切った時だけ」。
    Macが混んでいて見送った回でゲートを消費すると、**動いているのに一度も測れない**
    状態になる（931番のChrome掃除機が1時間ゲートで実質掃けていなかったのと同じ穴）。
  ・報告に出すのは「前回より悪くなった項目」だけ。良いままのものは黙っている。

■ 手で今すぐ回したいとき
  touch status/.fukumen_force && python3 tools/fukumen_daily.py
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

OUTDIR = os.path.join(ROOT, "status", "fukumen")
STAMP = os.path.join(ROOT, "status", ".fukumen_last")
FORCE = os.path.join(ROOT, "status", ".fukumen_force")
LOCK = os.path.join(OUTDIR, ".daily.lock")
LOG = os.path.join(OUTDIR, "daily.log")
HIST = os.path.join(OUTDIR, "history.jsonl")
OUTBOX = os.path.join(ROOT, "status", "dispatch_outbox.jsonl")
PUBURL = "https://tamago2022.github.io/tamago-shinchoku/share/check/1029-fukumen.html"

RUN_TIMEOUT = 45 * 60          # 1周の上限（これを超えたら打ち切って次の日に回す）
LOAD_LIMIT = 40.0              # このMacがこれより混んでいる間は見送る（ゲートは消費しない）
START_HOUR = 5                 # 毎日5時以降の最初の便で走る
LOCK_STALE = 60 * 60


def say(msg):
    line = "%s %s" % (time.strftime("%F %T"), msg)
    try:
        os.makedirs(OUTDIR, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def already_today():
    try:
        with open(STAMP) as f:
            return f.read().strip() == time.strftime("%Y-%m-%d")
    except Exception:
        return False


def take_lock():
    try:
        os.makedirs(OUTDIR, exist_ok=True)
        if os.path.exists(LOCK) and (time.time() - os.path.getmtime(LOCK)) < LOCK_STALE:
            return False
        with open(LOCK, "w") as f:
            f.write("%d %s\n" % (os.getpid(), time.strftime("%F %T")))
        return True
    except Exception:
        return False


def drop_lock():
    try:
        os.unlink(LOCK)
    except Exception:
        pass


def notify_worse(worse, cur, prev_day):
    """悪くなった項目だけを、既存の完了報告の口（dispatch_outbox.jsonl）へ1行出す。
    新しい通知の仕組みは作らない（増やすと誰も見ない口が増える）。"""
    if not worse:
        return
    body = "／".join("%s %s→%s" % (k, prev_day.get(k, "—"), cur.get(k)) for k in worse)
    row = {"ts": time.strftime("%F %T"),
           "n": "%s-fukumen" % time.strftime("%Y%m%d"),
           "type": "fukumen_worse",
           "title": "覆面調査員：前回より悪くなった項目 %d件" % len(worse),
           "message": "🕵️ 覆面調査員（昨日と比べて悪化）：%s\n%s" % (body, PUBURL),
           "urls": [PUBURL]}
    try:
        with open(OUTBOX, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    forced = os.path.exists(FORCE)
    if not forced:
        if already_today():
            return 0
        if time.localtime().tm_hour < START_HOUR:
            return 0
        try:
            if os.getloadavg()[0] > LOAD_LIMIT:
                # ★ここでゲートを消費しない。混み具合が下がった次の便で走る。
                return 0
        except Exception:
            pass
    if not take_lock():
        return 0
    try:
        say("覆面調査員 出発（forced=%s）" % forced)
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "fukumen.py"),
                                "--settle", "6000"],
                               cwd=ROOT, capture_output=True, text=True, timeout=RUN_TIMEOUT)
            say("fukumen.py rc=%d %s" % (p.returncode, (p.stdout or "")[-400:].replace("\n", " / ")))
            if p.returncode != 0:
                say("stderr: " + (p.stderr or "")[-400:])
                return 1
        except subprocess.TimeoutExpired:
            say("時間切れ（%d分）。今日はここまで。ゲートは使わない。" % (RUN_TIMEOUT // 60))
            return 1

        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "fukumen_report.py")],
                           cwd=ROOT, capture_output=True, text=True, timeout=300)
        say("fukumen_report.py rc=%d %s" % (r.returncode, (r.stdout or "").strip()[-200:]))
        if r.returncode != 0:
            say("stderr: " + (r.stderr or "")[-300:])
            return 1

        import fukumen_report as fr
        res = fr.load(None)
        prev_day, prev = fr.load_prev(res.get("日付"))
        cur, pm = fr.metrics(res), (fr.metrics(prev) if prev else {})
        worse = []
        for k, v in cur.items():
            if k in pm:
                try:
                    if float(v) > float(pm[k]) * 1.05:
                        worse.append(k)
                except Exception:
                    pass
        try:
            with open(HIST, "a") as f:
                f.write(json.dumps({"日付": res.get("日付"), "数字": cur,
                                    "悪化": worse, "分": round((time.time() - t0) / 60.0, 1)},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
        notify_worse(worse, cur, pm)
        with open(STAMP, "w") as f:
            f.write(time.strftime("%Y-%m-%d"))
        if forced:
            try:
                os.unlink(FORCE)
            except Exception:
                pass
        say("帰着 %.1f分 ／ 悪化 %d件 ／ %s" % ((time.time() - t0) / 60.0, len(worse), PUBURL))
        return 0
    finally:
        drop_lock()


if __name__ == "__main__":
    sys.exit(main())
