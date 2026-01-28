"""detect_group関数の単体テスト"""

import sys
from pathlib import Path

# scriptsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from main import GROUP_ALIASES, GROUP_PREFIXES, detect_group


class TestDetectGroup:
    """detect_group関数のテスト"""

    @pytest.mark.parametrize(
        "name,expected",
        [
            # 首都高速
            ("首都高速1号上野線", "首都高速"),
            ("首都高速1号羽田線", "首都高速"),
            ("首都高速2号目黒線", "首都高速"),
            ("首都高速中央環状線", "首都高速"),
            ("首都高速八重洲線", "首都高速"),
            ("首都高速湾岸線", "首都高速"),
            ("首都高速神奈川1号横羽線", "首都高速"),
            ("首都高速神奈川7号横浜北線", "首都高速"),
            ("首都高速神奈川7号横浜北西線", "首都高速"),
            ("首都高速都心環状線", "首都高速"),
            ("首都高速埼玉大宮線", "首都高速"),
            ("首都高速川口線", "首都高速"),
            ("首都高速川口線-中央環状線", "首都高速"),
            # 阪神高速
            ("阪神高速1号環状線", "阪神高速"),
            ("阪神高速11号池田線", "阪神高速"),
            ("阪神高速3号神戸線", "阪神高速"),
            ("阪神高速7号北神戸線", "阪神高速"),
            ("阪神高速7号北神戸線北延伸線", "阪神高速"),
            ("阪神高速31号神戸山手線", "阪神高速"),
            ("阪神高速32号新神戸トンネル", "阪神高速"),
            # 名古屋高速
            ("名古屋高速1号楠線", "名古屋高速"),
            ("名古屋高速11号小牧線", "名古屋高速"),
            ("名古屋高速環状線", "名古屋高速"),
            # 名古屋高速道路（表記揺れ）
            ("名古屋高速道路小牧-大高線高架路", "名古屋高速"),
            ("名古屋高速道路16号一宫線-6号線-4号東海線高架路", "名古屋高速"),
            # 名古屋で始まる自動車道も名古屋高速グループ
            ("名古屋第二環状自動車道", "名古屋高速"),
            # 広島高速
            ("広島高速1号", "広島高速"),
            ("広島高速2号", "広島高速"),
            ("広島高速3号", "広島高速"),
            ("広島高速4号", "広島高速"),
            # 北九州高速（北九州都市高速はエイリアス）
            ("北九州高速1号線", "北九州高速"),
            ("北九州都市高速1号線", "北九州高速"),
            ("北九州都市高速2号線", "北九州高速"),
            ("北九州都市高速5号線", "北九州高速"),
            # 福岡高速（福岡都市高速はエイリアス）
            ("福岡高速1号香椎線", "福岡高速"),
            ("福岡高速6号アイランドシティ線", "福岡高速"),
            ("福岡都市高速1号香椎線", "福岡高速"),
            ("福岡都市高速2号太宰府線", "福岡高速"),
            ("福岡都市高速環状線", "福岡高速"),
        ],
    )
    def test_grouped_highways(self, name: str, expected: str):
        """都市高速道路はグループが設定される"""
        assert detect_group(name) == expected

    @pytest.mark.parametrize(
        "name",
        [
            # NEXCO高速道路（グループなし）
            "東名高速道路",
            "名神高速道路",
            "中央自動車道",
            "東北自動車道",
            "関越自動車道",
            "常磐自動車道",
            "九州自動車道",
            "山陽自動車道",
            "中国自動車道",
            "北陸自動車道",
            "東海北陸自動車道",
            "新東名高速",
            "新名神高速道路",
            # その他自動車道
            "道央自動車道",
            "沖縄自動車道",
            "徳島自動車道",
            "松山自動車道",
            # 接頭辞が似ているが別物
            "広島自動車道",  # 広島高速とは別
            "東広島呉自動車道",
        ],
    )
    def test_non_grouped_highways(self, name: str):
        """NEXCO等の高速道路はグループなし"""
        assert detect_group(name) is None

    def test_group_prefixes_are_defined(self):
        """グループプレフィックスが定義されている"""
        assert len(GROUP_PREFIXES) > 0
        assert "首都高速" in GROUP_PREFIXES
        assert "阪神高速" in GROUP_PREFIXES
        assert "名古屋高速" in GROUP_PREFIXES
        assert "北九州高速" in GROUP_PREFIXES
        assert "福岡高速" in GROUP_PREFIXES

    def test_group_aliases(self):
        """グループエイリアスが正しく設定されている"""
        assert "北九州都市高速" in GROUP_ALIASES
        assert GROUP_ALIASES["北九州都市高速"] == "北九州高速"
        assert "福岡都市高速" in GROUP_ALIASES
        assert GROUP_ALIASES["福岡都市高速"] == "福岡高速"

    def test_empty_string(self):
        """空文字列はグループなし"""
        assert detect_group("") is None
