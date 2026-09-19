#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""615番の確認ページ用の内容早見図を作る（実機スクリーンショットではなく、内容を要約した図）。
実データ（本番のepisodes.json / index.html / 実行ログ）に基づく。"""
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

W, H = 900, 560
BG = (26, 32, 48)
INK = (233, 226, 211)
SUB = (154, 161, 173)
CARD = (33, 40, 57)
OK = (120, 200, 150)


def draw_before():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 40), "朗読の道具（Before・9/6時点）", font=get_font(26), fill=INK)
    d.text((40, 88), "たまごさんの言葉：「どのページを読んでるんだいって感じ」「どこを読んでるのか分からなかった」", font=get_font(16), fill=SUB)
    items = [
        "音声の題名が無く、何のノートを読んでいるか聴くまで分からない",
        "URL・出典・#タグ・コードブロックの記号までそのまま読み上げてしまう",
        "新しいノートを渡す手段が無い（Macで手打ちするしかない）",
        "声・速さを選べない（1種類固定）",
    ]
    y = 140
    for it in items:
        d.rounded_rectangle([40, y, 860, y + 78], radius=10, fill=CARD)
        d.text((60, y + 26), "・" + it, font=get_font(18), fill=SUB)
        y += 96
    img.save(os.path.join(OUT_DIR, "615-before.png"))


def draw_after():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 30), "朗読の道具（After・本番反映・実行検証済み）", font=get_font(24), fill=INK)
    items = [
        ("① どのノートか分かる", "音声冒頭で題名を1回読む／本番カードに題名＋「元ノートを開く」リンク実装・実測済み"),
        ("② URLは読まない", "実測: 382字→175字（URL・コードブロック・表罫線・#タグ除去）。リンクは文字だけ読む"),
        ("③ URL/パスを渡すだけで音声化", "CLI・Obsidianの「▶読み上げ」ボタン起動を実際に発火→自動でPodcastへ公開まで確認"),
        ("④ 声を選べる", "AivisSpeech 10種の声を一覧確認。--voiceで1回選ぶと記憶。--speedで速さも3段階"),
    ]
    y = 84
    for title, sub in items:
        d.rounded_rectangle([40, y, 860, y + 96], radius=10, fill=CARD)
        d.text((60, y + 14), title, font=get_font(19), fill=OK)
        d.text((60, y + 48), sub, font=get_font(15), fill=SUB)
        y += 114
    d.text((40, y + 10), "本番: tamago2022.github.io/tamago-shinchoku/share/podcast/", font=get_font(15), fill=SUB)
    img.save(os.path.join(OUT_DIR, "615-after.png"))


if __name__ == "__main__":
    draw_before()
    draw_after()
    print("done")
