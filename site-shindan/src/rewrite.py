"""機械チェックの結果を、優しい言葉の提案文へ言い換える係（土台のみ）。

設計: DESIGN.md 3章③言い換え を参照。
ルール: 専門用語を使わない。「AI」という語を極力使わない。1〜2点に絞る。
弱い言い換えで事実を薄めない（session preamble 枷18と同じ考え方）。
"""

from __future__ import annotations


def rewrite_as_kind_suggestions(raw_issues: list[str], max_points: int = 2) -> list[str]:
    """機械的な指摘（例: "LCPが遅い"）を、優しい提案文（例: "最初の写真が表示される
    までに少し時間がかかっています。写真を軽くすると良いかもしれません"）へ変換する（土台のみ）。

    実装方針: 固定の対応表（指摘キー→優しい言い換え）を用意し、該当する指摘のうち
    重要度の高いものから最大max_points件だけ選ぶ想定。LLM(Claude API)を使う場合も、
    店主の既存の文体ルール（短く・専門用語を避ける）をプロンプトへそのまま流用する。
    """
    raise NotImplementedError("35211番（実装・試作）で実装する予定の土台")
