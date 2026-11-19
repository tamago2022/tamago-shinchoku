#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/shiire_zaiko_kanmon.py ── 仕入れ在庫の関所。「まとめて最後にしていないか」の機械版。

1762号（2026-09-28発生・2026-10-20実装）:
  Obsidian Vault の AI出力/仕入れ/ に「カバー・CM候補」「仕入れ継続」系の
  調査メモが積み上がる一方、本番（joy-relief-station の src/lib/coverGuide.ts）
  への反映（commit・push・公開）が追いついていない実例を、2026-10-20 に実測した。

  実測（2026-10-20）：
    - 仕入れ系メモ：137件
    - 「通過」の語を含むファイル：111件（＝採用候補ありのまま止まっているファイル）
    - 「公開は未実施」等、本番未反映を明記したファイル：21件
  → 調査（研究）だけが増え続け、本番反映が「次回」に持ち越され続ける＝
    まさに「まとめて最後にしている」状態。最後（＝本番）に届かない回が多い。

  ★この関所は、次に新しい「仕入れ継続」ファイルを作る前に走らせる。
    既存の未反映バックログが多いときは、新規調査を追加する前に
    「先に在庫を減らせ」という数字を見せる（強制終了はしない＝exit 0 で
    数字を出すだけ。判断は呼んだ側に委ねる。既存のstop_kanmonのように
    exit 2で止める形は、仕入れという創造的な調査作業には強すぎると判断）。

使い方
    python3 tools/shiire_zaiko_kanmon.py            # 数えて status/public/ へ書く
    python3 tools/shiire_zaiko_kanmon.py --show     # 直近の結果だけ表示
"""
from __future__ import annotations

import datetime
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status", "public")
OUT = os.path.join(ST, "shiire_zaiko.json")

VAULT_CANDIDATES = [
    os.path.expanduser(
        "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain/AI出力/仕入れ"
    ),
]

JST = datetime.timezone(datetime.timedelta(hours=9))

MIKANRYOU_GO = re.compile(r"本番反映(前|時|は未)|coverGuide.*未実施|公開は未実施|未編集")


def now_jst():
    return datetime.datetime.now(JST)


def vault_dir():
    for p in VAULT_CANDIDATES:
        if os.path.isdir(p):
            return p
    return None


def shuukei():
    d = vault_dir()
    if not d:
        return {"ok": False, "naze": "Vaultの仕入れフォルダが見つからない", "atai": None}
    files = sorted(glob.glob(os.path.join(d, "*.md")))
    total = len(files)
    tsuuka_files = 0
    mikanryou_files = []
    for p in files:
        try:
            t = io.open(p, encoding="utf-8").read()
        except Exception:
            continue
        if "通過" in t:
            tsuuka_files += 1
        if MIKANRYOU_GO.search(t):
            mikanryou_files.append(os.path.basename(p))
    atai = {
        "sougaku_file": total,
        "tsuuka_kakunin_file": tsuuka_files,
        "mikanryou_meiji_file": len(mikanryou_files),
        "mikanryou_sample": mikanryou_files[-10:],
    }
    return {"ok": True, "atai": atai}


def main():
    argv = sys.argv[1:]
    if "--show" in argv:
        try:
            print(json.dumps(json.load(io.open(OUT, encoding="utf-8")), ensure_ascii=False, indent=2))
        except Exception as e:
            print("まだ記録がない:", e)
        return 0
    r = shuukei()
    r["checkedAt"] = now_jst().strftime("%Y-%m-%dT%H:%M:%S%z")
    os.makedirs(ST, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
