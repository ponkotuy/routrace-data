"""高速道路データ処理"""

import logging
from pathlib import Path

from osm_parser import ways_to_geojson
from simplify import simplify_geojson, get_coordinate_count
from config import SIMPLIFY_TOLERANCE
from utils import save_geojson

logger = logging.getLogger(__name__)


def extract_highway(highway_info: dict, ways: list[dict]) -> dict:
    """
    指定された路線のデータを抽出

    Args:
        highway_info: 高速道路情報 {"name": str, "name_en": str, "ref": str}
        ways: 抽出済みのwayリスト

    Returns:
        GeoJSON FeatureCollection (dict)
    """
    name = highway_info["name"]

    logger.info("高速道路データ変換中: %s", name)

    # GeoJSONに変換
    geojson = ways_to_geojson(ways)

    feature_count = len(geojson.get("features", []))
    logger.info("高速道路データ抽出完了: %s (%d features)", name, feature_count)

    if feature_count == 0:
        logger.warning("高速道路データが0件でした: %s", name)

    # 簡略化
    original_count = get_coordinate_count(geojson)
    simplified = simplify_geojson(geojson, SIMPLIFY_TOLERANCE)
    simplified_count = get_coordinate_count(simplified)

    logger.debug("簡略化: %d coords → %d coords", original_count, simplified_count)

    # プロパティを設定
    simplified["properties"] = {
        "name": name,
        "nameEn": highway_info.get("name_en", ""),
        "ref": highway_info.get("ref", ""),
    }

    return simplified


def save_highway(name: str, geojson: dict, output_dir: Path) -> int:
    """
    高速道路GeoJSONをファイルに保存

    Args:
        name: 高速道路名（ファイル名として使用）
        geojson: GeoJSON FeatureCollection
        output_dir: 出力ディレクトリ (data/highways/)

    Returns:
        保存したファイルのバイト数
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.json"
    return save_geojson(geojson, output_path)
