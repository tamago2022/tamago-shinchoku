#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""負荷を見て同時本数を2〜4本で決める（2026-10-08・たまごさん指示）。

たまごさん：「同時実行本数を固定2本から、Macの負荷を見て2〜4本で自動調整に。
            最優先は Mac が固まらないこと（キーボードが効かなくなる等は絶対NG）」

━━ 決め方（発車の直前に毎回測る）━━
  メモリ圧 赤            → 上限1本
  メモリ圧 黄            → 新規発車を止める（走っている子はそのまま）
  メモリ圧 緑
     1分ロード ÷ コア数 < 0.60 → 上限4本
     1分ロード ÷ コア数 < 0.70 → 上限3本
     それ以外                  → 上限2本
  測れなかった            → 上限2本（今までと同じ。推測で増やさない）

  ・上限を下げても、走っている子は殺さない。新規発車を止めるだけ。
  ・使う命令は権限ダイアログが出ないものだけ：
      sysctl（vm.loadavg / hw.ncpu / kern.memorystatus_vm_pressure_level）
      memory_pressure -Q ／ vm_stat
    osascript・AppleScript・System Events・画面収録・アクセシビリティ系は使わない。

━━ 1語で元に戻す ━━
  「固定2本に戻す」＝ status/dojisu_kotei2.flag を置く（中身は何でもよい）。
      python3 tools/fuka_hassha.py --kotei2     # 固定2本に戻す
      python3 tools/fuka_hassha.py --jidou      # 自動調整に戻す
  フラグがある間は、負荷に関係なく上限2本（2026-10-08以前と同じ動き）。

出力：
  status/health.json の "発車本数判定" キー（測定値・採用した上限・時刻）
  status/public/fuka_hassha.json（進捗表が読む写し）
  status/fuka_hassha.jsonl（判定の履歴・直近2000行）

使い方：
  python3 tools/fuka_hassha.py --print      # 測って画面に出すだけ
  python3 tools/fuka_hassha.py              # 測って書き出す
  python3 tools/fuka_hassha.py --self-test  # 判定の自己試験（Macでなくても走る）
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
HEALTH = os.path.join(STATUS, "health.json")
PUBLIC = os.path.join(STATUS, "public", "fuka_hassha.json")
HIST = os.path.join(STATUS, "fuka_hassha.jsonl")
KOTEI2_FLAG = os.path.join(STATUS, "dojisu_kotei2.flag")

# ---- しきい値（計測しながら微調整してよい）----
RATIO_4 = 0.60     # 1分ロード÷コア数がこれ未満なら4本
RATIO_3 = 0.70     # これ未満なら3本
CAP_MAX = 4
CAP_DEFAULT = 2    # 測れない／それ以外
CAP_RED = 1
# memory_pressure -Q の空き%からの読み替え（sysctlの段階値が取れないときだけ使う）
FREE_PCT_YELLOW = 20
FREE_PCT_RED = 10


def _run(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout or ""
    except Exception:
        return ""


def measure():
    """権限ダイアログが出ない命令だけで測る。1つ失敗しても他は続ける。"""
    m = {}
    la = re.search(r"\{\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\}", _run(["sysctl", "-n", "vm.loadavg"]))
    if la:
        m["load1"], m["load5"], m["load15"] = (float(la.group(i)) for i in (1, 2, 3))
    try:
        m["ncpu"] = int(_run(["sysctl", "-n", "hw.ncpu"]).strip())
    except Exception:
        pass
    # macOSのメモリ圧の段階：1=緑(normal) 2=黄(warn) 4=赤(critical)
    try:
        m["pressureLevel"] = int(_run(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"]).strip())
    except Exception:
        pass
    mp = re.search(r"free percentage:\s*(\d+)%", _run(["memory_pressure", "-Q"]))
    if mp:
        m["memFreePct"] = int(mp.group(1))
    return m


def pressure_color(m):
    lv = m.get("pressureLevel")
    if lv == 1:
        return "green"
    if lv == 2:
        return "yellow"
    if lv is not None and lv >= 4:
        return "red"
    fp = m.get("memFreePct")
    if fp is None:
        return None
    if fp < FREE_PCT_RED:
        return "red"
    if fp < FREE_PCT_YELLOW:
        return "yellow"
    return "green"


def judge(m, kotei2=False):
    """測定値から {cap, stopNew, color, ratio, reason} を返す。副作用なし。"""
    color = pressure_color(m)
    ratio = None
    if m.get("load1") is not None and m.get("ncpu"):
        ratio = round(m["load1"] / float(m["ncpu"]), 3)
    r = {"color": color, "ratio1": ratio, "stopNew": False}
    if kotei2:
        r.update(cap=CAP_DEFAULT, mode="固定2本", reason="固定2本フラグあり（status/dojisu_kotei2.flag）")
        return r
    r["mode"] = "自動"
    if color == "red":
        r.update(cap=CAP_RED, reason="メモリ圧=赤 → 上限1本")
    elif color == "yellow":
        r.update(cap=CAP_DEFAULT, stopNew=True, reason="メモリ圧=黄 → 新規発車を止める（走行中はそのまま）")
    elif color == "green" and ratio is not None:
        if ratio < RATIO_4:
            r.update(cap=4, reason="メモリ圧=緑・ロード比%.2f（%.2f未満）→ 上限4本" % (ratio, RATIO_4))
        elif ratio < RATIO_3:
            r.update(cap=3, reason="メモリ圧=緑・ロード比%.2f（%.2f未満）→ 上限3本" % (ratio, RATIO_3))
        else:
            r.update(cap=2, reason="メモリ圧=緑・ロード比%.2f（%.2f以上）→ 上限2本" % (ratio, RATIO_3))
    else:
        r.update(cap=CAP_DEFAULT, reason="測れなかった（メモリ圧=%s・ロード比=%s）→ 既定2本" % (color, ratio))
    return r


def kotei2_on():
    return os.path.exists(KOTEI2_FLAG)


def _atomic_json(path, obj):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".fuka_", suffix=".tmp")
    with io.open(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def write(m, r, alive=None, source=""):
    rec = {
        "時刻": time.strftime("%Y-%m-%dT%H:%M:%S+0900"),
        "採用した上限": r["cap"],
        "新規発車": "止める" if r["stopNew"] else "可",
        "モード": r["mode"],
        "理由": r["reason"],
        "メモリ圧": r["color"],
        "ロード比1分": r["ratio1"],
        "測定値": m,
        "走行本数": alive,
        "呼んだ所": source,
    }
    try:
        h = json.load(io.open(HEALTH, encoding="utf-8"))
        if not isinstance(h, dict):
            h = {}
    except Exception:
        h = {}
    h["発車本数判定"] = rec
    try:
        _atomic_json(HEALTH, h)
    except Exception:
        pass
    try:
        _atomic_json(PUBLIC, rec)
    except Exception:
        pass
    try:
        with io.open(HIST, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if os.path.getsize(HIST) > 2_000_000:
            lines = io.open(HIST, encoding="utf-8").read().splitlines()[-2000:]
            io.open(HIST, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    except Exception:
        pass
    return rec


def hantei(alive=None, source="", do_write=True):
    """発車の直前に呼ぶ口。測って判定して書く。例外は投げない（失敗＝既定2本）。"""
    try:
        m = measure()
        r = judge(m, kotei2=kotei2_on())
    except Exception as e:
        m, r = {}, {"cap": CAP_DEFAULT, "stopNew": False, "mode": "自動", "color": None,
                    "ratio1": None, "reason": "判定で例外（%s）→ 既定2本" % e}
    if do_write:
        try:
            write(m, r, alive=alive, source=source)
        except Exception:
            pass
    return r


def _self_test():
    ok = True

    def eq(a, b, label):
        nonlocal ok
        if a != b:
            ok = False
            print("NG", label, a, b)
    eq(judge({"pressureLevel": 1, "load1": 3.0, "ncpu": 8})["cap"], 4, "緑0.375→4")
    eq(judge({"pressureLevel": 1, "load1": 5.2, "ncpu": 8})["cap"], 3, "緑0.65→3")
    eq(judge({"pressureLevel": 1, "load1": 5.6, "ncpu": 8})["cap"], 2, "緑0.70→2")
    eq(judge({"pressureLevel": 1, "load1": 400, "ncpu": 8})["cap"], 2, "緑高負荷→2")
    eq(judge({"pressureLevel": 2, "load1": 1, "ncpu": 8})["stopNew"], True, "黄→止める")
    eq(judge({"pressureLevel": 4, "load1": 1, "ncpu": 8})["cap"], 1, "赤→1")
    eq(judge({"memFreePct": 5, "load1": 1, "ncpu": 8})["cap"], 1, "空き5%→赤")
    eq(judge({"memFreePct": 15, "load1": 1, "ncpu": 8})["stopNew"], True, "空き15%→黄")
    eq(judge({"memFreePct": 50, "load1": 1, "ncpu": 8})["cap"], 4, "空き50%→緑4")
    eq(judge({})["cap"], 2, "測れない→2")
    eq(judge({"pressureLevel": 1, "load1": 0.1, "ncpu": 8}, kotei2=True)["cap"], 2, "固定2")
    eq(judge({"pressureLevel": 4}, kotei2=True)["cap"], 2, "固定2は赤でも2（旧動作）")
    print("self-test", "OK" if ok else "NG")
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return _self_test()
    if "--kotei2" in a:
        io.open(KOTEI2_FLAG, "w", encoding="utf-8").write(
            "固定2本に戻した %s\n" % time.strftime("%F %T"))
        print("固定2本に戻しました（%s）" % KOTEI2_FLAG)
        return 0
    if "--jidou" in a:
        if os.path.exists(KOTEI2_FLAG):
            os.remove(KOTEI2_FLAG)
        print("自動調整（2〜4本）に戻しました")
        return 0
    r = hantei(source="cli", do_write="--print" not in a)
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
