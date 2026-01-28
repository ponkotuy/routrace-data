"""main.py のテスト"""

import pytest
import sys
from pathlib import Path

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from main import group_ways_by_ref, should_split_by_ref, is_national_route_ref


class TestGroupWaysByRef:
    """group_ways_by_ref関数のテスト"""

    def test_single_ref(self):
        """単一refは分割しない"""
        ways = [
            {"tags": {"ref": "E8"}, "coordinates": [[0, 0], [1, 1]]},
            {"tags": {"ref": "E8"}, "coordinates": [[1, 1], [2, 2]]},
        ]
        grouped = group_ways_by_ref(ways)
        assert len(grouped) == 1
        assert "E8" in grouped
        assert len(grouped["E8"]) == 2

    def test_multiple_refs(self):
        """複数refは分割"""
        ways = [
            {"tags": {"ref": "E19"}, "coordinates": [[0, 0], [1, 1]]},
            {"tags": {"ref": "E20"}, "coordinates": [[10, 10], [11, 11]]},
        ]
        grouped = group_ways_by_ref(ways)
        assert len(grouped) == 2
        assert "E19" in grouped
        assert "E20" in grouped

    def test_no_ref_merged_to_nearest(self):
        """refなしは最寄りに統合"""
        ways = [
            {"tags": {"ref": "E19"}, "coordinates": [[0, 0], [1, 1]]},
            {"tags": {"ref": "E20"}, "coordinates": [[100, 100], [101, 101]]},
            {"tags": {}, "coordinates": [[0.5, 0.5], [1.5, 1.5]]},  # E19に近い
        ]
        grouped = group_ways_by_ref(ways)
        assert len(grouped["E19"]) == 2  # E19 + no-ref
        assert len(grouped["E20"]) == 1

    def test_compound_ref(self):
        """複合refは最初の部分を使用"""
        ways = [
            {"tags": {"ref": "E4;E13"}, "coordinates": [[0, 0], [1, 1]]},
            {"tags": {"ref": "E4"}, "coordinates": [[1, 1], [2, 2]]},
        ]
        grouped = group_ways_by_ref(ways)
        assert len(grouped) == 1
        assert len(grouped["E4"]) == 2

    def test_all_no_ref(self):
        """全wayがrefなしの場合は空文字キー"""
        ways = [
            {"tags": {}, "coordinates": [[0, 0], [1, 1]]},
            {"tags": {}, "coordinates": [[1, 1], [2, 2]]},
        ]
        grouped = group_ways_by_ref(ways)
        assert len(grouped) == 1
        assert "" in grouped
        assert len(grouped[""]) == 2

    def test_empty_ways(self):
        """空リストの場合"""
        grouped = group_ways_by_ref([])
        assert grouped == {}


class TestIsNationalRouteRef:
    """is_national_route_ref関数のテスト"""

    def test_numeric_only_is_national_route(self):
        """数字のみは国道"""
        assert is_national_route_ref("4") is True
        assert is_national_route_ref("152") is True
        assert is_national_route_ref("353") is True

    def test_alphanumeric_is_expressway(self):
        """英字を含むものは高速道路"""
        assert is_national_route_ref("E1") is False
        assert is_national_route_ref("E20") is False
        assert is_national_route_ref("C2") is False
        assert is_national_route_ref("E1A") is False

    def test_empty_is_not_national_route(self):
        """空文字は国道ではない"""
        assert is_national_route_ref("") is False


class TestShouldSplitByRef:
    """should_split_by_ref関数のテスト"""

    def test_multiple_refs_should_split(self):
        """一般高速: 複数refは分割"""
        assert should_split_by_ref({"E19": [], "E20": []}, "中央自動車道") is True

    def test_single_ref_should_not_split(self):
        """一般高速: 単一refは分割しない"""
        assert should_split_by_ref({"E8": []}, "北陸自動車道") is False

    def test_only_empty_should_not_split(self):
        """空refのみは分割しない"""
        assert should_split_by_ref({"": []}, "中央自動車道") is False

    def test_one_ref_and_empty_should_not_split(self):
        """refと空文字の組み合わせは分割しない（空文字は無視）"""
        assert should_split_by_ref({"E8": [], "": []}, "北陸自動車道") is False

    def test_three_refs_should_split(self):
        """3つ以上のrefも分割"""
        assert should_split_by_ref({"E1": [], "E2": [], "E3": []}, "中央自動車道") is True

    def test_national_route_refs_ignored_for_general_highway(self):
        """一般高速: 国道refは分割判定でカウントしない"""
        # E20と4（国道4号）があっても、有効なのはE20のみなので分割しない
        assert should_split_by_ref({"E20": [], "4": []}, "中央自動車道") is False

    def test_national_route_refs_valid_for_urban_expressway(self):
        """都市高速: 数字のみのrefも有効（路線番号）"""
        # 首都高速は1号、2号など数字のみのrefを使用
        assert should_split_by_ref({"1": [], "2": []}, "首都高速1号上野線") is True

    def test_mixed_refs_for_general_highway(self):
        """一般高速: 複数の高速道路refがあれば分割"""
        # E19とE20があり、4は国道なので無視 → 分割対象
        assert should_split_by_ref({"E19": [], "E20": [], "4": []}, "中央自動車道") is True
