"""共有テストフィクスチャ"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def gotemba_pbf_path() -> Path:
    """テスト用PBFファイル（御殿場IC周辺）へのパスを提供"""
    path = FIXTURES_DIR / "gotemba-area.osm.pbf"
    if not path.exists():
        pytest.skip(f"テスト用PBFファイルが存在しません: {path}")
    return path


@pytest.fixture()
def feature_collection_factory():
    """単一FeatureのFeatureCollectionを作るファクトリ"""

    def _factory(
        geometry: dict,
        feature_properties: dict | None = None,
        collection_properties: dict | None = None,
    ) -> dict:
        if feature_properties is None:
            feature_properties = {}
        feature = {
            "type": "Feature",
            "geometry": geometry,
            "properties": feature_properties,
        }
        collection = {
            "type": "FeatureCollection",
            "features": [feature],
        }
        if collection_properties is not None:
            collection["properties"] = collection_properties
        return collection

    return _factory
