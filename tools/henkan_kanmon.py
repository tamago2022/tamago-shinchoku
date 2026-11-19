#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/henkan_kanmon.py ── 「変換できないまま保存したルールは、必ずもう一度言わせることになる」の実測道具（1694号）。

たまごさんがスマホから足した一言（1694号）をそのまま解釈すると、
tools/session_preamble.md に積まれている枷（番号付きルール）は、
文章だけで終わっているものと、機械の関所（tools/配下の実行ファイル）に
変換済みのものが混ざっている。前者は何度でも同じ指摘を言わせることになる
（このファイル自身の中にも「枷8」「枷17」「枷18」のように、まさに
「もう一度言わせた」経緯が書かれている）。

★この道具がやること（これだけ）
  session_preamble.md の「### N. タイトル」を1枷として数え、
  本文中に tools/ か scripts/ 配下の実行ファイル（.py .mjs .js .ts .sh 等）への
  参照があるか＝「変換済み」、無ければ「未変換（文章だけ）」と判定する。
  件数を数えて記録するだけで、新しい枷を足す動作そのものは止めない
  （既存の1184号・original関所と役割がかぶらないようにするため）。

使い方
    python3 tools/henkan_kanmon.py --check     # 数えて status/henkan_kanmon.json に保存
    python3 tools/henkan_kanmon.py --self-test # 自己試験（ファイルを書き換えない）
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PREAMBLE = os.path.join(HERE, "session_preamble.md")
OUT = os.path.join(REPO, "status", "henkan_kanmon.json")

JST = datetime.timezone(datetime.timedelta(hours=9))

_KASE_HEADER = re.compile(r"^###\s*(\d+)\.\s*(.+?)\s*$", re.M)
_TOOL_REF = re.compile(
    r"(?:tools|scripts)/[\w\-./]+\.(?:py|mjs|cjs|js|ts|tsx|sh|bash)", re.I
)


def scan(text):
    """枷ごとに「変換済み（関所あり）」か「未変換（文章だけ）」かを数える。"""
    heads = list(_KASE_HEADER.finditer(text))
    items = []
    for i, m in enumerate(heads):
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        refs = sorted(set(_TOOL_REF.findall(body)))
        items.append({
            "ban": m.group(1),
            "title": m.group(2).strip(),
            "henkan_sumi": bool(refs),
            "kansho": refs[:5],
        })
    converted = [x for x in items if x["henkan_sumi"]]
    unconverted = [x for x in items if not x["henkan_sumi"]]
    return {
        "total": len(items),
        "henkan_sumi": len(converted),
        "mi_henkan": len(unconverted),
        "mi_henkan_list": [{"ban": x["ban"], "title": x["title"]} for x in unconverted],
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        sample = (
            "### 1. 例あり\n- 本文 `tools/dummy_kanmon.py` を使う\n\n"
            "### 2. 例なし\n- 本文だけで終わる枷\n"
        )
        r = scan(sample)
        ok = r["total"] == 2 and r["henkan_sumi"] == 1 and r["mi_henkan"] == 1
        print("HENKAN_KANMON_SELFTEST: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    try:
        text = io.open(PREAMBLE, encoding="utf-8").read()
    except Exception as e:
        print("session_preamble.mdが読めません: %s" % e, file=sys.stderr)
        return 1

    result = scan(text)
    result["checkedAt"] = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

    if args.check:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with io.open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(json.dumps({
            "total": result["total"],
            "henkan_sumi": result["henkan_sumi"],
            "mi_henkan": result["mi_henkan"],
        }, ensure_ascii=False))
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
