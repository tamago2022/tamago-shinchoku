"""土台の雛形テスト（本体未実装のため、形だけを確認する）。

実装（35211番）が入ったら、このskipを外して本物のテストに置き換える。
"""

import pytest

from src.shindan import diagnose


def test_diagnose_is_not_yet_implemented():
    """本体が未実装であることそのものを確認する（土台段階のテスト）。

    35211番で本体が実装されたら、このテストはNotImplementedErrorを
    期待する形から、実際の出力を期待する形へ書き換える。
    """
    with pytest.raises(NotImplementedError):
        diagnose("https://example.com")
