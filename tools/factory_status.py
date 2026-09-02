#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
止まらない工場 / 状態1枚（2026-09-02）

やること（測るだけ。負荷をかける実験はしない・プロセスを止めない）:
  1. /Users/mac/Desktop/machine_load.sh（土台・作り直さない）で負荷1行を取る
  2. 既存の生存確認 tamago_kanshi.py を輸入し、生きている Claude Code セッションを列挙
  3. 各セッションの会話ログ末尾から「作業中／質問して停止／承認待ちで固まり／終わって待機」を判定
  4. 負荷（ロード・メモリ圧・スワップ・ディスク・I/O）から「いま何本まで安全か」= safeMax を出す
  5. 全部を status/machine.json に書く（PWAが読む。既存キーはそのまま残す）

使い方:
  python3 factory_status.py            # JSONを標準出力に出すだけ
  python3 factory_status.py --write    # status/machine.json に書く（machine_status_push.sh から呼ばれる）
  python3 factory_status.py --table    # 人が読む表（止まっているセッション一覧）

上限の考え方（全部この1か所。変えるならここだけ）:
  HARD_MAX      : 何があっても超えない本数。今日14本で2回固まった実績から 8（コア数と同じ）
  LOAD_PER_SESS : 走行中セッション1本あたりのロード見込み（仮定値 0.8。今日の実測: 5本で4.6, 14本で11）
  LOAD_CEIL     : ロード÷コア数 の上限 0.8（machine_load.sh と同じ）
  MEM_PER_SESS  : 1本あたりメモリ 350MB（実測平均341MB）
  DISK_STOP_GB  : 空きがこれ未満なら新規0本（5GB＝machine_load.sh と同じ）
  DISK_WARN_GB  : 空きがこれ未満なら「増やさない」（20GB）
  STALL_MIN     : この分数動きが無ければ「止まり」判定（10分。既存 kanshi の STUCK_MIN と同じ）
  SAFE_FLOOR    : 憲法「常時2本」。ロードが高くても、メモリ赤・ディスク5GB未満でない限り上限は2本を下回らない
                  （下回ると見回り係が永久に着火できず「工場が止まる」逆の事故になる）
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "machine.json")
LOADSH = "/Users/mac/Desktop/machine_load.sh"
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
KANSHI = os.path.join(VAULT, ".claude", "hooks", "tamago_kanshi.py")

HARD_MAX = int(os.environ.get("FACTORY_HARD_MAX", "8"))
LOAD_PER_SESS = 0.8
LOAD_CEIL = 0.8
MEM_PER_SESS_MB = 350
DISK_STOP_GB = 5
DISK_WARN_GB = 20
STALL_MIN = 10
SAFE_FLOOR = 2
PAGE = 4096

# 「質問して止まっている」の目印。末尾200字にこれがあれば asked 判定
ASK_PAT = re.compile(r"(続けますか|しますか|でしょうか|ますか[？?]|いかがです|どうしますか|確認してください|"
                     r"教えて(ください|くれれば)|一言(もらえ|ください)|GOなら|判断待ち[：:]\s*(?!なし)|"
                     r"押してください|選んでください|\?\s*$|？\s*$)")


def run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def load_kanshi():
    try:
        spec = importlib.util.spec_from_file_location("tamago_kanshi", KANSHI)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ---------- 負荷（土台は machine_load.sh） ----------
def base_line():
    line = run(["bash", LOADSH], timeout=30).strip()
    num = lambda key, unit: (re.search(key + r" ([0-9.]+)" + unit, line) or [None, None])[1]
    def f(x):
        try:
            return float(x)
        except Exception:
            return None
    d = {
        "raw": line,
        "load": f(num("負荷", "%")), "cpu": f(num("CPU", "%")), "mem": f(num("メモリ圧迫", "%")),
        "swapGB": f(num("スワップ", "GB")), "diskFreeGB": f(num("ディスク空き", "GB")),
        "sessions": f(num("稼働", "本")),
        "note": line.split("｜")[-1].strip() if line else "",
    }
    for k in ("load", "cpu", "mem", "sessions"):
        if d[k] is not None:
            d[k] = int(d[k])
    return d


def load_avg():
    m = re.search(r"\{ ([0-9.]+) ([0-9.]+) ([0-9.]+) \}", run(["sysctl", "-n", "vm.loadavg"]))
    return [float(x) for x in m.groups()] if m else [None, None, None]


def ncpu():
    try:
        return int(run(["sysctl", "-n", "hw.ncpu"]).strip())
    except Exception:
        return 8


def mem_pressure():
    """アクティビティモニタと同じ判定源（mem_stats.py と同じ）。1=green 2=yellow 他=red"""
    try:
        v = int(run(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"]).strip())
    except Exception:
        return "unknown"
    return {1: "green", 2: "yellow"}.get(v, "red")


def mem_avail_mb():
    """新規セッションに回せるメモリの目安。free+speculative+purgeable は全部、inactive は半分だけ数える（保守的）"""
    d = {}
    for ln in run(["vm_stat"]).splitlines():
        m = re.match(r"Pages ([a-z ]+):\s+(\d+)\.", ln.strip())
        if m:
            d[m.group(1).strip()] = int(m.group(2))
    mb = lambda k: d.get(k, 0) * PAGE / 1048576.0
    return mb("free") + mb("speculative") + mb("purgeable") + 0.5 * mb("inactive")


def swap_trend():
    """スワップが増えているか（1秒空けて2回読む）"""
    def used():
        m = re.search(r"used = ([0-9.]+)M", run(["sysctl", "-n", "vm.swapusage"]))
        return float(m.group(1)) if m else None
    a = used(); time.sleep(1); b = used()
    if a is None or b is None:
        return None, None
    return b, b > a


def io_mbs():
    """ディスクI/O MB/s（iostat 1秒×2回の2回目）。Googleドライブ転送などの渋滞検知用"""
    out = run(["iostat", "-d", "-w", "1", "-c", "2"], timeout=6).strip().splitlines()
    if len(out) < 2:
        return None
    nums = out[-1].split()
    try:
        # 列は KB/t tps MB/s がディスク数分並ぶ。MB/s（3列目ごと）を合計
        return round(sum(float(nums[i]) for i in range(2, len(nums), 3)), 2)
    except Exception:
        return None


# ---------- セッション状態 ----------
def tail_text(path, chunk=200000):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - chunk))
            return f.read().decode("utf-8", errors="ignore").splitlines()
    except Exception:
        return []


def classify(transcript, idle):
    """会話ログ末尾から状態を判定。
    working    : 動いている（idle < STALL_MIN）
    stuck_tool : 最後がtool_useのまま結果が来ない（承認ダイアログ前で固まり）
    asked      : 最後の文章が質問で終わっている（「続けますか」で止まり）
    idle_done  : 話し終えて待機（畳み候補）
    unknown    : 会話ログが特定できない
    """
    if idle is None or transcript is None:
        return "unknown", ""
    if idle < STALL_MIN:
        return "working", ""
    last = None
    for ln in reversed(tail_text(transcript)):
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if e.get("type") in ("assistant", "user"):
            last = e
            break
    if not last:
        return "unknown", ""
    msg = last.get("message") or {}
    content = msg.get("content")
    if last["type"] == "assistant" and isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_use" for c in content):
            return "stuck_tool", ""
        text = "".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
        tail = text[-200:].replace("\n", " ")
        if ASK_PAT.search(tail):
            return "asked", tail[-80:]
        return "idle_done", tail[-80:]
    if last["type"] == "user":
        # 最後がユーザー/ツール結果で止まっている＝返答を書く前に落ちた可能性
        return "stuck_tool", ""
    return "idle_done", ""


def sessions():
    k = load_kanshi()
    if not k:
        return []
    try:
        ss = k.enrich(k.idle_min(k.sessions()))
    except Exception:
        return []
    out = []
    for s in ss:
        kind, tail = classify(s.get("transcript"), s.get("idle"))
        out.append({
            "pid": int(s["pid"]),
            "title": s.get("title") or "（不明）",
            "dispatch": bool(s.get("dispatch")),
            "mb": int(s.get("mb") or 0),
            "idleMin": round(s["idle"], 1) if s.get("idle") is not None else None,
            "kind": kind,
            "tail": tail,
        })
    out.sort(key=lambda x: -(x["idleMin"] or 0))
    return out


KIND_LABEL = {
    "working": "🟢作業中", "asked": "🟡質問して停止", "stuck_tool": "🔴承認待ち/固まり",
    "idle_done": "⚪終わって待機", "unknown": "（不明）",
}


# ---------- 安全上限 ----------
def safe_max(base, ss, la1, cores, pressure, avail_mb, swap_up, iomb):
    alive = len(ss)
    working = sum(1 for s in ss if s["kind"] == "working")
    reasons = []
    disk = base.get("diskFreeGB")

    # ロードから：あと何本足せるか（走行中1本≒LOAD_PER_SESS）
    more_load = None
    if la1 is not None:
        more_load = int((cores * LOAD_CEIL - la1) / LOAD_PER_SESS)
        if more_load < 0:
            reasons.append("5分平均ロード%.1f（コア%d×%.1f超）" % (la1, cores, LOAD_CEIL))
    # メモリから
    more_mem = None
    if pressure == "red":
        more_mem = 0; reasons.append("メモリ圧=赤")
    elif pressure == "yellow":
        more_mem = 0; reasons.append("メモリ圧=黄")
    else:
        more_mem = int(avail_mb / MEM_PER_SESS_MB)
    if swap_up:
        more_mem = min(more_mem, 0); reasons.append("スワップ増加中")
    # ディスク
    if disk is not None:
        if disk < DISK_STOP_GB:
            reasons.append("ディスク空き%dGB未満" % DISK_STOP_GB)
            return 0, reasons, alive, working
        if disk < DISK_WARN_GB:
            reasons.append("ディスク空き%dGB未満（増やさない）" % DISK_WARN_GB)
            more_load = min(more_load or 0, 0); more_mem = min(more_mem or 0, 0)

    mores = [x for x in (more_load, more_mem) if x is not None]
    more = min(mores) if mores else 0
    more = max(more, -alive)
    sm = min(HARD_MAX, alive + more)
    if sm < SAFE_FLOOR and pressure != "red":
        sm = SAFE_FLOOR  # 常時2本は守る（赤・ディスク切れ以外）
    if sm == HARD_MAX and alive + more > HARD_MAX:
        reasons.append("上限%d本（固定）" % HARD_MAX)
    return max(sm, 0), reasons, alive, working


def build():
    base = base_line()
    la = load_avg(); cores = ncpu()
    pressure = mem_pressure(); avail = mem_avail_mb()
    swap_gb, swap_up = swap_trend()
    iomb = io_mbs()
    ss = sessions()
    # 上限は5分平均ロード（la[1]）で決める。1分平均は瞬間的に跳ねて上限が0↔6と暴れるため。1分平均はJSONに load1 として残す
    sm, reasons, alive, working = safe_max(base, ss, la[1] if la[1] is not None else la[0], cores, pressure, avail, swap_up, iomb)
    stalled = [s for s in ss if s["kind"] in ("asked", "stuck_tool")]
    waiting = [s for s in ss if s["kind"] == "idle_done"]
    more_ok = max(0, sm - alive)

    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    now = now[:-2] + ":" + now[-2:]
    parts = ["負荷 %s%%" % (base["load"] if base["load"] is not None else "測定不可")]
    parts.append("セッション%d本（作業中%d・止まり%d）" % (alive, working, len(stalled)))
    if sm < alive:
        parts.append("上限%d本・%d本超過（畳め）" % (sm, alive - sm))
    elif more_ok > 0:
        parts.append("上限%d本・あと%d本OK" % (sm, more_ok))
    else:
        parts.append("上限%d本・増やすな" % sm)
    parts.append("空き%sGB" % (base["diskFreeGB"] if base["diskFreeGB"] is not None else "測定不可"))
    line = " ｜ ".join(parts)

    d = dict(base)
    d.update({
        "measuredAt": now,
        "sessions": alive if ss else base.get("sessions"),
        "working": working,
        "stalled": len(stalled),
        "waiting": len(waiting),
        "safeMax": sm,
        "moreOK": more_ok,
        "hardMax": HARD_MAX,
        "blockReason": "、".join(reasons),
        "load1": la[0], "load5": la[1], "load15": la[2], "cores": cores,
        "loadRatio": round(la[0] / cores, 2) if la[0] is not None else None,
        "memPressure": pressure, "memAvailGB": round(avail / 1024.0, 1),
        "swapGB": swap_gb if swap_gb is not None else base.get("swapGB"),
        "swapIncreasing": swap_up,
        "ioMBs": iomb,
        "stalledList": [{k: s[k] for k in ("pid", "title", "kind", "idleMin", "dispatch")} for s in stalled],
        "sessionList": [{k: s[k] for k in ("pid", "title", "kind", "idleMin", "mb", "dispatch")} for s in ss],
        "line": line,
    })
    d["note"] = "上限%d本・あと%d本OK" % (sm, more_ok) + ("（%s）" % d["blockReason"] if reasons else "")
    return d


def table(d):
    print(d["line"])
    if d["blockReason"]:
        print("理由: " + d["blockReason"])
    print("ロード %s/%dコア（比%.2f）・メモリ圧=%s・空きメモリ目安%sGB・I/O %sMB/s" % (
        d["load1"], d["cores"], d["loadRatio"] or 0, d["memPressure"], d["memAvailGB"], d["ioMBs"]))
    print()
    print("| PID | 状態 | 動きなし | タイトル | 発生元 | メモリ |")
    print("|---|---|---|---|---|---|")
    for s in d["sessionList"]:
        print("| %d | %s | %s分 | %s | %s | %dMB |" % (
            s["pid"], KIND_LABEL.get(s["kind"], s["kind"]),
            "%.0f" % s["idleMin"] if s["idleMin"] is not None else "?",
            s["title"], "Dispatch" if s["dispatch"] else "直接", s["mb"]))


def main():
    d = build()
    if "--table" in sys.argv:
        table(d)
        return 0
    js = json.dumps(d, ensure_ascii=False)
    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(js)
        os.replace(tmp, OUT)
        print(d["line"])
    else:
        print(js)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 測れなくても止まらない
        print(json.dumps({"error": str(e), "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}))
        sys.exit(0)
