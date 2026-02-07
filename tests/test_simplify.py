"""simplify モジュールの単体テスト"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from simplify import get_coordinate_count, simplify_geojson


class TestSimplifyGeojson:
    """simplify_geojson関数のテスト"""

    def test_simplify_linestring(self, feature_collection_factory):
        """LineStringが簡略化される"""
        # 直線上の点は間引かれる
        geojson = feature_collection_factory(
            geometry={
                "type": "LineString",
                "coordinates": [
                    [0, 0],
                    [0.0001, 0.0001],  # 直線上の中間点
                    [0.0002, 0.0002],
                    [1, 1],
                ],
            },
            feature_properties={"name": "test"},
        )

        result = simplify_geojson(geojson, tolerance=0.001)

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1
        coords = result["features"][0]["geometry"]["coordinates"]
        # 中間点が間引かれて座標数が減る
        assert len(coords) < 4
        # 始点と終点は保持（shapelyはtupleを返す）
        assert tuple(coords[0]) == (0, 0)
        assert tuple(coords[-1]) == (1, 1)

    def test_simplify_multilinestring(self, feature_collection_factory):
        """MultiLineStringが簡略化される"""
        geojson = feature_collection_factory(
            geometry={
                "type": "MultiLineString",
                "coordinates": [
                    [[0, 0], [0.0001, 0], [1, 0]],
                    [[0, 1], [0.0001, 1], [1, 1]],
                ],
            },
        )

        result = simplify_geojson(geojson, tolerance=0.001)

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1
        geometry = result["features"][0]["geometry"]
        assert geometry["type"] == "MultiLineString"

    def test_non_featurecollection_returned_as_is(self):
        """FeatureCollection以外はそのまま返される"""
        geojson = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
        }

        result = simplify_geojson(geojson)

        assert result == geojson

    def test_skip_feature_with_no_geometry(self):
        """geometryがないfeatureはスキップされる"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": None, "properties": {}},
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                    "properties": {},
                },
            ],
        }

        result = simplify_geojson(geojson)

        assert len(result["features"]) == 1

    def test_preserves_properties(self):
        """propertiesが保持される"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                    "properties": {"name": "test", "ref": "E1"},
                }
            ],
        }

        result = simplify_geojson(geojson)

        props = result["features"][0]["properties"]
        assert props["name"] == "test"
        assert props["ref"] == "E1"

    def test_copies_collection_properties(self):
        """FeatureCollectionのpropertiesがコピーされる"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                    "properties": {},
                }
            ],
            "properties": {"source": "test"},
        }

        result = simplify_geojson(geojson, tolerance=0.001)

        assert result["properties"]["source"] == "test"
        assert result["properties"]["simplified"] is True
        assert result["properties"]["tolerance"] == 0.001

    def test_default_tolerance(self):
        """デフォルトのtoleranceが使用される"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                    "properties": {},
                }
            ],
            "properties": {},
        }

        result = simplify_geojson(geojson)

        # config.SIMPLIFY_TOLERANCE = 0.001
        assert result["properties"]["tolerance"] == 0.001


class TestGetCoordinateCount:
    """get_coordinate_count関数のテスト"""

    def test_count_linestring_coordinates(self):
        """LineStringの座標数をカウント"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[0, 0], [1, 1], [2, 2]],
                    },
                    "properties": {},
                }
            ],
        }

        count = get_coordinate_count(geojson)

        assert count == 3

    def test_count_multilinestring_coordinates(self):
        """MultiLineStringの座標数をカウント"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [
                            [[0, 0], [1, 1]],
                            [[2, 2], [3, 3], [4, 4]],
                        ],
                    },
                    "properties": {},
                }
            ],
        }

        count = get_coordinate_count(geojson)

        assert count == 5

    def test_count_multiple_features(self):
        """複数featureの座標数を合計"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[0, 0], [1, 1]],
                    },
                    "properties": {},
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[2, 2], [3, 3], [4, 4]],
                    },
                    "properties": {},
                },
            ],
        }

        count = get_coordinate_count(geojson)

        assert count == 5

    def test_empty_featurecollection(self):
        """空のFeatureCollectionは0を返す"""
        geojson = {"type": "FeatureCollection", "features": []}

        count = get_coordinate_count(geojson)

        assert count == 0

    def test_skip_feature_with_no_geometry(self):
        """geometryがないfeatureはスキップされる"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": None, "properties": {}},
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[0, 0], [1, 1]],
                    },
                    "properties": {},
                },
            ],
        }

        count = get_coordinate_count(geojson)

        assert count == 2

    def test_count_point_coordinates(self):
        """Pointの座標数をカウント"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                }
            ],
        }

        count = get_coordinate_count(geojson)

        assert count == 1

    def test_count_polygon_coordinates(self):
        """Polygonの座標数をカウント"""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    },
                    "properties": {},
                }
            ],
        }

        count = get_coordinate_count(geojson)

        assert count == 5
