"""高速道路データ処理"""

import json
import logging
from pathlib import Path

from osm_parser import filter_by_name, ways_to_geojson
from simplify import simplify_geojson, get_coordinate_count
from config import SIMPLIFY_TOLERANCE

logger = logging.getLogger(__name__)


def extract_highway(all_ways: list[dict], highway_config: dict) -> dict:
    """
    全高速道路データから指定された路線を抽出

    Args:
        all_ways: 全高速道路wayのリスト
        highway_config: config.pyのHIGHWAYS要素

    Returns:
        GeoJSON FeatureCollection (dict)
    """
    name = highway_config["name"]
    highway_id = highway_config["id"]
    query_name = highway_config["query_name"]

    logger.info(f"高速道路データ抽出中: {name}")

    # 名前でフィルタリング
    filtered_ways = filter_by_name(all_ways, query_name)

    # GeoJSONに変換
    geojson = ways_to_geojson(filtered_ways)

    feature_count = len(geojson.get("features", []))
    logger.info(f"高速道路データ抽出完了: {name} ({feature_count} features)")

    if feature_count == 0:
        logger.warning(f"高速道路データが0件でした: {name}")

    # 簡略化
    original_count = get_coordinate_count(geojson)
    simplified = simplify_geojson(geojson, SIMPLIFY_TOLERANCE)
    simplified_count = get_coordinate_count(simplified)

    logger.debug(f"簡略化: {original_count} coords → {simplified_count} coords")

    # プロパティを設定
    simplified["properties"] = {
        "id": highway_id,
        "name": name,
        "nameEn": highway_config["name_en"],
    }

    return simplified


def save_highway(highway_id: str, geojson: dict, output_dir: Path) -> int:
    """
    高速道路GeoJSONをファイルに保存

    Args:
        highway_id: 高速道路ID（例: "tomei"）
        geojson: GeoJSON FeatureCollection
        output_dir: 出力ディレクトリ (data/highways/)

    Returns:
        保存したファイルのバイト数
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{highway_id}.json"

    json_str = json.dumps(geojson, ensure_ascii=False, separators=(",", ":"))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_str)

    file_size = output_path.stat().st_size
    size_str = format_size(file_size)
    logger.info(f"保存: {output_path} ({size_str})")

    return file_size


def format_size(size_bytes: int) -> str:
    """バイト数を人間が読みやすい形式に変換"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    else:
        return f"{size_bytes} B"
