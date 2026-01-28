"""OSMデータパーサー"""

import logging
import re
from pathlib import Path

import osmium

logger = logging.getLogger(__name__)

# 高速道路として認識する名前パターン
HIGHWAY_PATTERNS = ['高速', '自動車道', '京葉道路']

# 除外パターン（高架橋、入口、出口などは除外）
EXCLUDE_PATTERNS = ['高架橋', '入口', '出口', '新設工事', '高架路', '連絡道路']


class HighwayDiscoverer(osmium.SimpleHandler):
    """高速道路のrelationを自動検出するハンドラー"""

    def __init__(self):
        super().__init__()
        # 基本名 -> set of way IDs
        self.way_ids_by_name: dict[str, set[int]] = {}
        # 基本名 -> relation情報（name_en, ref等）
        self.highway_info: dict[str, dict] = {}

    def _extract_base_name(self, name: str) -> str | None:
        """名前から基本名を抽出（括弧や方向を除去）"""
        # 除外パターンをチェック
        for pattern in EXCLUDE_PATTERNS:
            if pattern in name:
                return None

        # 複合路線名を除外（例: 首都高速川口線-中央環状線）
        if '線-' in name:
            return None

        # 高速道路パターンをチェック
        if not any(p in name for p in HIGHWAY_PATTERNS):
            return None

        # 括弧以降を除去
        base_name = re.sub(r'[（(].*$', '', name)
        # 方向を除去
        base_name = re.sub(r'(上り|下り|内回り|外回り|東行き|西行き|北行き|南行き)$', '', base_name)
        base_name = base_name.strip()

        return base_name if base_name else None

    def relation(self, r):
        tags = dict(r.tags)

        # route=road のrelationのみ対象
        if tags.get("route") != "road":
            return

        # 名前を取得
        name = tags.get("name", "")
        if not name:
            return

        # 基本名を抽出
        base_name = self._extract_base_name(name)
        if not base_name:
            return

        # way IDを収集
        if base_name not in self.way_ids_by_name:
            self.way_ids_by_name[base_name] = set()
            self.highway_info[base_name] = {
                "name": base_name,
                "name_en": tags.get("name:en", ""),
                "ref": tags.get("ref", ""),
            }

        for member in r.members:
            if member.type == "w":
                self.way_ids_by_name[base_name].add(member.ref)

        # 英語名やrefが空なら更新
        if not self.highway_info[base_name]["name_en"] and tags.get("name:en"):
            self.highway_info[base_name]["name_en"] = tags.get("name:en", "")
        if not self.highway_info[base_name]["ref"] and tags.get("ref"):
            self.highway_info[base_name]["ref"] = tags.get("ref", "")


class BulkWayCollector(osmium.SimpleHandler):
    """指定された全way IDのwayデータを一括収集するハンドラー"""

    def __init__(self, all_way_ids: set[int]):
        super().__init__()
        self.all_way_ids = all_way_ids
        # way_id -> way data
        self.ways_by_id: dict[int, dict] = {}

    def way(self, w):
        if w.id not in self.all_way_ids:
            return

        tags = dict(w.tags)

        # ノード座標を取得
        try:
            coordinates = [
                [node.lon, node.lat]
                for node in w.nodes
                if node.location.valid()
            ]
        except osmium.InvalidLocationError:
            return

        if len(coordinates) < 2:
            return

        self.ways_by_id[w.id] = {
            "id": w.id,
            "tags": tags,
            "coordinates": coordinates,
        }


def discover_highways(pbf_path: Path) -> tuple[list[dict], dict[str, set[int]]]:
    """
    PBFから高速道路を自動検出

    Args:
        pbf_path: フィルタリング済みPBFファイルパス

    Returns:
        (高速道路情報のリスト, 名前 -> way IDセットのマッピング)
    """
    logger.info("高速道路を自動検出中...")

    handler = HighwayDiscoverer()
    handler.apply_file(str(pbf_path))

    # 高速道路情報をリストに変換
    highways = []
    for name, info in sorted(handler.highway_info.items()):
        way_count = len(handler.way_ids_by_name[name])
        highways.append({
            "name": info["name"],
            "name_en": info["name_en"],
            "ref": info["ref"],
            "way_count": way_count,
        })

    total_ways = sum(len(ids) for ids in handler.way_ids_by_name.values())
    logger.info(f"検出完了: {len(highways)}路線, 合計 {total_ways} ways")

    return highways, handler.way_ids_by_name


def extract_all_ways(
    pbf_path: Path,
    all_way_ids: set[int],
) -> dict[int, dict]:
    """
    指定された全way IDのwayを一括抽出

    Args:
        pbf_path: PBFファイルパス
        all_way_ids: 抽出するway IDのセット

    Returns:
        way_id -> way data のマッピング
    """
    logger.info(f"wayデータを一括抽出中... ({len(all_way_ids)} ways)")

    handler = BulkWayCollector(all_way_ids)
    handler.apply_file(
        str(pbf_path),
        locations=True,
        idx="flex_mem",
    )

    logger.info(f"way抽出完了: {len(handler.ways_by_id)} ways")

    return handler.ways_by_id


def get_ways_for_highway(
    ways_by_id: dict[int, dict],
    way_ids: set[int],
) -> list[dict]:
    """
    メモリ内のwayデータから指定されたway IDのwayを取得

    Args:
        ways_by_id: way_id -> way data のマッピング
        way_ids: 取得するway IDのセット

    Returns:
        wayのリスト
    """
    return [ways_by_id[wid] for wid in way_ids if wid in ways_by_id]


def ways_to_geojson(ways: list[dict]) -> dict:
    """
    wayリストをGeoJSON FeatureCollectionに変換

    Args:
        ways: 高速道路wayのリスト

    Returns:
        GeoJSON FeatureCollection
    """
    features = []

    for way in ways:
        tags = way["tags"]

        feature = {
            "type": "Feature",
            "properties": {
                "name": tags.get("name", ""),
                "ref": tags.get("ref", ""),
                "highway": tags.get("highway", ""),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": way["coordinates"],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }
