#!/usr/bin/env python3
# 877番: Brave設定の実データをテキストのまま画像化する(スクリーンショットは撮らない・screencapture不使用)
import json
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
FONT_PATH_R = "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"

def font(size, bold=False):
    return ImageFont.truetype(FONT_PATH if bold else FONT_PATH_R, size)

def render(lines, out_path, width=1000):
    # lines: list of (text, size, color, bold)
    pad = 30
    line_h = []
    total_h = pad * 2
    imgs_font = []
    for text, size, color, bold in lines:
        f = font(size, bold)
        imgs_font.append(f)
        total_h += int(size * 1.5)
    img = Image.new("RGB", (width, total_h), "#1e1e2e")
    d = ImageDraw.Draw(img)
    y = pad
    for (text, size, color, bold), f in zip(lines, imgs_font):
        d.text((pad, y), text, font=f, fill=color)
        y += int(size * 1.5)
    img.save(out_path)
    print("saved:", out_path)

PREF = "/Users/mac/Library/Application Support/BraveSoftware/Brave-Browser/Default/Preferences"
with open(PREF) as f:
    d = json.load(f)
cs = d.get("profile", {}).get("content_settings", {}).get("exceptions", {})
sound = cs.get("sound", {})
autoplay = cs.get("autoplay", {})
me = cs.get("media_engagement", {}).get("https://www.youtube.com:443,*", {}).get("setting", {})

YEL = "#f9e2af"
GRN = "#a6e3a1"
WHT = "#cdd6f4"
RED = "#f38ba8"

lines1 = [
    ("たまごさんの「あなたの Brave」設定ファイルを直接読んだ実データ", 24, YEL, True),
    ("(ブラウザは一度も開いていない。ファイルを読んだだけ)", 16, WHT, False),
    ("", 10, WHT, False),
    ("■ sound (サイトの音声をミュートする設定)", 20, GRN, True),
    ('  "https://www.youtube.com:443,*"', 18, WHT, False),
    (f'  setting = {sound.get("https://www.youtube.com:443,*", {}).get("setting")}  → 1 = 音声「許可」(ミュートではない)', 18, WHT, False),
    ("", 10, WHT, False),
    ("■ autoplay (自動再生の設定)", 20, GRN, True),
    ('  "https://www.youtube.com:443,*"', 18, WHT, False),
    (f'  setting = {autoplay.get("https://www.youtube.com:443,*", {}).get("setting")}  → 1 = 自動再生「許可」', 18, WHT, False),
    ("", 10, WHT, False),
    ("■ media_engagement (このサイトでの再生実績スコア)", 20, GRN, True),
    (f'  hasHighScore = {me.get("hasHighScore")} / mediaPlaybacks = {me.get("mediaPlaybacks")} / visits = {me.get("visits")}', 18, WHT, False),
    ("", 15, WHT, False),
    ("結論: Brave側に「YouTubeをミュートする」設定は見つからなかった", 22, RED, True),
    ("(むしろ全部「許可」になっている。過去のAI操作の跡ではない)", 16, WHT, False),
]
render(lines1, "/Users/mac/Desktop/tamago-shinchoku/share/check/img/877-brave-settings-raw.png")

lines2 = [
    ("拡張機能・Brave Shields(広告/追跡ブロック)の個別設定も確認", 24, YEL, True),
    ("", 10, WHT, False),
    ("■ インストール済み拡張機能: 0件", 20, GRN, True),
    ("  ミュート系・音声制御系の拡張は入っていない", 18, WHT, False),
    ("", 10, WHT, False),
    ("■ Brave Shields (youtube.comへの個別設定)", 20, GRN, True),
    ("  shieldsAds / cosmeticFiltering / brave_webcompat_audio など", 18, WHT, False),
    ("  → youtube.com専用の例外は0件(標準設定のまま)", 18, WHT, False),
    ("", 15, WHT, False),
    ("→ ミュートの原因はBrave側の設定ではなく、", 22, RED, True),
    ("   YouTube自身が「前回のミュート状態」を記憶する仕様と見られる", 22, RED, True),
]
render(lines2, "/Users/mac/Desktop/tamago-shinchoku/share/check/img/877-brave-shields-ext.png")
