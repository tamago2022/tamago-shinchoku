#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""776番「心臓が止まっても人を起こさずに復活する形にする」の実測証拠を作る。

やること：わざと心臓(heartbeat.sh)をkillした実験のタイムラインを、
status/heartbeat.log の実測行から抽出し、外部ライブラリ無しの軽量SVGで描く
（tools/disk_trend.py と同じ思想：文字列だけで描く。依存を増やさない）。

出力：share/check/img/776-heartbeat-selftest.svg
"""
import io
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG_PATH = os.path.join(REPO, "status", "heartbeat.log")
OUT_SVG = os.path.join(REPO, "share", "check", "img", "776-heartbeat-selftest.svg")

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+)$")


def load_lines(path=LOG_PATH):
    out = []
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = LINE_RE.match(line.rstrip("\n"))
            if m:
                out.append((m.group(1), m.group(2)))
    return out


def find_events(lines, since_str):
    """since_str（実測開始のkillログの時刻文字列）以降のイベントだけを抜き出す。"""
    events = []
    started = False
    for ts, msg in lines:
        if not started:
            if ts == since_str:
                started = True
                events.append((ts, "🧪 意図的にkillした（実測開始）"))
            continue
        if "起動しました" in msg or "居ないと判定" in msg or "詰まっている" in msg or "動いています" in msg or "🚨" in msg:
            events.append((ts, msg))
        if "起動しました" in msg:
            break  # 復活を確認したら実験区間としてはここで打ち切る
    return events


def render_svg(events, out_path=OUT_SVG):
    W, H = 820, 46 + 40 * max(1, len(events))
    pad_l, pad_t = 170, 30
    parts = []
    parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="sans-serif">' % (W, H, W, H))
    parts.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H))
    parts.append(
        '<text x="16" y="20" font-size="14" fill="#111" font-weight="bold">'
        '776番 実測：心臓をわざと殺して自動で復活するかを見た記録</text>')
    y = pad_t + 10
    for i, (ts, msg) in enumerate(events):
        color = "#ef4444" if ("kill" in msg or "詰まって" in msg or "🚨" in msg) else (
            "#16a34a" if "起動しました" in msg else "#6b7280")
        dotcolor = color
        parts.append('<circle cx="20" cy="%d" r="6" fill="%s"/>' % (y, dotcolor))
        if i < len(events) - 1:
            parts.append('<line x1="20" y1="%d" x2="20" y2="%d" stroke="#d1d5db" stroke-width="2"/>'
                          % (y + 6, y + 40))
        parts.append('<text x="40" y="%d" font-size="12" fill="#111">%s</text>' % (y + 4, ts))
        safe_msg = (msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        parts.append('<text x="%d" y="%d" font-size="12" fill="%s">%s</text>'
                      % (pad_l, y + 4, color, safe_msg[:70]))
        y += 40
    parts.append("</svg>")
    svg = "\n".join(parts)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path


def main():
    since_str = sys.argv[1] if len(sys.argv) > 1 else None
    if not since_str:
        print("使い方: python3 tools/_776_heartbeat_selftest_chart.py 'YYYY-MM-DD HH:MM:SS'")
        return 1
    lines = load_lines()
    events = find_events(lines, since_str)
    if not events:
        print("実験開始行が見つかりませんでした: %s" % since_str)
        return 1
    out = render_svg(events)
    print("書きました: %s（イベント%d件）" % (out, len(events)))
    for ts, msg in events:
        print(" - %s %s" % (ts, msg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
