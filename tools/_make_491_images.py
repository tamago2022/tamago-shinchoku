#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""491番(2回目・検品対応)の確認ページ用の内容早見図を作る（実機スクリーンショットではなく、
実測データを要約した図）。前回(1回目)の画像は実測と食い違っていたため作り直す。"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/img"
os.makedirs(OUT_DIR, exist_ok=True)

FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def get_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


W, H = 1000, 460
BG = (26, 32, 48)
INK = (233, 226, 211)
SUB = (154, 161, 173)
CARD = (33, 40, 57)
BAD = (214, 118, 108)
GOOD = (120, 190, 140)


def draw_before():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 32), "検品ではねられた時点（1回目・09-06 20:47）", font=get_font(24), fill=INK)
    rows = [
        ("見張り対象の作業場", "旧2か所だけ（joy-relief-station/.worktrees・.claude/worktrees）", True),
        ("新しい主置き場（AI作業/.worktrees）", "監視から漏れていた（実測21件・約1.6GBが野放し）", True),
        ("確認ページの主張", "「disk_guardian.log 20:23まで記録継続」", False),
        ("main(GitHub)に実際に有るログ", "15:12で停止・06:17の1回しかコミットされていない", True),
        ("候補件数の表記", "本文18件／確認表17件で不一致", True),
    ]
    y = 90
    for label, val, bad in rows:
        d.rounded_rectangle([40, y, 960, y + 62], radius=8, fill=CARD)
        d.text((56, y + 10), label, font=get_font(17), fill=INK)
        d.text((56, y + 34), val, font=get_font(15), fill=(BAD if bad else SUB))
        y += 72
    img.save(os.path.join(OUT_DIR, "491-before.png"))


def draw_after():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 30), "直した後（2回目・main合流・実測確認）", font=get_font(24), fill=INK)
    rows = [
        ("見張り対象の作業場", "新しい主置き場(AI作業/.worktrees)を追加。3か所を監視", True),
        ("実測で確認", "AI作業/.worktrees/task465-related-fix/node_modules を候補として検出", True),
        ("ログ/候補一覧のpush", "5分おきの自動push対象に追加＝以後は人手なしで継続反映", True),
        ("main(GitHub)の実物", "disk_guardian.log と disk_candidates.json、同時刻(20:53:06)で一致", True),
        ("いまの空き / 候補件数", "35.9GB（安全域） / 19件・約1MB", True),
    ]
    y = 88
    for label, val, ok in rows:
        d.rounded_rectangle([40, y, 960, y + 62], radius=8, fill=CARD)
        d.text((56, y + 10), label, font=get_font(17), fill=INK)
        d.text((56, y + 34), val, font=get_font(15), fill=(GOOD if ok else SUB))
        y += 72
    img.save(os.path.join(OUT_DIR, "491-after.png"))


if __name__ == "__main__":
    draw_before()
    draw_after()
    print("done")
