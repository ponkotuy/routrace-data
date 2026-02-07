"""highway モジュールの単体テスト"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from highway import extract_highway, save_highway


class TestExtractHighway:
    """extract_highway関数のテスト"""

    @patch("highway.simplify_geojson")
    @patch("highway.get_coordinate_count")
    @patch("highway.ways_to_geojson")
    def test_basic_extraction(
        self, mock_ways_to_geojson, mock_get_count, mock_simplify
    ):
        """GeoJSON変換と簡略化が正しく行われる"""
        highway_info = {"name": "東名高速道路", "name_en": "Tomei Expwy", "ref": "E1"}
        ways = [{"id": 1, "nodes": [[139.0, 35.0], [139.1, 35.1]]}]

        # 高速道路用GeoJSON（LineString座標をJP地域に設定）
        mock_feature = {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[139.0, 35.0], [139.1, 35.1]]},
            "properties": {},
        }
        mock_geojson = {"type": "FeatureCollection", "features": [mock_feature]}
        mock_ways_to_geojson.return_value = mock_geojson
        mock_get_count.side_effect = [100, 50]  # original, simplified
        mock_simplify.return_value = {"type": "FeatureCollection", "features": [mock_feature]}

        result = extract_highway(highway_info, ways)

        mock_ways_to_geojson.assert_called_once_with(ways)
        mock_simplify.assert_called_once()
        assert result["type"] == "FeatureCollection"

    @patch("highway.simplify_geojson")
    @patch("highway.get_coordinate_count")
    @patch("highway.ways_to_geojson")
    def test_properties_set_correctly(
        self, mock_ways_to_geojson, mock_get_count, mock_simplify
    ):
        """name, nameEn, ref が設定される"""
        highway_info = {"name": "東名高速道路", "name_en": "Tomei Expwy", "ref": "E1"}
        ways = []

        mock_geojson = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
        mock_ways_to_geojson.return_value = mock_geojson
        mock_get_count.return_value = 10
        mock_simplify.return_value = {"type": "FeatureCollection", "features": []}

        result = extract_highway(highway_info, ways)

        assert result["properties"]["name"] == "東名高速道路"
        assert result["properties"]["nameEn"] == "Tomei Expwy"
        assert result["properties"]["ref"] == "E1"

    @patch("highway.simplify_geojson")
    @patch("highway.get_coordinate_count")
    @patch("highway.ways_to_geojson")
    def test_handles_missing_name_en(
        self, mock_ways_to_geojson, mock_get_count, mock_simplify
    ):
        """name_en が無い場合は空文字"""
        highway_info = {"name": "テスト道路"}  # name_en なし
        ways = []

        mock_ways_to_geojson.return_value = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature"}],
        }
        mock_get_count.return_value = 10
        mock_simplify.return_value = {"type": "FeatureCollection", "features": []}

        result = extract_highway(highway_info, ways)

        assert result["properties"]["nameEn"] == ""

    @patch("highway.simplify_geojson")
    @patch("highway.get_coordinate_count")
    @patch("highway.ways_to_geojson")
    def test_handles_missing_ref(
        self, mock_ways_to_geojson, mock_get_count, mock_simplify
    ):
        """ref が無い場合は空文字"""
        highway_info = {"name": "テスト道路", "name_en": "Test Road"}  # ref なし
        ways = []

        mock_ways_to_geojson.return_value = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature"}],
        }
        mock_get_count.return_value = 10
        mock_simplify.return_value = {"type": "FeatureCollection", "features": []}

        result = extract_highway(highway_info, ways)

        assert result["properties"]["ref"] == ""

    @patch("highway.simplify_geojson")
    @patch("highway.get_coordinate_count")
    @patch("highway.ways_to_geojson")
    def test_warns_on_zero_features(
        self, mock_ways_to_geojson, mock_get_count, mock_simplify, caplog
    ):
        """features が0件で警告ログ"""
        import logging

        highway_info = {"name": "空の道路"}
        ways = []

        mock_ways_to_geojson.return_value = {
            "type": "FeatureCollection",
            "features": [],  # 0件
        }
        mock_get_count.return_value = 0
        mock_simplify.return_value = {"type": "FeatureCollection", "features": []}

        with caplog.at_level(logging.WARNING):
            extract_highway(highway_info, ways)

        assert "高速道路データが0件でした" in caplog.text
        assert "空の道路" in caplog.text

    @patch("highway.simplify_geojson")
    @patch("highway.get_coordinate_count")
    @patch("highway.ways_to_geojson")
    def test_logs_coordinate_reduction(
        self, mock_ways_to_geojson, mock_get_count, mock_simplify, caplog
    ):
        """簡略化のログ出力"""
        import logging

        highway_info = {"name": "テスト道路"}
        ways = []

        mock_ways_to_geojson.return_value = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature"}],
        }
        mock_get_count.side_effect = [1000, 500]  # original=1000, simplified=500
        mock_simplify.return_value = {"type": "FeatureCollection", "features": []}

        with caplog.at_level(logging.DEBUG):
            extract_highway(highway_info, ways)

        assert "1000 coords" in caplog.text
        assert "500 coords" in caplog.text


class TestSaveHighway:
    """save_highway関数のテスト"""

    def test_saves_file_to_correct_path(self):
        """ファイルが正しいパスに保存される"""
        geojson = {"type": "FeatureCollection", "features": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "highways"
            output_dir.mkdir(parents=True)

            save_highway("test_highway", geojson, output_dir)

            expected_path = output_dir / "test_highway.json"
            assert expected_path.exists()

    def test_creates_output_directory(self):
        """ディレクトリが存在しない場合も作成"""
        geojson = {"type": "FeatureCollection", "features": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "highways"
            # ディレクトリを作成しない

            save_highway("test_highway", geojson, output_dir)

            expected_path = output_dir / "test_highway.json"
            assert expected_path.exists()

    def test_returns_file_size(self, feature_collection_factory):
        """戻り値がファイルサイズと一致"""
        geojson = feature_collection_factory(
            geometry={
                "type": "LineString",
                "coordinates": [[139.0, 35.0], [139.1, 35.1]],
            },
            feature_properties={"name": "test"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "highways"

            file_size = save_highway("test_highway", geojson, output_dir)

            expected_path = output_dir / "test_highway.json"
            assert file_size == expected_path.stat().st_size
            assert file_size > 0

    def test_japanese_filename(self):
        """日本語ファイル名で保存可能"""
        geojson = {
            "type": "FeatureCollection",
            "features": [],
            "properties": {"name": "東名高速道路"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "highways"

            save_highway("東名高速道路", geojson, output_dir)

            expected_path = output_dir / "東名高速道路.json"
            assert expected_path.exists()

            # 内容を確認
            with open(expected_path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["properties"]["name"] == "東名高速道路"
