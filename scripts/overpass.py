"""Overpass API クライアント"""

import time
import logging
import requests

from config import OVERPASS_ENDPOINT, OVERPASS_TIMEOUT

logger = logging.getLogger(__name__)


def query_overpass(query: str, timeout: int = OVERPASS_TIMEOUT) -> dict:
    """
    Overpass APIにクエリを送信してJSONレスポンスを取得

    Args:
        query: Overpass QL クエリ文字列
        timeout: タイムアウト秒数

    Returns:
        Overpass APIのJSONレスポンス (dict)

    Raises:
        requests.RequestException: 通信エラー
        ValueError: レスポンスのパースエラー
    """
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            logger.debug(f"Overpass API リクエスト送信 (試行 {attempt + 1}/{max_retries})")
            response = requests.post(
                OVERPASS_ENDPOINT,
                data={"data": query},
                timeout=timeout + 10,
            )
            response.raise_for_status()

            try:
                return response.json()
            except ValueError as e:
                raise ValueError(f"JSONパースエラー: {e}")

        except requests.Timeout:
            if attempt < max_retries - 1:
                logger.warning(f"タイムアウト。タイムアウト値を増やしてリトライ...")
                timeout = int(timeout * 1.5)
                time.sleep(retry_delay)
            else:
                raise

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"通信エラー: {e}。{retry_delay}秒後にリトライ...")
                time.sleep(retry_delay)
            else:
                raise

    raise requests.RequestException("最大リトライ回数に達しました")


def build_highway_query(name: str, timeout: int = OVERPASS_TIMEOUT) -> str:
    """
    高速道路取得用のOverpass QLクエリを生成

    Args:
        name: 高速道路名（例: "東名高速道路"）
        timeout: タイムアウト秒数

    Returns:
        Overpass QLクエリ文字列
    """
    # 高速道路名から短縮形を取得（例: "東名高速道路" -> "東名"）
    short_name = name.replace("高速道路", "").replace("自動車道", "")

    return f"""[out:json][timeout:{timeout}];
area["name"="日本"]["admin_level"="2"]->.japan;
(
  way["highway"="motorway"]["name"~"{name}"](area.japan);
  way["highway"="motorway_link"]["name"~"{short_name}"](area.japan);
);
out geom;"""


def build_coastline_query(bbox: tuple[float, float, float, float], timeout: int = OVERPASS_TIMEOUT) -> str:
    """
    海岸線取得用のOverpass QLクエリを生成

    Args:
        bbox: (南緯, 西経, 北緯, 東経)
        timeout: タイムアウト秒数

    Returns:
        Overpass QLクエリ文字列
    """
    south, west, north, east = bbox

    return f"""[out:json][timeout:{timeout}];
(
  way["natural"="coastline"]({south},{west},{north},{east});
);
out geom;"""
