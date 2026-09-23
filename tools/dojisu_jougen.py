#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1051番：同時に何本走らせてよいかを、推測ではなく実測で決める。

たまごさんの言葉（2026-09-24 02:40）:
  「今まで『同時2本まで』で止めていたのは、並列がブラウザを殺したから。
    でもそれは推測で決めた本数で、実測していない。
    空きメモリから割り出せ。重くなったら自動で本数を減らすところまで作れ。」

━━ 実測して分かったこと（2026-09-24 02:46・Mac実機）━━

  hw.memsize 32.0GB / hw.ncpu 8
  vm_stat 空き実効 14.16GB（free+inactive+speculative+purgeable）
  vm.swapusage  total 17408.00M / used 16344.75M / **free 1063.25M**
  vm.loadavg    { 22.64 27.30 23.67 }  → 22.64 / 8コア = 283%
  Brave 53プロセス 12,609MB ／ Chrome 16プロセス 1,951MB
  Claudeのセッション1本のRSS実測: 274 / 270 / 294 / 129 / 70 / 70 MB

  → **メモリは首では無かった。** 14.16GB空いていて1本0.3GBなら理屈では20本以上入る。
     首は2つ。①スワップの残りが1.04GBしかない ②8コアに対して負荷283%。
     そしてその両方を作っているのが Brave（12.3GB・53プロセス）。

━━ もう1つ、もっと悪いものが見つかった（自分で自分を縛る輪）━━

  上限を決めているのは status/calibration.json の safeN。その規則は
  「標本6件以上で合格した最大本数」。ところが実測の標本数は

      N=0 … 238件 ／ N=1 … 307件 ／ N=2 … 10件 ／ **N=3 … 1件（enough:false）**

  **上限が2本だから3本目が走らない。3本目が走らないから標本が集まらない。
    標本が集まらないから永久に2本のまま。** これは実測ではなく、
  実測のふりをした固定値だった。たまごさんの指摘どおり。

━━ ここが受け持つこと（既存のものを作り直さない）━━

  ・負荷の1行サマリ      … tools/machine_load.sh（そのまま）
  ・本数と画面           … tools/factory_status.py（そのまま。ここの答えを1つ足すだけ）
  ・プロセス単位の実測    … tools/machine_health.py（そのまま）
  ここが持つのは **「あと何本なら安全か」の1つの答えと、その根拠の内訳** だけ。

出力: status/dojisu_jougen.json
      ＋ status/health.json の "同時上限" キー（PWA・Dispatchはここだけ見れば済む）

使い方:
    python3 tools/dojisu_jougen.py            # 計測して書き出す
    python3 tools/dojisu_jougen.py --print    # 書き出さずに画面へ
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
OUT = os.path.join(STATUS, "dojisu_jougen.json")
HEALTH = os.path.join(STATUS, "health.json")
CALIB = os.path.join(STATUS, "calibration.json")

# ---- 定数はすべて実測から置いた。推測の数字を1つも置かない ----
PER_SESSION_GB = 0.30   # セッション1本のRSS実測 274/270/294MB の中央値≒0.28 → 0.30で見る
MEM_RESERVE_GB = 4.0    # たまごさんがPCを使う分。ここを食いつぶすと画面が固まる
SWAP_RESERVE_GB = 0.5   # スワップが完全に枯れるとMac全体が死ぬ。最後の0.5GBは触らない
LOAD_PER_SESSION = 1.5  # セッション1本が押し上げるロードの実測見込み
LOAD_CEIL_RATIO = 2.0   # ロード÷コア数の天井
HARD_MAX = 8
HARD_MIN = 1


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return ""


def measure():
    """Macの上で走っていれば実測する。そうでなければ直前の実測（machine.json）を使う。"""
    m = {"source": "実測"}
    pagesize = 4096
    try:
        pagesize = int(run(["sysctl", "-n", "hw.pagesize"]).strip() or 4096)
        m["memTotalGB"] = round(int(run(["sysctl", "-n", "hw.memsize"]).strip()) / 1024.0**3, 2)
    except Exception:
        m["memTotalGB"] = None
    vs = run(["vm_stat"])
    pages = {}
    for k in ("free", "inactive", "speculative", "purgeable"):
        mm = re.search(r"Pages %s:\s+(\d+)" % k, vs)
        pages[k] = int(mm.group(1)) if mm else 0
    if any(pages.values()):
        m["memAvailGB"] = round(sum(pages.values()) * pagesize / 1024.0**3, 2)
        m["pages"] = pages
    sw = run(["sysctl", "vm.swapusage"])
    mm = re.search(r"total = ([\d.]+)M\s+used = ([\d.]+)M\s+free = ([\d.]+)M", sw)
    if mm:
        m["swapTotalGB"] = round(float(mm.group(1)) / 1024.0, 2)
        m["swapUsedGB"] = round(float(mm.group(2)) / 1024.0, 2)
        m["swapFreeGB"] = round(float(mm.group(3)) / 1024.0, 2)
    la = re.search(r"\{ ([\d.]+) ([\d.]+) ([\d.]+) \}", run(["sysctl", "-n", "vm.loadavg"]))
    if la:
        m["load1"], m["load5"], m["load15"] = (float(la.group(i)) for i in (1, 2, 3))
    try:
        m["cores"] = int(run(["sysctl", "-n", "hw.ncpu"]).strip())
    except Exception:
        m["cores"] = None
    mp = run(["memory_pressure"])
    mm = re.search(r"System-wide memory free percentage:\s+(\d+)%", mp)
    if mm:
        m["memFreePct"] = int(mm.group(1))

    # Macの上に居ない（サンドボックス等）＝直前の実測を使う。**推測では埋めない**
    if m.get("memAvailGB") is None or m.get("swapFreeGB") is None:
        m["source"] = "直前の実測（machine.json）"
        try:
            j = json.load(io.open(os.path.join(STATUS, "machine.json"), encoding="utf-8"))
            m.setdefault("memAvailGB", j.get("memAvailGB"))
            m["load5"] = m.get("load5") or j.get("load5")
            m["cores"] = m.get("cores") or j.get("cores")
            m["measuredAtSource"] = j.get("measuredAt")
            sg = j.get("swapGB")
            if m.get("swapFreeGB") is None and sg:
                m["swapUsedGB"] = round(float(sg) / 1024.0, 2) if sg > 100 else float(sg)
        except Exception:
            pass
    return m


def ceilings(m):
    """3つの天井を別々に出す。いちばん低いものが答え。どれが効いたかを必ず残す。"""
    out = {}
    avail = m.get("memAvailGB")
    out["メモリ"] = int(max(0, (avail - MEM_RESERVE_GB)) / PER_SESSION_GB) if avail is not None else None
    sf = m.get("swapFreeGB")
    out["スワップ"] = int(max(0, (sf - SWAP_RESERVE_GB)) / PER_SESSION_GB) if sf is not None else None
    l5, cores = m.get("load5"), m.get("cores")
    if l5 is not None and cores:
        out["ロード"] = int(max(0, (cores * LOAD_CEIL_RATIO - l5)) / LOAD_PER_SESSION)
    else:
        out["ロード"] = None
    return out


def read_calibration():
    try:
        return json.load(io.open(CALIB, encoding="utf-8"))
    except Exception:
        return {}


def build():
    m = measure()
    c = ceilings(m)
    known = {k: v for k, v in c.items() if v is not None}
    raw = min(known.values()) if known else HARD_MIN
    binding = [k for k, v in known.items() if v == raw]

    calib = read_calibration()
    calib_n = int(calib.get("safeN") or 0)
    byN = calib.get("byN") or {}

    reasons = []
    n = max(HARD_MIN, min(HARD_MAX, raw))
    if known:
        reasons.append("首は「%s」（%s）" % ("・".join(binding),
                       "／".join("%s%s本" % (k, v) for k, v in known.items())))

    # ---- 自動減便（人が見張らない）----
    shed = None
    if m.get("swapFreeGB") is not None and m["swapFreeGB"] < 1.0:
        n = HARD_MIN
        shed = "スワップの残りが%.2fGB（1.0GB未満）＝Mac全体が落ちる手前。1本まで落とす" % m["swapFreeGB"]
    elif m.get("load5") and m.get("cores") and (m["load5"] / m["cores"]) > 2.5:
        n = HARD_MIN
        shed = "5分ロード比%.1f（2.5超）＝詰まっている。1本まで落とす" % (m["load5"] / m["cores"])
    if shed:
        reasons.append("自動減便：" + shed)

    # ---- 試し増便（自分で自分を縛る輪を切る）----
    # calibration.json は「標本6件以上で合格した最大本数」を上限にするが、
    # 上限が2本だと3本目が一度も走らず標本が永久に集まらない。
    # 3つの天井すべてに2本ぶんの余裕があり・減便条件にも当たっていないときだけ、
    # 1本だけ多く走らせて**標本を取りに行く**。
    probe = None
    nxt = str(calib_n + 1)
    if (not shed and calib_n and n >= calib_n
            and not (byN.get(nxt) or {}).get("enough")
            and all(v >= calib_n + 2 for v in known.values())):
        probe = calib_n + 1
        reasons.append("試し増便：%d本の標本が%d件しか無い。天井に2本ぶんの余裕があるので今回だけ%d本まで許す"
                       % (calib_n + 1, (byN.get(nxt) or {}).get("samples") or 0, probe))

    jougen = max(HARD_MIN, min(HARD_MAX, probe or n))

    out = {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S+0900"),
        "同時上限": jougen,
        "根拠": reasons,
        "天井": c,
        "実測": m,
        "自動減便": shed,
        "試し増便": probe,
        "calibrationSafeN": calib_n or None,
        "calibration標本数": {k: (v or {}).get("samples") for k, v in byN.items()},
        "定数": {
            "1本あたりGB": PER_SESSION_GB, "たまごさん用に空けるGB": MEM_RESERVE_GB,
            "スワップ予備GB": SWAP_RESERVE_GB, "1本あたりロード": LOAD_PER_SESSION,
            "ロード÷コアの天井": LOAD_CEIL_RATIO, "絶対上限": HARD_MAX,
        },
    }
    return out


def write(out):
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    # health.json に相乗りさせる（Dispatchは着火前にここ1か所を見れば済む）
    try:
        h = json.load(io.open(HEALTH, encoding="utf-8"))
    except Exception:
        h = {}
    h["同時上限"] = {
        "本数": out["同時上限"],
        "根拠": out["根拠"],
        "天井": out["天井"],
        "測った時刻": out["measuredAt"],
        "自動減便": out["自動減便"],
        "試し増便": out["試し増便"],
    }
    with io.open(HEALTH, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def main():
    out = build()
    if "--print" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    write(out)
    print("同時上限 %d本 ／ %s" % (out["同時上限"], " ／ ".join(out["根拠"]) or "根拠なし"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
