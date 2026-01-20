"""海岸線データ処理"""

import json
import logging
from pathlib import Path

import requests

from simplify import simplify_geojson, get_coordinate_count
from config import SIMPLIFY_TOLERANCE

logger = logging.getLogger(__name__)

# dataofjapan/land の japan.geojson URL
JAPAN_GEOJSON_URL = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"


def fetch_coastline() -> dict:
    """
    日本の海岸線データを取得

    Returns:
        GeoJSON FeatureCollection (dict)
    """
    logger.info("海岸線データ取得中...")
    logger.info(f"ソース: {JAPAN_GEOJSON_URL}")

    response = requests.get(JAPAN_GEOJSON_URL, timeout=60)
    response.raise_for_status()

    geojson = response.json()

    feature_count = len(geojson.get("features", []))
    logger.info(f"海岸線データ取得完了: {feature_count} features")

    if feature_count == 0:
        logger.warning("海岸線データが0件でした")

    # 簡略化
    original_count = get_coordinate_count(geojson)
    simplified = simplify_geojson(geojson, SIMPLIFY_TOLERANCE)
    simplified_count = get_coordinate_count(simplified)

    logger.info(f"海岸線データ簡略化: {original_count} coords → {simplified_count} coords")

    # プロパティを設定
    simplified["properties"] = {
        "name": "Japan Coastline",
        "source": "dataofjapan/land",
        "simplified": True,
        "tolerance": SIMPLIFY_TOLERANCE,
    }

    return simplified


def save_coastline(geojson: dict, output_path: Path) -> int:
    """
    海岸線GeoJSONをファイルに保存

    Args:
        geojson: GeoJSON FeatureCollection
        output_path: 出力ファイルパス (data/coastline.json)

    Returns:
        保存したファイルのバイト数
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

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
