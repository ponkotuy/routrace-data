"""エントリーポイント"""

import argparse
import json
import logging
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
from highway_grouping import (
    CORE_HIGHWAYS,
    GROUP_ORDER,
    URBAN_EXPRESSWAY_PREFIXES,
    detect_group,
    determine_general_group,
    get_all_coordinates,
    get_extent_segment,
)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def group_ways_by_ref(ways: list[dict]) -> dict[str, list[dict]]:
    """
    wayをrefでグループ化する

    複合ref（E4;E13等）は最初の部分のみ使用。
    refなしwayは最寄りのrefありwayのグループに統合。
    """
    from shapely.geometry import Point

    # まずrefありwayをグループ化
    grouped: dict[str, list[dict]] = {}
    no_ref_ways: list[dict] = []

    for way in ways:
        ref = way.get("tags", {}).get("ref", "")
        primary_ref = ref.split(";")[0].strip() if ref else ""

        if primary_ref:
            if primary_ref not in grouped:
                grouped[primary_ref] = []
            grouped[primary_ref].append(way)
        else:
            no_ref_ways.append(way)

    # refなしwayを最寄りのグループに統合
    if no_ref_ways and grouped:
        # 各グループの代表点（最初のwayの中点）を計算
        ref_centroids: dict[str, Point] = {}
        for ref, ref_ways in grouped.items():
            coords = ref_ways[0]["coordinates"]
            mid_idx = len(coords) // 2
            ref_centroids[ref] = Point(coords[mid_idx])

        # 各no-ref wayを最寄りのrefグループに割り当て
        for way in no_ref_ways:
            coords = way["coordinates"]
            mid_idx = len(coords) // 2
            way_point = Point(coords[mid_idx])

            # 最寄りのrefを見つける
            nearest_ref = min(
                ref_centroids.keys(),
                key=lambda r: way_point.distance(ref_centroids[r])
            )
            grouped[nearest_ref].append(way)
    elif no_ref_ways and not grouped:
        # 全wayがrefなしの場合は空文字キーで保持
        grouped[""] = no_ref_ways

    return grouped


def is_national_route_ref(ref: str) -> bool:
    """
    数字のみのref（国道）かどうかを判定。

    例: "4", "152", "353" → True (国道)
        "E20", "E1A", "C2" → False (高速道路)
    """
    return ref.isdigit()


def should_split_by_ref(grouped_ways: dict[str, list[dict]], name: str) -> bool:
    """
    分割が必要か判定。2つ以上の異なる非空の高速道路refがある場合のみ分割。

    一般高速道路の場合、数字のみのref（国道）は高速道路refとしてカウントしない。
    都市高速の場合は数字のみのrefも有効（路線番号として使用）。
    """
    is_urban = detect_group(name) is not None

    if is_urban:
        # 都市高速: 全ての非空refを有効とする
        valid_refs = [ref for ref in grouped_ways.keys() if ref]
    else:
        # 一般高速: 数字のみのref（国道）は除外
        valid_refs = [
            ref for ref in grouped_ways.keys()
            if ref and not is_national_route_ref(ref)
        ]
    return len(valid_refs) > 1


def create_highway_entry(
    name: str,
    name_en: str,
    ref: str,
    ways: list[dict],
    highways_dir: Path,
) -> dict | None:
    """
    高速道路エントリを作成しGeoJSONを保存

    一般高速道路で数字のみのref（国道）の場合はスキップする。
    都市高速の場合は数字のみのrefも有効。
    """
    # 一般高速道路で数字のみのref（国道）はスキップ
    is_urban = detect_group(name) is not None
    if ref and not is_urban and is_national_route_ref(ref):
        logger.info("国道refのためスキップ: %s (ref=%s)", name, ref)
        return None

    # refありならid末尾に付与
    entry_id = f"{name}_{ref}" if ref else name

    highway_info = {
        "name": name,
        "name_en": name_en,
        "ref": ref,
    }

    geojson = extract_highway(highway_info, ways)

    coords = get_all_coordinates(geojson)
    if not coords:
        logger.warning("座標がないためスキップ: %s", entry_id)
        return None

    file_size = save_highway(entry_id, geojson, highways_dir)
    ref_display = ref.split(";")[0] if ref else ""

    return {
        "id": entry_id,
        "name": name,
        "nameEn": name_en,
        "ref": ref,
        "refDisplay": ref_display,
        "fileSize": file_size,
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_geojson": geojson,
    }


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
    logger.info("出力先: %s/", data_dir)

    try:
        if args.coastline_only:
            generate_coastline(output_dir)
        elif args.highways_only:
            generate_highways(output_dir, args.highway_names)
        else:
            generate_all(output_dir)

        logger.info("完了")
    except Exception as e:
        logger.error("エラー: %s", e)
        sys.exit(1)


def generate_all(output_dir: Path) -> None:
    """
    全データを生成

    出力先:
        output_dir/data/metadata.json
        output_dir/data/coastline.json
        output_dir/data/highways/index.json
        output_dir/data/highways/group.json
        output_dir/data/highways/{name}.json
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
            logger.warning("指定された名前の高速道路が見つかりません: %s", highway_names)
            return
    else:
        targets = discovered

    logger.info("高速道路データ生成: %d路線", len(targets))

    # 全way IDを統合
    all_way_ids: set[int] = set()
    for h in targets:
        way_ids = way_ids_by_name.get(h["name"], set())
        all_way_ids.update(way_ids)

    # 全wayを一括抽出（元のPBFから、ノード座標を含む）
    ways_by_id = extract_all_ways(pbf_path, all_way_ids)

    highways_info = []
    highway_geojsons: dict[str, dict] = {}  # グループ計算用にGeoJSONを保持

    for highway_info in targets:
        try:
            name = highway_info["name"]
            way_ids = way_ids_by_name.get(name, set())

            # メモリ内のwayデータから該当するものを取得
            ways = get_ways_for_highway(ways_by_id, way_ids)

            logger.debug("%s: %d way IDs, %d ways抽出", name, len(way_ids), len(ways))

            # wayをrefでグループ化
            grouped_ways = group_ways_by_ref(ways)

            if should_split_by_ref(grouped_ways, name):
                # 複数refあり → 分割
                for ref, ref_ways in grouped_ways.items():
                    entry = create_highway_entry(
                        name=name,
                        name_en=highway_info.get("name_en", ""),
                        ref=ref,
                        ways=ref_ways,
                        highways_dir=highways_dir,
                    )
                    if entry:
                        geojson = entry.pop("_geojson")
                        highways_info.append(entry)
                        highway_geojsons[entry["id"]] = geojson
            else:
                # 単一ref（または全部refなし） → 従来通り
                # 有効なref（国道以外）を探す
                is_urban = detect_group(name) is not None
                valid_refs = [
                    r for r in grouped_ways
                    if r and (is_urban or not is_national_route_ref(r))
                ]
                ref = valid_refs[0] if valid_refs else ""
                entry = create_highway_entry(
                    name=name,
                    name_en=highway_info.get("name_en", ""),
                    ref=ref,
                    ways=ways,
                    highways_dir=highways_dir,
                )
                if entry:
                    geojson = entry.pop("_geojson")
                    highways_info.append(entry)
                    highway_geojsons[entry["id"]] = geojson

        except Exception as e:
            logger.error("高速道路データ抽出エラー: %s - %s", name, e)

    # グループを計算
    logger.info("グループ計算中...")
    assign_groups(highways_info, highway_geojsons)

    # index.json生成
    generate_index(output_dir, highways_info)

    # group.json生成
    generate_groups(output_dir)


def assign_groups(
    highways_info: list[dict],
    highway_geojsons: dict[str, dict],
) -> None:
    """
    各高速道路にグループを割り当てる

    Args:
        highways_info: 高速道路情報リスト（group属性が追加される）
        highway_geojsons: エントリID → GeoJSONのマッピング
    """
    # 各高速道路の線分（最近点、最遠点）を計算
    highway_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for entry_id, geojson in highway_geojsons.items():
        coords = get_all_coordinates(geojson)
        segment = get_extent_segment(coords)
        if segment:
            highway_segments[entry_id] = segment

    # 中心高速道路の線分を取得
    # entry_idは "name" または "name_ref" の形式なので、nameで始まるものを探す
    core_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for core_name in CORE_HIGHWAYS:
        # まず名前そのままで探す（分割されていない場合）
        if core_name in highway_segments:
            core_segments[core_name] = highway_segments[core_name]
        else:
            # 分割されている場合、name_* で始まるentry_idを探す
            for entry_id, segment in highway_segments.items():
                if entry_id.startswith(f"{core_name}_"):
                    core_segments[core_name] = segment
                    break  # 最初に見つかったものを使用

    # 各高速道路にグループを割り当て
    for entry in highways_info:
        name = entry["name"]
        entry_id = entry["id"]

        # 都市高速グループの判定
        urban_group = detect_group(name)
        if urban_group:
            entry["group"] = urban_group
            continue

        # 中心高速道路自身の場合
        if name in CORE_HIGHWAYS:
            entry["group"] = CORE_HIGHWAYS[name]
            continue

        # 一般高速道路のグループ判定
        if entry_id in highway_segments:
            if core_segments:
                group = determine_general_group(highway_segments[entry_id], core_segments)
                entry["group"] = group
            else:
                # core_segmentsが空の場合はデフォルトグループ
                logger.warning("core_segmentsが空のためデフォルトグループ: %s", entry_id)
                entry["group"] = "東名"
        else:
            # 座標がない高速道路は事前にフィルタされているはず
            logger.error("セグメントが見つかりません: %s", entry_id)
            entry["group"] = "東名"


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

    logger.info("保存: %s", output_path)


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

    logger.info("保存: %s", output_path)


def generate_groups(output_dir: Path) -> None:
    """
    data/highways/group.jsonを生成

    グループ情報を含むJSONファイルを生成する。
    各グループには以下の情報を含む:
    - name: グループ名（主キー）
    - type: "urban"（都市高速）または "general"（一般高速）
    - order: 順序番号
    """
    data_dir = output_dir / DATA_DIR
    highways_dir = data_dir / HIGHWAYS_DIR

    groups = []
    for order, group_name in enumerate(GROUP_ORDER):
        # 都市高速かどうかを判定
        is_urban = group_name in URBAN_EXPRESSWAY_PREFIXES

        groups.append({
            "name": group_name,
            "type": "urban" if is_urban else "general",
            "order": order,
        })

    highways_dir.mkdir(parents=True, exist_ok=True)
    output_path = highways_dir / "group.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"groups": groups}, f, ensure_ascii=False, separators=(",", ":"))

    logger.info("保存: %s", output_path)


if __name__ == "__main__":
    main()
