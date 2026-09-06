#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案件320番：fal早見表の確認ページ用に、教材ファイル一式MODEL_TABLE.md（2026-08-13検証・正本）の
11機種一覧テーブルをPNG画像としてレンダリングする。ブラウザ操作・画面録画は使わず、PILで直接描く
（413番・403番と同じ安全な方法）。有料API・fal生成は一切実行しない。

出典（読み取り専用参照）：
- Vault: AI出力/円卓EP0_v004/fal早見表.md「【2026-09-06追記】正本を『教材ファイル一式』へ切替」節
- Vault: AI出力/falの教科書_教材ファイル一式/fal-kyokasho/MODEL_TABLE.md（2026-08-13検証）
"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
FONT_PATH_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/img"
OUT_PATH = os.path.join(OUT_DIR, "320-fal-model-table.png")
os.makedirs(OUT_DIR, exist_ok=True)

# 役割 / model_id / 単価 / 事故防止メモ（教材ファイルMODEL_TABLE.md正本の転記・事実のみ）
ROWS = [
    ("画像・標準機", "fal-ai/nano-banana", "$0.04/枚", "—"),
    ("画像編集・標準機", "fal-ai/nano-banana/edit", "$0.04/枚", "—"),
    ("画像・新世代機", "fal-ai/nano-banana-2/edit", "$0.08/枚（2K×1.5・4K×2・512px×0.75）", "—"),
    ("画像・新世代機（廉価）", "google/nano-banana-2-lite/edit", "目安$0.03〜0.05/枚",
     "/editは実在（実発注7秒で動作確認済み）"),
    ("画像・高級機（文字）", "openai/gpt-image-2/edit", "high $0.219／medium $0.061／low $0.015",
     "旧窓口fal-ai/gpt-image-2/editはflat $1.00/回。新窓口へ移行推奨"),
    ("動画・標準機", "bytedance/seedance-2.0/mini/image-to-video", "約$0.40/本(5秒)",
     "fal-ai/を頭に付けると404"),
    ("動画・新世代機", "bytedance/seedance-2.5/reference-to-video", "$0.0214/1Kトークン",
     "image_urlsが複数形（書式注意）"),
    ("TTS・標準機", "fal-ai/minimax/speech-02-hd", "$0.10/1000文字", "—"),
    ("TTS・多表現機", "fal-ai/elevenlabs/tts/eleven-v3", "$0.10/1000文字", "声IDのうろ覚えは422で落ちる"),
    ("音楽", "fal-ai/stable-audio-25/text-to-audio", "$0.05/回",
     "尺は`seconds_total`。違う名前は黙って無視され190秒が返る"),
    ("効果音(SE)", "cassetteai/sound-effects-generator", "$0.02/回", "1秒のSEに85秒かかった実績あり"),
    ("3D", "tripo3d/tripo/v2.5/image-to-3d", "$0.40/回", "glbで返る"),
    ("LLM", "fal-ai/any-llm", "$0.001/回", "日本語はgemini系を指定"),
]

HEADERS = ["役割", "model_id", "単価", "事故防止メモ"]
COL_W = [190, 420, 300, 460]
PAD = 28
ROW_H = 56
HEAD_H = 60
TITLE_H = 96
W = PAD * 2 + sum(COL_W)
H = TITLE_H + HEAD_H + ROW_H * len(ROWS) + PAD * 2

BG = (18, 22, 28)
HEAD_BG = (32, 38, 47)
ROW_BG_A = (26, 32, 40)
ROW_BG_B = (22, 27, 34)
BORDER = (42, 50, 60)
TEXT = (233, 238, 244)
SUB = (159, 216, 255)
WARN = (244, 192, 95)


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

    f_title = font(30, bold=True)
    f_sub = font(16)
    f_head = font(18, bold=True)
    f_body = font(15)
    f_body_code = font(14)

    d.text((PAD, 24), "fal 機種・料金・早見表（13機種・教材ファイル正本）", font=f_title, fill=TEXT)
    d.text((PAD, 62), "出典：MODEL_TABLE.md（2026-08-13検証・教材ファイル一式）", font=f_sub, fill=SUB)

    y = TITLE_H
    x = PAD
    # ヘッダー行
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
            fill = WARN if (ci == 3 and cell != "—") else TEXT
            lines = wrap(d, cell, f, COL_W[ci] - 24)
            ly = y + ROW_H / 2 - (len(lines) * 18) / 2
            for ln in lines[:2]:
                d.text((cx + 12, ly), ln, font=f, fill=fill)
                ly += 18
            cx += COL_W[ci]
        y += ROW_H

    # 縦罫線
    cx = PAD
    for w_ in COL_W:
        d.line([(cx, TITLE_H), (cx, y)], fill=BORDER, width=1)
        cx += w_
    d.line([(W - PAD, TITLE_H), (W - PAD, y)], fill=BORDER, width=1)

    img.save(OUT_PATH)
    print(OUT_PATH, img.size)


if __name__ == "__main__":
    main()
