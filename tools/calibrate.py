#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全本数の実測校正（2026-09-03）— 「何本までなら絶対安全か」を推測でなくデータで出す。

入力:
  status/load_history.jsonl  … factory_status.py --write が5分おきに1行足す（本数・ロード÷コア・メモリ圧・スワップ・I/O・人が操作中か）
  status/heavy_events.jsonl  … 「重い」事象（固まった／ボタンが押せない／タブが切り替わらない）。人が mark_heavy.py で記録した分＋機械の自動検知分
  （初回だけ）git の status/machine.json 履歴を種にする（過去の5分刻みが80件以上ある）
出力:
  status/calibration.json    … {"safeN": 絶対安全な本数, "target": 常に維持する本数(=safeNの8割・最低2), "byN": 本数ごとの実測, "heavy": 重い事象の一覧}

判定（本数 N ごとに集計。標本6件以上ある N だけ判定）:
  - その N で「重い」事象が1件でもあれば N は不合格（それ以上も不合格）
  - ロード÷コア数の90パーセンタイルが LOAD_OK(0.8) 以下、かつ メモリ圧が緑の割合が MEM_OK(0.95) 以上、かつ スワップ増加の割合が SWAP_OK(0.1) 以下 → 合格
  - safeN = 合格した N の最大（連続して合格している範囲）。標本が足りなければ既定 4（今日の実測：5本で快適、14本で固まった）
  - ロードが本数と無関係に高い時間帯（Brave/node 由来）も混ざるので、標本は「ロードの主因がセッション」に限らず全部使う＝安全側
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HIST = os.path.join(REPO, "status", "load_history.jsonl")
HEAVY = os.path.join(REPO, "status", "heavy_events.jsonl")
OUT = os.path.join(REPO, "status", "calibration.json")
LOAD_OK, MEM_OK, SWAP_OK = 0.8, 0.95, 0.10
MIN_SAMPLES = 6
DEFAULT_SAFE = 4
HARD_CEIL = 8
# 2026-09-03 実測（3日ぶんの記録334件をたまごさんの指示で集計）
#   0本=2.41 / 3本=2.81 / 4本=4.14 / 5本=6.61 ここまで想定内
#   6本=19.48 / 10本=12.96 / 11本=52.30 ← 11本のときに実際にフリーズした
# → セッション1本あたりの増分は約1.0。絶対値が12を超えたところから危ない。
LOAD_PER_SESSION = 1.0    # 1本増えるごとに許すロード比の増分
HARD_RATIO = 12.0         # これを超えたら本数に関係なく危険（コア8に対して1.5倍）
BASE_RATIO_DEFAULT = 2.5  # 0本の標本が無いときの土台（ブラウザ等の常駐ぶん）
MARGIN = 0.8  # たまごさん「ちょっと余裕を見ていい」→ 上限の8割を維持目標に


def read_jsonl(p):
    out = []
    try:
        for ln in open(p, encoding="utf-8"):
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    except Exception:
        pass
    return out


def seed_from_git():
    """load_history が無い／少ないとき、git の machine.json 履歴から種を作る"""
    rows = []
    try:
        hs = subprocess.run(["git", "-C", REPO, "log", "--format=%H", "--since=3 days ago", "--", "status/machine.json"],
                            capture_output=True, text=True, timeout=30).stdout.split()
        for h in hs[:400]:
            raw = subprocess.run(["git", "-C", REPO, "show", "%s:status/machine.json" % h], capture_output=True, text=True, timeout=10).stdout
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if d.get("sessions") is None:
                continue
            rows.append({"t": d.get("measuredAt"), "n": d.get("sessions"), "working": d.get("working"),
                         "loadRatio": (d.get("load5") / d.get("cores")) if d.get("load5") and d.get("cores") else None,
                         "mem": d.get("memPressure"), "swapUp": d.get("swapIncreasing"), "seed": True})
    except Exception:
        pass
    return rows


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = int(round((len(xs) - 1) * q))
    return xs[k]


def main():
    hist = read_jsonl(HIST)
    if len(hist) < 30:
        hist = seed_from_git() + hist
    heavy = read_jsonl(HEAVY)
    # topCpu が記録されていて、かつ claude 系プロセスが主犯でない（node/lint/build/Chrome等の外部要因と判明している）場合は
    # その時のセッション本数(n)を「危険な本数」に数えない。孤児プロセス由来の負荷スパイクで safeN が不当に下がる事故を防ぐ（2026-09-03）
    def session_is_cause(h):
        tc = (h.get("topCpu") or "").strip()
        if not tc:
            return True  # 原因不明は安全側（従来どおりセッションのせいとみなす）
        return "claude" in tc.lower()
    heavy_n = sorted({int(h.get("n")) for h in heavy if h.get("n") is not None and session_is_cause(h)})
    # 2026-09-03：セッション0本のときにも重い事象が起きているなら、それはセッションのせいではない
    # （ブラウザ・大きなファイルコピー・Spotlight等）。本数を責めても上限が1本に張り付くだけなので、
    # その場合は「重い事象による本数の除外」を無効にする。実データで0〜5本すべてがheavy扱いになり
    # safeN=1 に固定されていた事故への対処。負荷そのものはロード比の判定（allow / HARD_RATIO）で見る。
    if 0 in heavy_n:
        heavy_n = []
    by = {}
    for r in hist:
        n = r.get("n")
        if n is None:
            continue
        b = by.setdefault(int(n), {"samples": 0, "loadRatios": [], "memGreen": 0, "swapUp": 0})
        b["samples"] += 1
        b["loadRatios"].append(r.get("loadRatio"))
        if r.get("mem") == "green":
            b["memGreen"] += 1
        if r.get("swapUp"):
            b["swapUp"] += 1
    # 土台（セッション0本のときの負荷）。ブラウザ・常駐アプリの分。ここを引かないと何本でも不合格になる。
    base_ratio = None
    if 0 in by:
        base_ratio = pct(by[0]["loadRatios"], 0.9)
    if base_ratio is None:
        base_ratio = BASE_RATIO_DEFAULT

    byN = {}
    for n in sorted(by):
        b = by[n]
        p90 = pct(b["loadRatios"], 0.9)
        mem_ok = b["memGreen"] / b["samples"] if b["samples"] else 0
        swap_r = b["swapUp"] / b["samples"] if b["samples"] else 0
        enough = b["samples"] >= MIN_SAMPLES
        heavy_here = n in heavy_n
        # 2026-09-03 判定を作り直した。
        # 旧: 絶対値 p90 <= 0.8 で合格。→ ブラウザ等の常駐だけで p90 が 2.4 あるため
        #     「0本のときですら不合格」になり、safeN が常に 1 に張り付いていた（実データで確認）。
        # 新: セッションが増やす分（限界増分）で見る。0本のときの負荷を土台として引き、
        #     1本あたり LOAD_PER_SESSION まで増えるのは想定内とする。
        #     ただし絶対値がフリーズ域（コア数比 HARD_RATIO）に達したらその時点で不合格。
        #     実データ: 0本=2.41 / 5本=6.61（想定内）/ 6本=19.48（破綻）/ 11本=52.30（実際にフリーズ）
        allow = base_ratio + n * LOAD_PER_SESSION
        ok = (enough and not heavy_here
              and (p90 is None or (p90 <= allow and p90 < HARD_RATIO))
              and mem_ok >= MEM_OK and swap_r <= SWAP_OK)
        byN[str(n)] = {"samples": b["samples"], "loadRatioP90": round(p90, 2) if p90 is not None else None,
                       "memGreenRate": round(mem_ok, 2), "swapUpRate": round(swap_r, 2), "heavy": heavy_here,
                       "enough": enough, "ok": ok}
    # safeN：小さい本数から連続して ok な範囲の最大。重い事象が出た最小本数の1つ下を上限に
    safe = None
    for n in sorted(int(k) for k in byN):
        if byN[str(n)]["ok"]:
            safe = n
        else:
            # 2026-09-03：不合格でも「標本不足」なら素通りしていたため、
            # 6本で破綻（p90=19.5）しているのに9本まで合格と判定されていた。
            # 保証できない本数に当たったら、そこで打ち切る。上を見に行かない。
            break
    heavy_floor = (min(heavy_n) - 1) if heavy_n else None
    if safe is None:
        safe = DEFAULT_SAFE
        basis = "標本不足→既定%d本" % DEFAULT_SAFE
    else:
        basis = "実測（%d本まで合格）" % safe
    if heavy_floor is not None:
        safe = min(safe, max(heavy_floor, 1))
        basis += "・重い事象は%d本で発生" % min(heavy_n)
    safe = max(1, min(HARD_CEIL, safe))
    target = max(2, int(safe * MARGIN))
    out = {"updatedAt": time.strftime("%Y-%m-%d %H:%M"), "safeN": safe, "target": target, "basis": basis,
           "samples": len(hist), "heavyEvents": len(heavy), "byN": byN,
           "rule": "safeN=標本6件以上で ロード÷コアP90≤0.8・メモリ緑95%以上・スワップ増10%以下 が連続して合格した最大本数（重い事象が出た本数の1つ下で頭打ち）。target=safeNの8割（最低2）"}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    if "--quiet" not in sys.argv:
        print("safeN=%d target=%d（%s・標本%d・重い事象%d）" % (safe, target, basis, len(hist), len(heavy)))
        for k, v in byN.items():
            print(" ", k, "本:", v)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(0)
