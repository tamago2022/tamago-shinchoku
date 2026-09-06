#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""413番の確認ページ用に、dispatch_outbox.jsonlの実データをテキストプレビュー画像として書き出す。
ブラウザ操作・画面録画は使わず、PILでテキストを直接レンダリングする（音も鳴らず、
画面も奪わない、403番と同じ安全な方法）。
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/PingFang.ttc"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/img"
os.makedirs(OUT_DIR, exist_ok=True)

W = 1000
PAD = 36
LINE_H = 32


def font(size, bold=False):
    idx = 1 if bold else 0
    try:
        return ImageFont.truetype(FONT_PATH, size, index=idx)
    except Exception:
        return ImageFont.truetype(FONT_PATH, size)


def wrap(draw, text, f, max_w):
    lines = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue
        cur = ""
        for ch in raw_line:
            test = cur + ch
            if draw.textlength(test, font=f) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur = test
        lines.append(cur)
    return lines


def render(title, blocks, out_path, bg=(255, 255, 255)):
    tmp = Image.new("RGB", (W, 100), bg)
    d = ImageDraw.Draw(tmp)
    f_title = font(28, bold=True)
    f_head = font(20, bold=True)
    f_body = font(18)

    max_w = W - PAD * 2
    all_lines = []
    for t in wrap(d, title, f_title, max_w):
        all_lines.append((t, f_title, (30, 30, 30)))
    all_lines.append(("", f_body, (0, 0, 0)))

    for heading, body in blocks:
        if heading:
            for hl in wrap(d, heading, f_head, max_w):
                all_lines.append((hl, f_head, (138, 90, 30)))
        for bl in wrap(d, body, f_body, max_w):
            all_lines.append((bl, f_body, (20, 20, 20)))
        all_lines.append(("", f_body, (0, 0, 0)))

    height = PAD * 2 + len(all_lines) * LINE_H
    img = Image.new("RGB", (W, height), bg)
    dd = ImageDraw.Draw(img)
    y = PAD
    for text, f, color in all_lines:
        dd.text((PAD, y), text, font=f, fill=color)
        y += LINE_H
    img.save(out_path)
    print("saved:", out_path, img.size)


# --- before: 実装前の状態（このファイルは存在しなかった） ---
render(
    "413番 実装前：status/dispatch_outbox.jsonl は存在しなかった",
    [
        (
            "困っていたこと",
            "子セッションが3時間で仕事を終えても、それを店主(Dispatch)へ\n"
            "自動で伝える道が無かった。完了報告はセッションの中で\n"
            "止まったままで、誰かが見に行かない限り気づけなかった。",
        ),
        (
            "実装前のファイル一覧（statusフォルダにdispatch_outbox.jsonlが無い）",
            "status/queue.json\nstatus/whiteboard.json\nstatus/health.json\n"
            "status/history.jsonl\n（dispatch_outbox.jsonl は存在しない）",
        ),
    ],
    os.path.join(OUT_DIR, "413-before.png"),
)

# --- after: 実データ（52行が実際に自動追記されている） ---
lines = open(
    "/Users/mac/Desktop/tamago-shinchoku/status/dispatch_outbox.jsonl", encoding="utf-8"
).read().strip().split("\n")
total = len(lines)
recent = lines[-5:]

recent_text_lines = []
for l in recent:
    d = json.loads(l)
    ok = "成功" if d.get("ok") else "失敗"
    recent_text_lines.append(
        "%s  n=%s  %s\n  %s ・ 所要%s分 ・ %s"
        % (
            d.get("ts", ""),
            d.get("n", ""),
            (d.get("title", "") or "")[:36],
            ok,
            d.get("elapsedMin", "?"),
            d.get("ts", ""),
        )
    )

render(
    "413番 実装後：status/dispatch_outbox.jsonl に実際に%d件が自動で溜まっている" % total,
    [
        (
            "本番ファイルの中身（末尾5件・そのまま抜粋）",
            "\n\n".join(recent_text_lines),
        ),
        (
            "件数",
            "合計 %d 行。子セッションが完了するたびに tools/auto_launcher.py の\n"
            "append_outbox() が自動で1行ずつ追記している（テストではなく本番運用の実績）。"
            % total,
        ),
    ],
    os.path.join(OUT_DIR, "413-after.png"),
)
