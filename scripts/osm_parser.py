"""OSMデータパーサー"""

import logging
from pathlib import Path

import osmium

logger = logging.getLogger(__name__)


class HighwayHandler(osmium.SimpleHandler):
    """高速道路データを抽出するハンドラー"""

    def __init__(self):
        super().__init__()
        self.ways = []

    def way(self, w):
        tags = dict(w.tags)
        highway_type = tags.get("highway")

        # motorway または motorway_link のみ抽出
        if highway_type not in ("motorway", "motorway_link"):
            return

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

        self.ways.append({
            "id": w.id,
            "tags": tags,
            "coordinates": coordinates,
        })


def parse_highways(pbf_path: Path) -> list[dict]:
    """
    PBFファイルから高速道路データを抽出

    Args:
        pbf_path: PBFファイルパス

    Returns:
        高速道路wayのリスト
    """
    logger.info(f"OSMデータ解析中: {pbf_path}")

    handler = HighwayHandler()

    # NodeLocationsForWaysを使用してノード座標を取得可能にする
    handler.apply_file(
        str(pbf_path),
        locations=True,
        idx="flex_mem",
    )

    logger.info(f"高速道路データ抽出完了: {len(handler.ways)} ways")

    return handler.ways


def filter_by_name(ways: list[dict], query_name: str) -> list[dict]:
    """
    名前でフィルタリング

    Args:
        ways: 高速道路wayのリスト
        query_name: 検索する名前（部分一致）

    Returns:
        フィルタリングされたwayのリスト
    """
    filtered = []

    for way in ways:
        name = way["tags"].get("name", "")
        if query_name in name:
            filtered.append(way)

    return filtered


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
