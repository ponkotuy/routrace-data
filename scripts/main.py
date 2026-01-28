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

# 都市高速グループのプレフィックス
URBAN_EXPRESSWAY_PREFIXES = [
    "首都高速",
    "名古屋高速",
    "阪神高速",
    "広島高速",
    "北九州高速",
    "福岡高速",
]

# 別名からグループへのマッピング（表記揺れ対応）
URBAN_EXPRESSWAY_ALIASES = {
    "北九州都市高速": "北九州高速",
    "福岡都市高速": "福岡高速",
    "東京高速道路": "首都高速",  # 東京高速道路KK線
}

# 中心高速道路とグループ名のマッピング
CORE_HIGHWAYS = {
    "東名高速道路": "東名",
    "名神高速道路": "名神",
    "中国自動車道": "中国",
    "高松自動車道": "四国",
    "九州自動車道": "九州",
    "京葉道路": "千葉",
    "北陸自動車道": "北陸",
    "関越自動車道": "関越",
    "東北自動車道": "東北",
    "道央自動車道": "北海道",
}

# グループの順序（仕様書に従う）
GROUP_ORDER = [
    "首都高速",
    "東名",
    "名古屋高速",
    "名神",
    "阪神高速",
    "中国",
    "広島高速",
    "四国",
    "九州",
    "北九州高速",
    "福岡高速",
    "千葉",
    "北陸",
    "関越",
    "東北",
    "北海道",
]


# 後方互換性のためのエイリアス（テストで使用）
GROUP_PREFIXES = URBAN_EXPRESSWAY_PREFIXES
GROUP_ALIASES = URBAN_EXPRESSWAY_ALIASES

# 東京駅の座標（中心座標）
TOKYO_STATION = (139.7671, 35.6812)


def detect_group(name: str) -> str | None:
    """
    高速道路名から都市高速グループを推定

    都市高速道路（首都高速、阪神高速など）を同一グループとして判定する。
    一般高速道路の場合はNoneを返す。
    例:
        首都高速1号上野線 → 首都高速
        阪神高速11号池田線 → 阪神高速
        名古屋高速道路小牧-大高線高架路 → 名古屋高速
        福岡高速6号アイランドシティ線 → 福岡高速
        東名高速道路 → None（都市高速ではない）
    """
    for prefix in URBAN_EXPRESSWAY_PREFIXES:
        if name.startswith(prefix):
            return prefix
    # 別名（福岡都市高速→福岡高速など）
    for alias, group in URBAN_EXPRESSWAY_ALIASES.items():
        if name.startswith(alias):
            return group
    # 「名古屋高速道路」のような表記揺れにも対応
    for prefix in URBAN_EXPRESSWAY_PREFIXES:
        alt_prefix = prefix + "道路"
        if name.startswith(alt_prefix):
            return prefix
    # 「名古屋」で始まる高速道路は名古屋高速グループ（名古屋第二環状自動車道など）
    if name.startswith("名古屋"):
        return "名古屋高速"
    return None


def get_all_coordinates(geojson: dict) -> list[tuple[float, float]]:
    """GeoJSONから全座標を取得"""
    coords = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "LineString":
            coords.extend(tuple(c) for c in geometry.get("coordinates", []))
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(tuple(c) for c in line)
    return coords


def distance_squared(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """2点間の距離の2乗を計算"""
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


def get_extent_segment(
    coords: list[tuple[float, float]],
    center: tuple[float, float] = TOKYO_STATION,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """
    座標リストから中心座標に最も近い点と最も遠い点を取得

    Args:
        coords: 座標リスト [(lon, lat), ...]
        center: 中心座標（デフォルト: 東京駅）

    Returns:
        (最近点, 最遠点) のタプル、または座標がない場合はNone
    """
    if not coords:
        return None

    min_dist = float("inf")
    max_dist = 0
    nearest = coords[0]
    farthest = coords[0]

    for coord in coords:
        dist = distance_squared(coord, center)
        if dist < min_dist:
            min_dist = dist
            nearest = coord
        if dist > max_dist:
            max_dist = dist
            farthest = coord

    return (nearest, farthest)


def cross_product(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """外積を計算（符号で左右判定）"""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def segments_intersect(
    seg1: tuple[tuple[float, float], tuple[float, float]],
    seg2: tuple[tuple[float, float], tuple[float, float]],
) -> bool:
    """2つの線分が交差するかどうかを判定"""
    p1, p2 = seg1
    p3, p4 = seg2

    d1 = cross_product(p3, p4, p1)
    d2 = cross_product(p3, p4, p2)
    d3 = cross_product(p1, p2, p3)
    d4 = cross_product(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    return False


def point_to_segment_distance_squared(
    point: tuple[float, float],
    seg: tuple[tuple[float, float], tuple[float, float]],
) -> float:
    """点から線分への最短距離の2乗を計算"""
    p1, p2 = seg
    px, py = point
    x1, y1 = p1
    x2, y2 = p2

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return distance_squared(point, p1)

    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    return distance_squared(point, (proj_x, proj_y))


def segment_to_segment_distance(
    seg1: tuple[tuple[float, float], tuple[float, float]],
    seg2: tuple[tuple[float, float], tuple[float, float]],
) -> float:
    """2つの線分間の最短距離を計算（交差する場合は0）"""
    if segments_intersect(seg1, seg2):
        return 0.0

    # 各端点から他方の線分への距離の最小値
    distances = [
        point_to_segment_distance_squared(seg1[0], seg2),
        point_to_segment_distance_squared(seg1[1], seg2),
        point_to_segment_distance_squared(seg2[0], seg1),
        point_to_segment_distance_squared(seg2[1], seg1),
    ]
    return min(distances) ** 0.5


def determine_general_group(
    highway_segment: tuple[tuple[float, float], tuple[float, float]],
    core_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]],
) -> str:
    """
    一般高速道路のグループを決定

    Args:
        highway_segment: 対象高速道路の線分（最近点、最遠点）
        core_segments: 中心高速道路名 → 線分のマッピング

    Returns:
        最も近い中心高速道路のグループ名
    """
    min_distance = float("inf")
    nearest_group = "東名"  # デフォルト

    # CORE_HIGHWAYSの順序で処理（同距離の場合はリスト上位を優先）
    for highway_name in CORE_HIGHWAYS:
        if highway_name not in core_segments:
            continue
        core_segment = core_segments[highway_name]
        distance = segment_to_segment_distance(highway_segment, core_segment)
        if distance < min_distance:
            min_distance = distance
            nearest_group = CORE_HIGHWAYS[highway_name]

    return nearest_group


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
    highway_geojsons: dict[str, dict] = {}  # グループ計算用にGeoJSONを保持

    for highway_info in targets:
        try:
            name = highway_info["name"]
            way_ids = way_ids_by_name.get(name, set())

            # メモリ内のwayデータから該当するものを取得
            ways = get_ways_for_highway(ways_by_id, way_ids)

            logger.debug(f"{name}: {len(way_ids)} way IDs, {len(ways)} ways抽出")

            geojson = extract_highway(highway_info, ways)

            # 座標がない高速道路はスキップ
            coords = get_all_coordinates(geojson)
            if not coords:
                logger.warning(f"座標がないためスキップ: {name}")
                continue

            file_size = save_highway(name, geojson, highways_dir)

            ref = highway_info.get("ref", "")
            ref_display = ref.split(";")[0] if ref else ""

            entry = {
                "id": name,
                "name": name,
                "nameEn": highway_info.get("name_en", ""),
                "ref": ref,
                "refDisplay": ref_display,
                "fileSize": file_size,
                "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

            highways_info.append(entry)
            highway_geojsons[name] = geojson
        except Exception as e:
            logger.error(f"高速道路データ抽出エラー: {name} - {e}")

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
        highway_geojsons: 高速道路名 → GeoJSONのマッピング
    """
    # 各高速道路の線分（最近点、最遠点）を計算
    highway_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for name, geojson in highway_geojsons.items():
        coords = get_all_coordinates(geojson)
        segment = get_extent_segment(coords)
        if segment:
            highway_segments[name] = segment

    # 中心高速道路の線分を取得
    core_segments: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for core_name in CORE_HIGHWAYS:
        if core_name in highway_segments:
            core_segments[core_name] = highway_segments[core_name]

    # 各高速道路にグループを割り当て
    for entry in highways_info:
        name = entry["name"]

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
        if name in highway_segments and core_segments:
            group = determine_general_group(highway_segments[name], core_segments)
            entry["group"] = group
        else:
            # 座標がない高速道路は事前にフィルタされているはず
            logger.error(f"座標がない高速道路が残っています: {name}")
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

    logger.info(f"保存: {output_path}")


if __name__ == "__main__":
    main()
