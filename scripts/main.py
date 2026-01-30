"""エントリーポイント"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import Point

from config import DATA_DIR, HIGHWAYS_DIR, NATIONAL_ROADS_DIR
from coastline import fetch_coastline, save_coastline
from highway import extract_highway, save_highway
from osm_downloader import (
    download_japan_osm,
    filter_highways_pbf,
    filter_national_routes_pbf,
)
from osm_parser import (
    discover_highways,
    discover_national_routes,
    extract_all_ways,
    get_ways_for_highway,
)
from highway_grouping import (
    CORE_HIGHWAYS,
    CORE_NATIONAL_ROUTES,
    GROUP_ORDER,
    NATIONAL_ROUTE_GROUP_ORDER,
    URBAN_EXPRESSWAY_PREFIXES,
    detect_group,
    determine_general_group,
    determine_national_route_group,
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
                key=lambda r, wp=way_point: wp.distance(ref_centroids[r])
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


def _process_single_highway(
    highway_info: dict,
    way_ids_by_name: dict[str, set[int]],
    ways_by_id: dict[int, dict],
    highways_dir: Path,
) -> list[tuple[dict, dict]]:
    """
    単一の高速道路を処理してエントリとGeoJSONのペアを返す

    Returns:
        [(entry, geojson), ...] のリスト（複数refで分割される場合は複数）
    """
    name = highway_info["name"]
    way_ids = way_ids_by_name.get(name, set())

    # メモリ内のwayデータから該当するものを取得
    ways = get_ways_for_highway(ways_by_id, way_ids)

    logger.debug("%s: %d way IDs, %d ways抽出", name, len(way_ids), len(ways))

    # wayをrefでグループ化
    grouped_ways = group_ways_by_ref(ways)

    results: list[tuple[dict, dict]] = []

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
                results.append((entry, geojson))
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
            results.append((entry, geojson))

    return results


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
        "--national-roads-only",
        action="store_true",
        help="国道のみ生成",
    )
    parser.add_argument(
        "--national-route-ref",
        action="append",
        dest="national_route_refs",
        help="特定の国道のみ生成（ref番号指定、複数可）",
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

    if args.coastline_only:
        generate_coastline(output_dir)
    elif args.highways_only:
        generate_highways(output_dir, args.highway_names)
    elif args.national_roads_only or args.national_route_refs:
        generate_national_roads(output_dir, args.national_route_refs)
    else:
        generate_all(output_dir)

    logger.info("完了")


def generate_all(output_dir: Path) -> None:
    """
    全データを生成

    出力先:
        output_dir/data/metadata.json
        output_dir/data/coastline.json
        output_dir/data/highways/index.json
        output_dir/data/highways/group.json
        output_dir/data/highways/{name}.json
        output_dir/data/national-roads/index.json
        output_dir/data/national-roads/group.json
        output_dir/data/national-roads/{name}.json
    """
    generate_metadata(output_dir)
    generate_coastline(output_dir)
    generate_highways(output_dir)
    generate_national_roads(output_dir)


def _prepare_osm_data(
    highway_names: list[str] | None,
) -> tuple[list[dict], dict[str, set[int]], dict[int, dict]] | None:
    """
    OSMデータを準備し、対象の高速道路を取得

    Returns:
        (targets, way_ids_by_name, ways_by_id) または None（対象なしの場合）
    """
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
            return None
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

    return targets, way_ids_by_name, ways_by_id


def generate_highways(
    output_dir: Path,
    highway_names: list[str] | None = None,
) -> None:
    """高速道路データを生成"""
    highways_dir = output_dir / DATA_DIR / HIGHWAYS_DIR

    osm_data = _prepare_osm_data(highway_names)
    if osm_data is None:
        return
    targets, way_ids_by_name, ways_by_id = osm_data

    highways_info = []
    highway_geojsons: dict[str, dict] = {}  # グループ計算用にGeoJSONを保持

    for highway_info in targets:
        try:
            for entry, geojson in _process_single_highway(
                highway_info, way_ids_by_name, ways_by_id, highways_dir
            ):
                highways_info.append(entry)
                highway_geojsons[entry["id"]] = geojson
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("高速道路データ抽出エラー: %s - %s", highway_info["name"], e)

    # グループを計算
    logger.info("グループ計算中...")
    assign_groups(highways_info, highway_geojsons)

    # index.json生成
    generate_index(output_dir, highways_info)

    # group.json生成
    generate_groups(output_dir)


def _determine_group(
    name: str,
    entry_id: str,
    highway_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]],
    core_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]],
) -> str:
    """
    高速道路のグループを決定

    Returns:
        グループ名
    """
    # 都市高速グループの判定
    urban_group = detect_group(name)
    if urban_group:
        return urban_group

    # 中心高速道路自身の場合
    if name in CORE_HIGHWAYS:
        return CORE_HIGHWAYS[name]

    # 一般高速道路のグループ判定
    if entry_id in highway_segments:
        if core_segments:
            return determine_general_group(highway_segments[entry_id], core_segments)
        logger.warning("core_segmentsが空のためデフォルトグループ: %s", entry_id)
        return "東名"

    logger.error("セグメントが見つかりません: %s", entry_id)
    return "東名"


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
        entry["group"] = _determine_group(
            entry["name"], entry["id"], highway_segments, core_segments
        )


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


# ============================================
# 国道生成関数
# ============================================


def _prepare_national_route_data(
    national_route_refs: list[str] | None,
) -> tuple[list[dict], dict[str, set[int]], dict[int, dict]] | None:
    """
    国道用OSMデータを準備し、対象の国道を取得

    Returns:
        (targets, way_ids_by_ref, ways_by_id) または None（対象なしの場合）
    """
    # OSMデータをダウンロード（キャッシュがあればスキップ）
    pbf_path = download_japan_osm()

    # osmiumで事前フィルター（国道用）
    filtered_pbf_path = filter_national_routes_pbf(pbf_path)

    # 国道を自動検出
    discovered, way_ids_by_ref = discover_national_routes(filtered_pbf_path)

    # 対象の国道を絞り込み
    if national_route_refs:
        targets = [r for r in discovered if r["ref"] in national_route_refs]
        if not targets:
            logger.warning("指定されたref番号の国道が見つかりません: %s", national_route_refs)
            return None
    else:
        targets = discovered

    logger.info("国道データ生成: %d路線", len(targets))

    # 全way IDを統合
    all_way_ids: set[int] = set()
    for r in targets:
        way_ids = way_ids_by_ref.get(r["ref"], set())
        all_way_ids.update(way_ids)

    # 全wayを一括抽出（元のPBFから、ノード座標を含む）
    ways_by_id = extract_all_ways(pbf_path, all_way_ids)

    return targets, way_ids_by_ref, ways_by_id


def _process_single_national_route(
    route_info: dict,
    way_ids_by_ref: dict[str, set[int]],
    ways_by_id: dict[int, dict],
    output_dir: Path,
) -> tuple[dict, dict] | None:
    """
    単一の国道を処理してエントリとGeoJSONのペアを返す

    Returns:
        (entry, geojson) または None（エラー時）
    """
    ref = route_info["ref"]
    name = route_info["name"]
    name_en = route_info["name_en"]
    way_ids = way_ids_by_ref.get(ref, set())

    # メモリ内のwayデータから該当するものを取得
    ways = get_ways_for_highway(ways_by_id, way_ids)

    logger.debug("%s: %d way IDs, %d ways抽出", name, len(way_ids), len(ways))

    if not ways:
        logger.warning("wayがないためスキップ: %s", name)
        return None

    highway_info = {
        "name": name,
        "name_en": name_en,
        "ref": ref,
    }

    geojson = extract_highway(highway_info, ways)

    coords = get_all_coordinates(geojson)
    if not coords:
        logger.warning("座標がないためスキップ: %s", name)
        return None

    file_size = save_highway(name, geojson, output_dir)

    entry = {
        "id": name,
        "name": name,
        "nameEn": name_en,
        "ref": ref,
        "fileSize": file_size,
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    return entry, geojson


def assign_national_route_groups(
    routes_info: list[dict],
    route_geojsons: dict[str, dict],
) -> None:
    """
    各国道にグループを割り当てる

    Args:
        routes_info: 国道情報リスト（group属性が追加される）
        route_geojsons: 国道名 → GeoJSONのマッピング
    """
    # 各国道の線分（最近点、最遠点）を計算
    route_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for name, geojson in route_geojsons.items():
        coords = get_all_coordinates(geojson)
        segment = get_extent_segment(coords)
        if segment:
            route_segments[name] = segment

    # 1桁国道の線分を取得（グループの中心となる国道）
    core_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for ref, group_name in CORE_NATIONAL_ROUTES.items():
        if group_name in route_segments:
            core_segments[group_name] = route_segments[group_name]

    # 各国道にグループを割り当て
    for entry in routes_info:
        name = entry["name"]
        ref = entry["ref"]

        # 1桁国道は自分自身がグループ
        if ref in CORE_NATIONAL_ROUTES:
            entry["group"] = CORE_NATIONAL_ROUTES[ref]
        elif name in route_segments and core_segments:
            entry["group"] = determine_national_route_group(
                route_segments[name], core_segments
            )
        else:
            # セグメントがない場合はデフォルト
            logger.warning("セグメントが見つからないためデフォルトグループ: %s", name)
            entry["group"] = "国道1号"


def generate_national_routes_index(output_dir: Path, routes_info: list[dict]) -> None:
    """data/national-roads/index.jsonを生成"""
    data_dir = output_dir / DATA_DIR
    national_roads_dir = data_dir / NATIONAL_ROADS_DIR

    index = {
        "nationalRoutes": routes_info,
    }

    national_roads_dir.mkdir(parents=True, exist_ok=True)
    output_path = national_roads_dir / "index.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    logger.info("保存: %s", output_path)


def generate_national_routes_groups(output_dir: Path) -> None:
    """data/national-roads/group.jsonを生成"""
    data_dir = output_dir / DATA_DIR
    national_roads_dir = data_dir / NATIONAL_ROADS_DIR

    groups = []
    for order, group_name in enumerate(NATIONAL_ROUTE_GROUP_ORDER):
        groups.append({
            "name": group_name,
            "order": order,
        })

    national_roads_dir.mkdir(parents=True, exist_ok=True)
    output_path = national_roads_dir / "group.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"groups": groups}, f, ensure_ascii=False, separators=(",", ":"))

    logger.info("保存: %s", output_path)


def generate_national_roads(
    output_dir: Path,
    national_route_refs: list[str] | None = None,
) -> None:
    """国道データを生成"""
    national_roads_dir = output_dir / DATA_DIR / NATIONAL_ROADS_DIR

    osm_data = _prepare_national_route_data(national_route_refs)
    if osm_data is None:
        return
    targets, way_ids_by_ref, ways_by_id = osm_data

    routes_info = []
    route_geojsons: dict[str, dict] = {}  # グループ計算用にGeoJSONを保持

    for route_info in targets:
        try:
            result = _process_single_national_route(
                route_info, way_ids_by_ref, ways_by_id, national_roads_dir
            )
            if result:
                entry, geojson = result
                routes_info.append(entry)
                route_geojsons[entry["name"]] = geojson
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("国道データ抽出エラー: %s - %s", route_info["name"], e)

    # グループを計算
    logger.info("グループ計算中...")
    assign_national_route_groups(routes_info, route_geojsons)

    # index.json生成
    generate_national_routes_index(output_dir, routes_info)

    # group.json生成
    generate_national_routes_groups(output_dir)


if __name__ == "__main__":
    main()
