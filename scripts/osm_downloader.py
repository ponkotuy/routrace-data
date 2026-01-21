"""OSMデータダウンローダー"""

import logging
from pathlib import Path

import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)

# Geofabrik 日本データURL
JAPAN_PBF_URL = "https://download.geofabrik.de/asia/japan-latest.osm.pbf"

# デフォルトキャッシュディレクトリ
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "cache"


def download_japan_osm(cache_dir: Path = DEFAULT_CACHE_DIR, force: bool = False) -> Path:
    """
    日本のOSMデータ（PBF形式）をダウンロード

    Args:
        cache_dir: キャッシュディレクトリ
        force: 既存ファイルがあっても再ダウンロード

    Returns:
        ダウンロードしたPBFファイルのパス
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = cache_dir / "japan-latest.osm.pbf"

    if output_path.exists() and not force:
        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"キャッシュ済み: {output_path} ({size_mb:.1f} MB)")
        return output_path

    logger.info(f"OSMデータダウンロード中: {JAPAN_PBF_URL}")

    response = requests.get(JAPAN_PBF_URL, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with open(output_path, "wb") as f:
        with tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            desc="Downloading",
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                pbar.update(len(chunk))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"ダウンロード完了: {output_path} ({size_mb:.1f} MB)")

    return output_path


def get_cached_pbf_path(cache_dir: Path = DEFAULT_CACHE_DIR) -> Path | None:
    """
    キャッシュ済みのPBFファイルパスを取得

    Returns:
        PBFファイルパス、存在しない場合はNone
    """
    pbf_path = cache_dir / "japan-latest.osm.pbf"
    return pbf_path if pbf_path.exists() else None
