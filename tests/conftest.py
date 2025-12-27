"""pytest共通フィクスチャ"""

import pytest


@pytest.fixture
def sample_fixture() -> str:
    """サンプルフィクスチャ"""
    return "sample"
