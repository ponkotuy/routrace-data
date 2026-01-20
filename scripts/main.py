"""エントリーポイント"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR
from coastline import fetch_coastline, save_coastline

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """
    コマンドライン引数:
        --output-dir: 出力ベースディレクトリ（デフォルト: リポジトリルート）
        --highways-only: 高速道路のみ生成
        --coastline-only: 海岸線のみ生成
        --highway-id: 特定の高速道路のみ生成（複数指定可）
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
        "--highway-id",
        action="append",
        dest="highway_ids",
        help="特定の高速道路のみ生成（複数指定可）",
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
            generate_highways(output_dir, args.highway_ids)
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
    # TODO: generate_highways実装後に追加
    # generate_highways(output_dir)


def generate_highways(
    output_dir: Path,
    highway_ids: list[str] | None = None,
) -> None:
    """高速道路データを生成"""
    # TODO: 実装
    logger.warning("高速道路データ生成は未実装です")


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
    # TODO: 実装
    pass


if __name__ == "__main__":
    main()
