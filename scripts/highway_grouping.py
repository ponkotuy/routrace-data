"""高速道路グループ判定と幾何学計算"""

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


def cross_product(
    o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
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

    if (d1 * d2 < 0) and (d3 * d4 < 0):
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
    for highway_name, group_name in CORE_HIGHWAYS.items():
        if highway_name not in core_segments:
            continue
        core_segment = core_segments[highway_name]
        distance = segment_to_segment_distance(highway_segment, core_segment)
        if distance < min_distance:
            min_distance = distance
            nearest_group = group_name

    return nearest_group
