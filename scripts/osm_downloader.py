"""OSMデータダウンローダー"""

import logging
import subprocess
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
        logger.info("キャッシュ済み: %s (%.1f MB)", output_path, size_mb)
        return output_path

    logger.info("OSMデータダウンロード中: %s", JAPAN_PBF_URL)

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
    logger.info("ダウンロード完了: %s (%.1f MB)", output_path, size_mb)

    return output_path


def filter_highways_pbf(
    input_pbf: Path,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> Path:
    """
    osmiumでPBFから高速道路のrelation/wayのみを抽出（relation収集用）

    Args:
        input_pbf: 入力PBFファイルパス
        cache_dir: キャッシュディレクトリ
        force: 既存ファイルがあっても再生成

    Returns:
        フィルタリング済みPBFファイルのパス（ノードは含まない）
    """
    output_path = cache_dir / "japan-highways.osm.pbf"

    if output_path.exists() and not force:
        # 入力ファイルより新しければスキップ
        if output_path.stat().st_mtime >= input_pbf.stat().st_mtime:
            size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info("フィルター済みキャッシュ: %s (%.1f MB)", output_path, size_mb)
            return output_path

    logger.info("osmiumで高速道路relation/wayを抽出中...")

    cmd = [
        "osmium",
        "tags-filter",
        str(input_pbf),
        "r/route=road",
        "w/highway=motorway,motorway_link",
        "-R",  # relationのメンバーも含める
        "-o",
        str(output_path),
        "--overwrite",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "osmiumコマンドが見つかりません。osmium-toolをインストールしてください。\n"
            "  Ubuntu/Debian: sudo apt install osmium-tool\n"
            "  macOS: brew install osmium-tool\n"
            "  Arch Linux: sudo pacman -S osmium-tool"
        ) from exc
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"osmiumコマンドが失敗しました: {e.stderr}") from e

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("フィルター完了: %s (%.1f MB)", output_path, size_mb)

    return output_path


def filter_national_routes_pbf(
    input_pbf: Path,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> Path:
    """
    osmiumでPBFから国道のrelation/wayのみを抽出

    Args:
        input_pbf: 入力PBFファイルパス
        cache_dir: キャッシュディレクトリ
        force: 既存ファイルがあっても再生成

    Returns:
        フィルタリング済みPBFファイルのパス
    """
    output_path = cache_dir / "japan-national-routes.osm.pbf"

    if output_path.exists() and not force:
        # 入力ファイルより新しければスキップ
        if output_path.stat().st_mtime >= input_pbf.stat().st_mtime:
            size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info("フィルター済みキャッシュ: %s (%.1f MB)", output_path, size_mb)
            return output_path

    logger.info("osmiumで国道relation/wayを抽出中...")

    cmd = [
        "osmium",
        "tags-filter",
        str(input_pbf),
        "r/network=JP:national",
        "w/highway=trunk,trunk_link",
        "-R",  # relationのメンバーも含める
        "-o",
        str(output_path),
        "--overwrite",
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "osmiumコマンドが見つかりません。osmium-toolをインストールしてください。\n"
            "  Ubuntu/Debian: sudo apt install osmium-tool\n"
            "  macOS: brew install osmium-tool\n"
            "  Arch Linux: sudo pacman -S osmium-tool"
        ) from exc
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"osmiumコマンドが失敗しました: {e.stderr}") from e

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("フィルター完了: %s (%.1f MB)", output_path, size_mb)

    return output_path
