"""国道関連機能の単体テスト"""

import sys
from pathlib import Path

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from osm_parser import (
    NationalRouteDiscoverer,
    NationalRouteStandaloneWayDiscoverer,
    _is_valid_national_route_ref,
)
from highway_grouping import (
    NATIONAL_ROUTE_GROUP_ORDER,
    NATIONAL_ROUTE_GROUPS,
    determine_national_route_group,
    get_all_core_national_route_refs,
    get_core_national_route_name,
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


class TestNationalRouteGroups:
    """国道グループ定数のテスト"""

    def test_national_route_groups_have_non_empty_refs(self):
        """各グループに中心国道が定義されている"""
        assert NATIONAL_ROUTE_GROUPS
        assert all(refs for refs in NATIONAL_ROUTE_GROUPS.values())

    def test_national_route_groups_have_unique_refs(self):
        """中心国道ref番号は重複しない"""
        all_refs = [ref for refs in NATIONAL_ROUTE_GROUPS.values() for ref in refs]
        assert all_refs
        assert len(all_refs) == len(set(all_refs))

    def test_national_route_groups_refs_are_numeric(self):
        """中心国道ref番号は数字のみ"""
        for ref in get_all_core_national_route_refs():
            assert ref.isdigit()

    def test_get_all_core_national_route_refs(self):
        """全ての中心国道のref番号を取得"""
        refs = get_all_core_national_route_refs()
        assert refs == {"1", "2", "3", "4", "5", "6", "7", "8", "9", "11", "42", "279", "334"}

    def test_get_core_national_route_name(self):
        """ref番号から国道名を生成"""
        assert get_core_national_route_name("1") == "国道1号"
        assert get_core_national_route_name("11") == "国道11号"


class TestNationalRouteGroupOrder:
    """国道グループ順序のテスト"""

    def test_group_order_unique(self):
        """グループ順序は重複がない"""
        assert NATIONAL_ROUTE_GROUP_ORDER
        assert len(NATIONAL_ROUTE_GROUP_ORDER) == len(set(NATIONAL_ROUTE_GROUP_ORDER))

    def test_all_groups_in_group_order(self):
        """全てのグループがグループ順序に含まれる"""
        assert set(NATIONAL_ROUTE_GROUP_ORDER) == set(NATIONAL_ROUTE_GROUPS)
        for group_name in NATIONAL_ROUTE_GROUPS:
            assert group_name in NATIONAL_ROUTE_GROUP_ORDER, (
                f"{group_name} not in NATIONAL_ROUTE_GROUP_ORDER"
            )


class TestDetermineNationalRouteGroup:
    """determine_national_route_group関数のテスト"""

    def test_with_empty_core_segments(self):
        """中心国道がない場合はデフォルト（東名阪）"""
        route_segment = ((139.0, 35.0), (140.0, 36.0))
        result = determine_national_route_group(route_segment, {})
        assert result == "東名阪"

    def test_nearest_core_route_hokkaido(self):
        """北海道の国道は北海道グループになる"""
        # 北海道の座標（国道5号に近い）
        route_segment = ((141.0, 43.0), (141.5, 43.5))
        # 中心国道の線分
        core_segments = {
            "国道1号": ((139.0, 35.0), (138.0, 34.5)),  # 東京付近
            "国道5号": ((141.3, 43.0), (141.0, 42.5)),  # 北海道
        }
        result = determine_national_route_group(route_segment, core_segments)
        assert result == "北海道"

    def test_nearest_core_route_tokyo_area(self):
        """東京付近の国道は東名阪または東北グループになる"""
        # 東京付近の座標
        route_segment = ((139.5, 35.5), (139.8, 35.7))
        # 中心国道の線分
        core_segments = {
            "国道1号": ((139.7, 35.6), (139.0, 35.0)),  # 東京〜静岡方面
            "国道4号": ((139.8, 35.7), (140.0, 36.5)),  # 東北方面
            "国道6号": ((139.9, 35.8), (140.5, 36.0)),  # 常磐方面
        }
        result = determine_national_route_group(route_segment, core_segments)
        # 最も近い中心国道を持つグループを返す
        assert result in ["東名阪", "東北"]

    def test_multi_core_route_group(self):
        """複数の中心国道を持つグループのテスト"""
        # 山陰地方の座標（国道9号に近い）
        route_segment = ((133.0, 35.5), (134.0, 35.5))
        # 中心国道の線分
        core_segments = {
            "国道1号": ((139.0, 35.0), (136.0, 35.0)),  # 東京〜大阪
            "国道2号": ((135.0, 34.7), (132.0, 34.5)),  # 大阪〜広島
            "国道9号": ((135.5, 35.0), (132.5, 35.5)),  # 京都〜山陰
        }
        result = determine_national_route_group(route_segment, core_segments)
        # 国道2号と9号は両方とも中国グループ
        assert result == "中国"


class TestIsValidNationalRouteRef:
    """_is_valid_national_route_ref関数のテスト"""

    def test_valid_single_digit(self):
        """1桁の有効な国道番号"""
        assert _is_valid_national_route_ref("1") is True
        assert _is_valid_national_route_ref("9") is True

    def test_valid_double_digit(self):
        """2桁の有効な国道番号"""
        assert _is_valid_national_route_ref("10") is True
        assert _is_valid_national_route_ref("99") is True

    def test_valid_triple_digit(self):
        """3桁の有効な国道番号"""
        assert _is_valid_national_route_ref("100") is True
        assert _is_valid_national_route_ref("197") is True
        assert _is_valid_national_route_ref("507") is True

    def test_invalid_zero(self):
        """0は無効"""
        assert _is_valid_national_route_ref("0") is False

    def test_invalid_over_507(self):
        """507を超える番号は無効"""
        assert _is_valid_national_route_ref("508") is False
        assert _is_valid_national_route_ref("1000") is False

    def test_invalid_empty(self):
        """空文字は無効"""
        assert _is_valid_national_route_ref("") is False

    def test_invalid_non_digit(self):
        """数字以外は無効"""
        assert _is_valid_national_route_ref("abc") is False
        assert _is_valid_national_route_ref("1a") is False
        assert _is_valid_national_route_ref("E1") is False


class TestNationalRouteStandaloneWayDiscoverer:
    """NationalRouteStandaloneWayDiscoverer クラスのテスト"""

    def test_excludes_relation_way_ids(self):
        """relationで検出済みのway IDは除外される"""
        relation_way_ids = {100, 200, 300}
        discoverer = NationalRouteStandaloneWayDiscoverer(relation_way_ids)

        # relation_way_idsが正しく設定されていることを確認
        assert discoverer.relation_way_ids == relation_way_ids
        assert 100 in discoverer.relation_way_ids
        assert 999 not in discoverer.relation_way_ids

    def test_initial_state(self):
        """初期状態でway_ids_by_refは空"""
        discoverer = NationalRouteStandaloneWayDiscoverer(set())
        assert discoverer.way_ids_by_ref == {}

    def test_is_ref_consistent_with_name_no_name(self):
        """nameがない場合は矛盾なし"""
        discoverer = NationalRouteStandaloneWayDiscoverer(set())
        assert discoverer._is_ref_consistent_with_name("56", "") is True
        assert discoverer._is_ref_consistent_with_name("56", None) is True

    def test_is_ref_consistent_with_name_no_route_number(self):
        """nameに国道番号がない場合は矛盾なし"""
        discoverer = NationalRouteStandaloneWayDiscoverer(set())
        assert discoverer._is_ref_consistent_with_name("56", "○○バイパス") is True
        assert discoverer._is_ref_consistent_with_name("56", "宇和島道路") is True

    def test_is_ref_consistent_with_name_matching(self):
        """nameとrefが一致する場合は矛盾なし"""
        discoverer = NationalRouteStandaloneWayDiscoverer(set())
        assert discoverer._is_ref_consistent_with_name("56", "国道56号") is True
        assert discoverer._is_ref_consistent_with_name("197", "国道197号バイパス") is True

    def test_is_ref_consistent_with_name_mismatch(self):
        """nameとrefが矛盾する場合"""
        discoverer = NationalRouteStandaloneWayDiscoverer(set())
        assert discoverer._is_ref_consistent_with_name("56", "国道197号") is False
        assert discoverer._is_ref_consistent_with_name("197", "国道56号") is False
