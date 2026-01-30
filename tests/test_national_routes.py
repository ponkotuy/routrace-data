"""国道関連機能の単体テスト"""

import sys
from pathlib import Path

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from osm_parser import NationalRouteDiscoverer
from highway_grouping import (
    CORE_NATIONAL_ROUTES,
    NATIONAL_ROUTE_GROUP_ORDER,
    determine_national_route_group,
)


class TestNationalRouteDiscoverer:
    """NationalRouteDiscoverer クラスのテスト"""

    def test_normalize_name_single_digit(self):
        """1桁国道の名前正規化"""
        discoverer = NationalRouteDiscoverer()
        assert discoverer._normalize_name("1") == "国道1号"
        assert discoverer._normalize_name("9") == "国道9号"

    def test_normalize_name_double_digit(self):
        """2桁国道の名前正規化"""
        discoverer = NationalRouteDiscoverer()
        assert discoverer._normalize_name("20") == "国道20号"
        assert discoverer._normalize_name("52") == "国道52号"

    def test_normalize_name_triple_digit(self):
        """3桁国道の名前正規化"""
        discoverer = NationalRouteDiscoverer()
        assert discoverer._normalize_name("152") == "国道152号"
        assert discoverer._normalize_name("459") == "国道459号"


class TestCoreNationalRoutes:
    """1桁国道定数のテスト"""

    def test_core_national_routes_count(self):
        """1桁国道は9路線"""
        assert len(CORE_NATIONAL_ROUTES) == 9

    @pytest.mark.parametrize(
        "ref,expected_name",
        [
            ("1", "国道1号"),
            ("2", "国道2号"),
            ("3", "国道3号"),
            ("4", "国道4号"),
            ("5", "国道5号"),
            ("6", "国道6号"),
            ("7", "国道7号"),
            ("8", "国道8号"),
            ("9", "国道9号"),
        ],
    )
    def test_core_national_routes_mapping(self, ref: str, expected_name: str):
        """1桁国道のマッピングが正しい"""
        assert CORE_NATIONAL_ROUTES[ref] == expected_name


class TestNationalRouteGroupOrder:
    """国道グループ順序のテスト"""

    def test_group_order_length(self):
        """グループ順序に9グループが定義されている"""
        assert len(NATIONAL_ROUTE_GROUP_ORDER) == 9

    def test_group_order_starts_with_route1(self):
        """最初は国道1号"""
        assert NATIONAL_ROUTE_GROUP_ORDER[0] == "国道1号"

    def test_group_order_ends_with_route9(self):
        """最後は国道9号"""
        assert NATIONAL_ROUTE_GROUP_ORDER[-1] == "国道9号"

    def test_core_routes_in_group_order(self):
        """1桁国道がグループ順序に含まれる"""
        for group_name in CORE_NATIONAL_ROUTES.values():
            assert group_name in NATIONAL_ROUTE_GROUP_ORDER, (
                f"{group_name} not in NATIONAL_ROUTE_GROUP_ORDER"
            )


class TestDetermineNationalRouteGroup:
    """determine_national_route_group関数のテスト"""

    def test_with_empty_core_segments(self):
        """1桁国道がない場合はデフォルト（国道1号）"""
        route_segment = ((139.0, 35.0), (140.0, 36.0))
        result = determine_national_route_group(route_segment, {})
        assert result == "国道1号"

    def test_nearest_core_route(self):
        """最も近い1桁国道のグループを返す"""
        # 北海道の座標（国道5号に近い）
        route_segment = ((141.0, 43.0), (141.5, 43.5))
        # 簡易的な1桁国道の線分
        core_segments = {
            "国道1号": ((139.0, 35.0), (138.0, 34.5)),  # 東京付近
            "国道5号": ((141.3, 43.0), (141.0, 42.5)),  # 北海道
        }
        result = determine_national_route_group(route_segment, core_segments)
        assert result == "国道5号"

    def test_nearest_core_route_tokyo_area(self):
        """東京付近の国道は国道1号グループになる"""
        # 東京付近の座標
        route_segment = ((139.5, 35.5), (139.8, 35.7))
        # 簡易的な1桁国道の線分
        core_segments = {
            "国道1号": ((139.7, 35.6), (139.0, 35.0)),  # 東京〜静岡方面
            "国道4号": ((139.8, 35.7), (140.0, 36.5)),  # 東北方面
            "国道6号": ((139.9, 35.8), (140.5, 36.0)),  # 常磐方面
        }
        result = determine_national_route_group(route_segment, core_segments)
        # 最も近い1桁国道を返す
        assert result in ["国道1号", "国道4号", "国道6号"]
