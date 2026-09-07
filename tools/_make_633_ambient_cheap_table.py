#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件633番：falの安いモデルを表現ごとに試して育てる早見表。
「10〜数十円で良いアンビエント動画が作れるか」の実測結果だけをPNGで描く
（320番と同じ安全な方法＝PIL直接描画、ブラウザ操作・画面録画は使わない）。

出典：status/fal_cost_ledger.json（実測台帳・n=633のレコード）
基準：n=588「花・湖・山のアンビエント動画」たまごさん評価90点・89円（合算）
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
FONT_PATH_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/img"
OUT_PATH = os.path.join(OUT_DIR, "633-ambient-cheap-table.png")
os.makedirs(OUT_DIR, exist_ok=True)

# 表現 / モデル / 単価(実測) / 出来(自己採点、基準=588番90点との比較) / メモ
ROWS = [
    ("微動ループ(基準)", "合算：nano-banana+seedance-2.0/mini+stable-audio-25",
     "89円", "90点(たまごさん評価)", "588番。画像拡張+動画8秒+環境音22秒の3点セット"),
    ("微動ループ・動画のみ", "lightricks/ltx-2.5/image-to-video/fast",
     "9.2円(6秒/720p/無音)", "基準と同等(自己採点・要たまごさん確認)",
     "588番と同一画像・同一意図プロンプトで比較。基準の10分の1の価格"),
    ("微動ループ・動画のみ", "fal-ai/ltx-video-13b-distilled/image-to-video",
     "約30円(5秒/720p)", "自己採点・要たまごさん確認",
     "基準の3分の1の価格。detail_pass無効時の素の実力"),
]

HEADERS = ["表現", "試したモデル", "単価(実測)", "出来", "メモ"]
COL_W = [190, 420, 220, 260, 340]
PAD = 28
ROW_H = 84
HEAD_H = 60
TITLE_H = 110
W = PAD * 2 + sum(COL_W)
H = TITLE_H + HEAD_H + ROW_H * len(ROWS) + PAD * 2

BG = (18, 22, 28)
HEAD_BG = (32, 38, 47)
ROW_BG_A = (26, 32, 40)
ROW_BG_B = (22, 27, 34)
BORDER = (42, 50, 60)
TEXT = (233, 238, 244)
SUB = (159, 216, 255)
GOOD = (140, 220, 160)


def font(size, bold=False):
    path = FONT_PATH_BOLD if bold else FONT_PATH
    return ImageFont.truetype(path, size)


def wrap(draw, text, f, max_w):
    lines = []
    cur = ""
    for ch in text:
        test = cur + ch
        if draw.textlength(test, font=f) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines or [""]


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    f_title = font(28, bold=True)
    f_sub = font(15)
    f_head = font(17, bold=True)
    f_body = font(14)
    f_body_code = font(13)

    d.text((PAD, 22), "10円〜数十円で良いアンビエント動画は作れるか（常設・育てる早見表）", font=f_title, fill=TEXT)
    d.text((PAD, 58), "出典：status/fal_cost_ledger.json（n=633）／基準：n=588 花・湖・山（たまごさん評価90点・89円）", font=f_sub, fill=SUB)
    d.text((PAD, 80), "人物なし・台詞なし・リップシンクなし。同じ画像・同じ意図で比較。", font=f_sub, fill=SUB)

    y = TITLE_H
    x = PAD
    d.rectangle([PAD, y, W - PAD, y + HEAD_H], fill=HEAD_BG, outline=BORDER)
    cx = x
    for i, htext in enumerate(HEADERS):
        d.text((cx + 12, y + HEAD_H / 2 - 11), htext, font=f_head, fill=SUB)
        cx += COL_W[i]
    y += HEAD_H

    for ri, row in enumerate(ROWS):
        row_bg = ROW_BG_A if ri % 2 == 0 else ROW_BG_B
        d.rectangle([PAD, y, W - PAD, y + ROW_H], fill=row_bg, outline=BORDER)
        cx = x
        for ci, cell in enumerate(row):
            f = f_body_code if ci == 1 else f_body
            fill = GOOD if ci == 0 and ri == 0 else TEXT
            lines = wrap(d, cell, f, COL_W[ci] - 24)
            ly = y + 10
            for ln in lines[:4]:
                d.text((cx + 12, ly), ln, font=f, fill=fill)
                ly += 17
            cx += COL_W[ci]
        y += ROW_H

    cx = PAD
    for w_ in COL_W:
        d.line([(cx, TITLE_H), (cx, y)], fill=BORDER, width=1)
        cx += w_
    d.line([(W - PAD, TITLE_H), (W - PAD, y)], fill=BORDER, width=1)

    img.save(OUT_PATH)
    print(OUT_PATH, img.size)


if __name__ == "__main__":
    main()
