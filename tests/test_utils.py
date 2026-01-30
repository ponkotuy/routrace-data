"""utils モジュールの単体テスト"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from utils import format_size, save_geojson


class TestFormatSize:
    """format_size関数のテスト"""

    def test_bytes(self):
        """バイト単位"""
        assert format_size(0) == "0 B"
        assert format_size(1) == "1 B"
        assert format_size(512) == "512 B"
        assert format_size(1023) == "1023 B"

    def test_kilobytes(self):
        """キロバイト単位"""
        assert format_size(1024) == "1 KB"
        assert format_size(1536) == "2 KB"  # 1.5 KB -> 2 KB (rounded)
        assert format_size(10240) == "10 KB"
        assert format_size(1024 * 1024 - 1) == "1024 KB"

    def test_megabytes(self):
        """メガバイト単位"""
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 2) == "2.0 MB"
        assert format_size(1024 * 1024 * 10) == "10.0 MB"
        assert format_size(int(1024 * 1024 * 1.5)) == "1.5 MB"


class TestSaveGeojson:
    """save_geojson関数のテスト"""

    def test_save_and_read(self):
        """GeoJSONを保存して読み込めることを確認"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [139.7, 35.6]},
                    "properties": {"name": "Tokyo"},
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            file_size = save_geojson(geojson, output_path)

            assert output_path.exists()
            assert file_size > 0
            assert file_size == output_path.stat().st_size

            # 内容を確認
            import json
            with open(output_path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["type"] == "FeatureCollection"
            assert len(loaded["features"]) == 1

    def test_creates_parent_directories(self):
        """親ディレクトリが存在しない場合も作成される"""
        geojson = {"type": "FeatureCollection", "features": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "test.json"
            save_geojson(geojson, output_path)

            assert output_path.exists()

    def test_japanese_characters(self):
        """日本語文字が正しく保存される"""
        geojson = {
            "type": "FeatureCollection",
            "features": [],
            "properties": {"name": "東京"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            save_geojson(geojson, output_path)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()
            assert "東京" in content
