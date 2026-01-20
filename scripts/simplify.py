"""ジオメトリ簡略化"""

from shapely.geometry import shape, mapping, LineString, MultiLineString
from shapely import get_coordinates

from config import SIMPLIFY_TOLERANCE


def simplify_geojson(geojson: dict, tolerance: float = SIMPLIFY_TOLERANCE) -> dict:
    """
    GeoJSONのジオメトリを簡略化

    Args:
        geojson: GeoJSON FeatureCollection
        tolerance: 簡略化の許容誤差（度単位）

    Returns:
        簡略化されたGeoJSON FeatureCollection

    Note:
        - Shapely の simplify() を使用
        - preserve_topology=True で位相関係を保持
    """
    if geojson.get("type") != "FeatureCollection":
        return geojson

    simplified_features = []

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry")
        if geometry is None:
            continue

        try:
            geom = shape(geometry)
            simplified_geom = geom.simplify(tolerance, preserve_topology=True)

            # 簡略化で点になってしまった場合はスキップ
            if simplified_geom.is_empty:
                continue

            simplified_feature = {
                "type": "Feature",
                "properties": feature.get("properties", {}),
                "geometry": mapping(simplified_geom),
            }
            simplified_features.append(simplified_feature)

        except Exception:
            # 変換に失敗した場合は元のfeatureをそのまま使用
            simplified_features.append(feature)

    result = {
        "type": "FeatureCollection",
        "features": simplified_features,
    }

    # propertiesがあればコピー
    if "properties" in geojson:
        result["properties"] = geojson["properties"].copy()
        result["properties"]["simplified"] = True
        result["properties"]["tolerance"] = tolerance

    return result


def get_coordinate_count(geojson: dict) -> int:
    """
    GeoJSON内の総座標数をカウント

    Args:
        geojson: GeoJSON FeatureCollection

    Returns:
        座標点の総数
    """
    count = 0

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry")
        if geometry is None:
            continue

        try:
            geom = shape(geometry)
            coords = get_coordinates(geom)
            count += len(coords)
        except Exception:
            # カウントできない場合はスキップ
            pass

    return count
