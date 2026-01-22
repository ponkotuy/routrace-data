"""OSMデータパーサー"""

import logging
from pathlib import Path

import osmium

logger = logging.getLogger(__name__)


class AllRelationsCollector(osmium.SimpleHandler):
    """全高速道路のrelationからway IDを収集するハンドラー"""

    def __init__(self, query_names: list[str]):
        super().__init__()
        self.query_names = query_names
        # query_name -> set of way IDs
        self.way_ids_by_query: dict[str, set[int]] = {name: set() for name in query_names}

    def relation(self, r):
        tags = dict(r.tags)

        # route=road のrelationのみ対象
        if tags.get("route") != "road":
            return

        # highway:name または name を取得
        highway_name = tags.get("highway:name", "")
        name = tags.get("name", "")

        # どのquery_nameにマッチするか確認
        for query_name in self.query_names:
            if highway_name.startswith(query_name) or name.startswith(query_name):
                # メンバーのway IDを収集
                for member in r.members:
                    if member.type == "w":
                        self.way_ids_by_query[query_name].add(member.ref)


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


def collect_all_highway_way_ids(
    pbf_path: Path,
    query_names: list[str],
) -> dict[str, set[int]]:
    """
    全高速道路のway IDを一括収集

    Args:
        pbf_path: フィルタリング済みPBFファイルパス
        query_names: 検索する高速道路名のリスト

    Returns:
        query_name -> way IDのセット のマッピング
    """
    logger.info(f"全高速道路のrelationを収集中... ({len(query_names)}路線)")

    handler = AllRelationsCollector(query_names)
    handler.apply_file(str(pbf_path))

    total_ways = sum(len(ids) for ids in handler.way_ids_by_query.values())
    logger.info(f"relation収集完了: 合計 {total_ways} ways")

    return handler.way_ids_by_query


def extract_all_ways(
    pbf_path: Path,
    all_way_ids: set[int],
) -> dict[int, dict]:
    """
    指定された全way IDのwayを一括抽出

    Args:
        pbf_path: PBFファイルパス（座標埋め込み済み）
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
