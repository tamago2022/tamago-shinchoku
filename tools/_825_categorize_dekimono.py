#!/usr/bin/env python3
"""825番：できたもの2 - 既存items(287件)へ category(ページ/曲/レイアウト/実装/仕組み/お金)を機械分類で付与。
削除はしない。既存フィールドはそのまま、category を追加するだけ。1件に1つだけ。迷ったら「実装」。
分類ロジックの正本は tools/dekimono_lib.py の categorize()（新規登録時にもここが使われる）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dekimono_lib import categorize  # noqa: E402

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "status", "dekimono.json")


def main():
    with open(PATH, encoding="utf-8") as f:
        d = json.load(f)
    items = d["items"]
    counts = {}
    for it in items:
        cat = categorize(it.get("title", ""), it.get("what", ""))
        it["category"] = cat
        counts[cat] = counts.get(cat, 0) + 1
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("done", counts, "total", len(items))


if __name__ == "__main__":
    main()
