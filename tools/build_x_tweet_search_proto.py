#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
案件#667: 過去ツイート検索アプリのプロトタイプ生成
たまごさん本人のXアーカイブ(既にDesktopに解凍済み)から tweets.js を読み、
軽量なJSON索引 + 静的HTML検索ページ(share/x-search/)を作る。

材料: ~/Desktop/Xアーカイブ_2026-09-07_本文/data/tweets.js (47,011件)
出力: share/x-search/data.json, share/x-search/index.html
"""
import json
import os
import re
import sys

ARCHIVE = os.path.expanduser("~/Desktop/Xアーカイブ_2026-09-07_本文/data/tweets.js")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "share", "x-search")


def load_tweets():
    with open(ARCHIVE, encoding="utf-8") as f:
        content = f.read()
    idx = content.index("[")
    return json.loads(content[idx:])


def strip_tco(text):
    # t.co短縮リンクは検索の邪魔になるので末尾のURL列だけ軽く削る(本文は残す)
    return text


MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def parse_created_at(s):
    # "Tue Jun 13 22:00:16 +0000 2023" -> "2023-06-13"
    m = re.match(r"\w+ (\w+) (\d+) [\d:]+ \+0000 (\d+)", s)
    if not m:
        return ""
    mon, day, year = m.groups()
    return f"{year}-{MONTHS.get(mon, '01')}-{int(day):02d}"


def main():
    tweets = load_tweets()
    rows = []
    for item in tweets:
        t = item.get("tweet", item)
        full_text = t.get("full_text", "")
        created = parse_created_at(t.get("created_at", ""))
        tid = t.get("id_str") or t.get("id", "")
        fav = int(t.get("favorite_count", 0) or 0)
        rt = int(t.get("retweet_count", 0) or 0)
        is_reply = bool(t.get("in_reply_to_status_id_str"))
        rows.append({
            "id": tid,
            "d": created,
            "t": strip_tco(full_text),
            "f": fav,
            "r": rt,
            "rp": is_reply,
        })
    # 新しい順
    rows.sort(key=lambda r: r["d"], reverse=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    data_path = os.path.join(OUT_DIR, "data.json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(data_path)
    print(f"件数: {len(rows)}")
    print(f"data.json サイズ: {size/1024/1024:.2f} MB -> {data_path}")

    # 日付範囲
    dates = [r["d"] for r in rows if r["d"]]
    if dates:
        print(f"日付範囲: {min(dates)} 〜 {max(dates)}")

    return rows


if __name__ == "__main__":
    main()
