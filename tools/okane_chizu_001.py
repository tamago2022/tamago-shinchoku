#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
お金の流れ・一枚地図 #001
出典：行政事業レビュー（RSシステム）事業ページ。数字は一次資料のまま。
断定しない。質問の形で終わる。
"""
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1500, 2120
KINARI = (237, 230, 214)
SUMI = (34, 48, 74)
SHU = (193, 68, 46)
USU = (34, 48, 74, 38)

SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"


def f(size, bold=False):
    return ImageFont.truetype(SERIF_B if bold else SERIF, size)


def tracked(d, xy, text, font, fill, tracking=0, anchor_left=True):
    """字間を開けて描く。戻り値は右端x。"""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + tracking
    return x - tracking


def tracked_width(d, text, font, tracking=0):
    w = sum(d.textlength(ch, font=font) for ch in text)
    return w + tracking * (len(text) - 1)


img = Image.new("RGB", (W, H), KINARI)
d = ImageDraw.Draw(img, "RGBA")

# ---- 紙の目（薄いノイズ）----
noise = Image.new("L", (W // 2, H // 2))
px = noise.load()
rnd = random.Random(7)
for yy in range(noise.height):
    for xx in range(noise.width):
        px[xx, yy] = rnd.randint(118, 138)
noise = noise.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.6))
img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.055)
d = ImageDraw.Draw(img, "RGBA")

M = 120  # 左マージン
R = W - 120

# ---- 天：小さな見出し ----
tracked(d, (M, 96), "おかねの流れ　一枚地図", f(23), (34, 48, 74, 210), 7)
n = "N o . 0 0 1"
d.text((R - d.textlength(n, font=f(20)), 100), n, font=f(20), fill=SHU)
d.line([(M, 146), (R, 146)], fill=(34, 48, 74, 90), width=1)

# ---- 主見出し ----
y = 236
tracked(d, (M, y), "予算はふえて、", f(74), SUMI, 4)
y += 110
tracked(d, (M, y), "使ったお金はへりました。", f(74), SUMI, 4)

# ---- 副題 ----
y += 146
tracked(d, (M, y), "原子力防災体制等構築事業", f(31), SUMI, 3)
y += 54
d.text((M, y), "内閣府／特別会計：エネルギー対策・電源開発促進勘定／2017年度開始",
       font=f(23), fill=(34, 48, 74, 190))

# ---- グラフ ----
y += 96
rows = [
    ("2021年度", 22098, 16000, "1,600万円"),
    ("2022年度", 22641, 19882, "1,988万円"),
    ("2023年度", 50002, 19582, "1,958万円"),
    ("2024年度", 38997, 5685, "569万円"),
    ("2025年度", 37789, None, "まだ出ていません"),
]
maxv = 50002
gx = M + 200
gw = R - gx - 250
rowh = 118

tracked(d, (gx, y - 46), "うすい線＝きめた予算　　　朱＝じっさいに使ったお金", f(21), (34, 48, 74, 170), 2)

for i, (label, bud, exe, exel) in enumerate(rows):
    ry = y + i * rowh
    d.text((M, ry + 18), label, font=f(26), fill=SUMI)
    bw = int(gw * bud / maxv)
    d.rectangle([gx, ry + 8, gx + bw, ry + 34], outline=(34, 48, 74, 130), width=2)
    d.text((gx + bw + 14, ry + 6), f"{bud/10:,.0f}万円".replace(".0", ""),
           font=f(22), fill=(34, 48, 74, 175))
    if exe is not None:
        ew = int(gw * exe / maxv)
        d.rectangle([gx, ry + 46, gx + ew, ry + 76], fill=SHU)
        d.text((gx + ew + 14, ry + 46), exel, font=f(24), fill=SHU)
    else:
        d.text((gx + 4, ry + 46), exel, font=f(22), fill=(34, 48, 74, 140))

y += len(rows) * rowh + 26
d.line([(M, y), (R, y)], fill=(34, 48, 74, 70), width=1)

# ---- 読めること（事実だけ）----
y += 46
for line in [
    "・きめた予算は、2021年度の約2,210万円から2023年度の約5,000万円へ、約2.3倍になりました。",
    "・じっさいに使ったお金は、2021年度の1,600万円から2024年度の569万円へ減りました。",
    "・2024年度に使われた569万円は、1つの会社に出ています（株式会社NX総合研究所）。",
]:
    d.text((M, y), line, font=f(26), fill=SUMI)
    y += 50

# ---- 質問（この道具の出口）----
y += 34
box_h = 236
d.rectangle([M, y, R, y + box_h], outline=SHU, width=3)
tracked(d, (M + 34, y + 30), "きいてみたいこと", f(24), SHU, 5)
d.text((M + 34, y + 84), "予算をふやしたのに、使ったお金がへったのは、なぜですか。",
       font=f(30), fill=SUMI)
d.text((M + 34, y + 140), "使わなかったぶんのお金は、そのあとどこへ行きましたか。",
       font=f(30), fill=SUMI)

# ---- 注記と出典 ----
y += box_h + 44
d.text((M, y), "この紙は、国が公開している資料に書いてある数字をならべただけです。",
       font=f(22), fill=(34, 48, 74, 175))
d.text((M, y + 34), "だれかが悪いことをした、とは書いていません。おかしいと思ったら、聞いてください。",
       font=f(22), fill=(34, 48, 74, 175))

y += 92
d.line([(M, y), (R, y)], fill=(34, 48, 74, 70), width=1)
y += 22
d.text((M, y), "出典（行政事業レビュー／RSシステム・内閣官房）", font=f(20), fill=(34, 48, 74, 165))
y += 30
for u in [
    "予算と執行額：rssystem.go.jp/project/b0acbd95-9765-4fea-a102-12002cdb9245?activeKey=detailed-breakdown",
    "支出先　　　：rssystem.go.jp/project/b0acbd95-9765-4fea-a102-12002cdb9245?activeKey=payment",
    "金額の原文単位は千円。万円への換算のみこちらで行いました（22,098千円＝約2,210万円）。",
]:
    d.text((M, y), u, font=f(19), fill=(34, 48, 74, 150))
    y += 27

img.save("/sessions/awesome-epic-cori/mnt/tamago-shinchoku/1028_okane_chizu_001.png", "PNG")
print("saved")
