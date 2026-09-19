#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
802番（2026-09-14）「できたもの284件→見て嬉しいものだけ・間違っているやつを載せない」対応。

たまごさんの言葉：「281件とか並んでてさ、もう気が遠くなるわけよ。しかも間違えてるやつ。」
→ status/oni_kantoku_log.jsonl（鬼監督・触る検品の結果）と status/dekimono.json の
   items を n番で突き合わせ、直近の判定が "fail" のものだけ verified:false を付ける。
   verified:false は index.html 側（renderDekita）が棚から除外する合図。
   **dekimono.json の行そのものは削除しない**（消さない・記録は残す、という802番の指示どおり）。

冪等：何度実行しても同じ結果になる（verifiedフィールドを都度計算し直すだけ）。
日次の見張りタスクに乗せて再走査すれば、後から付いた検品結果にも追いつける
（record_done() 登録時点ではまだ検品が済んでいないケースのフォロー）。
"""
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from dekimono_lib import DEKI_PATH, ONI_LOG_PATH  # noqa: E402


def load_decisions():
    latest = {}
    try:
        with io.open(ONI_LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                n = row.get("n")
                if not isinstance(n, int):
                    continue
                latest[n] = row.get("decision")  # 後勝ち＝最新
    except Exception:
        pass
    return latest


def main():
    decisions = load_decisions()
    if not os.path.exists(DEKI_PATH):
        print("dekimono.json が無い・何もしない")
        return
    with io.open(DEKI_PATH, encoding="utf-8") as f:
        d = json.load(f)
    items = d.get("items") or []
    newly_hidden = []
    newly_restored = []
    for it in items:
        n = it.get("n")
        dec = decisions.get(n)
        want_visible = dec != "fail"
        had = it.get("verified", True)
        if want_visible != had:
            if want_visible:
                newly_restored.append(n)
            else:
                newly_hidden.append(n)
        it["verified"] = want_visible
    tmp = DEKI_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DEKI_PATH)
    hidden_total = sum(1 for it in items if it.get("verified") is False)
    print("総件数:", len(items))
    print("今回新たに非表示にした番号:", newly_hidden)
    print("今回表示に戻した番号:", newly_restored)
    print("非表示（検品NG）合計:", hidden_total)


if __name__ == "__main__":
    main()
