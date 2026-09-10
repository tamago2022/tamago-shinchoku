#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
716番：メンテナンス・運用保守の常設係（毎日1回・自動）。715番（憲法遵守点検）と同じ枠組み。

たまごさんの言葉（2026-09-10）：「コンピューターが重いのね」「調べて、快適に保つのも
あなたの仕事ね」「その係も作る？メンテナンス・運用保守の係。お願いします」

このスクリプトは、715番(kenpou_check.py)と対になる「Macの健康診断」係。
点検すること（軽さ・空き容量・負荷・常駐便の生死）：
  1. 常駐便の生死：~/Library/LaunchAgents/com.tamago.*.plist を全部読み、
     ProgramArguments が指すスクリプト/実行ファイルが実在するか確認する。
     実在しない（＝参照先のworktreeが掃除された後に取り残されたゾンビ）は、
     launchctl unload してから ~/Library/LaunchAgents/_retired/ へ退避する
     （削除ではなく退避＝壺と金庫は触らない、の精神。いつでも戻せる）。
     【2026-09-10 実例】taste-intake-review(30分おき)・daily-kenpin(毎朝)・
     engineering-research(毎朝)・sns-queue-build(毎朝) の4本が、参照先の
     worktreeが worktree_reaper.py に掃除された後もゾンビとして残り、
     每回コマンド不在(exit 127)で空振りし続けていた。この4本は本スクリプト
     作成時に手動で退避済み。以後はこのスクリプトが日次で自動検出・自動退避する。
  2. ディスク空き：df の空きGBを前回計測（status/maintenance_daily.jsonl）と比較。
     一定以上減っていれば注意フラグを立てる（原因の自動特定はしない＝直せないものとして通知）。
  3. 負荷：os.getloadavg()。閾値を超えていたら、その瞬間のCPU上位プロセスを記録する
     （「Braveが重い」で終わらせず、プロセス名まで残す）。
  4. 主要な掃除係（disk_guardian・worktree_reaper）が動き続けているか：
     ログの最終更新時刻が想定間隔から大きく遅れていないかを見る。

直せるものは黙って直す（1のゾンビ退避）。直せないものだけ status/dispatch_outbox.jsonl へ
1行（n=716固定）。結果は status/maintenance_check.json に保存する
（index.html 側で読み込んで表示する拡張は別途・715番のkenpou_check.jsonと対になる形）。

実行:
  python3 tools/tamago_maintenance.py            # 点検のみ・書き込みなし確認は --dry-run
  python3 tools/tamago_maintenance.py --push     # 書いた後 git add/commit/push まで行う
  python3 tools/tamago_maintenance.py --dry-run  # 何も書かず・何も直さず結果だけ表示
"""
import argparse
import glob
import io
import json
import os
import plistlib
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

STATUS = os.path.join(REPO, "status")
RESULT = os.path.join(STATUS, "maintenance_check.json")
HIST = os.path.join(STATUS, "maintenance_check_log.jsonl")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")

LAUNCH_AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
RETIRED_DIR = os.path.join(LAUNCH_AGENTS_DIR, "_retired")

LOAD_ALERT_THRESHOLD = 20.0  # loadavg1がこれを超えたら「重い」と判定
DISK_DROP_ALERT_GB = 5.0  # 前回計測よりこれ以上減っていたら注意

# 掃除係ごとの「これだけ間が空いたら止まっていると見なす」秒数
WATCHDOGS = {
    "disk_guardian": {
        "log": os.path.join(STATUS, "disk_guardian.log"),
        "max_gap_sec": 3 * 3600,  # 15分おきの設計。3時間空いたら止まっている
    },
}


def now_jst_str():
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _run(args, timeout=20):
    try:
        p = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return 1, "", str(e)


def load_json(p, default):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_jsonl(p):
    rows = []
    if not os.path.exists(p):
        return rows
    with io.open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def append_jsonl(p, row):
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# 1. 常駐便の生死点検（ゾンビlaunchdジョブの検出・退避）
# ---------------------------------------------------------------------------

def _plist_program_path(plist_path):
    """ProgramArguments または Program の実体パス（実行可能ファイル or スクリプト）を返す。
    「/usr/bin/python3 foo.py」のような形は foo.py 側（2番目の引数）を見る。
    「/bin/bash foo.sh」も同様。それ以外（1個しか要素が無い等）は1番目を見る。
    """
    try:
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)
    except Exception:
        return None
    args = data.get("ProgramArguments")
    if args:
        interpreters = {"/bin/bash", "/bin/sh", "/usr/bin/python3", "/usr/local/bin/python3",
                         "/usr/local/bin/node", "/opt/homebrew/bin/node"}
        if len(args) >= 2 and args[0] in interpreters:
            return args[1]
        return args[0]
    prog = data.get("Program")
    if prog:
        return prog
    return None


def check_zombie_launch_agents(dry_run=False):
    """com.tamago.*.plist を全部読み、参照先が実在しないものを検出・退避する。"""
    found = []
    retired = []
    for plist_path in sorted(glob.glob(os.path.join(LAUNCH_AGENTS_DIR, "com.tamago.*.plist"))):
        label = os.path.basename(plist_path)[:-len(".plist")]
        target = _plist_program_path(plist_path)
        if target is None:
            continue
        # システム標準コマンド(/usr/bin/python3等インタプリタ自体)は対象外。
        # ここでは「2番目の引数=スクリプト本体」が取れているケースだけ実在チェックする。
        if not (target.startswith("/") or target.startswith("~")):
            continue
        target_expanded = os.path.expanduser(target)
        exists = os.path.exists(target_expanded)
        found.append({"label": label, "target": target, "exists": exists})
        if not exists:
            # ゾンビ確定：unloadしてから退避する（削除はしない＝いつでも戻せる）
            if not dry_run:
                _run(["/bin/launchctl", "unload", plist_path], timeout=15)
                os.makedirs(RETIRED_DIR, exist_ok=True)
                dest = os.path.join(RETIRED_DIR, os.path.basename(plist_path))
                try:
                    os.replace(plist_path, dest)
                    retired.append({"label": label, "target": target, "retiredTo": dest})
                except Exception as e:
                    retired.append({"label": label, "target": target, "error": str(e)})
            else:
                retired.append({"label": label, "target": target, "dryRun": True})
    return {"checked": len(found), "zombies": retired}


# ---------------------------------------------------------------------------
# 2. ディスク空き
# ---------------------------------------------------------------------------

def disk_free_gb():
    """★正しい測り方：/System/Volumes/Data を見る（disk_guardian.pyの既存実装と同じ。
    os.statvfs("/") はAPFSの読み取り専用システムボリュームを見てしまい実態と大きくズレる）。"""
    try:
        r = subprocess.run(["df", "-k", "/System/Volumes/Data"], capture_output=True, text=True, timeout=10)
        lines = r.stdout.strip().splitlines()
        if len(lines) < 2:
            return None
        cols = lines[1].split()
        avail_kb = int(cols[3])
        return round(avail_kb / 1024.0 / 1024.0, 1)
    except Exception:
        return None


def check_disk(history):
    free_gb = disk_free_gb()
    prev = history[-1] if history else None
    drop = None
    alert = False
    if prev and isinstance(prev.get("diskFreeGB"), (int, float)) and free_gb is not None:
        drop = round(prev["diskFreeGB"] - free_gb, 1)
        if drop >= DISK_DROP_ALERT_GB:
            alert = True
    return {"diskFreeGB": free_gb, "dropFromPrevGB": drop, "alert": alert}


# ---------------------------------------------------------------------------
# 3. 負荷（load）とCPU上位プロセス
# ---------------------------------------------------------------------------

def check_load():
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1 = load5 = load15 = None
    top = []
    if load1 is not None and load1 >= LOAD_ALERT_THRESHOLD:
        rc, out, _ = _run(["ps", "-Ao", "pcpu,comm", "-r"], timeout=10)
        if rc == 0:
            lines = [l.strip() for l in out.splitlines()[1:] if l.strip()]
            for l in lines[:5]:
                parts = l.split(None, 1)
                if len(parts) == 2:
                    top.append({"pcpu": parts[0], "comm": os.path.basename(parts[1])})
    return {
        "load1": round(load1, 1) if load1 is not None else None,
        "load5": round(load5, 1) if load5 is not None else None,
        "alert": bool(load1 and load1 >= LOAD_ALERT_THRESHOLD),
        "topCpu": top,
    }


# ---------------------------------------------------------------------------
# 4. 主要な掃除係が動き続けているか
# ---------------------------------------------------------------------------

def check_watchdogs():
    out = {}
    now = time.time()
    for name, cfg in WATCHDOGS.items():
        log_path = cfg["log"]
        if not os.path.exists(log_path):
            out[name] = {"alive": False, "reason": "ログファイルが無い"}
            continue
        mtime = os.path.getmtime(log_path)
        gap = now - mtime
        alive = gap <= cfg["max_gap_sec"]
        out[name] = {"alive": alive, "lastUpdateAgoMin": round(gap / 60, 1)}
    return out


# ---------------------------------------------------------------------------
# 直せないものだけ dispatch_outbox.jsonl へ1行
# ---------------------------------------------------------------------------

def notify_if_needed(disk_result, load_result, watchdog_result, dry_run=False):
    problems = []
    if disk_result.get("alert"):
        problems.append(
            "ディスク空きが前回より%.1fGB減少(現在%.1fGB)。原因は自動特定不可・手動確認が要る"
            % (disk_result["dropFromPrevGB"], disk_result["diskFreeGB"])
        )
    if load_result.get("alert"):
        top = ", ".join("%s(%s%%)" % (t["comm"], t["pcpu"]) for t in load_result.get("topCpu", []))
        problems.append("負荷高止まり(load1=%s)。CPU上位: %s" % (load_result["load1"], top or "不明"))
    for name, w in watchdog_result.items():
        if not w.get("alive"):
            problems.append("掃除係『%s』が止まっている可能性(%s)" % (name, w.get("reason") or ("最終更新%s分前" % w.get("lastUpdateAgoMin"))))

    if not problems or dry_run:
        return problems

    row = {
        "ts": now_jst_str(),
        "n": 716,
        "title": "メンテナンス係の日次点検",
        "ok": False,
        "elapsedMin": 0,
        "urls": [],
        "result": "【問題】" + " / ".join(problems),
    }
    append_jsonl(OUTBOX, row)
    return problems


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    history = load_jsonl(HIST)

    zombie_result = check_zombie_launch_agents(dry_run=args.dry_run)
    disk_result = check_disk(history)
    load_result = check_load()
    watchdog_result = check_watchdogs()
    problems = notify_if_needed(disk_result, load_result, watchdog_result, dry_run=args.dry_run)

    result = {
        "measuredAt": now_jst_str(),
        "launchAgents": zombie_result,
        "disk": disk_result,
        "load": load_result,
        "watchdogs": watchdog_result,
        "problemsNotified": problems,
    }

    print(json.dumps(result, ensure_ascii=False, indent=1))

    if args.dry_run:
        return 0

    with io.open(RESULT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    append_jsonl(HIST, {"measuredAt": result["measuredAt"], "diskFreeGB": disk_result["diskFreeGB"],
                         "load1": load_result["load1"], "zombiesRetired": len(zombie_result["zombies"])})

    if args.push:
        _push()
    return 0


def _push(paths=("status/maintenance_check.json", "status/maintenance_check_log.jsonl",
                  "status/dispatch_outbox.jsonl"), retries=5, wait_sec=8):
    for attempt in range(1, retries + 1):
        rc, out, err = _run(["git", "add"] + list(paths))
        if rc != 0:
            print("add失敗(試行%d): %s" % (attempt, (out + err).strip()[:300]))
            time.sleep(wait_sec)
            continue
        diff_rc, _, _ = _run(["git", "diff", "--cached", "--quiet"])
        if diff_rc != 0:
            rc, out, err = _run(["git", "commit", "-m",
                                  "maintenance-check: メンテナンス係 自動更新 %s" % time.strftime("%Y-%m-%d %H:%M")])
            if rc != 0:
                print("commit失敗(試行%d): %s" % (attempt, (out + err).strip()[:300]))
                time.sleep(wait_sec)
                continue
        ahead_rc, ahead_out, _ = _run(["git", "rev-list", "--count", "HEAD", "^origin/main"])
        if ahead_rc != 0 or ahead_out.strip() in ("", "0"):
            print("git: pushすべき新規コミットなし")
            return True
        rc, out, err = _run(["git", "push", "origin", "main"], timeout=60)
        if rc == 0:
            print("git push 成功")
            return True
        print("push失敗(試行%d): %s" % (attempt, (out + err).strip()[:300]))
        time.sleep(wait_sec)
    print("push断念（%d回試行）" % retries)
    return False


if __name__ == "__main__":
    sys.exit(main())
