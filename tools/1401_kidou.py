#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1401番【起動係】2026-09-28

心臓（tools/top_status.py → _okosu）から毎周呼ばれる。やることは3つだけ。

① 一発コマンド窓口(oneshot)の詰まりを外す
   実測（2026-09-28 00:1x〜00:2x）：status/oneshot/running/ に .sh が居座ったまま
   10分以上どの票も走らなくなっていた。原因は oneshot_runner.py の
   `subprocess.run(..., capture_output=True, timeout=240)`。
   **孫プロセスがパイプを握ったままだと、timeout で子を殺してもパイプが閉じず、
   communicate() が永遠に返らない。**（Python公式にも記載のある既知の落とし穴）
   すると top_status.py の `_okosu` が「もう走っている」と判断して二度と起こさず、
   窓口そのものが死ぬ。rescue() は runner の中にあるので、runner が固まると動かない。
   → ここは runner の**外側**。10分以上生きている runner を落とし、
     running/ の居残りを pending/ へ戻す。窓口は次の周で自力で再開する。

② Chromeタブ掃除便(launchd)を載せる（冪等。既に入っていれば何もしない）

③ 何をしたかを status/1401_kidou.log に残す（黙って死なない）

AppleScript / osascript / System Events は1行も使っていない。
"""
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
LOG = os.path.join(STATUS, "1401_kidou.log")
ONESHOT = os.path.join(STATUS, "oneshot")
INSTALL_GATE = os.path.join(STATUS, ".1401_install_at")
STUCK_SEC = 600


def say(m):
    try:
        os.makedirs(STATUS, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), m))
        if os.path.getsize(LOG) > 300000:
            lines = open(LOG, encoding="utf-8").read().splitlines()[-500:]
            open(LOG, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    except Exception:
        pass


def _etime_sec(s):
    """ps の etime（[[dd-]hh:]mm:ss）を秒へ。"""
    s = s.strip()
    d = 0
    if "-" in s:
        d, s = s.split("-", 1)
        d = int(d)
    parts = [int(x) for x in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return d * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def fix_oneshot():
    killed = 0
    try:
        r = subprocess.run(["ps", "-axo", "pid=,etime=,command="],
                           capture_output=True, text=True, timeout=15)
        for ln in r.stdout.splitlines():
            if "tools/oneshot_runner.py" not in ln:
                continue
            parts = ln.strip().split(None, 2)
            if len(parts) < 3:
                continue
            pid, et = parts[0], parts[1]
            try:
                if _etime_sec(et) < STUCK_SEC:
                    continue
                os.kill(int(pid), 9)
                killed += 1
            except Exception:
                pass
    except Exception:
        pass

    moved = 0
    run = os.path.join(ONESHOT, "running")
    pend = os.path.join(ONESHOT, "pending")
    if os.path.isdir(run) and os.path.isdir(pend):
        now = time.time()
        for n in sorted(os.listdir(run)):
            if not n.endswith(".sh"):
                continue
            p = os.path.join(run, n)
            try:
                if now - os.path.getmtime(p) < STUCK_SEC:
                    continue
                os.replace(p, os.path.join(pend, n))
                moved += 1
            except Exception:
                pass
    if killed or moved:
        say("oneshot: 固まったrunnerを%d本落とし、居残りの票を%d本 pending へ戻しました" % (killed, moved))
    return killed, moved


def install_launchd():
    try:
        last = os.path.getmtime(INSTALL_GATE)
        if time.time() - last < 600:
            return
    except OSError:
        pass
    try:
        r = subprocess.run(["/bin/bash", os.path.join(HERE, "1401_install.sh")],
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        out = (r.stdout + r.stderr).strip().splitlines()
        if out and not out[-1].startswith("ALREADY"):
            say("launchd: " + out[-1])
        open(INSTALL_GATE, "w").write(time.strftime("%F %T") + "\n")
    except Exception as e:
        say("launchd: 失敗 %s" % e)


HOOK_GATE = os.path.join(STATUS, ".1401_hooks_at")


def install_hooks():
    """1401号の上流の関所（PreToolUse）を ~/.claude と各リポジトリへ配る。
    install_hooks.mjs は足りない分だけ足す作りなので、何回流しても同じ（冪等）。"""
    try:
        if time.time() - os.path.getmtime(HOOK_GATE) < 600:
            return
    except OSError:
        pass
    try:
        r = subprocess.run(
            ["node", os.path.join(HERE, "stop_kanmon", "install_hooks.mjs")],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace")
        out = (r.stdout + r.stderr).strip()
        if "足した: " in out:
            say("hooks: " + " / ".join(
                l.strip() for l in out.splitlines() if "足した: " in l))
        open(HOOK_GATE, "w").write(time.strftime("%F %T") + "\n" + out[-2000:])
    except Exception as e:
        say("hooks: 失敗 %s" % e)


if __name__ == "__main__":
    fix_oneshot()
    install_launchd()
    install_hooks()
