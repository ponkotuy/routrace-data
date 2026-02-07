"""共有テストフィクスチャ"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def gotemba_pbf_path() -> Path:
    """テスト用PBFファイル（御殿場IC周辺）へのパスを提供"""
    path = FIXTURES_DIR / "gotemba-area.osm.pbf"
    if not path.exists():
        pytest.skip(f"テスト用PBFファイルが存在しません: {path}")
    return path
