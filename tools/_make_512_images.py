#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""512番の確認ページ用の内容早見図を作る（実機スクリーンショットではなく、内容を要約した図）。"""
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

W, H = 900, 500
BG = (26, 32, 48)
INK = (233, 226, 211)
SUB = (154, 161, 173)
CARD = (33, 40, 57)


def draw_before():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 40), "朗読の道具（Before）", font=get_font(28), fill=INK)
    d.text((40, 90), "iPhone標準の読み上げ・ずんだもん → 機械っぽくて、寝る前に聴く気になれない", font=get_font(18), fill=SUB)
    d.rectangle([40, 150, 860, 250], outline=(70, 80, 100), width=2)
    d.text((60, 180), "円卓ノート(10〜20分)は、目で読むにはただ長いだけ", font=get_font(18), fill=SUB)
    d.rectangle([40, 280, 860, 380], outline=(70, 80, 100), width=2)
    d.text((60, 310), "iPhoneで寝ながら連続再生できる音声は、この時点で存在しない", font=get_font(18), fill=SUB)
    img.save(os.path.join(OUT_DIR, "512-before.png"))


def draw_after():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 32), "たまごの寝る前ノート（After・本番公開済み）", font=get_font(26), fill=INK)
    items = [
        ("円卓：AIソロプレナーと『昔は人の仕事だったこと』", "15:48 ・ AivisSpeech（無料・人物ごとに声を変更）"),
        ("円卓：AIが壊すのは修行期間、才能を証明するまでの10年", "6:03 ・ AivisSpeech（無料・人物ごとに声を変更）"),
        ("聴き比べ：① AivisSpeech ② Style-Bert-VITS2 ③ ElevenLabs", "同じ文章・3種類・押したら鳴る"),
    ]
    y = 90
    for title, sub in items:
        d.rounded_rectangle([40, y, 860, y + 90], radius=10, fill=CARD)
        d.text((60, y + 16), title, font=get_font(19), fill=INK)
        d.text((60, y + 50), sub, font=get_font(16), fill=SUB)
        d.ellipse([800, y + 30, 830, y + 60], outline=INK, width=2)
        d.polygon([(810, y + 38), (810, y + 52), (822, y + 45)], fill=INK)
        y += 110
    d.text((40, y + 10), "iPhone「ポッドキャスト」アプリにRSSのURLを登録 → ロック画面操作・連続再生・スリープタイマー対応", font=get_font(16), fill=SUB)
    img.save(os.path.join(OUT_DIR, "512-after.png"))


if __name__ == "__main__":
    draw_before()
    draw_after()
    print("done")
