#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
739番：「進捗表からGitHubへ飛ぶと戻れない」対応。

PWA（ホーム画面アプリ）はブラウザの戻るボタン・アドレスバー・タブが無いため、
外部リンク（GitHub・本番サイト等）へ飛ぶと行き止まりになる、または share/ 配下の
別ページ（確認ページ・共有資料）へ移動しても進捗表トップへ戻る手段が無かった。

対策：share/ 配下の全HTML（テンプレート含む）と money.html に、
<body>直後（画面上部）と</body>直前（画面下部）の両方へ
「← 進捗表に戻る」の固定リンクを機械的に挿入する。

冪等：マーカー文字列 SHINCHOKU_BACK_LINK が既に入っているファイルはスキップする
（何度実行しても壊れない・二重挿入しない）。
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME_URL = "https://tamago2022.github.io/tamago-shinchoku/"
MARKER = "SHINCHOKU_BACK_LINK"

TOP_HTML = f"""<!-- {MARKER} -->
<div id="shinchokuBackTop" style="position:sticky;top:0;left:0;right:0;z-index:9999;background:#1c1c1c;border-bottom:1px solid #3a3a3a;padding:8px 14px;text-align:left;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;">
  <a href="{HOME_URL}" style="color:#8ef0ae;text-decoration:none;font-weight:700;font-size:0.9rem;">← 進捗表に戻る</a>
</div>
"""

BOTTOM_HTML = f"""<div id="shinchokuBackBottom" style="margin:30px 0 10px;padding:14px;text-align:center;background:#1c1c1c;border-radius:10px;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;">
  <a href="{HOME_URL}" style="color:#8ef0ae;text-decoration:none;font-weight:700;font-size:0.95rem;">← 進捗表に戻る</a>
</div>
<!-- /{MARKER} -->
"""

BODY_OPEN_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
BODY_CLOSE_RE = re.compile(r"(</body>)", re.IGNORECASE)


def process(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except (UnicodeDecodeError, OSError) as e:
        return f"SKIP(read-error:{e}) {path}"

    if MARKER in text:
        return f"SKIP(already) {path}"

    if not BODY_OPEN_RE.search(text) or not BODY_CLOSE_RE.search(text):
        return f"SKIP(no-body-tag) {path}"

    text = BODY_OPEN_RE.sub(lambda m: m.group(1) + "\n" + TOP_HTML, text, count=1)
    text = BODY_CLOSE_RE.sub(lambda m: BOTTOM_HTML + m.group(1), text, count=1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return f"OK {path}"


def main():
    targets = sorted(glob.glob(os.path.join(ROOT, "share", "**", "*.html"), recursive=True))
    money = os.path.join(ROOT, "money.html")
    if os.path.exists(money):
        targets.append(money)

    ok, skip_already, skip_other = 0, 0, 0
    for path in targets:
        result = process(path)
        rel = os.path.relpath(path, ROOT)
        if result.startswith("OK"):
            ok += 1
        elif "already" in result:
            skip_already += 1
        else:
            skip_other += 1
            print(f"{result.split(' ')[0]} {rel}")

    print(f"---\n合計{len(targets)}件 / 新規挿入{ok}件 / 既に対応済み{skip_already}件 / 対象外{skip_other}件")


if __name__ == "__main__":
    sys.exit(main())
