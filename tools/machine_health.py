#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macの健康診断と、安全な残骸だけの回収。2026-09-18（Cowork側から設置）

なぜ作ったか（実測）:
  2026-09-18 07:26 の status/machine.json が 負荷5046% / スワップ17.06GB。
  そのまま1時間半、machine.json が更新されていなかった（心臓は07:15で停止、
  5分便は1回30分以上かかる状態）。つまり「重い」という数字はあるのに、
  **何がどれだけ食っているのかを持っている場所がどこにも無かった。**
  status/heavy_events.jsonl は上位3本の名前しか残さない（topCpu欄）。

  Cowork/Dispatchのサンドボックスは別のLinuxなので、Macのps/topには届かない。
  そこで「Mac側で走っている仕組み（launchdの5分便）」に1行だけ相乗りして、
  実測をリポジトリの中（status/machine_health.json）へ落とす。

既存のものを作り直さない:
  - 全体の1行サマリ      … tools/machine_load.sh（そのまま呼ぶ）
  - lint/build系の孤児   … tools/orphan_reaper.py（守備範囲が違うので触らない）
  ここが受け持つのは「プロセス単位の実測」と「工場が自分で撒いた残骸の回収」だけ。

使い方:
  python3 machine_health.py                 # 計測だけ（status/machine_health.json）
  python3 machine_health.py --reap          # 計測＋安全な残骸の回収
  python3 machine_health.py --reap --dry-run  # 回収の判定だけ（落とさない）
"""
import json
import io
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
OUT_JSON = os.path.join(STATUS, "machine_health.json")
OUT_JSONL = os.path.join(STATUS, "machine_health.jsonl")
REAP_LOG = os.path.join(STATUS, "machine_health_reap.log")

TOP_N = 15

# ---------------------------------------------------------------- 回収の規則
# 「工場が自分で起動したもの」「一過性のはずなのに終わっていないもの」だけ。
# たまごさんが使っているアプリ（Brave・エディタ・Obsidian・Eagle）と、
# システム（WindowServer・kernel）と、Cowork本体の仮想マシンには一切触らない。

# 絶対に触らないもの（コマンド行のどこかに一致したら即除外）
#   たまごさんが使っているアプリ・システム・Cowork本体・本当に長く回る生成系。
NEVER = re.compile(
    r"(Brave|Obsidian|Eagle|WindowServer|loginwindow|/sbin/launchd|kernel_task|"
    r"com\.apple\.Virtualization|Finder\.app|Dock\.app|SystemUIServer|"
    r"Claude\.app|Claude Helper|Antigravity|Code Helper|Visual Studio Code|"
    r"tools/relay_server\.py|tools/heartbeat\.sh|tools/machine_status_push\.sh|"
    # 生成・変換・アップロードは本当に何十分もかかる。作り直せないので触らない。
    r"gen_video|gen_images|gen_narration|line_stamp_pipeline|eagle_|ffmpeg|"
    r"youtube_stats_sync|gumroad_sales_sync|build_podcast_feed)"
)

# 心臓(heartbeat.sh)に相乗りしている工場のpython。
#   どれも「待ちが空ならディレクトリを1回見るだけで即座に戻る」設計なので、
#   15分以上生きている＝詰まっている、と断言できる。ここだけを対象にする
#   （tools/*.py を丸ごと対象にすると、本当に長い生成系を巻き込む）。
SHORT_LIVED_PY = (
    "auto_launcher|command_ingest|auth_watch|relay_watch|worktree_reaper|"
    "check_page_pruner|check_anthropic_reply|check_line_reply|check_line_shinsa|renraku|"
    "daily_ingest_scheduler|genzaichi|top_status|launch_watchdog|kenpin_gate|"
    "chrome_tab_sweeper|git_lock_reaper|gaibu_runner|orphan_reaper|"
    "session_watchdog|factory_status|machine_health"
)

# 回収の候補（すべて「数秒〜数分で終わるはず」のもの）
RULES = [
    # 1. 自動操作用のChrome。たまごさんが自分で開いたChrome/Braveには当たらない。
    ("headless-chrome", re.compile(
        r"(--headless|--remote-debugging-port|--enable-automation|"
        r"Chrome for Testing|--user-data-dir=(/tmp|/var/folders))"), 5),
    # 2. 工場の検品/撮影スクリプト(node/puppeteer)。数十秒で終わる設計。
    ("factory-node", re.compile(r"tamago-shinchoku/tools/[^ ]+\.mjs"), 15),
    # 3. 心臓に相乗りしている工場のpython（上のSHORT_LIVED_PYだけ）。
    ("factory-python", re.compile(
        r"tamago-shinchoku/tools/(%s)[^ ]*\.py" % SHORT_LIVED_PY), 15),
    # 4. 中継所のトンネルの残骸。
    ("tunnel-junk", re.compile(r"(localtunnel|cloudflared.*localhost:8788)"), 30),
    # 5. puppeteer が置いていった Chromium。
    ("puppeteer-chromium", re.compile(r"(puppeteer|\.cache/puppeteer).*(Chromium|chrome)"), 10),
]


def sh(cmd, timeout=20):
    """外部コマンドを叩いて標準出力を返す。失敗しても落ちない。"""
    try:
        p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                           text=True, timeout=timeout)
        return (p.stdout or "").strip()
    except Exception:
        return ""


def etime_to_sec(s):
    """psのetime（[[dd-]hh:]mm:ss）を秒にする。"""
    s = (s or "").strip()
    try:
        days = 0
        if "-" in s:
            d, s = s.split("-", 1)
            days = int(d)
        parts = [int(x) for x in s.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, sec = parts[-3], parts[-2], parts[-1]
        return days * 86400 + h * 3600 + m * 60 + sec
    except Exception:
        return 0


def snapshot_processes():
    """ps から全プロセスを取る。高負荷でも ps は速い（machine_load.sh の実測より）。"""
    raw = sh(["ps", "-Ao", "pid=,ppid=,pcpu=,pmem=,rss=,etime=,user=,command="], timeout=30)
    procs = []
    for line in raw.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        pid, ppid, pcpu, pmem, rss, etime, user, cmd = parts
        try:
            procs.append({
                "pid": int(pid), "ppid": int(ppid),
                "cpu": float(pcpu), "mem": float(pmem),
                "rssMB": round(int(rss) / 1024.0, 1),
                "sec": etime_to_sec(etime), "user": user,
                "cmd": cmd[:300],
            })
        except Exception:
            continue
    return procs


def vitals():
    """sysctl だけ。高負荷でもミリ秒で返る。"""
    cores = int(sh(["sysctl", "-n", "hw.ncpu"], timeout=5) or 8)
    loadavg = sh(["sysctl", "-n", "vm.loadavg"], timeout=5)   # { 5.12 4.98 4.70 }
    try:
        l1 = float(loadavg.split()[1])
    except Exception:
        l1 = 0.0
    swap_raw = sh(["sysctl", "vm.swapusage"], timeout=5)
    m = re.search(r"used\s*=\s*([0-9.]+)M", swap_raw)
    swap_gb = round(float(m.group(1)) / 1024.0, 2) if m else 0.0
    return {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cores": cores, "loadavg": loadavg, "load1": l1,
        "loadPct": int((l1 / cores) * 100) if cores else 0,
        "swapGB": swap_gb,
    }


def measure():
    """★速い順に並べ、途中で殺されても「取れたところまで」が残るようにする。
    2026-09-18 実測の教訓：最初の版は machine_load.sh(ps -A + memory_pressure) と
    top -l 1 を先に回してから書いていたため、呼び出し側の90秒タイムアウトに
    先に殺されてファイルが1度も生まれなかった（heavy_events は同じ巡回で
    書かれているのに machine_health.json だけ出来ない、という形で露見した）。
    重い計測（top / machine_load.sh）は最後に回し、取れたら足すだけにする。"""
    data = vitals()
    procs = snapshot_processes()          # ps は高負荷でも速い
    by_cpu = sorted(procs, key=lambda x: -x["cpu"])[:TOP_N]
    by_mem = sorted(procs, key=lambda x: -x["rssMB"])[:TOP_N]
    data["procCount"] = len(procs)
    data["topCpu"] = [{k: p[k] for k in ("pid", "ppid", "cpu", "rssMB", "sec", "cmd")} for p in by_cpu]
    data["topMem"] = [{k: p[k] for k in ("pid", "ppid", "mem", "rssMB", "sec", "cmd")} for p in by_mem]
    return data, procs


def slow_extras(data):
    """取れたら足すだけ。取れなくても何も壊さない。"""
    data["vm_stat"] = sh(["vm_stat"], timeout=10)[:2000]
    data["oneline"] = sh([os.path.join(HERE, "machine_load.sh")], timeout=25)
    # top -l 1 は高負荷時に十数秒〜（machine_load.sh のコメント参照）。ヘッダだけ・最後。
    data["top"] = sh("top -l 1 -n 0 2>/dev/null | head -12", timeout=20)
    return data


def pick_targets(procs):
    """落としてよいものだけを選ぶ。判断材料も一緒に返す（あとで読めるように）。"""
    me = os.getpid()
    targets = []
    for p in procs:
        cmd = p["cmd"]
        if p["pid"] in (me, 0, 1) or p["user"] == "root":
            continue
        if NEVER.search(cmd):
            continue
        for name, pat, min_min in RULES:
            if not pat.search(cmd):
                continue
            if p["sec"] < min_min * 60:
                continue
            targets.append(dict(p, rule=name, ageMin=int(p["sec"] / 60)))
            break
    # 念のため一度に落としすぎない
    targets.sort(key=lambda x: -(x["cpu"] + x["rssMB"] / 100.0))
    return targets[:12]


def reap(procs, dry_run=False):
    targets = pick_targets(procs)
    killed = []
    for t in targets:
        if dry_run:
            killed.append(dict(t, killed=False))
            continue
        try:
            os.kill(t["pid"], 15)          # まず行儀よく
            time.sleep(0.3)
            try:
                os.kill(t["pid"], 0)
                os.kill(t["pid"], 9)       # 残っていたら強制
            except OSError:
                pass
            killed.append(dict(t, killed=True))
        except Exception as e:
            killed.append(dict(t, killed=False, error=str(e)))
    if killed:
        try:
            with io.open(REAP_LOG, "a", encoding="utf-8") as f:
                for k in killed:
                    f.write("%s %s pid=%s cpu=%.1f rss=%sMB %s分 %s | %s\n" % (
                        time.strftime("%F %T"), "DRY" if dry_run else "KILL",
                        k["pid"], k["cpu"], k["rssMB"], k["ageMin"],
                        k["rule"], k["cmd"][:160]))
        except Exception:
            pass
    return killed


GATE_SECONDS = 120  # 複数の常駐に相乗りしても重ならないための間引き


def main():
    args = sys.argv[1:]
    do_reap = "--reap" in args
    dry = "--dry-run" in args

    # 複数の入口（5分便・心臓・sales-watch…）に同じ1行を置いてあるので、
    # どれか1つでも生きていれば走る。ただし重ならないよう2分で間引く。
    if "--force" not in args:
        try:
            if time.time() - os.path.getmtime(OUT_JSON) < GATE_SECONDS:
                return
        except OSError:
            pass

    os.makedirs(STATUS, exist_ok=True)

    def flush(d):
        """途中で殺されても「そこまで」が必ず残るよう、節目ごとに書き出す。"""
        try:
            tmp = OUT_JSON + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, OUT_JSON)
        except Exception:
            pass

    data, procs = measure()
    flush(data)                      # ★まずここで必ず1回残す

    if do_reap:
        killed = reap(procs, dry_run=dry)
        data["reap"] = {"dryRun": dry, "count": len([k for k in killed if k.get("killed")]),
                        "targets": killed}
        flush(data)
        if killed and not dry:
            time.sleep(2)
            data["after"] = vitals()   # sysctlだけ＝一瞬
            flush(data)

    slow_extras(data)                # 取れたら足す（取れなくても上の結果は残っている）
    flush(data)

    # before/after を後から追えるよう、細い履歴も残す（1行）
    try:
        with io.open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "t": data["measuredAt"], "loadPct": data["loadPct"],
                "load1": data["load1"], "swapGB": data["swapGB"],
                "afterLoadPct": (data.get("after") or {}).get("loadPct"),
                "afterSwapGB": (data.get("after") or {}).get("swapGB"),
                "reaped": (data.get("reap") or {}).get("count", 0),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    print(data.get("oneline") or "計測しました")


if __name__ == "__main__":
    # 呼び出し側は全て `>/dev/null 2>&1 || true` なので、
    # 何かで落ちても誰も気づけない。落ちた事実だけは必ず残す。
    try:
        main()
    except Exception:
        import traceback
        try:
            with io.open(REAP_LOG, "a", encoding="utf-8") as f:
                f.write("%s CRASH\n%s\n" % (time.strftime("%F %T"), traceback.format_exc()))
        except Exception:
            pass
        raise
