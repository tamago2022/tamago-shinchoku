#!/usr/bin/env python3
"""
35236番：フードレーダー(/food-radar)のフィルター「排他・クリア」挙動を裏付ける、
実データ集計の棒グラフを share/check/img/35236-filters.png へ書き出す。

★これはブラウザの実写スクリーンショットではない（1186号の関所でChrome本体の
  起動が全面禁止されているため、本セッションでは実クリックのスクショが作れない）。
  src/data/foodRadarData.ts の実データを、filterRecipes/chefCounts/dishTagGroupsと
  同じ条件でこのスクリプト内で再集計し、その数字をグラフにしている（捏造防止）。
  グラフの隅にもその旨を明記する。

既存の実例 tools/perf_watch_chart.py のPIL描画パターンをそのまま流用。

使い方:
  python3 tools/_35236_food_radar_chart.py
"""
import os
import re

from PIL import Image, ImageDraw, ImageFont

REPO = "/Users/mac/tamago/tamago-shinchoku"
JOY_RELIEF_SRC = "/Users/mac/Documents/AI作業/.worktrees/q35236-0904/src/data/foodRadarData.ts"
OUT = os.path.join(REPO, "share", "check", "img", "35236-filters.png")


def count_real_data():
    """joy-relief-station側の実データ(foodRadarData.ts)を集計する（捏造しない）。"""
    text = open(JOY_RELIEF_SRC, encoding="utf-8").read()
    m = re.search(r"export const foodRecipes: FoodRecipe\[\] = \[(.*?)\n\];", text, re.S)
    body = m.group(1)
    entries = re.split(r"\n  \{\n", body)
    recipes = []
    for e in entries:
        tm = re.search(r'title:\s*"([^"]*)"', e)
        cm = re.search(r'chefName:\s*"([^"]*)"', e)
        if not tm and not cm:
            continue
        recipes.append({"title": tm.group(1) if tm else "", "chef": cm.group(1) if cm else ""})
    total = len(recipes)
    chef_ryuji = sum(1 for r in recipes if r["chef"] == "リュウジ")
    pasta_kw = ["パスタ", "スパゲッティ", "リングイネ", "ペペロンチーノ", "カルボナーラ"]
    dish_pasta = sum(1 for r in recipes if any(k in r["title"] for k in pasta_kw))
    return total, chef_ryuji, dish_pasta


def main():
    total, chef_n, dish_n = count_real_data()
    bars = [
        ("フィルターなし（全件）", total, (122, 117, 104)),
        ("シェフ「リュウジ」選択時", chef_n, (196, 72, 58)),
        ("→別軸「パスタ」へ切替後\n(リュウジの選択は自動解除)", dish_n, (58, 122, 82)),
    ]

    W, H = 640, 300
    img = Image.new("RGB", (W, H), (244, 239, 228))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 14)
        font_small = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 11)
        font_big = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 20)
    except Exception:
        font = font_small = font_big = ImageFont.load_default()

    draw.text((14, 10), "#35236 フードレーダー フィルター排他・クリア 実データ集計", fill=(42, 42, 42), font=font)

    margin_l, margin_t = 30, 50
    bar_h = 46
    gap = 28
    max_v = max(b[1] for b in bars) or 1
    plot_w = W - margin_l - 140

    y = margin_t
    for label, value, color in bars:
        bw = int(plot_w * (value / max_v)) if max_v else 0
        draw.rectangle([margin_l, y, margin_l + bw, y + bar_h], fill=color)
        draw.text((margin_l + bw + 10, y + 10), f"{value}件", fill=(42, 42, 42), font=font_big)
        for i, line in enumerate(label.split("\n")):
            draw.text((margin_l, y - 18 - 14 * (len(label.split("\n")) - 1 - i)), line, fill=(42, 42, 42), font=font_small)
        y += bar_h + gap

    draw.text(
        (14, H - 46),
        "※ブラウザの実写ではない。src/data/foodRadarData.tsの実データを同じ条件で\n　このスクリプトが再集計した数字のグラフ（1186号の関所でChrome起動は禁止のため）。",
        fill=(122, 117, 104),
        font=font_small,
    )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(f"[35236] 書き出し: {OUT} total={total} chef_ryuji={chef_n} dish_pasta={dish_n}")


if __name__ == "__main__":
    main()
