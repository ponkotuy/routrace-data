"""高速道路データ処理"""

import json
import logging
from pathlib import Path

from osm_parser import ways_to_geojson
from simplify import simplify_geojson, get_coordinate_count
from config import SIMPLIFY_TOLERANCE

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

    logger.info(f"高速道路データ変換中: {name}")

    # GeoJSONに変換
    geojson = ways_to_geojson(ways)

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
