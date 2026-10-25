"""サイト診断ツールの入口（土台のみ・本体は35211番で実装）。

設計: DESIGN.md 全体のパイプライン図を参照。
fetch_page → run_pagespeed → rewrite_as_kind_suggestions を束ねて、
「URLを渡すと、優しい言葉の提案が1〜2点返ってくる」を実現する入口。
"""

from __future__ import annotations


def diagnose(url: str) -> list[str]:
    """URLを渡すと、優しい言葉の改善提案を最大2件返す（土台のみ）。

    実装方針（DESIGN.md 5章）:
      1. fetch.fetch_page(url) でページ情報を取る
      2. pagespeed.run_pagespeed(url) で速度・SEO等の指標を取る
      3. rewrite.rewrite_as_kind_suggestions(...) で優しい文章へ変換する
      4. 1〜2件に絞って返す
    """
    raise NotImplementedError("35211番（実装・試作）で実装する予定の土台")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使い方: python -m site_shindan.shindan <URL>")
        raise SystemExit(1)
    for suggestion in diagnose(sys.argv[1]):
        print(suggestion)
