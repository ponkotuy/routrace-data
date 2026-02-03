"""OSMデータパーサー"""

import logging
import re
from pathlib import Path

import osmium

logger = logging.getLogger(__name__)

# 高速道路として認識する名前パターン
HIGHWAY_PATTERNS = ['高速', '自動車道', '京葉道路', 'アクアライン', '仙台東部道', '仙台南部道', '仙台北部道', '第二神明道路', '第二神明北線', '播但連絡道路']

# 除外パターン（高架橋、入口、出口などは除外）
EXCLUDE_PATTERNS = ['高架橋', '入口', '出口', '新設工事', '高架路', '連絡道路']

# 除外パターンより優先するパターン（完全な道路名）
PRIORITY_PATTERNS = ['播但連絡道路']


def _extract_highway_base_name(name: str) -> str | None:
    """名前から基本名を抽出（括弧や方向を除去）"""
    # 優先パターンにマッチする場合は除外パターンをスキップ
    is_priority = any(p in name for p in PRIORITY_PATTERNS)

    # 除外パターンをチェック（優先パターン以外）
    if not is_priority:
        for pattern in EXCLUDE_PATTERNS:
            if pattern in name:
                return None

    # 複合路線名を除外（例: 首都高速川口線-中央環状線）
    if '線-' in name:
        return None

    # 高速道路パターンをチェック
    if not any(p in name for p in HIGHWAY_PATTERNS):
        return None

    # コロン以降を除去（例: 山陰自動車道:浜田バイパス → 山陰自動車道）
    base_name = re.sub(r':.*$', '', name)
    # 括弧以降を除去
    base_name = re.sub(r'[（(].*$', '', base_name)
    # 方向を除去
    base_name = re.sub(r'(上り|下り|内回り|外回り|東行き|西行き|北行き|南行き)$', '', base_name)
    base_name = base_name.strip()

    return base_name if base_name else None


class HighwayDiscoverer(osmium.SimpleHandler):
    """高速道路のrelationを自動検出するハンドラー"""

    def __init__(self):
        super().__init__()
        # 基本名 -> set of way IDs
        self.way_ids_by_name: dict[str, set[int]] = {}
        # 基本名 -> relation情報（name_en, ref等）
        self.highway_info: dict[str, dict] = {}

    def _extract_base_name(self, name: str) -> str | None:
        """名前から基本名を抽出（括弧や方向を除去）"""
        return _extract_highway_base_name(name)

    def relation(self, r):
        """route=roadのrelationから高速道路のway IDを収集"""
        tags = dict(r.tags)

        # route=road のrelationのみ対象
        if tags.get("route") != "road":
            return

        # 名前を取得
        name = tags.get("name", "")
        if not name:
            return

        # 基本名を抽出
        base_name = self._extract_base_name(name)
        if not base_name:
            return

        # way IDを収集
        if base_name not in self.way_ids_by_name:
            self.way_ids_by_name[base_name] = set()
            self.highway_info[base_name] = {
                "name": base_name,
                "name_en": tags.get("name:en", ""),
                "ref": tags.get("ref", ""),
            }

        for member in r.members:
            if member.type == "w":
                self.way_ids_by_name[base_name].add(member.ref)

        # 英語名やrefが空なら更新
        if not self.highway_info[base_name]["name_en"] and tags.get("name:en"):
            self.highway_info[base_name]["name_en"] = tags.get("name:en", "")
        if not self.highway_info[base_name]["ref"] and tags.get("ref"):
            self.highway_info[base_name]["ref"] = tags.get("ref", "")


class HighwayStandaloneWayDiscoverer(osmium.SimpleHandler):
    """relationに含まれないwayから高速道路を検出するハンドラー"""

    def __init__(self, relation_way_ids: set[int]):
        """
        Args:
            relation_way_ids: relationで既に検出されたway IDのセット（除外用）
        """
        super().__init__()
        self.relation_way_ids = relation_way_ids
        # 基本名 -> set of way IDs
        self.way_ids_by_name: dict[str, set[int]] = {}

    def _extract_base_name(self, name: str) -> str | None:
        """名前から基本名を抽出（括弧や方向を除去）"""
        return _extract_highway_base_name(name)

    def way(self, w):
        """highway=motorway かつ高速道路名を持つwayを収集"""
        # relationで既に検出済みのwayはスキップ
        if w.id in self.relation_way_ids:
            return

        tags = dict(w.tags)

        # highway=motorwayのみ対象(motorway_linkを除外)
        highway_type = tags.get("highway", "")
        if highway_type != "motorway":
            return

        # access=no のwayは除外
        if tags.get("access") == "no":
            return

        # 名前タグから基本名を抽出
        name = tags.get("name", "")
        if not name:
            return

        base_name = self._extract_base_name(name)
        if not base_name:
            return

        if base_name not in self.way_ids_by_name:
            self.way_ids_by_name[base_name] = set()
        self.way_ids_by_name[base_name].add(w.id)


class BulkWayCollector(osmium.SimpleHandler):
    """指定された全way IDのwayデータを一括収集するハンドラー"""

    def __init__(self, all_way_ids: set[int]):
        super().__init__()
        self.all_way_ids = all_way_ids
        # way_id -> way data
        self.ways_by_id: dict[int, dict] = {}

    def way(self, w):
        """指定されたway IDに該当するwayのデータを収集"""
        if w.id not in self.all_way_ids:
            return

        tags = dict(w.tags)

        # access=no のwayは除外（実際に通行できない区間）
        if tags.get("access") == "no":
            return

        # ノード座標を取得
        try:
            coordinates = [
                [node.lon, node.lat]
                for node in w.nodes
                if node.location.valid()
            ]
        except osmium.InvalidLocationError:
            return

        if len(coordinates) < 2:
            return

        self.ways_by_id[w.id] = {
            "id": w.id,
            "tags": tags,
            "coordinates": coordinates,
        }


def discover_highways(pbf_path: Path) -> tuple[list[dict], dict[str, set[int]]]:
    """
    PBFから高速道路を自動検出

    Phase 1: relationから検出（route=road, 高速道路名パターン）
    Phase 2: wayから検出（highway=motorway, 高速道路名パターン、relation未検出のみ）
    Phase 3: 結果をマージ

    Args:
        pbf_path: フィルタリング済みPBFファイルパス

    Returns:
        (高速道路情報のリスト, 名前 -> way IDセットのマッピング)
    """
    logger.info("高速道路を自動検出中...")

    # Phase 1: relationから検出
    logger.info("Phase 1: relationから高速道路を検出中...")
    relation_handler = HighwayDiscoverer()
    relation_handler.apply_file(str(pbf_path))

    relation_routes = len(relation_handler.highway_info)
    relation_ways = sum(len(ids) for ids in relation_handler.way_ids_by_name.values())
    logger.info("  relationから検出: %d路線, %d ways", relation_routes, relation_ways)

    # Phase 2: wayから検出（relation検出済みのway IDを除外）
    logger.info("Phase 2: wayから高速道路を検出中（relation未検出のみ）...")
    all_relation_way_ids = set()
    for way_ids in relation_handler.way_ids_by_name.values():
        all_relation_way_ids.update(way_ids)

    way_handler = HighwayStandaloneWayDiscoverer(all_relation_way_ids)
    way_handler.apply_file(str(pbf_path))

    standalone_ways = sum(len(ids) for ids in way_handler.way_ids_by_name.values())
    logger.info("  wayから追加検出: %d ways", standalone_ways)

    # Phase 3: 結果をマージ
    way_ids_by_name: dict[str, set[int]] = {}
    highway_info: dict[str, dict] = {}

    # relationからの結果をコピー
    for name, way_ids in relation_handler.way_ids_by_name.items():
        way_ids_by_name[name] = set(way_ids)
        highway_info[name] = relation_handler.highway_info[name]

    # wayからの結果をマージ
    for name, way_ids in way_handler.way_ids_by_name.items():
        if name in way_ids_by_name:
            # 既存の名前にway IDを追加
            way_ids_by_name[name].update(way_ids)
        else:
            # 新しい名前（relationには存在しないがwayで見つかった高速道路）
            way_ids_by_name[name] = set(way_ids)
            highway_info[name] = {
                "name": name,
                "name_en": "",
                "ref": "",
            }

    # 高速道路情報をリストに変換
    highways = []
    for name, info in sorted(highway_info.items()):
        way_count = len(way_ids_by_name[name])
        highways.append({
            "name": info["name"],
            "name_en": info["name_en"],
            "ref": info["ref"],
            "way_count": way_count,
        })

    total_ways = sum(len(ids) for ids in way_ids_by_name.values())
    logger.info("検出完了: %d路線, 合計 %d ways", len(highways), total_ways)

    return highways, way_ids_by_name


def extract_all_ways(
    pbf_path: Path,
    all_way_ids: set[int],
) -> dict[int, dict]:
    """
    指定された全way IDのwayを一括抽出

    Args:
        pbf_path: PBFファイルパス
        all_way_ids: 抽出するway IDのセット

    Returns:
        way_id -> way data のマッピング
    """
    logger.info("wayデータを一括抽出中... (%d ways)", len(all_way_ids))

    handler = BulkWayCollector(all_way_ids)
    handler.apply_file(
        str(pbf_path),
        locations=True,
        idx="flex_mem",
    )

    logger.info("way抽出完了: %d ways", len(handler.ways_by_id))

    return handler.ways_by_id


def get_ways_for_highway(
    ways_by_id: dict[int, dict],
    way_ids: set[int],
) -> list[dict]:
    """
    メモリ内のwayデータから指定されたway IDのwayを取得

    Args:
        ways_by_id: way_id -> way data のマッピング
        way_ids: 取得するway IDのセット

    Returns:
        wayのリスト
    """
    return [ways_by_id[wid] for wid in way_ids if wid in ways_by_id]


def ways_to_geojson(ways: list[dict]) -> dict:
    """
    wayリストをGeoJSON FeatureCollectionに変換

    Args:
        ways: 高速道路wayのリスト

    Returns:
        GeoJSON FeatureCollection
    """
    features = []

    for way in ways:
        tags = way["tags"]

        feature = {
            "type": "Feature",
            "properties": {
                "name": tags.get("name", ""),
                "ref": tags.get("ref", ""),
                "highway": tags.get("highway", ""),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": way["coordinates"],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _is_valid_national_route_ref(ref: str) -> bool:
    """
    有効な日本の国道番号かチェック

    Args:
        ref: ref番号文字列

    Returns:
        1〜507の範囲の数字ならTrue
    """
    if not ref or not ref.isdigit():
        return False
    num = int(ref)
    return 1 <= num <= 507


class NationalRouteDiscoverer(osmium.SimpleHandler):
    """国道のrelationを自動検出するハンドラー"""

    def __init__(self):
        super().__init__()
        # ref番号 -> set of way IDs
        self.way_ids_by_ref: dict[str, set[int]] = {}
        # ref番号 -> relation情報
        self.route_info: dict[str, dict] = {}

    def _normalize_name(self, ref: str) -> str:
        """ref番号から正規化した名前を生成"""
        return f"国道{ref}号"

    def relation(self, r):
        """route=road かつ network=JP:national のrelationからway IDを収集"""
        tags = dict(r.tags)

        # route=road かつ network=JP:national のrelationのみ対象
        if tags.get("route") != "road":
            return
        if tags.get("network") != "JP:national":
            return

        # ref番号を取得（有効な国道番号のみ対象）
        ref = tags.get("ref", "")
        if not _is_valid_national_route_ref(ref):
            return

        # way IDを収集
        if ref not in self.way_ids_by_ref:
            self.way_ids_by_ref[ref] = set()
            self.route_info[ref] = {
                "ref": ref,
                "name": self._normalize_name(ref),
                "name_en": f"National Route {ref}",
            }

        for member in r.members:
            if member.type == "w":
                self.way_ids_by_ref[ref].add(member.ref)


class NationalRouteStandaloneWayDiscoverer(osmium.SimpleHandler):
    """relationに含まれないwayから国道を検出するハンドラー"""

    # nameタグから国道番号を抽出するパターン
    _NATIONAL_ROUTE_NAME_PATTERN = re.compile(r'国道(\d+)号')

    def __init__(self, relation_way_ids: set[int]):
        """
        Args:
            relation_way_ids: relationで既に検出されたway IDのセット（除外用）
        """
        super().__init__()
        self.relation_way_ids = relation_way_ids
        # ref番号 -> set of way IDs
        self.way_ids_by_ref: dict[str, set[int]] = {}

    def _is_ref_consistent_with_name(self, ref: str, name: str) -> bool:
        """
        refがnameと矛盾しないかチェック

        Args:
            ref: 国道番号（例: "56"）
            name: wayのnameタグ

        Returns:
            矛盾しない場合True、矛盾する場合False
        """
        if not name:
            # nameがない場合は矛盾なしとする
            return True

        # nameから国道番号を抽出
        match = self._NATIONAL_ROUTE_NAME_PATTERN.search(name)
        if not match:
            # nameに国道番号がない場合は矛盾なしとする
            return True

        # nameに含まれる国道番号とrefが一致するかチェック
        name_ref = match.group(1)
        return ref == name_ref

    def way(self, w):
        """highway=trunk/trunk_link かつ有効なref番号を持つwayを収集"""
        # relationで既に検出済みのwayはスキップ
        if w.id in self.relation_way_ids:
            return

        tags = dict(w.tags)

        # highway=trunkのみ対象(trunk_linkを除外)
        highway_type = tags.get("highway", "")
        if highway_type != "trunk":
            return

        # ref タグから国道番号を取得
        ref = tags.get("ref", "")
        if not ref:
            return

        name = tags.get("name", "")

        # 複数refの場合（"56;197"等）は分割して処理
        refs = [r.strip() for r in ref.split(";")]
        for single_ref in refs:
            if _is_valid_national_route_ref(single_ref):
                # nameとrefが矛盾する場合はスキップ
                if not self._is_ref_consistent_with_name(single_ref, name):
                    continue
                if single_ref not in self.way_ids_by_ref:
                    self.way_ids_by_ref[single_ref] = set()
                self.way_ids_by_ref[single_ref].add(w.id)


def discover_national_routes(pbf_path: Path) -> tuple[list[dict], dict[str, set[int]]]:
    """
    PBFから国道を自動検出

    Phase 1: relationから検出（route=road, network=JP:national）
    Phase 2: wayから検出（highway=trunk/trunk_link, ref=国道番号、relation未検出のみ）
    Phase 3: 結果をマージ

    Args:
        pbf_path: フィルタリング済みPBFファイルパス

    Returns:
        (国道情報のリスト, ref番号 -> way IDセットのマッピング)
    """
    logger.info("国道を自動検出中...")

    # Phase 1: relationから検出
    logger.info("Phase 1: relationから国道を検出中...")
    relation_handler = NationalRouteDiscoverer()
    relation_handler.apply_file(str(pbf_path))

    relation_routes = len(relation_handler.route_info)
    relation_ways = sum(len(ids) for ids in relation_handler.way_ids_by_ref.values())
    logger.info("  relationから検出: %d路線, %d ways", relation_routes, relation_ways)

    # Phase 2: wayから検出（relation検出済みのway IDを除外）
    logger.info("Phase 2: wayから国道を検出中（relation未検出のみ）...")
    all_relation_way_ids = set()
    for way_ids in relation_handler.way_ids_by_ref.values():
        all_relation_way_ids.update(way_ids)

    way_handler = NationalRouteStandaloneWayDiscoverer(all_relation_way_ids)
    way_handler.apply_file(str(pbf_path))

    standalone_ways = sum(len(ids) for ids in way_handler.way_ids_by_ref.values())
    logger.info("  wayから追加検出: %d ways", standalone_ways)

    # Phase 3: 結果をマージ
    way_ids_by_ref: dict[str, set[int]] = {}
    route_info: dict[str, dict] = {}

    # relationからの結果をコピー
    for ref, way_ids in relation_handler.way_ids_by_ref.items():
        way_ids_by_ref[ref] = set(way_ids)
        route_info[ref] = relation_handler.route_info[ref]

    # wayからの結果をマージ
    for ref, way_ids in way_handler.way_ids_by_ref.items():
        if ref in way_ids_by_ref:
            # 既存のrefにway IDを追加
            way_ids_by_ref[ref].update(way_ids)
        else:
            # 新しいref（relationには存在しないがwayで見つかった国道）
            way_ids_by_ref[ref] = set(way_ids)
            route_info[ref] = {
                "ref": ref,
                "name": f"国道{ref}号",
                "name_en": f"National Route {ref}",
            }

    # 国道情報をリストに変換（ref番号でソート）
    routes = []
    for ref in sorted(route_info.keys(), key=int):
        info = route_info[ref]
        way_count = len(way_ids_by_ref[ref])
        routes.append({
            "ref": info["ref"],
            "name": info["name"],
            "name_en": info["name_en"],
            "way_count": way_count,
        })

    total_ways = sum(len(ids) for ids in way_ids_by_ref.values())
    logger.info("検出完了: %d路線, 合計 %d ways", len(routes), total_ways)

    return routes, way_ids_by_ref
