"""エントリーポイント"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR, HIGHWAYS_DIR
from coastline import fetch_coastline, save_coastline
from highway import extract_highway, save_highway
from osm_downloader import download_japan_osm, filter_highways_pbf
from osm_parser import (
    discover_highways,
    extract_all_ways,
    get_ways_for_highway,
)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# グループ化対象の都市高速プレフィックス
GROUP_PREFIXES = [
    "首都高速",
    "名古屋高速",
    "阪神高速",
    "広島高速",
    "北九州高速",
    "福岡高速",
]

# 別名からグループへのマッピング（表記揺れ対応）
GROUP_ALIASES = {
    "北九州都市高速": "北九州高速",
    "福岡都市高速": "福岡高速",
}


def detect_group(name: str) -> str | None:
    """
    高速道路名からグループを推定

    都市高速道路（首都高速、阪神高速など）を同一グループとして判定する。
    例:
        首都高速1号上野線 → 首都高速
        阪神高速11号池田線 → 阪神高速
        名古屋高速道路小牧-大高線高架路 → 名古屋高速
        福岡高速6号アイランドシティ線 → 福岡都市高速
        東名高速道路 → None（グループなし）
    """
    for prefix in GROUP_PREFIXES:
        if name.startswith(prefix):
            return prefix
    # 別名（福岡高速→福岡都市高速など）
    for alias, group in GROUP_ALIASES.items():
        if name.startswith(alias):
            return group
    # 「名古屋高速道路」のような表記揺れにも対応
    for prefix in GROUP_PREFIXES:
        alt_prefix = prefix + "道路"
        if name.startswith(alt_prefix):
            return prefix
    return None


def main():
    """
    コマンドライン引数:
        --output-dir: 出力ベースディレクトリ（デフォルト: リポジトリルート）
        --highways-only: 高速道路のみ生成
        --coastline-only: 海岸線のみ生成
        --highway-name: 特定の高速道路のみ生成（複数指定可、部分一致）
        --verbose: 詳細ログ出力
    """
    parser = argparse.ArgumentParser(
        description="routrace用の地図データを生成"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent,
        help="出力ベースディレクトリ（デフォルト: リポジトリルート）",
    )
    parser.add_argument(
        "--highways-only",
        action="store_true",
        help="高速道路のみ生成",
    )
    parser.add_argument(
        "--coastline-only",
        action="store_true",
        help="海岸線のみ生成",
    )
    parser.add_argument(
        "--highway-name",
        action="append",
        dest="highway_names",
        help="特定の高速道路のみ生成（複数指定可、部分一致）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログ出力",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = args.output_dir.resolve()
    data_dir = output_dir / DATA_DIR

    logger.info("開始: データ生成")
    logger.info(f"出力先: {data_dir}/")

    try:
        if args.coastline_only:
            generate_coastline(output_dir)
        elif args.highways_only:
            generate_highways(output_dir, args.highway_names)
        else:
            generate_all(output_dir)

        logger.info("完了")
    except Exception as e:
        logger.error(f"エラー: {e}")
        sys.exit(1)


def generate_all(output_dir: Path) -> None:
    """
    全データを生成

    出力先:
        output_dir/data/metadata.json
        output_dir/data/coastline.json
        output_dir/data/highways/index.json
        output_dir/data/highways/{id}.json
    """
    generate_metadata(output_dir)
    generate_coastline(output_dir)
    generate_highways(output_dir)


def generate_highways(
    output_dir: Path,
    highway_names: list[str] | None = None,
) -> None:
    """高速道路データを生成"""
    data_dir = output_dir / DATA_DIR
    highways_dir = data_dir / HIGHWAYS_DIR

    # OSMデータをダウンロード（キャッシュがあればスキップ）
    pbf_path = download_japan_osm()

    # osmiumで事前フィルター（高速化）
    filtered_pbf_path = filter_highways_pbf(pbf_path)

    # 高速道路を自動検出
    discovered, way_ids_by_name = discover_highways(filtered_pbf_path)

    # 対象の高速道路を絞り込み
    if highway_names:
        targets = [h for h in discovered if any(n in h["name"] for n in highway_names)]
        if not targets:
            logger.warning(f"指定された名前の高速道路が見つかりません: {highway_names}")
            return
    else:
        targets = discovered

    logger.info(f"高速道路データ生成: {len(targets)}路線")

    # 全way IDを統合
    all_way_ids: set[int] = set()
    for h in targets:
        way_ids = way_ids_by_name.get(h["name"], set())
        all_way_ids.update(way_ids)

    # 全wayを一括抽出（元のPBFから、ノード座標を含む）
    ways_by_id = extract_all_ways(pbf_path, all_way_ids)

    highways_info = []

    for highway_info in targets:
        try:
            name = highway_info["name"]
            way_ids = way_ids_by_name.get(name, set())

            # メモリ内のwayデータから該当するものを取得
            ways = get_ways_for_highway(ways_by_id, way_ids)

            logger.debug(f"{name}: {len(way_ids)} way IDs, {len(ways)} ways抽出")

            geojson = extract_highway(highway_info, ways)
            file_size = save_highway(name, geojson, highways_dir)

            ref = highway_info.get("ref", "")
            ref_display = ref.split(";")[0] if ref else ""
            group = detect_group(name)

            entry = {
                "id": name,
                "name": name,
                "nameEn": highway_info.get("name_en", ""),
                "ref": ref,
                "refDisplay": ref_display,
                "fileSize": file_size,
                "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            if group:
                entry["group"] = group

            highways_info.append(entry)
        except Exception as e:
            logger.error(f"高速道路データ抽出エラー: {name} - {e}")

    # index.json生成
    generate_index(output_dir, highways_info)


def generate_coastline(output_dir: Path) -> None:
    """海岸線データを生成"""
    data_dir = output_dir / DATA_DIR

    geojson = fetch_coastline()

    output_path = data_dir / "coastline.json"
    save_coastline(geojson, output_path)


def generate_metadata(output_dir: Path) -> None:
    """data/metadata.jsonを生成"""
    data_dir = output_dir / DATA_DIR

    metadata = {
        "version": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "OpenStreetMap",
        "license": "ODbL",
        "attribution": "© OpenStreetMap contributors",
    }

    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "metadata.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, separators=(",", ":"))

    logger.info(f"保存: {output_path}")


def generate_index(output_dir: Path, highways_info: list[dict]) -> None:
    """data/highways/index.jsonを生成"""
    data_dir = output_dir / DATA_DIR
    highways_dir = data_dir / HIGHWAYS_DIR

    index = {
        "highways": highways_info,
    }

    highways_dir.mkdir(parents=True, exist_ok=True)
    output_path = highways_dir / "index.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    logger.info(f"保存: {output_path}")


if __name__ == "__main__":
    main()
