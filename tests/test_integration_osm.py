"""OSMパーサーの統合テスト

御殿場IC周辺のOSMデータを使用して、discover_highways()とdiscover_national_routes()の
実際の動作を検証する。
"""

import json
import sys
from pathlib import Path

import pytest

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from osm_parser import (
    discover_highways,
    discover_national_routes,
    extract_all_ways,
    get_ways_for_highway,
    ways_to_geojson,
)
from utils import save_geojson


@pytest.fixture(scope="session")
def gotemba_highways(gotemba_pbf_path: Path):
    """御殿場IC周辺PBFの高速道路検出結果を共有する"""
    return discover_highways(gotemba_pbf_path)


@pytest.fixture(scope="session")
def gotemba_routes(gotemba_pbf_path: Path):
    """御殿場IC周辺PBFの国道検出結果を共有する"""
    return discover_national_routes(gotemba_pbf_path)


class TestDiscoverHighwaysIntegration:
    """discover_highways() の統合テスト"""

    def test_discovers_tomei_expressway(self, gotemba_highways):
        """東名高速道路が検出されること"""
        highways, _ = gotemba_highways

        # 東名高速道路が含まれていることを確認
        highway_names = [h["name"] for h in highways]
        assert "東名高速道路" in highway_names

    def test_highway_has_required_fields(self, gotemba_highways):
        """検出された高速道路が必須フィールドを持つこと"""
        highways, _ = gotemba_highways

        assert len(highways) > 0
        for highway in highways:
            assert "name" in highway
            assert "name_en" in highway
            assert "ref" in highway
            assert "way_count" in highway
            assert highway["way_count"] > 0


class TestDiscoverNationalRoutesIntegration:
    """discover_national_routes() の統合テスト"""

    def test_discovers_national_routes(self, gotemba_routes):
        """国道138号または246号が検出されること"""
        routes, _ = gotemba_routes

        # 国道138号または246号のいずれかが含まれていることを確認
        route_refs = [r["ref"] for r in routes]
        assert "138" in route_refs or "246" in route_refs

    def test_national_route_has_required_fields(self, gotemba_routes):
        """検出された国道が必須フィールドを持つこと"""
        routes, _ = gotemba_routes

        assert len(routes) > 0
        for route in routes:
            assert "ref" in route
            assert "name" in route
            assert "name_en" in route
            assert "way_count" in route
            assert route["way_count"] > 0

    def test_national_route_name_format(self, gotemba_routes):
        """国道の名前が「国道X号」形式であること"""
        routes, _ = gotemba_routes

        for route in routes:
            assert route["name"].startswith("国道")
            assert route["name"].endswith("号")
            # 「国道{ref}号」の形式であることを確認
            assert route["name"] == f"国道{route['ref']}号"


class TestGeoJsonOutputIntegration:
    """GeoJSON出力の統合テスト"""

    def test_highway_geojson_output(self, gotemba_highways, gotemba_pbf_path: Path, tmp_path: Path):
        """高速道路のGeoJSON出力が正しいこと"""
        # 高速道路を検出
        _, way_ids_by_name = gotemba_highways
        assert "東名高速道路" in way_ids_by_name

        # wayデータを抽出
        all_way_ids = way_ids_by_name["東名高速道路"]
        ways_by_id = extract_all_ways(gotemba_pbf_path, all_way_ids)

        # GeoJSONに変換
        ways = get_ways_for_highway(ways_by_id, all_way_ids)
        geojson = ways_to_geojson(ways)

        # tmp_pathに保存
        output_path = tmp_path / "東名高速道路.json"
        file_size = save_geojson(geojson, output_path)

        # ファイルが作成されたことを確認
        assert output_path.exists()
        assert file_size > 0

        # ファイル内容を検証
        with open(output_path, encoding="utf-8") as f:
            saved_geojson = json.load(f)

        assert saved_geojson["type"] == "FeatureCollection"
        assert len(saved_geojson["features"]) > 0

        # 各featureがLineString geometryを持つことを確認
        for feature in saved_geojson["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "LineString"
            assert len(feature["geometry"]["coordinates"]) >= 2

    def test_national_route_geojson_output(
        self, gotemba_routes, gotemba_pbf_path: Path, tmp_path: Path
    ):
        """国道のGeoJSON出力が正しいこと"""
        # 国道を検出
        _, way_ids_by_ref = gotemba_routes

        # 246号が存在することを確認
        assert "246" in way_ids_by_ref

        # wayデータを抽出
        all_way_ids = way_ids_by_ref["246"]
        ways_by_id = extract_all_ways(gotemba_pbf_path, all_way_ids)

        # GeoJSONに変換
        ways = get_ways_for_highway(ways_by_id, all_way_ids)
        geojson = ways_to_geojson(ways)

        # tmp_pathに保存
        output_path = tmp_path / "国道246号.json"
        file_size = save_geojson(geojson, output_path)

        # ファイルが作成されたことを確認
        assert output_path.exists()
        assert file_size > 0

        # ファイル内容を検証
        with open(output_path, encoding="utf-8") as f:
            saved_geojson = json.load(f)

        assert saved_geojson["type"] == "FeatureCollection"
        assert len(saved_geojson["features"]) > 0
