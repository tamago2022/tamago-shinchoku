#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""403番の確認ページ用に、Vault成果物の中身をテキストプレビュー画像として書き出す。
ブラウザ操作・画面録画は使わず、PILでテキストを直接レンダリングする（音も鳴らず、
画面も奪わない、安全な方法）。
"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT_REGULAR = "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"
FONT_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
OUT_DIR = "/Users/mac/Desktop/tamago-shinchoku/share/check/img"
os.makedirs(OUT_DIR, exist_ok=True)

W = 1000
PAD = 36
LINE_H = 34


def font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, size)


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


def render(title, blocks, out_path):
    """blocks: list of (heading:str, body:str)"""
    tmp = Image.new("RGB", (W, 100), "white")
    d = ImageDraw.Draw(tmp)
    f_title = font(30, bold=True)
    f_head = font(22, bold=True)
    f_body = font(19)

    max_w = W - PAD * 2
    all_lines = []  # (text, font, color)
    title_lines = wrap(d, title, f_title, max_w)
    for t in title_lines:
        all_lines.append((t, f_title, (30, 30, 30)))
    all_lines.append(("", f_body, (0, 0, 0)))

    for heading, body in blocks:
        for hl in wrap(d, heading, f_head, max_w):
            all_lines.append((hl, f_head, (138, 90, 30)))
        for bl in wrap(d, body, f_body, max_w):
            all_lines.append((bl, f_body, (20, 20, 20)))
        all_lines.append(("", f_body, (0, 0, 0)))

    height = PAD * 2 + len(all_lines) * LINE_H
    img = Image.new("RGB", (W, height), "white")
    dd = ImageDraw.Draw(img)
    y = PAD
    for text, f, color in all_lines:
        dd.text((PAD, y), text, font=f, fill=color)
        y += LINE_H
    img.save(out_path)
    print("saved:", out_path, img.size)


# --- 画像1：出典一覧（一次情報7件） ---
render(
    "403番 円卓の素材：出典一覧（一次情報7件・全件到達確認済み）",
    [
        ("① NHK番組公式ページ", "https://www.nhk.jp/p/netadori/ts/QL8GZ2L5VX/episode/te/8IFYUFWE13/\n「首都圏情報 ネタドリ！」2026-09-04放送・公開紹介文のみ使用"),
        ("② 東洋経済オンライン(2017/04/01)", "https://toyokeizai.net/articles/-/563017\n落合陽一氏インタビュー「僕たちがAIと幸せに暮らす方法」"),
        ("③ 東洋経済オンライン(2024/07/05)", "https://toyokeizai.net/articles/-/761017\n落合陽一氏×暦本純一氏 対談"),
        ("④ PRESIDENT Online(2024/06/21)", "https://president.jp/articles/-/82377\n落合陽一氏 著書『生成AIが変える未来』抜粋"),
        ("⑤ JILPT 調査シリーズNo.256", "https://www.jil.go.jp/institute/research/2025/256.html\n労働者Webアンケート2.2万人・G7労働雇用大臣会合でも活用"),
        ("⑥ JILPT／OECD紹介記事", "https://www.jil.go.jp/foreign/jihou/2025/03/oecd_01.html\nOECD諸国の労働者の約4分の1が生成AIの影響下"),
        ("⑦ パーソル総研×中央大学", "https://rc.persol-group.co.jp/thinktank/spe/roudou2030/\n労働市場の未来推計2030：2030年に644万人の人手不足"),
    ],
    os.path.join(OUT_DIR, "403-shutten-ichiran.png"),
)

# --- 画像2：円卓用対立軸A〜C ---
render(
    "403番 円卓の素材：対立軸A〜C（Vaultファイルより）",
    [
        ("論点A：奪われているのは「仕事」か「作業」か",
         "落合氏＝AIが吸収するのは定型「作業」、人間に残るのは「選ぶ・判断する」上位の「仕事」。\n"
         "反対仮説＝OECD分析では経営・管理／教育指導など「上位の仕事」ほどAI露出度が高い。"),
        ("論点B：「AI失業」は統計的に実在するか",
         "NHK事例＝500人の配置転換は実在。マクロでは日本は644万人の人手不足という逆方向の圧力が支配的。\n"
         "問い＝「奪われた側」の痛みが可視化されやすいから大きく見えているだけでは？"),
        ("論点C：ゲーム化する働き方は希望か、諦めか",
         "落合氏(2017)＝『ポケモンGOを楽しむ感覚で働ける』は前向きな描写。\n"
         "反対仮説＝実態は『AIに管理される側』への地位低下ではないか。"),
        ("出典（Vault本体ファイル）",
         "AI出力/40_プロジェクト/円卓会議/AI失業回_素材_2026-09-05.md（13,797バイト・実在確認済み）"),
    ],
    os.path.join(OUT_DIR, "403-taisetsujiku.png"),
)
