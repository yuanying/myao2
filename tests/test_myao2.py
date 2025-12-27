"""myao2 基本テスト"""

import myao2


def test_version() -> None:
    """バージョンが正しく設定されていることを確認"""
    assert myao2.__version__ == "0.1.0"
