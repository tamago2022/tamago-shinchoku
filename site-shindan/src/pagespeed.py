"""Google PageSpeed Insights API呼び出しの係（土台のみ・本体は35211番で実装）。

設計: DESIGN.md 4章「技術方針」を参照。
公式API: https://developers.google.com/speed/docs/insights/v5/get-started
自前で速度計測ロジックを新規に作らず、この公式APIをそのまま呼ぶ方針。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageSpeedResult:
    """PageSpeed Insights APIの結果を必要な分だけ抜いた形（型だけ）。"""

    performance_score: float | None = None
    issues: list[str] = field(default_factory=list)


def run_pagespeed(url: str) -> PageSpeedResult:
    """PageSpeed Insights APIを呼び、結果をPageSpeedResultへ詰めて返す（土台のみ）。

    実装方針: GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=...
    （公式ドキュメントのサンプルをそのまま使う。APIキーは.env.local等に
    店主が直接書き込む運用とし、このファイルには値を書かない）。
    """
    raise NotImplementedError("35211番（実装・試作）で実装する予定の土台")
