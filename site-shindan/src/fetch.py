"""URLからサイトの情報を取る係（土台のみ・本体は35211番で実装）。

設計: DESIGN.md 3章①取得 を参照。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PageSnapshot:
    """取得した1ページの情報（型だけ・本体未実装）。"""

    url: str
    html: str
    title: str | None
    meta_description: str | None


def fetch_page(url: str) -> PageSnapshot:
    """URLを取得してPageSnapshotを返す（土台のみ）。

    実装方針（DESIGN.md 4章）: requestsで取得し、BeautifulSoup等の
    一般的なHTML解析ライブラリでtitle/meta descriptionを抜く想定。
    自前の独自パーサーは新規に書かない（オリジナル禁止・1184番関所）。
    """
    raise NotImplementedError("35211番（実装・試作）で実装する予定の土台")
