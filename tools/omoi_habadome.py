#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1163番【重い処理の歯止め】(2026-09-26)

たまごさん（2026-09-26・Macが固まって再起動したあと）:
  「VOICEVOXの一括生成など重い処理は、負荷が高いときは自動で止まるようにする。」

■ なぜ要るか（実測。推測ではない）
  固まる直前の実測（status/dojisu_jougen.json 16:22:28）:
      swapTotal 29.00GB / swapUsed 28.41GB / **swapFree 0.59GB**
  スワップを29GB使い切る手前まで走らせていた。つまり Mac は
  「メモリが足りない」で固まったのではなく **スワップが枯れて固まった。**

  そして既存の自動減便（tools/dojisu_jougen.py）は
      swapFree < 1.0GB になってから 1本に落とす
  という設計だった。**残り1.0GBは、もう手遅れの地点。**
  減便が効いたときには画面はすでに固まっている。

  もう1つの実測: status/kanmon.jsonl は同じ日に 上限2本・3本 を通していた
  （13:59 上限2／14:28 上限3／14:51 上限2／15:18 上限2／15:20 上限2）。
  これは dojisu_jougen.py の「試し増便」が、**すでにスワップを28GB使っている
  Mac の上で標本を取りに行っていた** から。増便してよい状態ではなかった。

■ ここが持つこと（1つだけ）
  「いま重い処理を走らせてよいか」の判定。1か所に置いて、重い口が全部ここを通る。
  本数を決めるのは dojisu_jougen.py の役。ここは **走る／待つ／やめる** だけ。

■ 3つの門（いちばん厳しいものが効く）
  スワップ残り  4.0GB 未満 → だめ（固まる前に止める。実測0.59GBは遅すぎた）
  スワップ使用率  70% 超   → だめ（総量が増えても率で効く）
  5分ロード÷コア  1.5 超   → だめ（詰まっている）
  空きメモリ     3.0GB 未満 → だめ

■ 使い方（呼ぶ側は3行）
      import omoi_habadome
      ok, why = omoi_habadome.hashiru_te_ii()
      if not ok: ...   # 待つ or 進捗を保存して抜ける

      omoi_habadome.matsu(max_sec=900)   # 静かになるまで待つ。だめなら False
      # → False が返ったら「進捗を保存して抜ける」。次に走ったとき続きから。

■ Macの上に居ないとき（サンドボックス等）
  実測が取れないので **止めない**（ok=True, why="実測できないので素通し"）。
  ここで止めると、Macの外で走る点検まで全部止まる。

戻し方（1行）:
  rm tools/omoi_habadome.py && git checkout -- tools/1155_zunda.py tools/dojisu_jougen.py
"""
import io
import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
LOG = os.path.join(STATUS, "habadome.jsonl")

# ---- しきい値。すべて2026-09-26の固まった実測から置いた ----
SWAP_FREE_MIN_GB = 4.0    # 実測0.59GBで固まった。1.0GBでは遅い
SWAP_USED_PCT_MAX = 70    # 総量が変わっても率で効く
LOAD_RATIO_MAX = 1.5      # 5分ロード÷コア
MEM_AVAIL_MIN_GB = 3.0


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""


def jittai():
    """いまのMacを実測する。取れなかった項目は None のまま返す（推測で埋めない）。"""
    m = {}
    sw = _run(["sysctl", "vm.swapusage"])
    mm = re.search(r"total = ([\d.]+)M\s+used = ([\d.]+)M\s+free = ([\d.]+)M", sw)
    if mm:
        m["swapTotalGB"] = round(float(mm.group(1)) / 1024.0, 2)
        m["swapUsedGB"] = round(float(mm.group(2)) / 1024.0, 2)
        m["swapFreeGB"] = round(float(mm.group(3)) / 1024.0, 2)
        if m["swapTotalGB"] > 0:
            m["swapUsedPct"] = int(round(m["swapUsedGB"] / m["swapTotalGB"] * 100))
    la = re.search(r"\{ ([\d.]+) ([\d.]+) ([\d.]+) \}", _run(["sysctl", "-n", "vm.loadavg"]))
    if la:
        m["load1"], m["load5"], m["load15"] = (float(la.group(i)) for i in (1, 2, 3))
    try:
        m["cores"] = int(_run(["sysctl", "-n", "hw.ncpu"]).strip())
    except Exception:
        m["cores"] = None
    try:
        pagesize = int(_run(["sysctl", "-n", "hw.pagesize"]).strip() or 4096)
        vs = _run(["vm_stat"])
        pages = 0
        for k in ("free", "inactive", "speculative", "purgeable"):
            g = re.search(r"Pages %s:\s+(\d+)" % k, vs)
            if g:
                pages += int(g.group(1))
        if pages:
            m["memAvailGB"] = round(pages * pagesize / 1024.0 ** 3, 2)
    except Exception:
        pass
    if m.get("load5") is not None and m.get("cores"):
        m["loadRatio"] = round(m["load5"] / m["cores"], 2)
    return m


def hashiru_te_ii(m=None):
    """(ok, why) を返す。why は日本語1行。Macの上に居なければ素通し。"""
    m = m if m is not None else jittai()
    if not m or m.get("swapFreeGB") is None and m.get("loadRatio") is None:
        return True, "実測できないので素通し（Macの上に居ない）"

    ng = []
    sf = m.get("swapFreeGB")
    if sf is not None and sf < SWAP_FREE_MIN_GB:
        ng.append("スワップ残り%.2fGB（%.1fGB未満）" % (sf, SWAP_FREE_MIN_GB))
    sp = m.get("swapUsedPct")
    if sp is not None and sp > SWAP_USED_PCT_MAX:
        ng.append("スワップ使用%d%%（%d%%超）" % (sp, SWAP_USED_PCT_MAX))
    lr = m.get("loadRatio")
    if lr is not None and lr > LOAD_RATIO_MAX:
        ng.append("5分ロード比%.2f（%.1f超）" % (lr, LOAD_RATIO_MAX))
    ma = m.get("memAvailGB")
    if ma is not None and ma < MEM_AVAIL_MIN_GB:
        ng.append("空きメモリ%.2fGB（%.1fGB未満）" % (ma, MEM_AVAIL_MIN_GB))

    if ng:
        return False, "重いので止めました：" + "／".join(ng)
    parts = []
    if sf is not None:
        parts.append("スワップ残り%.2fGB" % sf)
    if lr is not None:
        parts.append("5分ロード比%.2f" % lr)
    if ma is not None:
        parts.append("空きメモリ%.2fGB" % ma)
    return True, "走ってよい（" + "／".join(parts) + "）"


def kiroku(who, ok, why, m=None):
    """1行だけ残す。落ちても原因が後から読める形にする。"""
    try:
        os.makedirs(STATUS, exist_ok=True)
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S+0900"), "who": who,
               "ok": bool(ok), "why": why}
        if m:
            rec["実測"] = {k: m.get(k) for k in
                           ("swapFreeGB", "swapUsedPct", "loadRatio", "memAvailGB")}
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def matsu(max_sec=900, kankaku=20, who="?"):
    """静かになるまで待つ。静かになれば True。max_sec 待ってもだめなら False。

    False のとき呼ぶ側がやること: **進捗を保存して素直に抜ける。**
    次に走ったときに続きから再開できるなら、それがいちばん安い止まり方。
    """
    t0 = time.time()
    first = True
    while True:
        m = jittai()
        ok, why = hashiru_te_ii(m)
        if ok:
            if not first:
                kiroku(who, True, "静かになったので再開（%d秒待った）" % int(time.time() - t0), m)
            return True
        if first:
            kiroku(who, False, why, m)
            first = False
        if time.time() - t0 >= max_sec:
            kiroku(who, False, "%d秒待っても重いまま。進捗を保存して退きます（%s）"
                   % (max_sec, why), m)
            return False
        time.sleep(kankaku)


def main():
    m = jittai()
    ok, why = hashiru_te_ii(m)
    print(json.dumps({"ok": ok, "why": why, "実測": m}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
