"""海岸線データ処理"""

import logging
from pathlib import Path

import requests

from simplify import simplify_geojson, get_coordinate_count
from config import SIMPLIFY_TOLERANCE
from utils import save_geojson

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
    logger.info("ソース: %s", JAPAN_GEOJSON_URL)

    response = requests.get(JAPAN_GEOJSON_URL, timeout=60)
    response.raise_for_status()

    geojson = response.json()

    feature_count = len(geojson.get("features", []))
    logger.info("海岸線データ取得完了: %d features", feature_count)

    if feature_count == 0:
        logger.warning("海岸線データが0件でした")

    # 簡略化
    original_count = get_coordinate_count(geojson)
    simplified = simplify_geojson(geojson, SIMPLIFY_TOLERANCE)
    simplified_count = get_coordinate_count(simplified)

    logger.info("海岸線データ簡略化: %d coords → %d coords", original_count, simplified_count)

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
    return save_geojson(geojson, output_path)
