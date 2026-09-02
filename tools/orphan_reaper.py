#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孤児プロセス回収（orphan reaper） 2026-09-03

背景: Claude Codeセッションが `bun run lint` 等の検証コマンドを走らせた後、
セッション終了時にkillされず親(ppid)がlaunchd(pid1)に付け替わった「孤児」のまま
CPUを食い続けるケースが実際に発生した（eslintが5.5時間・87%CPUでロード100%の主因になった）。
これを毎回人手で見つけるのではなく、5分おきの見張り番サイクルで機械的に検知して止める。

対象（安全にkillしてよい一過性コマンドだけ。開発サーバーは対象外）:
  eslint / tsc（--watchでない）/ jest / vitest（--watchでない）/ playwright test /
  webpack / rollup / bun run lint|build|test / npm run lint|build|test / next build

条件（すべて満たす時だけkill）:
  - ppid == 1（launchdの子＝孤児化した証拠。生きているセッションの子ならppidは別）
  - 経過時間 >= ORPHAN_MIN 分（通常のlint/buildは数分で終わる。誤検知を避けるため長めに取る）
  - %CPU >= CPU_MIN（0%近辺の待機プロセス＝esbuildのpingサービス等は対象外）
  - コマンドが上記ホワイトリストに一致し、かつ dev/serve/watch を含まない

実行: 5分おきの machine_status_push.sh から session_watchdog.py の直後に呼ばれる。
記録: 見張り番ログ.md に1行、status/reaper-state.json に累計。
使い方:
  python3 orphan_reaper.py            # 判定＋実行
  python3 orphan_reaper.py --dry-run  # 判定だけ
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATE_JSON = os.path.join(REPO, "status", "reaper-state.json")
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
LOG_MD = os.path.join(VAULT, "AI出力", "_ルール", "見張り番ログ.md")

ORPHAN_MIN = 20
CPU_MIN = 3.0
MAX_KILL_PER_RUN = 3

WHITELIST = re.compile(
    r"(\beslint\b|\btsc\b|\bjest\b|\bvitest\b|playwright test|\bwebpack\b|\brollup\b|"
    r"bun run (lint|build|test)|npm run (lint|build|test)|next build|verify-project\.sh)"
)
EXCLUDE = re.compile(r"(--watch|\bdev\b|\bserve\b|--service|vite$|vite dev)")


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def append(path, line):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def etime_to_min(etime):
    # 形式: [[DD-]HH:]MM:SS
    parts = etime.strip().split("-")
    days = int(parts[0]) if len(parts) == 2 else 0
    rest = parts[-1].split(":")
    if len(rest) == 3:
        h, m, s = rest
    elif len(rest) == 2:
        h, m, s = "0", rest[0], rest[1]
    else:
        return 0.0
    return days * 1440 + int(h) * 60 + int(m) + int(s) / 60.0


def candidates():
    out = subprocess.run(["ps", "-Ao", "pid,ppid,etime,pcpu,command"], capture_output=True, text=True, timeout=15).stdout
    found = []
    for ln in out.splitlines()[1:]:
        parts = ln.strip().split(None, 4)
        if len(parts) < 5:
            continue
        pid, ppid, etime, pcpu, cmd = parts
        if ppid != "1":
            continue
        if not WHITELIST.search(cmd) or EXCLUDE.search(cmd):
            continue
        try:
            mins = etime_to_min(etime)
            cpu = float(pcpu)
        except Exception:
            continue
        if mins >= ORPHAN_MIN and cpu >= CPU_MIN:
            found.append({"pid": int(pid), "etimeMin": round(mins, 1), "cpu": cpu, "cmd": cmd[:160]})
    found.sort(key=lambda x: -x["etimeMin"])
    return found


def main():
    dry = "--dry-run" in sys.argv
    state = load_json(STATE_JSON, {"_totals": {"killed": 0}})
    totals = state.setdefault("_totals", {"killed": 0})
    found = candidates()
    killed = []
    for c in found[:MAX_KILL_PER_RUN]:
        if dry:
            killed.append({**c, "dry": True})
            continue
        try:
            os.kill(c["pid"], 15)
            killed.append(c)
            totals["killed"] += 1
            append(LOG_MD, "- %s 🧹 孤児プロセス回収: pid %d（%.0f分・CPU%.0f%%）%s" % (now(), c["pid"], c["etimeMin"], c["cpu"], c["cmd"]))
        except Exception as e:
            append(LOG_MD, "- %s ❌ 孤児回収失敗 pid %d: %s" % (now(), c["pid"], e))
    if not dry:
        state["_lastRun"] = now()
        state["_lastFound"] = found
        save_json(STATE_JSON, state)
    print(json.dumps({"found": found, "killed": killed}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        append(LOG_MD, "- %s ❌ 孤児回収エラー: %s" % (now(), e))
        print(json.dumps({"error": str(e)}))
        sys.exit(0)
