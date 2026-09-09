#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20番「走行中が空いたら自動で次を発車させる」の実績を1枚の棒グラフにする。

2026-09-06/09-06 鬼監督差し戻し：確認ページに<img>が1つも無くFAIL（img_count=0）。
このスクリプトは status/auto_launch.log から直近24時間の「🚀 自動発車」件数を
1時間刻みで集計し、PNGへ書き出す（perf_watch_chart.py と同じPIL方式）。

使い方:
  python3 tools/auto_launch_chart.py
"""
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

REPO = "/Users/mac/Desktop/tamago-shinchoku"
LOG = os.path.join(REPO, "status", "auto_launch.log")
OUT = os.path.join(REPO, "share", "check", "img", "20-auto-launch-trend.png")


def read_launches(hours=24):
    now = datetime.now()
    cutoff = now - timedelta(hours=hours)
    # 直近hours時間を1時間刻みのバケツに分ける（空の時間も0として必ず出す）
    buckets = OrderedDict()
    t = cutoff.replace(minute=0, second=0, microsecond=0)
    while t <= now:
        buckets[t.strftime("%m-%d %H時")] = 0
        t += timedelta(hours=1)
    total = 0
    if not os.path.exists(LOG):
        return buckets, total
    with open(LOG, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if "🚀 自動発車" not in line:
                continue
            m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}):\d{2}:\d{2}", line)
            if not m:
                continue
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H")
            if ts < cutoff or ts > now:
                continue
            key = ts.strftime("%m-%d %H時")
            if key in buckets:
                buckets[key] += 1
                total += 1
    return buckets, total


def main():
    buckets, total = read_launches(24)
    labels = list(buckets.keys())
    values = list(buckets.values())
    max_v = max(values) if values else 1
    max_v = max(max_v, 1)

    W, H = 720, 300
    img = Image.new("RGB", (W, H), (244, 239, 228))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 15)
        font_small = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 10)
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    draw.text(
        (14, 10),
        "#20 自動発車の実績（直近24時間・1時間ごとの着火回数）合計%d回" % total,
        fill=(42, 42, 42),
        font=font,
    )

    margin_l, margin_r, margin_t, margin_b = 40, 16, 44, 56
    plot_w = W - margin_l - margin_r
    plot_h = H - margin_t - margin_b

    draw.line([(margin_l, margin_t), (margin_l, margin_t + plot_h)], fill=(122, 117, 104))
    draw.line(
        [(margin_l, margin_t + plot_h), (margin_l + plot_w, margin_t + plot_h)],
        fill=(122, 117, 104),
    )
    draw.text((6, margin_t - 4), "%d" % max_v, fill=(122, 117, 104), font=font_small)
    draw.text((6, margin_t + plot_h - 6), "0", fill=(122, 117, 104), font=font_small)

    n = len(labels)
    bar_w = plot_w / max(n, 1) * 0.7
    step_x = plot_w / max(n, 1)
    color = (58, 122, 82)
    for i, (label, v) in enumerate(zip(labels, values)):
        x0 = margin_l + i * step_x + (step_x - bar_w) / 2
        x1 = x0 + bar_w
        y1 = margin_t + plot_h
        y0 = y1 - (v / max_v) * plot_h if v else y1
        if v:
            draw.rectangle([x0, y0, x1, y1], fill=color)
            draw.text((x0, y0 - 14), str(v), fill=(42, 42, 42), font=font_small)
        # ラベルは間引く（込み合うので3本おき）
        if i % 3 == 0 or i == n - 1:
            draw.text((margin_l + i * step_x - 2, margin_t + plot_h + 8), label,
                       fill=(122, 117, 104), font=font_small)

    draw.text(
        (14, H - 16),
        "出典: status/auto_launch.log（Mac常駐・実ログ集計。人が手で書いた数字ではない）",
        fill=(122, 117, 104),
        font=font_small,
    )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print("[auto_launch_chart] 直近24時間・%d時間分・合計%d回を書き出しました: %s" % (len(labels), total, OUT))


if __name__ == "__main__":
    main()
