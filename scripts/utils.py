"""共通ユーティリティ"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """バイト数を人間が読みやすい形式に変換"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


def save_geojson(geojson: dict, output_path: Path) -> int:
    """
    GeoJSONをファイルに保存

    Args:
        geojson: GeoJSON FeatureCollection
        output_path: 出力ファイルパス

    Returns:
        保存したファイルのバイト数
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_str = json.dumps(geojson, ensure_ascii=False, separators=(",", ":"))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_str)

    file_size = output_path.stat().st_size
    size_str = format_size(file_size)
    logger.info("保存: %s (%s)", output_path, size_str)

    return file_size
