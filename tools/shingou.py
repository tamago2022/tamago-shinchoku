#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1174番【信号機】Macの余力を数値で見て、同時に走ってよい本数を自分で上下させる。

たまごさん（2026-09-27・原文）:
  「2本は約束じゃないよ。パソコンの空き状態を見て、4本でも6本でも10本でも
    走らせていい。パソコンが重くなったらダメだって話。バランス取れないの、それ？
    数値で分からないの？これ以上いったら重くなるっていう。
    タブも切り替えられないぐらい重いんだ」

■ 何を直したか
  これまで本数は「2本（実測の天井）」という固定の数字と、歯止め（omoi_habadome）の
  「重いので1本」という崖の2つで決まっていた。余裕が戻っても戻らない
  （実測：直近400巡回のうち397回が「見送り: 走行1本／上限1本」）。
  ここでは固定の約束をやめ、**余力の実測から本数を毎回引き直す。**

■ 赤の基準は机上の数字ではない
  たまごさんが「タブも切り替えられないぐらい重い」と言ったその瞬間のMacを測り、
  status/shingou_aka.json に「これが赤」として保存する（1回だけ・上書きしない）。
  緑／黄／赤の線はすべてこの実測からの比で引く。

■ 崖にしない
  ・一気に0にしない（下限1本）。下げるのは1回に最大2本まで。
  ・上げるのは1回に1本だけ。しかも緑が2回続いたときだけ（ぶれで増やさない）。
  ・余裕が戻れば自動で戻る（人が触らなくても戻る＝過去の「戻らない門」を繰り返さない）。

■ 測るもの（swapFree単独で見て永久に条件を満たさなかった失敗を繰り返さない）
  ① memory_pressure コマンドの「System-wide memory free percentage」
  ② vm_stat の圧縮メモリ（Pages occupied by compressor）＝本当の逼迫はここに出る
  ③ sysctl vm.swapusage（used/free）
  ④ sysctl vm.loadavg の5分平均 ÷ コア数（体感の詰まり）
  どれか1つが赤なら赤（一番悪いものに合わせる）。

出力: status/shingou.json … memory_pressure / ok_honsuu / riyuu ほか
使い方: python3 tools/shingou.py
"""
import io
import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "shingou.json")
AKA = os.path.join(ST, "shingou_aka.json")

SHITA = 1        # 下限。0にはしない（工場を止めない）
UE = 8           # 上限。ここから上は実測が無いので出さない
SAGERU_MAX = 2   # 1回に下げてよい本数
AGERU_MAX = 1    # 1回に上げてよい本数


def sh(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception:
        return ""


def jload(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    tmp = p + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        json.dumps(o, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


def hakaru():
    """今のMacを1回だけ測る（常時監視はしない。全部ミリ秒〜1秒で返るものだけ）。"""
    d = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    # ① memory_pressure（macOS純正。これが「空きメモリ％」の正本）
    raw = sh(["memory_pressure"], timeout=20)
    m = re.search(r"System-wide memory free percentage:\s*([0-9]+)", raw)
    d["memFreePct"] = int(m.group(1)) if m else None
    m = re.search(r"The system has ([0-9]+) \((\d+) pages\) of memory", raw)
    d["memory_pressure_raw"] = (raw.strip().splitlines() or [""])[-1][:200]

    # ② vm_stat の圧縮メモリ（逼迫は空き％より先にここへ出る）
    vs = sh(["vm_stat"], timeout=10)
    pg = 16384
    m = re.search(r"page size of (\d+) bytes", vs)
    if m:
        pg = int(m.group(1))
    m = re.search(r"Pages occupied by compressor:\s*(\d+)", vs)
    d["compressorGB"] = round(int(m.group(1)) * pg / 1024.0 ** 3, 2) if m else None
    m = re.search(r"Pages free:\s*(\d+)", vs)
    d["freeGB"] = round(int(m.group(1)) * pg / 1024.0 ** 3, 2) if m else None

    # ③ スワップ（使用量。残りだけを見て永久に条件を満たさなかった失敗はここが原因）
    sw = sh(["sysctl", "vm.swapusage"], timeout=10)
    mu = re.search(r"used\s*=\s*([0-9.]+)M", sw)
    mt = re.search(r"total\s*=\s*([0-9.]+)M", sw)
    d["swapUsedGB"] = round(float(mu.group(1)) / 1024.0, 2) if mu else None
    d["swapTotalGB"] = round(float(mt.group(1)) / 1024.0, 2) if mt else None

    # ④ 5分ロード比（体感の詰まり。8コアなら 1.0 で満席）
    cores = 8
    try:
        cores = int(sh(["sysctl", "-n", "hw.ncpu"], timeout=5) or 8)
    except Exception:
        pass
    la = sh(["sysctl", "-n", "vm.loadavg"], timeout=5)
    try:
        d["load5"] = float(la.split()[2])
    except Exception:
        d["load5"] = None
    d["cores"] = cores
    d["loadRatio"] = (round(d["load5"] / cores, 2)
                      if (d.get("load5") and cores) else None)
    return d


def aka_kiroku(now):
    """「タブも切り替えられないぐらい重い」と言われた時の実測を、赤の基準として1回だけ保存する。"""
    a = jload(AKA)
    if isinstance(a, dict) and a.get("memFreePct") is not None:
        return a
    a = {
        "koe": "たまごさん「タブも切り替えられないぐらい重い」（2026-09-27）",
        "at": now["at"],
        "memFreePct": now.get("memFreePct"),
        "loadRatio": now.get("loadRatio"),
        "swapUsedGB": now.get("swapUsedGB"),
        "compressorGB": now.get("compressorGB"),
        "note": "この瞬間のMacを『赤』として記録した。緑／黄の線は全部ここからの比で引く。"
                "机上の数字は使っていない。",
    }
    jsave(AKA, a)
    return a


def shingou(now, aka):
    """緑／黄／赤 と、その理由。一番悪いものに合わせる。"""
    riyuu = []
    aka_hit, midori_hit = [], []

    def cmp_low(key, name, tan=""):
        """小さいほど苦しい値（空きメモリ%）"""
        v, b = now.get(key), aka.get(key)
        if v is None or not b:
            return
        if v <= b * 1.15:
            aka_hit.append("%s %s%s（赤の基準 %s%s の1.15倍以内）" % (name, v, tan, b, tan))
        elif v >= b * 2.0:
            midori_hit.append("%s %s%s（赤の基準の2倍以上）" % (name, v, tan))
        else:
            riyuu.append("%s %s%s（赤 %s%s と緑 %.0f%s の間）"
                         % (name, v, tan, b, tan, b * 2.0, tan))

    def cmp_high(key, name, tan=""):
        """大きいほど苦しい値（ロード比・スワップ・圧縮）"""
        v, b = now.get(key), aka.get(key)
        if v is None or not b:
            return
        if v >= b * 0.85:
            aka_hit.append("%s %s%s（赤の基準 %s%s の85%%以上）" % (name, v, tan, b, tan))
        elif v <= b * 0.40:
            midori_hit.append("%s %s%s（赤の基準の40%%以下）" % (name, v, tan))
        else:
            riyuu.append("%s %s%s（赤 %s%s の40〜85%%）" % (name, v, tan, b, tan))

    # ★どの指標で赤を判定するかは、較正の実測で決めた（2026-09-27 11:35:31）。
    #   たまごさんが「タブも切り替えられないぐらい重い」と言ったその瞬間の数字：
    #     空きメモリ 81% ／ 5分ロード比 2.28 ／ スワップ使用 16.51GB ／ 圧縮メモリ 1.84GB
    #   → **空きメモリ81%。つまり空きメモリ％は「重い」を全く表していない。**
    #     これを判定に入れると、赤の基準が81%なので以後ほぼ永久に赤になる
    #     （swapFree単独で見て永久に条件を満たさなかった過去の失敗と同じ形）。
    #   → 判定に使うのは、赤の瞬間に実際に振り切れていた2つだけ：
    #       ① 5分ロード比（＝タブが切り替わらない体感そのもの）
    #       ② 圧縮メモリ（＝メモリ逼迫は空き％より先にここへ出る）
    #     スワップ使用量は一度膨らむと軽くなっても減らない（再起動まで残る）ので、
    #     判定には使わず表示だけにする。空きメモリ％も表示だけ。
    cmp_high("loadRatio", "5分ロード比")
    cmp_high("compressorGB", "圧縮メモリ", "GB")

    # 表示だけの指標（判定には使わない。理由は上のコメント）
    sankou = []
    if now.get("memFreePct") is not None:
        sankou.append("空きメモリ %s%%（判定には使わない＝赤の時も81%%だった）"
                      % now.get("memFreePct"))
    if now.get("swapUsedGB") is not None:
        sankou.append("スワップ使用 %sGB（減らないので判定には使わない）" % now.get("swapUsedGB"))

    if aka_hit:
        return "赤", aka_hit + riyuu + sankou
    # 緑は「見えている指標が全部緑」のときだけ（1つでも中間なら黄）
    if midori_hit and not riyuu:
        return "緑", midori_hit + sankou
    return "黄", (riyuu + midori_hit + sankou) or ["測れた指標が無いので黄にしておく"]


def kime(sg, mae, midori_renzoku):
    """信号から今回の本数を決める。★崖にしない・戻れるようにする。"""
    if sg == "赤":
        mokuhyou = 1
    elif sg == "黄":
        # ★黄を2本で固定しない。緑の線（赤の40%以下）は厳しいので、黄で止まり続けると
        #   「一度締まった門が戻らない」に逆戻りする。黄＝ふつうに走れる状態＝3本。
        mokuhyou = 3
    else:
        mokuhyou = min(UE, max(4, mae + 1))
    n = mae
    if mokuhyou < mae:
        n = max(mokuhyou, mae - SAGERU_MAX)      # 下げるのも一気にしない
    elif mokuhyou > mae:
        if sg == "緑" and midori_renzoku < 2:
            n = mae                              # 緑が2回続くまで増やさない
        else:
            n = min(mokuhyou, mae + AGERU_MAX)   # 上げるのは1本ずつ
    return max(SHITA, min(UE, n))


def main():
    now = hakaru()
    aka = aka_kiroku(now)
    sg, riyuu = shingou(now, aka)

    mae_d = jload(OUT, {}) or {}
    mae = mae_d.get("ok_honsuu")
    if not isinstance(mae, int) or mae < SHITA:
        mae = 2
    renzoku = int(mae_d.get("midoriRenzoku") or 0)
    renzoku = renzoku + 1 if sg == "緑" else 0

    n = kime(sg, mae, renzoku)
    ichi = riyuu[0] if riyuu else "理由なし"
    d = dict(now)
    d.update({
        "shingou": sg,
        "ok_honsuu": n,
        "mae_honsuu": mae,
        "midoriRenzoku": renzoku,
        "riyuu": "%s：%s → 同時%d本（前回%d本）" % (sg, ichi, n, mae),
        "riyuuZenbu": riyuu,
        "aka": aka,
        "memory_pressure": now.get("memFreePct"),
    })
    jsave(OUT, d)
    try:
        with io.open(os.path.join(ST, "shingou.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": d["at"], "shingou": sg, "ok": n,
                                "memFreePct": now.get("memFreePct"),
                                "loadRatio": now.get("loadRatio"),
                                "swapUsedGB": now.get("swapUsedGB"),
                                "compressorGB": now.get("compressorGB")},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass
    print("%s ok_honsuu=%d  %s" % (sg, n, d["riyuu"]))


if __name__ == "__main__":
    main()
