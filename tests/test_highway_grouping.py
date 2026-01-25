"""高速道路グループ計算の単体テスト"""

import sys
from pathlib import Path

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from main import (
    CORE_HIGHWAYS,
    GROUP_ORDER,
    TOKYO_STATION,
    determine_general_group,
    distance_squared,
    get_all_coordinates,
    get_extent_segment,
    point_to_segment_distance_squared,
    segment_to_segment_distance,
    segments_intersect,
)


class TestDistanceCalculations:
    """距離計算関数のテスト"""

    def test_distance_squared_same_point(self):
        """同じ点の距離は0"""
        assert distance_squared((0, 0), (0, 0)) == 0

    def test_distance_squared_horizontal(self):
        """水平方向の距離"""
        assert distance_squared((0, 0), (3, 0)) == 9

    def test_distance_squared_vertical(self):
        """垂直方向の距離"""
        assert distance_squared((0, 0), (0, 4)) == 16

    def test_distance_squared_diagonal(self):
        """斜め方向の距離（3-4-5三角形）"""
        assert distance_squared((0, 0), (3, 4)) == 25


class TestGetExtentSegment:
    """get_extent_segment関数のテスト"""

    def test_empty_coords(self):
        """空の座標リストはNoneを返す"""
        assert get_extent_segment([]) is None

    def test_single_coord(self):
        """単一座標は同じ点を返す"""
        result = get_extent_segment([(139.0, 35.0)])
        assert result is not None
        assert result[0] == result[1]

    def test_multiple_coords(self):
        """複数座標から最近点と最遠点を取得"""
        coords = [
            (139.0, 35.0),   # 東京から遠い
            (139.7, 35.7),   # 東京に近い
            (140.0, 36.0),   # 東京から遠い
        ]
        result = get_extent_segment(coords, center=TOKYO_STATION)
        assert result is not None
        nearest, farthest = result
        # 東京駅に最も近い点は(139.7, 35.7)
        assert nearest == (139.7, 35.7)


class TestSegmentsIntersect:
    """segments_intersect関数のテスト"""

    def test_crossing_segments(self):
        """交差する線分"""
        seg1 = ((0, 0), (2, 2))
        seg2 = ((0, 2), (2, 0))
        assert segments_intersect(seg1, seg2) is True

    def test_parallel_segments(self):
        """平行な線分は交差しない"""
        seg1 = ((0, 0), (2, 0))
        seg2 = ((0, 1), (2, 1))
        assert segments_intersect(seg1, seg2) is False

    def test_non_crossing_segments(self):
        """交差しない線分"""
        seg1 = ((0, 0), (1, 0))
        seg2 = ((2, 0), (3, 0))
        assert segments_intersect(seg1, seg2) is False


class TestSegmentToSegmentDistance:
    """segment_to_segment_distance関数のテスト"""

    def test_intersecting_segments(self):
        """交差する線分の距離は0"""
        seg1 = ((0, 0), (2, 2))
        seg2 = ((0, 2), (2, 0))
        assert segment_to_segment_distance(seg1, seg2) == 0.0

    def test_parallel_horizontal_segments(self):
        """平行な水平線分の距離"""
        seg1 = ((0, 0), (2, 0))
        seg2 = ((0, 1), (2, 1))
        assert segment_to_segment_distance(seg1, seg2) == 1.0

    def test_perpendicular_segments(self):
        """直交する線分の距離"""
        seg1 = ((0, 0), (1, 0))
        seg2 = ((2, 0), (2, 1))
        assert segment_to_segment_distance(seg1, seg2) == 1.0


class TestGetAllCoordinates:
    """get_all_coordinates関数のテスト"""

    def test_empty_geojson(self):
        """空のGeoJSONは空リストを返す"""
        geojson = {"features": []}
        assert get_all_coordinates(geojson) == []

    def test_linestring(self):
        """LineStringから座標を取得"""
        geojson = {
            "features": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[139.0, 35.0], [140.0, 36.0]],
                    }
                }
            ]
        }
        coords = get_all_coordinates(geojson)
        assert len(coords) == 2
        assert (139.0, 35.0) in coords
        assert (140.0, 36.0) in coords


class TestDetermineGeneralGroup:
    """determine_general_group関数のテスト"""

    def test_with_empty_core_segments(self):
        """中心高速道路がない場合はデフォルト（東名）"""
        highway_segment = ((139.0, 35.0), (140.0, 36.0))
        result = determine_general_group(highway_segment, {})
        assert result == "東名"

    def test_nearest_core_highway(self):
        """最も近い中心高速道路のグループを返す"""
        # 北海道の座標（道央自動車道に近い）
        highway_segment = ((141.0, 43.0), (142.0, 43.5))
        # 簡易的な中心高速道路の線分
        core_segments = {
            "東名高速道路": ((139.0, 35.0), (138.0, 34.5)),  # 東京付近
            "道央自動車道": ((141.5, 43.0), (141.0, 42.5)),  # 北海道
        }
        result = determine_general_group(highway_segment, core_segments)
        assert result == "北海道"


class TestGroupOrder:
    """グループ順序の設定テスト"""

    def test_group_order_length(self):
        """グループ順序に16グループが定義されている"""
        assert len(GROUP_ORDER) == 16

    def test_group_order_starts_with_shutoko(self):
        """最初は首都高速"""
        assert GROUP_ORDER[0] == "首都高速"

    def test_group_order_ends_with_hokkaido(self):
        """最後は北海道"""
        assert GROUP_ORDER[-1] == "北海道"

    def test_core_highways_in_group_order(self):
        """中心高速道路のグループ名がGROUP_ORDERに含まれる"""
        for group_name in CORE_HIGHWAYS.values():
            assert group_name in GROUP_ORDER, f"{group_name} not in GROUP_ORDER"
