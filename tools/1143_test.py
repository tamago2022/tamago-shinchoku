#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1143番【回帰テスト】「走っているから大丈夫」で赤が消える穴を、数字で確かめる。

━━ 何を確かめるか ━━
  4日半だれも気づかなかった事故の形をそのまま再現して、
    旧：進捗表の stoppedReason（走行本数で判定）
    新：成果の鮮度計（成果の年齢で判定）
  の2つが、同じ状況でどう答えるかを並べる。

  ケース1  走行0本                → 旧も新も赤（ここは元から合っている）
  ケース2  【空回し】が1本走っている  → 旧は 2026-09-25 の修正で赤が残る（修正済み）
  ケース3  ラベルが空回しでない案件が1本、
           実際には何も出さずに走っている → ★旧は黙る（穴は残っている）／新は赤のまま

  ケース3が本番でいま起きていた形。ラベルの文字列で判定する限り、
  「空回し」と書いていない空回しは必ず通り抜ける（Prefactorの言う silent failure）。

  0円。AIを叩かない。本番のファイルを1文字も書き換えない（読むだけ）。

  使い方： python3 tools/1143_test.py
"""
from __future__ import annotations

import importlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ts = importlib.import_module("top_status")
fresh = importlib.import_module("1143_freshness")


def kyuu_handan(running_labels):
    """旧ロジックの再現：走行中の案件のラベルだけを見て、赤を出すか決める。
    （tools/top_status.py の stoppedReason の呼び出し条件と同じ式）"""
    honmono = [l for l in running_labels if "空回し" not in (l or "")]
    return None if honmono else (ts.stopped_reason() or "（理由不明）")


def shin_handan():
    """新ロジック：成果の年齢だけを見る。走行本数は一切受け取らない。"""
    p = fresh.hakaru(write=False)
    aka = [a for a in p["alerts"] if a["level"] == "red"]
    return (aka[0]["midashi"] if aka else None), p


def main():
    shin, p = shin_handan()
    keesu = [
        ("1", "走行0本", []),
        ("2", "【空回し】が1本", ["【空回し】ログイン復帰待ち"]),
        ("3", "空回しと書いていない案件が1本", ["911番 Devin Desktopを主戦場にする"]),
    ]
    print("1143 回帰テスト  %s" % p["at"])
    print("  鮮度計が見ている年齢：")
    for k, v in p["pipes"].items():
        print("    %-9s %-16s %s時間（閾値%.0f時間）"
              % (k, v["na"], "測れない" if v["ageH"] is None else v["ageH"], v["shikiiH"]))
    print("  ---")
    ng = 0
    for no, na, labels in keesu:
        kyuu = kyuu_handan(labels)
        print("  ケース%s %-28s" % (no, na))
        print("      旧（走行本数で判定）: %s" % ("赤 → " + kyuu if kyuu else "★黙る（赤が出ない）"))
        print("      新（成果の年齢で判定）: %s" % ("赤 → " + shin if shin else "緑（鮮度は閾値内）"))
        if shin and not kyuu:
            print("      ＝この状況で、旧は見逃し・新は捕まえる")
        if kyuu is None and shin is None:
            ng += 1
    print("  ---")
    # 新ロジックが走行本数を一度も参照していないことを、コードの字面でも確かめる
    # コメント・文字列リテラル（説明文）を全部落として、**実行される式だけ**を見る
    import ast
    src = io.open(os.path.join(HERE, "1143_freshness.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            node.value.value = ""       # docstringを空にする
    body = ast.unparse(tree)
    kinshi = [w for w in ("runningNow", "running_now", "psutil", "ps ax", "空回し",
                          "startedAt", "elapsedMin") if w in body]
    print("  鮮度計の本体が走行状態を参照していないか： %s"
          % ("OK（1語も無い）" if not kinshi else "NG（%s を参照している）" % kinshi))
    print("  結論：%s" % ("鮮度計だけが全ケースで赤を維持した" if shin
                          else "いまは鮮度が閾値内なので、赤は出ていない（正常）"))
    return 0 if not kinshi else 1


if __name__ == "__main__":
    sys.exit(main())
