#!/usr/bin/env python3
"""
429番：軽さ見張り。status/perf_history.jsonl から直近7日のLCP推移を
小さなPNGにして share/check/img/429-lcp-trend.png へ書き出す（進捗表に貼るための画像）。

使い方：
  python3 tools/perf_watch_chart.py
"""
import json
import os
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont

REPO = "/Users/mac/Desktop/tamago-shinchoku"
HISTORY = os.path.join(REPO, "status", "perf_history.jsonl")
OUT = os.path.join(REPO, "share", "check", "img", "429-lcp-trend.png")

PAGE_LABELS = {"home": "トップ", "world_music": "世界の音楽", "cover_guide": "カバーガイド"}
COLORS = {"home": (196, 72, 58), "world_music": (58, 95, 122), "cover_guide": (58, 122, 82)}


def read_history():
    if not os.path.exists(HISTORY):
        return []
    rows = []
    with open(HISTORY, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def main():
    rows = read_history()
    # 日付ごと・ページごとに「その日最後の実測」を採用する（--forceで複数回計測した日もあるため）。
    by_date_page = {}
    for r in rows:
        if r.get("lcp_ms") is None:
            continue
        key = (r.get("date"), r.get("key"))
        by_date_page[key] = r  # 後勝ち＝末尾ほど新しい前提（appendのみのファイルなので順序は時系列）

    dates = sorted({d for (d, _p) in by_date_page.keys()})[-7:]  # 直近7日分だけ

    W, H = 640, 260
    img = Image.new("RGB", (W, H), (244, 239, 228))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 14)
        font_small = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 12)
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    draw.text((14, 10), "本番3ページ LCP推移（直近7日・単位ms）", fill=(42, 42, 42), font=font)

    margin_l, margin_r, margin_t, margin_b = 50, 20, 40, 40
    plot_w = W - margin_l - margin_r
    plot_h = H - margin_t - margin_b

    if not dates:
        draw.text((14, 60), "実測データがまだありません（初回計測待ち）", fill=(122, 117, 104), font=font)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        img.save(OUT)
        print(f"[perf_watch_chart] データ0件のため空グラフを書き出しました: {OUT}")
        return

    all_vals = [by_date_page[(d, p)]["lcp_ms"] for (d, p) in by_date_page if d in dates]
    max_v = max(all_vals) if all_vals else 1000
    max_v = max(max_v, 1000)

    # 軸
    draw.line([(margin_l, margin_t), (margin_l, margin_t + plot_h)], fill=(122, 117, 104))
    draw.line(
        [(margin_l, margin_t + plot_h), (margin_l + plot_w, margin_t + plot_h)],
        fill=(122, 117, 104),
    )
    draw.text((margin_l - 46, margin_t - 4), f"{max_v}ms", fill=(122, 117, 104), font=font_small)
    draw.text((margin_l - 30, margin_t + plot_h - 6), "0", fill=(122, 117, 104), font=font_small)

    n = len(dates)
    step_x = plot_w / max(n - 1, 1)

    for key, color in COLORS.items():
        points = []
        for i, d in enumerate(dates):
            row = by_date_page.get((d, key))
            if row is None:
                continue
            x = margin_l + i * step_x
            y = margin_t + plot_h - (row["lcp_ms"] / max_v) * plot_h
            points.append((x, y))
        if len(points) >= 2:
            draw.line(points, fill=color, width=3)
        for x, y in points:
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)

    for i, d in enumerate(dates):
        x = margin_l + i * step_x
        draw.text((x - 20, margin_t + plot_h + 8), d[5:], fill=(122, 117, 104), font=font_small)

    legend_x = margin_l
    legend_y = H - 18
    for key, color in COLORS.items():
        draw.ellipse([legend_x, legend_y, legend_x + 8, legend_y + 8], fill=color)
        draw.text((legend_x + 12, legend_y - 4), PAGE_LABELS.get(key, key), fill=(42, 42, 42), font=font_small)
        legend_x += 130

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(f"[perf_watch_chart] {len(dates)}日分・{len(all_vals)}点を書き出しました: {OUT}")


if __name__ == "__main__":
    main()
