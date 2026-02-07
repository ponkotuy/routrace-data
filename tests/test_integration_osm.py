"""OSMパーサーの統合テスト

御殿場IC周辺のOSMデータを使用して、discover_highways()とdiscover_national_routes()の
実際の動作を検証する。
"""

import sys
from pathlib import Path

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from osm_parser import discover_highways, discover_national_routes


class TestDiscoverHighwaysIntegration:
    """discover_highways() の統合テスト"""

    def test_discovers_tomei_expressway(self, gotemba_pbf_path: Path):
        """東名高速道路が検出されること"""
        highways, way_ids_by_name = discover_highways(gotemba_pbf_path)

        # 東名高速道路が含まれていることを確認
        highway_names = [h["name"] for h in highways]
        assert "東名高速道路" in highway_names

    def test_highway_has_required_fields(self, gotemba_pbf_path: Path):
        """検出された高速道路が必須フィールドを持つこと"""
        highways, way_ids_by_name = discover_highways(gotemba_pbf_path)

        assert len(highways) > 0
        for highway in highways:
            assert "name" in highway
            assert "name_en" in highway
            assert "ref" in highway
            assert "way_count" in highway
            assert highway["way_count"] > 0


class TestDiscoverNationalRoutesIntegration:
    """discover_national_routes() の統合テスト"""

    def test_discovers_national_routes(self, gotemba_pbf_path: Path):
        """国道138号または246号が検出されること"""
        routes, way_ids_by_ref = discover_national_routes(gotemba_pbf_path)

        # 国道138号または246号のいずれかが含まれていることを確認
        route_refs = [r["ref"] for r in routes]
        assert "138" in route_refs or "246" in route_refs

    def test_national_route_has_required_fields(self, gotemba_pbf_path: Path):
        """検出された国道が必須フィールドを持つこと"""
        routes, way_ids_by_ref = discover_national_routes(gotemba_pbf_path)

        assert len(routes) > 0
        for route in routes:
            assert "ref" in route
            assert "name" in route
            assert "name_en" in route
            assert "way_count" in route
            assert route["way_count"] > 0

    def test_national_route_name_format(self, gotemba_pbf_path: Path):
        """国道の名前が「国道X号」形式であること"""
        routes, way_ids_by_ref = discover_national_routes(gotemba_pbf_path)

        for route in routes:
            assert route["name"].startswith("国道")
            assert route["name"].endswith("号")
            # 「国道{ref}号」の形式であることを確認
            assert route["name"] == f"国道{route['ref']}号"
