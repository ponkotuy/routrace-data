"""osm_parser モジュールの単体テスト"""

import sys
from pathlib import Path

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from osm_parser import HIGHWAY_PATTERNS, HighwayDiscoverer


class TestHighwayPatterns:
    """高速道路パターンのテスト"""

    def test_highway_patterns_unique_and_non_empty(self):
        """高速道路パターンは重複や空要素がない"""
        assert HIGHWAY_PATTERNS
        assert "" not in HIGHWAY_PATTERNS
        assert len(HIGHWAY_PATTERNS) == len(set(HIGHWAY_PATTERNS))


class TestHighwayDiscoverer:
    """HighwayDiscoverer クラスのテスト"""

    def test_extract_base_name_keiyo(self):
        """京葉道路が正しく基本名として抽出される"""
        discoverer = HighwayDiscoverer()
        base_name = discoverer._extract_base_name("京葉道路")
        assert base_name == "京葉道路"

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("東名高速道路", "東名高速道路"),
            ("東名高速道路（上り）", "東名高速道路"),
            ("首都高速1号上野線", "首都高速1号上野線"),
            ("中央自動車道上り", "中央自動車道"),
            ("京葉道路", "京葉道路"),
            ("北関東自動車道東行き", "北関東自動車道"),
            ("北関東自動車道西行き", "北関東自動車道"),
            ("第二神明道路", "第二神明道路"),
            ("第二神明北線", "第二神明北線"),
            ("播但連絡道路", "播但連絡道路"),  # 「連絡道路」を含むが優先パターン
            ("山陰自動車道:浜田バイパス", "山陰自動車道"),  # コロン以降を除去
        ],
    )
    def test_extract_base_name(self, name: str, expected: str):
        """基本名抽出が正しく動作する"""
        discoverer = HighwayDiscoverer()
        assert discoverer._extract_base_name(name) == expected

    @pytest.mark.parametrize(
        "name",
        [
            "一般道路",
            "国道1号",
            "県道○○線",
            "市道",
        ],
    )
    def test_extract_base_name_non_highway(self, name: str):
        """高速道路以外はNoneを返す"""
        discoverer = HighwayDiscoverer()
        assert discoverer._extract_base_name(name) is None

    @pytest.mark.parametrize(
        "name",
        [
            "東名高速道路入口",
            "首都高速出口",
            "○○高架橋",
            "△△新設工事",
            "名古屋高速道路16号一宮線-6号線-4号東海線高架路",
            "名古屋高速道路小牧-大高線高架路",
            "京葉道路船橋ＩＣ連絡道路",
        ],
    )
    def test_extract_base_name_excluded(self, name: str):
        """除外パターンにマッチするものはNoneを返す"""
        discoverer = HighwayDiscoverer()
        assert discoverer._extract_base_name(name) is None

    @pytest.mark.parametrize(
        "name",
        [
            "首都高速川口線-中央環状線",
            "○○高速△△線-□□線",
        ],
    )
    def test_extract_base_name_compound_route_excluded(self, name: str):
        """複合路線名（線-を含む）はNoneを返す"""
        discoverer = HighwayDiscoverer()
        assert discoverer._extract_base_name(name) is None

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("名古屋第二環状自動車道支線", "名古屋第二環状自動車道支線"),
            ("山陽自動車道倉敷早島支線", "山陽自動車道倉敷早島支線"),
            ("山陽自動車道木見支線", "山陽自動車道木見支線"),
            ("阪神高速32号新神戸トンネル", "阪神高速32号新神戸トンネル"),
        ],
    )
    def test_extract_base_name_special_routes_not_excluded(self, name: str, expected: str):
        """支線やトンネル路線は除外されない"""
        discoverer = HighwayDiscoverer()
        assert discoverer._extract_base_name(name) == expected
